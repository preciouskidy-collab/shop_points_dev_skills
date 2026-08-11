#!/usr/bin/env python3
"""技术方案修订轮 prepare：拉群消息 + 新 design-patch。"""

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
    save_state,
)
from design_plan_builder import (  # noqa: E402
    DESIGN_TARGETS,
    build_agent_pending_design_plan,
    design_patch_dir,
    finalize_design_round,
    new_approval_nonce,
    next_design_patch_id,
)
from collab_inbox import load_inbox  # noqa: E402
from collab_intent_consume import consume_collab_intent  # noqa: E402
from sender_roles import format_collab_messages_md, format_sender_roles_legend  # noqa: E402


def _resolve_pull_intent_id(change_dir: Path, explicit: int | None) -> int | None:
    if explicit is not None:
        return explicit
    inbox = load_inbox(change_dir)
    if inbox and inbox.get("action") == "tech_revise" and inbox.get("id") is not None:
        return int(inbox["id"])
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="技术方案修订轮（企微 /整理方案 后）")
    parser.add_argument("--req-id", required=True)
    parser.add_argument(
        "--pull-intent-id",
        type=int,
        default=None,
        help="wait 返回的 tech_revise intent；prepare 成功后自动 consume",
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

    collab = state.setdefault("collaboration", {})
    tdr = collab.setdefault("tech_design_review", {})
    since = tdr.get("revision_cursor") or tdr.get("started_at")
    client = AgentClient.from_config()
    msg_resp = client.list_messages(req_id, since=since, limit=500)
    messages = msg_resp.get("messages", [])

    patch_id, seq = next_design_patch_id(change_dir, state)
    pdir = design_patch_dir(change_dir, patch_id)
    revision_round = int(tdr.get("revision_round", 0)) + 1

    messages_md = format_collab_messages_md(messages)
    (pdir / "messages_raw.md").write_text(messages_md or "（无有效消息）\n", encoding="utf-8")

    plan = build_agent_pending_design_plan(
        patch_id=patch_id,
        extra={"revision_round": revision_round},
    )
    nonce = new_approval_nonce()

    revise_prompt = "\n".join(
        [
            "# Revise Prompt · 技术方案修订轮",
            "",
            f"req_id: {req_id}",
            f"patch: {patch_id}",
            f"revision_round: {revision_round}",
            f"since: {since}",
            "",
            "## 发言角色映射",
            format_sender_roles_legend(),
            "",
            "## 修订轮群消息",
            messages_md or "（无消息）",
            "",
            "## 当前方案文件（请 refetch 工作区最新版）",
            "",
            *[
                f"### {rel}"
                for rel in DESIGN_TARGETS
            ],
            "",
            "## Agent 任务",
            "1. 综合群讨论修订 design_plan.json",
            "2. finalize-design → push-preview（新 nonce）→ 再 wait",
        ]
    )

    finalize_design_round(
        change_dir,
        state,
        pdir,
        patch_id=patch_id,
        seq=seq,
        req_id=req_id,
        plan=plan,
        design_prompt=revise_prompt,
        meta_extra={
            "preview_type": "tech_design",
            "revision_round": revision_round,
            "approval_nonce": nonce,
            "plan_source": "agent_pending",
            "message_count": len(messages),
            "since": since,
        },
        log_message=f"TECH-REVISE prepare {patch_id} round={revision_round}",
    )

    tdr["active_patch"] = patch_id
    tdr["revision_round"] = revision_round
    save_state(change_dir, state)
    append_log(change_dir, f"TECH-REVISE prepare {patch_id} messages={len(messages)}")

    pull_intent_id = _resolve_pull_intent_id(change_dir, args.pull_intent_id)
    if pull_intent_id is not None:
        consumed = consume_collab_intent(
            pull_intent_id,
            req_id=req_id,
            expected_actions=("tech_revise",),
        )
        consumed_ids = tdr.setdefault("consumed_intent_ids", [])
        if pull_intent_id not in consumed_ids:
            consumed_ids.append(pull_intent_id)
        tdr["last_consumed_intent_id"] = pull_intent_id
        save_state(change_dir, state)
        append_log(
            change_dir,
            f"TECH-REVISE consumed intent_id={pull_intent_id} action={consumed.get('action')}",
        )
    else:
        print(
            "WARN: 未提供 --pull-intent-id 且 inbox 无 tech_revise；"
            "wait 可能重复返回同一 intent（流程事故）",
            file=sys.stderr,
        )

    print(f"✓ patch: {patch_id}")
    print(f"✓ design_prompt: {pdir / 'design_prompt.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
