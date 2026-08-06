#!/usr/bin/env python3
"""collab-tech-design-sync Skill 统一 CLI 入口。"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

_REQ_TO_DEV_SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"


def _run(script: str, argv: list[str]) -> int:
    path = _REQ_TO_DEV_SCRIPTS / script
    if not path.exists():
        print(f"ERROR: 脚本不存在: {path}", file=sys.stderr)
        return 1
    proc = subprocess.run([sys.executable, str(path), *argv])
    return proc.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="技术方案企微评审（collab-tech-design-sync）")
    sub = parser.add_subparsers(dest="command", required=True)

    p_prepare = sub.add_parser("prepare", help="打包 plan-approve 审批包 + design_prompt")
    p_prepare.add_argument("--req-id", required=True)

    p_finalize = sub.add_parser("finalize-design", help="Agent 修订 design_plan 后重算预览")
    p_finalize.add_argument("--req-id", required=True)
    p_finalize.add_argument("--patch", required=True)

    p_push = sub.add_parser("push-preview", help="发群 preview + 同一回合须 wait")
    p_push.add_argument("--req-id", required=True)
    p_push.add_argument("--patch", required=True)

    p_wait = sub.add_parser("wait", help="阻塞长轮询意图邮箱")
    p_wait.add_argument("--req-id", required=True)
    p_wait.add_argument("--timeout", type=int, default=3600)

    p_revise = sub.add_parser("tech-revise", help="企微 /整理方案 后修订轮 prepare")
    p_revise.add_argument("--req-id", required=True)

    p_approve = sub.add_parser("approve-design", help="应用 design_plan + 解锁 plan-approve")
    p_approve.add_argument("--req-id", required=True)
    p_approve.add_argument("--patch", default=None)
    p_approve.add_argument("--approver", default=None)
    p_approve.add_argument("--chat-confirm", default=None)
    p_approve.add_argument("--pull-intent-id", type=int, default=None)

    args = parser.parse_args()

    if args.command == "prepare":
        return _run("tech_design_prepare.py", ["--req-id", args.req_id])
    if args.command == "finalize-design":
        return _run("finalize_design.py", ["--req-id", args.req_id, "--patch", args.patch])
    if args.command == "push-preview":
        return _run(
            "collab_push_preview.py",
            ["--req-id", args.req_id, "--patch", args.patch],
        )
    if args.command == "wait":
        return _run(
            "collab_wait.py",
            ["--req-id", args.req_id, "--timeout", str(args.timeout)],
        )
    if args.command == "tech-revise":
        return _run("tech_design_revise_prepare.py", ["--req-id", args.req_id])
    if args.command == "approve-design":
        argv = ["--req-id", args.req_id]
        if args.patch:
            argv.extend(["--patch", args.patch])
        if args.approver:
            argv.extend(["--approver", args.approver])
        if args.chat_confirm:
            argv.extend(["--chat-confirm", args.chat_confirm])
        if args.pull_intent_id:
            argv.extend(["--pull-intent-id", str(args.pull_intent_id)])
        return _run("approve_design.py", argv)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
