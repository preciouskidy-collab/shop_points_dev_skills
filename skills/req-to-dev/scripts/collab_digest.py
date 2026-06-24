#!/usr/bin/env python3
"""联调消息整理：拉 Agent 消息 → AI 摘要 + 对照 PRD → lark-cli dry-run。"""

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
from patch_builder import (  # noqa: E402
    _format_collab_messages_md,
    build_collab_plan,
    build_human_summary_pipeline,
    chat_confirm_phrase,
    new_approval_nonce,
)
from llm_client import is_llm_available  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="联调 digest：AI 摘要群消息 + 对照 PRD 生成 patch + dry-run",
    )
    parser.add_argument("--req-id", required=True)
    parser.add_argument("--window", default="48h")
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="禁用 LLM，仅用启发式（颜色/删除类规则）",
    )
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
        print("WARN: 时间窗内无消息，仍将基于 PRD 生成 patch")

    patch_id, seq = next_patch_id(change_dir, state)
    pdir = patch_dir(change_dir, patch_id)

    prd_snapshot = change_dir / "request" / "prd.md"
    fetch(prd_url, prd_snapshot)
    prd_md = prd_snapshot.read_text(encoding="utf-8")
    (pdir / "prd_snapshot.md").write_text(prd_md, encoding="utf-8")

    messages_md = _format_collab_messages_md(messages)
    (pdir / "messages_raw.md").write_text(
        messages_md or "（无有效消息）\n", encoding="utf-8"
    )

    use_llm = not args.no_llm
    if use_llm and not is_llm_available():
        print("WARN: 未配置 LLM（secrets.local.json → llm.api_key），使用启发式摘要")

    plan, plan_source = build_collab_plan(
        messages,
        prd_md,
        prd_url=prd_url,
        patch_id=patch_id,
        use_llm=use_llm,
    )
    (pdir / "collab_summary.md").write_text(
        (plan.get("consensus_summary") or "") + "\n", encoding="utf-8"
    )

    update_cmd = plan.get("update", {}).get("command", "?")
    print(f"✓ 规划完成 plan_source={plan_source} update.command={update_cmd}")

    (pdir / "digest_prompt.md").write_text(
        "\n".join(
            [
                "# Digest Prompt · 联调群 → PRD",
                "",
                f"plan_source: {plan_source}",
                "",
                "## PRD URL",
                prd_url,
                "",
                "## 原始联调消息",
                messages_md,
                "",
                "## AI 联调共识摘要",
                plan.get("consensus_summary") or "",
                "",
                "## PRD 差异说明",
                plan.get("prd_diff_summary") or "",
                "",
                "## 当前 PRD 快照（节选）",
                prd_md[:8000],
            ]
        ),
        encoding="utf-8",
    )

    plan_path = pdir / "plan.json"
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
        print("✓ lark-cli dry-run 通过")
    except RuntimeError as e:
        print(f"WARN: dry-run 失败（可修订 plan.json 后重试）: {e}")

    meta = {
        "patch_id": patch_id,
        "seq": seq,
        "req_id": req_id,
        "window": args.window,
        "message_count": len(messages),
        "plan_source": plan_source,
        "update_command": update_cmd,
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
    append_log(change_dir, f"COLLAB digest {patch_id} messages={len(messages)} source={plan_source}")

    print(f"✓ patch 已生成: {pdir}")
    print(f"✓ 请在 Agent 对话中回复：`{chat_confirm_phrase(patch_id, approval_nonce)}`")
    print("\n--- human_summary 预览 ---")
    print(summary_path.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
