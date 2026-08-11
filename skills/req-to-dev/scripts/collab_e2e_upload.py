#!/usr/bin/env python3
"""E2E 人工上传：企微通知 + 阻塞 wait（须在主会话同一回合内处理 upload_confirm）。

无 Cursor 对话降级：Agent API 不可达时脚本报错退出，不得改走聊天确认。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

_LIB = Path(__file__).resolve().parent / "lib"
sys.path.insert(0, str(_LIB))

from agent_client import AgentClient  # noqa: E402
from collab_common import (  # noqa: E402
    append_log,
    ensure_active_binding,
    find_change_dir,
    iso_now,
    load_state,
    save_state,
)
from collab_inbox import persist_intent  # noqa: E402
from e2e_upload_common import (  # noqa: E402
    DEFAULT_CONFIRM_PHRASES,
    load_session,
    matches_upload_confirm,
    message_text,
    new_upload_id,
    save_session,
    synthesize_intent_from_message,
    upload_confirm_phrase,
)
from patch_builder import new_approval_nonce  # noqa: E402


def push_upload_notify(
    req_id: str,
    *,
    label: str,
    detail: str | None = None,
    mentions: list[str] | None = None,
) -> dict:
    change_dir = find_change_dir(req_id)
    state = load_state(change_dir)
    req_id = state.get("req_id", req_id)
    group_id = ensure_active_binding(change_dir, state, req_id)

    upload_id = new_upload_id()
    nonce = new_approval_nonce()
    since = iso_now()
    confirm = upload_confirm_phrase(upload_id, nonce)

    session = {
        "upload_id": upload_id,
        "nonce": nonce,
        "label": label,
        "detail": detail or "",
        "confirm_phrases": list(DEFAULT_CONFIRM_PHRASES),
        "confirm_strict": confirm,
        "since": since,
        "status": "pending",
        "notified_at": since,
        "group_id": group_id,
    }
    save_session(change_dir, session)

    collab = state.setdefault("collaboration", {})
    collab["phase"] = "e2e_upload"
    collab["e2e_upload"] = {
        "upload_id": upload_id,
        "status": "pending",
        "label": label,
        "since": since,
        "nonce": nonce,
    }
    save_state(change_dir, state)

    try:
        from collab_push_state import push_state_for_change  # noqa: WPS433

        push_state_for_change(change_dir, state)
    except Exception as e:
        print(f"WARN: push-state 失败: {e}", file=sys.stderr)

    lines = [
        f"### E2E 需人工上传 · `{req_id}`",
        "",
        f"**任务**：{label}",
    ]
    if detail:
        lines.extend(["", detail])
    lines.extend(
        [
            "",
            "请在浏览器弹窗中 **选择文件并上传**，完成后在本群回复：",
            "",
            f"> `{confirm}`",
            "",
            "> 或简短回复：`已上传` / `文件已选好`",
            "",
            "Agent 收到确认后将 **同一回合** 继续点击「确定」并完成验收。",
        ]
    )
    markdown = "\n".join(lines)

    client = AgentClient.from_config()
    notify_resp = client.notify(
        {
            "reqId": req_id,
            "groupId": group_id,
            "mentions": mentions or None,
            "markdown": markdown,
        }
    )

    append_log(change_dir, f"E2E_UPLOAD notify upload_id={upload_id}")
    print(f"✓ 企微已通知人工上传 upload_id={upload_id}")
    print(f"  确认语（推荐）: {confirm}")
    print("  同一回合须阻塞: collab_e2e_upload.py wait --req-id ...")

    return {
        "req_id": req_id,
        "upload_id": upload_id,
        "nonce": nonce,
        "confirm_phrase": confirm,
        "group_id": group_id,
        "since": since,
        "notify": notify_resp,
    }


def wait_for_upload_confirm(
    req_id: str,
    *,
    timeout: int = 3600,
    poll_sec: int = 55,
    legacy_message_fallback: bool = False,
) -> dict:
    """阻塞等待 upload_confirm（优先 Agent intent 队列；默认不走群消息兜底）。"""
    change_dir = find_change_dir(req_id)
    session = load_session(change_dir)
    if not session or session.get("status") != "pending":
        raise RuntimeError(
            "无 pending 上传会话。请先执行: collab_e2e_upload.py notify --req-id ... --label ..."
        )

    req_id = session.get("req_id") or req_id
    since = session.get("since")
    client = AgentClient.from_config()
    deadline = time.time() + timeout
    seen_message_ids: set[str] = set()

    while time.time() < deadline:
        remaining = int(deadline - time.time())
        if remaining <= 0:
            break
        chunk = min(poll_sec, remaining, 120)

        try:
            resp = client.wait_intents(
                req_id,
                timeout_sec=chunk,
                action="upload_confirm",
            )
            intents = resp.get("intents") or []
            for intent in intents:
                if intent.get("action") == "upload_confirm":
                    intent_id = intent.get("id")
                    if intent_id is not None:
                        try:
                            intent = client.consume_intent(int(intent_id))
                        except RuntimeError as ce:
                            print(f"WARN: consume upload_confirm 失败: {ce}", file=sys.stderr)
                    _complete_session(change_dir, session, intent)
                    persist_intent(change_dir, intent)
                    return intent
                if intent.get("action") in ("approve", "meeting_revise", "plan_approve", "tech_revise"):
                    intent_id = intent.get("id")
                    print(
                        f"WARN: wait 期间收到协作 intent action={intent.get('action')}，"
                        "已消费并落盘；请仅回复上传确认",
                        file=sys.stderr,
                    )
                    persist_intent(change_dir, intent)
                    if intent_id is not None:
                        try:
                            client.consume_intent(int(intent_id))
                        except RuntimeError as ce:
                            print(f"WARN: consume intent 失败: {ce}", file=sys.stderr)
        except RuntimeError as e:
            print(f"WARN: intents/wait 失败: {e}", file=sys.stderr)

        if legacy_message_fallback:
            try:
                msg_resp = client.list_messages(req_id, since=since, limit=100)
                messages = msg_resp.get("messages") or []
                for msg in messages:
                    mid = str(msg.get("id") or msg.get("messageId") or "")
                    if mid and mid in seen_message_ids:
                        continue
                    text = message_text(msg)
                    if not text:
                        continue
                    if mid:
                        seen_message_ids.add(mid)
                    if matches_upload_confirm(text, session):
                        intent = synthesize_intent_from_message(req_id, session, msg, text)
                        _complete_session(change_dir, session, intent)
                        persist_intent(change_dir, intent)
                        print(
                            "WARN: 使用 legacy 群消息兜底（非 Agent intent 队列）；"
                            "请部署 shop-points-agent upload_confirm 解析",
                            file=sys.stderr,
                        )
                        return intent
            except RuntimeError as e:
                print(f"WARN: list_messages 失败: {e}", file=sys.stderr)

    return {"status": "timeout", "req_id": req_id, "upload_id": session.get("upload_id")}


def _complete_session(change_dir: Path, session: dict, intent: dict) -> None:
    session["status"] = "confirmed"
    session["confirmed_at"] = iso_now()
    session["confirm_text"] = intent.get("text")
    save_session(change_dir, session)
    state = load_state(change_dir)
    collab = state.setdefault("collaboration", {})
    if collab.get("e2e_upload"):
        collab["e2e_upload"]["status"] = "confirmed"
        save_state(change_dir, state)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="E2E 人工上传：企微通知 + 阻塞 wait（主会话同一回合）",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_notify = sub.add_parser("notify", help="企微通知用户上传文件")
    p_notify.add_argument("--req-id", required=True)
    p_notify.add_argument("--label", required=True, help="上传任务说明，如「上传贝壳币 Excel」")
    p_notify.add_argument("--detail", default=None, help="补充说明（弹窗路径等）")

    p_wait = sub.add_parser("wait", help="阻塞等待 upload_confirm（同一回合，禁止结束对话）")
    p_wait.add_argument("--req-id", required=True)
    p_wait.add_argument("--timeout", type=int, default=3600)
    p_wait.add_argument("--poll-sec", type=int, default=55)
    p_wait.add_argument(
        "--legacy-message-fallback",
        action="store_true",
        help="[废弃] 启用群消息短语兜底；默认仅 Agent intent 队列",
    )

    args = parser.parse_args()

    try:
        if args.command == "notify":
            result = push_upload_notify(
                args.req_id,
                label=args.label,
                detail=args.detail,
            )
            print(json.dumps(result, ensure_ascii=False))
            return 0

        if args.command == "wait":
            intent = wait_for_upload_confirm(
                args.req_id,
                timeout=args.timeout,
                poll_sec=args.poll_sec,
                legacy_message_fallback=getattr(args, "legacy_message_fallback", False),
            )
            print(json.dumps(intent, ensure_ascii=False))
            if intent.get("status") == "timeout":
                print(
                    "ℹ wait 超时：请在同一回合立即再次执行 wait，勿结束对话",
                    file=sys.stderr,
                )
                return 0
            print(
                f"✓ UPLOAD_CONFIRM_RECEIVED upload_id={intent.get('upload_id')} "
                f"→ 同一回合内继续浏览器操作（点确定等），勿结束对话",
                file=sys.stderr,
            )
            return 0
    except (RuntimeError, FileNotFoundError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
