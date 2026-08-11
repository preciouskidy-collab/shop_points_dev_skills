#!/usr/bin/env python3
"""
wait 返回 intent 后的统一编排（修订轮由 meeting-revise / tech-revise prepare 成功后 consume）。

用法:

  python3 collab_handle_intent.py --req-id <id> --stdin   # 管道接 wait stdout
  python3 collab_handle_intent.py --req-id <id> --pull-intent-id <id> --action meeting_revise
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_REQ_ROOT = _SCRIPTS.parent
_ROOT = _REQ_ROOT.parent.parent  # shop_points_dev_skills


def _run(argv: list[str]) -> int:
    proc = subprocess.run([sys.executable, *argv], cwd=str(_ROOT))
    return proc.returncode


def dispatch_intent(req_id: str, intent: dict) -> int:
    action = intent.get("action")
    intent_id = intent.get("id")
    if intent_id is None:
        print("ERROR: intent 缺少 id", file=sys.stderr)
        return 1

    if action == "approve":
        return _run(
            [
                str(_REQ_ROOT / "sub_skills/collab-prd-sync/scripts/collab_prd_sync.py"),
                "approve",
                "--req-id",
                req_id,
                "--pull-intent-id",
                str(intent_id),
            ]
        )
    if action == "plan_approve":
        return _run(
            [
                str(_REQ_ROOT / "sub_skills/collab-tech-design-sync/scripts/collab_tech_design_sync.py"),
                "approve-design",
                "--req-id",
                req_id,
                "--pull-intent-id",
                str(intent_id),
            ]
        )
    if action == "meeting_revise":
        return _run(
            [
                str(_REQ_ROOT / "sub_skills/collab-prd-sync/scripts/collab_prd_sync.py"),
                "meeting-revise",
                "--req-id",
                req_id,
                "--pull-intent-id",
                str(intent_id),
            ]
        )
    if action == "tech_revise":
        return _run(
            [
                str(_REQ_ROOT / "sub_skills/collab-tech-design-sync/scripts/collab_tech_design_sync.py"),
                "tech-revise",
                "--req-id",
                req_id,
                "--pull-intent-id",
                str(intent_id),
            ]
        )

    print(f"ERROR: 未知 action={action!r}", file=sys.stderr)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="wait 后统一处理企微 intent")
    parser.add_argument("--req-id", required=True)
    parser.add_argument("--pull-intent-id", type=int, default=None)
    parser.add_argument("--action", default=None)
    parser.add_argument("--stdin", action="store_true", help="从 stdin 读一行 JSON（wait 输出）")
    args = parser.parse_args()

    if args.stdin:
        line = sys.stdin.readline().strip()
        if not line:
            print("ERROR: stdin 无 JSON", file=sys.stderr)
            return 1
        intent = json.loads(line)
    elif args.pull_intent_id is not None:
        intent = {"id": args.pull_intent_id, "action": args.action, "reqId": args.req_id}
    else:
        parser.error("需要 --pull-intent-id 或 --stdin")

    if args.action and intent.get("action") and intent.get("action") != args.action:
        print(
            f"WARN: --action={args.action!r} 与 intent.action={intent.get('action')!r} 不一致",
            file=sys.stderr,
        )

    return dispatch_intent(args.req_id, intent)


if __name__ == "__main__":
    raise SystemExit(main())
