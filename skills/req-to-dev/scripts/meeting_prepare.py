#!/usr/bin/env python3
"""链路1 meeting prepare：只 fetch 材料 + agent_pending 骨架（智能在 Cursor）。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parent / "lib"
sys.path.insert(0, str(_LIB))

from collab_check_config import _print_report, run_check  # noqa: E402
from collab_common import (  # noqa: E402
    append_log,
    effective_req_id,
    ensure_active_binding,
    find_change_dir,
    iso_now,
    load_state,
    next_patch_id,
    patch_dir,
    save_state,
)
from lark_cli import fetch  # noqa: E402
from patch_builder import (  # noqa: E402
    build_agent_pending_plan,
    finalize_patch,
    new_approval_nonce,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="会议纪要 → PRD prepare（pipeline，有 req_id）")
    parser.add_argument("--req-id", required=True)
    parser.add_argument(
        "--skip-preflight", action="store_true",
        help="跳过凭证 / 权限预检（调试用）",
    )
    args = parser.parse_args()

    change_dir = find_change_dir(args.req_id)
    state = load_state(change_dir)
    req_id = effective_req_id(state, change_dir)

    try:
        ensure_active_binding(change_dir, state, req_id)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    trigger = state.get("trigger", {})
    prd_url = trigger.get("url")
    meeting_url = trigger.get("meeting_url")
    if not prd_url or not meeting_url:
        print("ERROR: pipeline_state.trigger 缺少 url / meeting_url", file=sys.stderr)
        return 1

    collab = state.setdefault("collaboration", {})
    if collab.get("phase") != "prd_review":
        print(f"ERROR: 当前 phase={collab.get('phase')}，仅 prd_review 可 meeting prepare", file=sys.stderr)
        return 1
    pr_review = collab.get("prd_review") or {}
    if pr_review.get("ended_at"):
        print("ERROR: PRD 评审已结束", file=sys.stderr)
        return 1

    if not args.skip_preflight:
        preflight = run_check(test_url=prd_url)
        if not preflight.ok:
            _print_report(preflight)
            return 1

    patch_id, seq = next_patch_id(change_dir, state)
    pdir = patch_dir(change_dir, patch_id)
    revision_round = int(pr_review.get("revision_round", 0)) + 1

    meeting_path = pdir / "meeting.md"
    print(f"📄 拉取会议纪要: {meeting_url}")
    fetch(meeting_url, meeting_path)

    prd_snapshot = change_dir / "request" / "prd.md"
    print(f"📄 拉取 PRD: {prd_url}")
    fetch(prd_url, prd_snapshot)
    prd_md = prd_snapshot.read_text(encoding="utf-8")
    (pdir / "prd_snapshot.md").write_text(prd_md, encoding="utf-8")

    meeting_md = meeting_path.read_text(encoding="utf-8")
    plan = build_agent_pending_plan(
        prd_url=prd_url,
        patch_id=patch_id,
        source="feishu_meeting",
        consensus_summary="",
        prd_diff_summary="待 Agent 对照 meeting_prompt.md 撰写 plan.json（str_replace）",
        extra={"meeting_url": meeting_url},
    )

    approval_nonce = new_approval_nonce()
    meeting_prompt = "\n".join(
        [
            "# Meeting Prompt · 评审纪要 → PRD",
            "",
            f"req_id: {req_id}",
            f"patch: {patch_id}",
            f"revision_round: {revision_round}",
            "",
            "## PRD URL",
            prd_url,
            "",
            "## 会议纪要 URL",
            meeting_url,
            "",
            "## 会议纪要正文",
            meeting_md,
            "",
            "## 当前 PRD 快照（节选）",
            prd_md[:8000],
            "",
            "## Agent 任务",
            "1. 对照纪要凝练共识，找出与 PRD 的冲突/差异",
            "2. 修订 plan.json（str_replace），执行 finalize-plan 重算预览",
            "3. 执行 push-preview 发群 @PM",
            "",
            "## 说明",
            "plan_source 固定 agent_pending；禁止脚本侧启发式写 plan。",
        ]
    )

    finalize_patch(
        change_dir,
        state,
        pdir,
        patch_id=patch_id,
        seq=seq,
        req_id=req_id,
        prd_url=prd_url,
        plan=plan,
        source_label="飞书会议纪要",
        meta_extra={
            "source": "feishu_meeting",
            "meeting_url": meeting_url,
            "plan_source": "agent_pending",
            "update_command": "agent_pending",
            "approval_nonce": approval_nonce,
            "revision_round": revision_round,
        },
        log_message=f"MEETING prepare {patch_id} round={revision_round}",
        digest_prompt=meeting_prompt,
        notify="待 Cursor 写 plan → finalize-plan → push-preview",
        prompt_filename="meeting_prompt.md",
    )

    collab = state.setdefault("collaboration", {})
    pr = collab.setdefault("prd_review", {})
    pr["active_patch"] = patch_id
    pr["revision_round"] = revision_round
    if not pr.get("started_at"):
        pr["started_at"] = iso_now()
    save_state(change_dir, state)
    append_log(change_dir, f"MEETING prepare done {patch_id}")

    print(f"✓ patch: {patch_id}")
    print(f"✓ meeting_prompt: {pdir / 'meeting_prompt.md'}")
    print("ℹ 下一步: Cursor 写 plan.json → finalize-plan → push-preview")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
