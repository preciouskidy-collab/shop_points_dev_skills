#!/usr/bin/env python3
"""链路1 主路径：阻塞长轮询 Agent 意图队列；stdout 输出一行 JSON。"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

_LIB = Path(__file__).resolve().parent / "lib"
sys.path.insert(0, str(_LIB))

from agent_client import AgentClient  # noqa: E402
from collab_common import append_log, find_change_dir  # noqa: E402
from collab_inbox import persist_intent  # noqa: E402

# PRD / 技术方案评审须接收全部 intent；仅 E2E 上传场景允许 action 过滤
_ALLOWED_WAIT_ACTION_FILTERS = frozenset({"upload_confirm"})


def _reject_disallowed_action_filter(action: str | None) -> None:
    if not action or action in _ALLOWED_WAIT_ACTION_FILTERS:
        return
    print(
        f"ERROR: collab_wait --action {action!r} 禁止用于 PRD/技术方案评审。\n"
        "push-preview 后须使用 **无 action 过滤** 的阻塞 wait，以同时接收 "
        "approve / meeting_revise / tech_revise / plan_approve。\n"
        "企微 /整理评审 允许多次；收到 meeting_revise 应走修订循环，不得丢弃。\n"
        "正确命令:\n"
        "  python3 skills/req-to-dev/sub_skills/collab-prd-sync/scripts/collab_prd_sync.py "
        "wait --req-id <req_id> --timeout 3600\n"
        "E2E 人工上传请用 collab_e2e_upload.py wait（非本脚本）。\n"
        "详见 guardrails/pipeline-redlines.md R2.2",
        file=sys.stderr,
    )
    raise SystemExit(2)


def wait_for_intent(
    req_id: str,
    *,
    timeout: int = 600,
    poll_sec: int = 55,
    action: str | None = None,
    client: AgentClient | None = None,
) -> dict:
    """阻塞等待首个 pending intent；超时返回 {"status": "timeout", "req_id": ...}。"""
    client = client or AgentClient.from_config()
    deadline = time.time() + timeout

    while time.time() < deadline:
        remaining = int(deadline - time.time())
        if remaining <= 0:
            break
        timeout_sec = min(poll_sec, remaining, 120)
        try:
            resp = client.wait_intents(
                req_id,
                timeout_sec=timeout_sec,
                action=action,
            )
        except RuntimeError as e:
            print(f"WARN: wait 失败: {e}", file=sys.stderr)
            time.sleep(2)
            continue

        intents = resp.get("intents") or []
        if intents:
            intent = intents[0]
            if action and intent.get("action") != action:
                print(
                    f"WARN: 收到非目标 action={intent.get('action')}，继续 wait（目标={action}）",
                    file=sys.stderr,
                )
                continue
            return intent

    return {"status": "timeout", "req_id": req_id}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="阻塞等待企微协作意图（链路1 主路径；须在主会话同一回合内调用）",
    )
    parser.add_argument("--req-id", required=True)
    parser.add_argument("--timeout", type=int, default=3600, help="总阻塞超时秒数（默认 1h）")
    parser.add_argument("--poll-sec", type=int, default=55, help="单次 long-poll 秒数")
    parser.add_argument(
        "--action",
        default=None,
        help="仅 E2E 上传场景允许 upload_confirm；PRD/技术方案评审禁止传此参数",
    )
    args = parser.parse_args()

    _reject_disallowed_action_filter(args.action)

    intent = wait_for_intent(
        args.req_id,
        timeout=args.timeout,
        poll_sec=args.poll_sec,
        action=args.action,
    )
    print(json.dumps(intent, ensure_ascii=False))

    if intent.get("status") == "timeout":
        print(
            "ℹ wait 超时：请在同一回合立即再次执行 wait，勿结束对话",
            file=sys.stderr,
        )
        return 0

    try:
        change_dir = find_change_dir(args.req_id)
        persist_intent(change_dir, intent)
        append_log(change_dir, f"WAIT intent {intent.get('action')} id={intent.get('id')}")
    except FileNotFoundError as e:
        print(f"WARN: 落盘失败: {e}", file=sys.stderr)

    action = intent.get("action")
    intent_id = intent.get("id")
    handle_cmd = (
        f"python3 skills/req-to-dev/scripts/collab_handle_intent.py "
        f"--req-id {args.req_id} --pull-intent-id {intent_id} --action {action}"
    )
    print(
        f"✓ COLLAB_INTENT_RECEIVED action={action} intent_id={intent_id}\n"
        f"→ 同一回合内执行: {handle_cmd}\n"
        f"  meeting_revise/tech_revise 须在 meeting-revise/tech-revise 带 --pull-intent-id（prepare 成功后自动 consume）",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
