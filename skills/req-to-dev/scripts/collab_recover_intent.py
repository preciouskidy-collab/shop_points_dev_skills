#!/usr/bin/env python3
"""补救：拉取队列中尚未消费的 pending intent。"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parent / "lib"
_SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_LIB))
sys.path.insert(0, str(_SCRIPTS))

from collab_common import find_change_dir, project_root  # noqa: E402
from collab_inbox import persist_intent  # noqa: E402
from collab_listener import start_listener  # noqa: E402
from collab_wait import wait_for_intent  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="消费队列中遗留的协作意图")
    parser.add_argument("--req-id", required=True)
    parser.add_argument("--timeout", type=int, default=10, help="短轮询秒数")
    parser.add_argument("--start-listener", action="store_true", help="处理后启动无头 listen")
    parser.add_argument(
        "--emit-wake",
        action="store_true",
        help="[已废弃] 仅落盘 intent；请在主会话阻塞 wait",
    )
    args = parser.parse_args()

    intent = wait_for_intent(args.req_id, timeout=args.timeout, poll_sec=min(args.timeout, 55))
    if intent.get("status") == "timeout":
        print(json.dumps({"status": "no_pending", "req_id": args.req_id}, ensure_ascii=False))
        print("ℹ 队列中无 pending intent（可能已消费或未入队）", file=sys.stderr)
        return 1

    change_dir = find_change_dir(args.req_id)
    persist_intent(change_dir, intent)
    print(json.dumps(intent, ensure_ascii=False))

    action = intent.get("action")
    intent_id = intent.get("id")

    if args.emit_wake:
        print(
            "WARN: --emit-wake 已废弃；请在主会话同一回合执行 wait 并处理返回的 JSON",
            file=sys.stderr,
        )

    if action == "approve" and intent_id is not None:
        cli = (
            project_root()
            / "skills/req-to-dev/sub_skills/collab-prd-sync/scripts/collab_prd_sync.py"
        )
        proc = subprocess.run(
            [
                sys.executable,
                str(cli),
                "approve",
                "--req-id",
                args.req_id,
                "--pull-intent-id",
                str(intent_id),
            ],
            cwd=str(project_root()),
        )
        if proc.returncode != 0:
            return proc.returncode
        print("✅ 已消费 approval_intent 并完成 approve")
    elif action == "meeting_revise":
        print(
            "ℹ meeting_revise 已落盘 inbox.json；请在主会话同一回合："
            "meeting-revise → 写 plan → finalize-plan → push-preview → wait",
            file=sys.stderr,
        )
    elif action == "tech_revise":
        print(
            "ℹ tech_revise 已落盘；请在主会话同一回合："
            "collab_tech_design_sync tech-revise → 写 design_plan → finalize-design "
            "→ push-preview → wait",
            file=sys.stderr,
        )
    elif action == "plan_approve":
        print(
            "ℹ plan_approve 已落盘；请在主会话同一回合：approve-design --pull-intent-id",
            file=sys.stderr,
        )

    if args.start_listener:
        pid = start_listener(args.req_id, auto_approve=True, scripts_dir=_SCRIPTS)
        print(f"✓ 无头监听已启动 pid={pid}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
