#!/usr/bin/env python3
"""collab-prd-sync Skill 统一 CLI 入口（转发至 req-to-dev/scripts）。"""

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
    parser = argparse.ArgumentParser(
        description="联调 PRD 同步（collab-prd-sync Skill 入口）",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_digest = sub.add_parser("digest", help="企微联调群消息 → PRD digest（dry-run）")
    p_digest.add_argument("--req-id", required=True)
    p_digest.add_argument("--window", default="48h")

    p_meeting = sub.add_parser("meeting", help="会议纪要 → PRD（pre-pipeline，无需 req_id）")
    p_meeting.add_argument("--meeting-url", required=True)
    p_meeting.add_argument("--prd-url", required=True)

    p_approve = sub.add_parser("approve", help="交互审批 + 写回 PRD")
    p_approve.add_argument("--patch", required=True)
    p_approve.add_argument("--approver", required=True)
    p_approve.add_argument("--req-id", default=None, help="Pipeline 联调（链路 2）")
    p_approve.add_argument("--prd-url", default=None, help="会议纪要定稿（链路 1，无 req_id）")
    p_approve.add_argument("--note", default="")
    p_approve.add_argument("--force", action="store_true")
    p_approve.add_argument(
        "--mode",
        choices=("agent-chat", "terminal"),
        default="agent-chat",
        help="默认 agent-chat：用户在对话确认后 Agent 代跑",
    )
    p_approve.add_argument("--chat-confirm", default="", help="用户在对话中的确认原话")
    p_approve.add_argument("--confirmed-by", default="")

    p_resync = sub.add_parser("resync", help="PRD diff 增量回灌 spec/tasks")
    p_resync.add_argument("--req-id", required=True)

    p_test = sub.add_parser("test", help="lark-cli fetch + dry-run 连通性测试")
    p_test.add_argument("--url", default=None)
    p_test.add_argument("--skip-update-dry-run", action="store_true")

    args = parser.parse_args()

    if args.command == "digest":
        return _run("collab_digest.py", ["--req-id", args.req_id, "--window", args.window])
    if args.command == "meeting":
        return _run(
            "feishu_prd_sync.py",
            ["--meeting-url", args.meeting_url, "--prd-url", args.prd_url],
        )
    if args.command == "approve":
        argv = ["--patch", args.patch, "--approver", args.approver]
        if args.prd_url:
            argv.extend(["--prd-url", args.prd_url])
        elif args.req_id:
            argv.extend(["--req-id", args.req_id])
        else:
            print("ERROR: approve 需要 --prd-url 或 --req-id", file=sys.stderr)
            return 1
        if args.note:
            argv.extend(["--note", args.note])
        if args.force:
            argv.append("--force")
        argv.extend(["--mode", args.mode])
        if args.chat_confirm:
            argv.extend(["--chat-confirm", args.chat_confirm])
        if args.confirmed_by:
            argv.extend(["--confirmed-by", args.confirmed_by])
        return _run("collab_approve.py", argv)
    if args.command == "resync":
        return _run("prd_resync.py", ["--req-id", args.req_id])
    if args.command == "test":
        argv = []
        if args.url:
            argv.extend(["--url", args.url])
        if args.skip_update_dry_run:
            argv.append("--skip-update-dry-run")
        return _run("collab_lark_test.py", argv)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
