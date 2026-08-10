#!/usr/bin/env python3
"""注册 preview 会话并向企微群发送 Markdown 预览（须先绑群）。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parent / "lib"
_SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_LIB))
sys.path.insert(0, str(_SCRIPTS))

from agent_client import AgentClient  # noqa: E402
from collab_common import (  # noqa: E402
    ensure_active_binding,
    find_change_dir,
    iso_now,
    load_state,
    save_state,
)
from collab_listener import is_listener_running, start_listener, stop_listener  # noqa: E402
from patch_builder import chat_confirm_phrase  # noqa: E402
from collab_wecom import (  # noqa: E402
    REVISE_COMMAND_PRD,
    REVISE_COMMAND_TECH,
    push_preview_wait_footer,
)
from design_plan_builder import design_chat_confirm_phrase  # noqa: E402


def _excerpt(text: str, limit: int = 400) -> str:
    stripped = text.strip()
    if len(stripped) <= limit:
        return stripped
    return stripped[: limit - 3] + "..."


def _resolve_patch_dir(change_dir: Path, patch_id: str) -> Path:
    pdir = change_dir / "collaboration" / patch_id
    if not pdir.exists():
        raise FileNotFoundError(f"缺少 patch 目录: {pdir}")
    return pdir


def push_preview(
    req_id: str,
    patch_id: str,
    *,
    mentions: list[str] | None = None,
    preview_type: str = "prd",
) -> str:
    """发群 preview；返回 group_id。未绑群时抛 RuntimeError。"""
    change_dir = find_change_dir(req_id)
    state = load_state(change_dir)
    req_id = state.get("req_id", req_id)
    group_id = ensure_active_binding(change_dir, state, req_id)

    pdir = _resolve_patch_dir(change_dir, patch_id)
    meta_path = pdir / "meta.json"
    summary_path = pdir / "human_summary.md"
    if not meta_path.exists():
        raise FileNotFoundError(f"缺少 {meta_path}")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    preview_type = meta.get("preview_type", preview_type)
    nonce = meta.get("approval_nonce")
    if not nonce:
        raise RuntimeError("meta 缺少 approval_nonce")

    summary = summary_path.read_text(encoding="utf-8") if summary_path.exists() else ""
    revision_round = meta.get("revision_round", 1)
    is_design = preview_type == "tech_design" or patch_id.startswith("design-patch-")
    confirm = (
        design_chat_confirm_phrase(patch_id, nonce)
        if is_design
        else chat_confirm_phrase(patch_id, nonce)
    )

    client = AgentClient.from_config()
    client.upsert_preview_session(
        {
            "reqId": req_id,
            "patchId": patch_id,
            "previewType": "tech_design" if is_design else "prd",
            "groupId": group_id,
            "nonce": nonce,
            "revisionRound": revision_round,
            "summaryExcerpt": _excerpt(summary),
            "status": "draft",
        }
    )

    if is_design:
        markdown = "\n".join(
            [
                f"### 技术方案评审 · `{req_id}` · {patch_id}",
                "",
                _excerpt(summary, 1200),
                "",
                f"> 确认方案请回复：`{confirm}`",
                "",
                f"> 需修订请发送：`{REVISE_COMMAND_TECH}`（技术方案专用，勿用 {REVISE_COMMAND_PRD}）",
                "",
                "> 可在群里先补充修订意见，再发上述口令。",
            ]
        )
    else:
        markdown = "\n".join(
            [
                f"### PRD 修订预览 · `{req_id}` · {patch_id}",
                "",
                _excerpt(summary, 1200),
                "",
                f"> PM 确认写回请回复：`{confirm}`",
                "",
                f"> 需修订请发送：`{REVISE_COMMAND_PRD}`",
            ]
        )
    client.notify(
        {
            "reqId": req_id,
            "groupId": group_id,
            "mentions": mentions or None,
            "markdown": markdown,
        }
    )

    collab = state.setdefault("collaboration", {})
    if is_design:
        collab["phase"] = "tech_design_review"
    elif collab.get("phase") not in ("prd_review", "tech_design_review"):
        collab["phase"] = "prd_review"

    now = iso_now()
    if is_design:
        tdr = collab.setdefault("tech_design_review", {})
        tdr["active_patch"] = patch_id
        tdr["last_preview_at"] = now
        tdr["revision_cursor"] = now
    else:
        pr = collab.setdefault("prd_review", {})
        pr["active_patch"] = patch_id
        pr["last_preview_at"] = now
        pr["revision_cursor"] = now
    save_state(change_dir, state)

    try:
        from collab_push_state import push_state_for_change  # noqa: WPS433

        push_state_for_change(change_dir, state)
    except RuntimeError as e:
        print(f"WARN: push-state 失败: {e}")

    print(f"✓ preview 已注册: {patch_id} nonce={nonce}")
    print(f"✓ Webhook 已发送至已绑定群 group_id={group_id}")
    print(f"✓ 确认语: `{confirm}`")
    return group_id


def ensure_headless_listener(req_id: str, *, restart: bool = False) -> int:
    """无头降级：Cursor 不在时自动 approve。"""
    change_dir = find_change_dir(req_id)
    if restart and is_listener_running(change_dir):
        stop_listener(change_dir)
    pid = start_listener(req_id, auto_approve=True, scripts_dir=_SCRIPTS)
    if pid is None:
        raise RuntimeError("启动无头监听失败")
    print(f"✓ 无头监听 pid={pid}（仅自动 approve，不唤醒主会话）")
    return pid


def main() -> int:
    parser = argparse.ArgumentParser(description="push-preview：绑群 + Webhook")
    parser.add_argument("--req-id", required=True)
    parser.add_argument("--patch", required=True)
    parser.add_argument("--mention", action="append", default=[], help="企微 @userid，可重复")
    parser.add_argument(
        "--headless-listen",
        action="store_true",
        help="额外启动无头 listen（仅自动 approve，不唤醒主会话）",
    )
    parser.add_argument(
        "--restart-listener",
        action="store_true",
        help="启动 headless listen 前重启已有 listen 进程",
    )
    args = parser.parse_args()

    try:
        push_preview(args.req_id, args.patch, mentions=args.mention or None)
    except (RuntimeError, FileNotFoundError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    if args.headless_listen:
        try:
            ensure_headless_listener(args.req_id, restart=args.restart_listener)
        except (RuntimeError, FileNotFoundError) as e:
            print(f"ERROR: 无头监听启动失败: {e}", file=sys.stderr)
            return 1

    phase = load_state(find_change_dir(args.req_id)).get("collaboration", {}).get("phase")
    for line in push_preview_wait_footer(args.req_id, phase=phase):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
