#!/usr/bin/env python3
"""联调消息整理：拉 Agent 消息 + lark-cli fetch/dry-run + 本地 patch。"""

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
    find_change_dir,
    iso_now,
    load_state,
    next_patch_id,
    parse_window,
    patch_dir,
    save_state,
)
from lark_cli import fetch, update_dry_run  # noqa: E402
from patch_builder import build_human_summary_pipeline, chat_confirm_phrase, new_approval_nonce  # noqa: E402


def _format_messages(messages: list[dict]) -> str:
    lines = []
    for m in messages:
        sender = m.get("senderId") or m.get("sender_id") or "unknown"
        content = (m.get("content") or "").strip()
        if not content or content.startswith("/"):
            continue
        lines.append(f"- [{sender}] {content}")
    return "\n".join(lines) if lines else "- （无有效聊天消息）"


def _build_plan_json(messages_md: str, prd_url: str, patch_id: str) -> dict:
    items = []
    bullet_lines = []
    for line in messages_md.splitlines():
        text = line.strip()
        if text.startswith("- ["):
            items.append({"type": "collab_item", "summary": text})
            bullet_lines.append(text[2:].strip() if text.startswith("- ") else text)

    content_lines = [f"## 联调变更 · {patch_id}", ""]
    if bullet_lines:
        content_lines.extend(f"- {b}" for b in bullet_lines)
    else:
        content_lines.append("- （待补充联调共识）")
    content_lines.append("")

    return {
        "version": 1,
        "source": "collab_digest",
        "prd_url": prd_url,
        "changes": items,
        "update": {
            "command": "append",
            "doc_format": "markdown",
            "content": "\n".join(content_lines),
        },
    }


def _build_human_summary(patch_id: str, req_id: str, plan: dict) -> str:
    lines = [f"# {patch_id} 预览 · `{req_id}`", ""]
    for i, item in enumerate(plan.get("changes", []), 1):
        lines.append(f"{i}. {item.get('summary', item)}")
    lines.extend(
        [
            "",
            "请 @产品 确认后，由 RD 在本机执行：",
            f"  python collab_approve.py --req-id {req_id} --patch {patch_id} --approver <pm_id>",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="联调 digest：拉消息 + lark-cli + 本地 patch")
    parser.add_argument("--req-id", required=True)
    parser.add_argument("--window", default="48h")
    parser.add_argument("--agent-config", type=Path, default=None)
    args = parser.parse_args()

    change_dir = find_change_dir(args.req_id)
    state = load_state(change_dir)
    req_id = state.get("req_id", args.req_id)
    prd_url = state.get("trigger", {}).get("url")
    if not prd_url:
        print("ERROR: pipeline_state.trigger.url 缺失", file=sys.stderr)
        return 1

    client = AgentClient.from_config()
    binding = client.get_binding(req_id)
    if binding.get("status") != "active":
        print(f"ERROR: 联调群未绑定或已关闭: {binding}", file=sys.stderr)
        return 1

    since_dt = parse_window(args.window)
    since = since_dt.isoformat().replace("+00:00", "Z")
    msg_resp = client.list_messages(req_id, since=since, limit=500)
    messages = msg_resp.get("messages", [])
    if not messages:
        print("WARN: 时间窗内无消息，仍将基于 PRD 生成空 patch")

    patch_id, seq = next_patch_id(change_dir, state)
    pdir = patch_dir(change_dir, patch_id)

    prd_snapshot = change_dir / "request" / "prd.md"
    fetch(prd_url, prd_snapshot)

    messages_md = _format_messages(messages)
    (pdir / "digest_prompt.md").write_text(
        "\n".join(
            [
                "# Digest Prompt",
                "",
                "## PRD URL",
                prd_url,
                "",
                "## 联调消息",
                messages_md,
                "",
                "## 任务",
                "请根据联调消息与 PRD，输出 PRD patch 计划到 plan.json（changes 数组）。",
            ]
        ),
        encoding="utf-8",
    )

    plan_path = pdir / "plan.json"
    plan = _build_plan_json(messages_md, prd_url, patch_id)
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    approval_nonce = new_approval_nonce()
    summary_path = pdir / "human_summary.md"
    summary_path.write_text(
        build_human_summary_pipeline(
            patch_id, req_id, plan, source_label="企微联调群", approval_nonce=approval_nonce
        ),
        encoding="utf-8",
    )

    dry_log = pdir / "dry_run.log"
    try:
        update_dry_run(prd_url, plan_path, log_path=dry_log)
    except RuntimeError as e:
        print(f"WARN: dry-run 失败（可完善 plan.json 后重试 approve 前再跑）: {e}")

    meta = {
        "patch_id": patch_id,
        "seq": seq,
        "req_id": req_id,
        "window": args.window,
        "message_count": len(messages),
        "digest_at": iso_now(),
        "status": "draft",
        "approver": None,
        "approved_at": None,
        "approval_note": None,
        "ready_for_resync": False,
        "approval_nonce": approval_nonce,
    }
    (pdir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    collab = state.setdefault("collaboration", {})
    collab["binding_status"] = binding.get("status")
    collab["group_id"] = binding.get("groupId") or binding.get("group_id")
    collab["last_patch_seq"] = seq
    collab.setdefault("patches", {})[patch_id] = {"status": "draft", "digest_at": meta["digest_at"]}
    save_state(change_dir, state)
    append_log(change_dir, f"COLLAB digest {patch_id} messages={len(messages)}")

    print(f"✓ patch 已生成: {pdir}")
    print(f"✓ 请在 Agent 对话中回复：`{chat_confirm_phrase(patch_id, approval_nonce)}`")
    print("\n--- human_summary 预览 ---")
    print(summary_path.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
