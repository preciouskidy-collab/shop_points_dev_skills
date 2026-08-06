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


def wait_for_intent(
    req_id: str,
    *,
    timeout: int = 600,
    poll_sec: int = 55,
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
            resp = client.wait_intents(req_id, timeout_sec=timeout_sec)
        except RuntimeError as e:
            print(f"WARN: wait 失败: {e}", file=sys.stderr)
            time.sleep(2)
            continue

        intents = resp.get("intents") or []
        if intents:
            return intents[0]

    return {"status": "timeout", "req_id": req_id}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="阻塞等待企微协作意图（链路1 主路径；须在主会话同一回合内调用）",
    )
    parser.add_argument("--req-id", required=True)
    parser.add_argument("--timeout", type=int, default=3600, help="总阻塞超时秒数（默认 1h）")
    parser.add_argument("--poll-sec", type=int, default=55, help="单次 long-poll 秒数")
    args = parser.parse_args()

    intent = wait_for_intent(
        args.req_id,
        timeout=args.timeout,
        poll_sec=args.poll_sec,
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
    print(
        f"✓ COLLAB_INTENT_RECEIVED action={action} intent_id={intent_id} "
        f"→ 同一回合内处理（approve / meeting-revise / approve-design / tech-revise），勿结束对话",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
