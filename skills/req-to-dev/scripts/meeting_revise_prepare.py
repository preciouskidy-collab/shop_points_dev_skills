#!/usr/bin/env python3
"""链路1 修订轮 prepare：拉 revision_cursor 后群消息 + refetch 纪要/PRD。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parent / "lib"
sys.path.insert(0, str(_LIB))

from agent_client import AgentClient  # noqa: E402
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
from collab_inbox import load_inbox  # noqa: E402
from collab_intent_consume import consume_collab_intent  # noqa: E402
from patch_builder import build_agent_pending_plan, finalize_patch, new_approval_nonce  # noqa: E402
from sender_roles import format_collab_messages_md, format_sender_roles_legend  # noqa: E402


def _resolve_pull_intent_id(change_dir: Path, explicit: int | None) -> int | None:
    if explicit is not None:
        return explicit
    inbox = load_inbox(change_dir)
    if inbox and inbox.get("action") == "meeting_revise" and inbox.get("id") is not None:
        return int(inbox["id"])
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="评审修订轮 prepare（企微 /整理评审 后）")
    parser.add_argument("--req-id", required=True)
    parser.add_argument(
        "--pull-intent-id",
        type=int,
        default=None,
        help="wait 返回的 meeting_revise intent；prepare 成功后自动 consume（未传则从 inbox 解析）",
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
        print(f"ERROR: 当前 phase={collab.get('phase')}", file=sys.stderr)
        return 1
    pr_review = collab.setdefault("prd_review", {})
    if pr_review.get("ended_at"):
        print("ERROR: PRD 评审已结束，无法修订", file=sys.stderr)
        return 1

    since = pr_review.get("revision_cursor") or pr_review.get("started_at")
    client = AgentClient.from_config()
    msg_resp = client.list_messages(req_id, since=since, limit=500)
    messages = msg_resp.get("messages", [])

    patch_id, seq = next_patch_id(change_dir, state)
    pdir = patch_dir(change_dir, patch_id)
    revision_round = int(pr_review.get("revision_round", 0)) + 1

    meeting_path = pdir / "meeting.md"
    fetch(meeting_url, meeting_path)
    prd_snapshot = change_dir / "request" / "prd.md"
    fetch(prd_url, prd_snapshot)
    prd_md = prd_snapshot.read_text(encoding="utf-8")
    (pdir / "prd_snapshot.md").write_text(prd_md, encoding="utf-8")

    messages_md = format_collab_messages_md(messages)
    roles_legend = format_sender_roles_legend()
    (pdir / "messages_raw.md").write_text(messages_md or "（无有效消息）\n", encoding="utf-8")

    plan = build_agent_pending_plan(
        prd_url=prd_url,
        patch_id=patch_id,
        source="feishu_meeting",
        consensus_summary="",
        prd_diff_summary="待 Agent 对照 revise_prompt.md 修订 plan.json",
        extra={"meeting_url": meeting_url, "revision_round": revision_round},
    )
    approval_nonce = new_approval_nonce()
    meeting_md = meeting_path.read_text(encoding="utf-8")

    revise_prompt = "\n".join(
        [
            "# Revise Prompt · 评审修订轮",
            "",
            f"req_id: {req_id}",
            f"patch: {patch_id}",
            f"revision_round: {revision_round}",
            f"since: {since}",
            "",
            "## PRD URL",
            prd_url,
            "",
            "## 会议纪要 URL",
            meeting_url,
            "",
            "## 发言角色映射",
            roles_legend,
            "",
            "## 修订轮群消息",
            messages_md or "（无消息）",
            "",
            "## 会议纪要（refetch）",
            meeting_md[:6000],
            "",
            "## 当前 PRD 快照（节选）",
            prd_md[:8000],
            "",
            "## Agent 任务",
            "1. 综合群讨论 + 纪要，修订 plan.json",
            "2. finalize-plan → push-preview（新 nonce）",
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
        source_label="评审修订",
        meta_extra={
            "source": "feishu_meeting",
            "meeting_url": meeting_url,
            "plan_source": "agent_pending",
            "revision_round": revision_round,
            "message_count": len(messages),
            "since": since,
            "approval_nonce": approval_nonce,
        },
        log_message=f"MEETING-REVISE prepare {patch_id} round={revision_round}",
        digest_prompt=revise_prompt,
        notify="待 Cursor 写 plan → finalize-plan → push-preview",
        prompt_filename="revise_prompt.md",
    )

    pr_review["active_patch"] = patch_id
    pr_review["revision_round"] = revision_round
    save_state(change_dir, state)
    append_log(change_dir, f"MEETING-REVISE prepare {patch_id} messages={len(messages)}")

    pull_intent_id = _resolve_pull_intent_id(change_dir, args.pull_intent_id)
    if pull_intent_id is not None:
        consumed = consume_collab_intent(
            pull_intent_id,
            req_id=req_id,
            expected_actions=("meeting_revise",),
        )
        consumed_ids = pr_review.setdefault("consumed_intent_ids", [])
        if pull_intent_id not in consumed_ids:
            consumed_ids.append(pull_intent_id)
        pr_review["last_consumed_intent_id"] = pull_intent_id
        save_state(change_dir, state)
        append_log(
            change_dir,
            f"MEETING-REVISE consumed intent_id={pull_intent_id} action={consumed.get('action')}",
        )
    else:
        print(
            "WARN: 未提供 --pull-intent-id 且 inbox 无 meeting_revise；"
            "wait 可能重复返回同一 intent（流程事故）",
            file=sys.stderr,
        )

    print(f"✓ patch: {patch_id}")
    print(f"✓ revise_prompt: {pdir / 'revise_prompt.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
