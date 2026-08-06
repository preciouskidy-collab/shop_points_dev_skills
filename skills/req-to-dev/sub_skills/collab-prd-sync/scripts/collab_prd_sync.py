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

    p_boot = sub.add_parser("bootstrap", help="链路1 立项：PRD+纪要 → req_id")
    p_boot.add_argument("--prd-url", default=None)
    p_boot.add_argument("--meeting-url", default=None)
    p_boot.add_argument("--slug", default=None)
    p_boot.add_argument("--req-id", default=None)
    p_boot.add_argument("--apply-scope-hint", action="store_true")
    p_boot.add_argument("--scope-hint-json", default=None)
    p_boot.add_argument("--project", default=None)
    p_boot.add_argument("--target", default=None)
    p_boot.add_argument("--surfaces", default="h5")

    p_bind = sub.add_parser("binding-check", help="校验企微群已 /init 绑定")
    p_bind.add_argument("--req-id", required=True)

    p_meeting = sub.add_parser("meeting", help="链路1 meeting prepare（须 req_id）")
    p_meeting.add_argument("--req-id", required=True)
    p_meeting.add_argument("--skip-preflight", action="store_true")

    p_revise = sub.add_parser("meeting-revise", help="链路1 修订轮 prepare")
    p_revise.add_argument("--req-id", required=True)

    p_push_preview = sub.add_parser("push-preview", help="绑群 + Webhook；同一回合须阻塞 wait")
    p_push_preview.add_argument("--req-id", required=True)
    p_push_preview.add_argument("--patch", required=True)
    p_push_preview.add_argument("--mention", action="append", default=[])
    p_push_preview.add_argument(
        "--headless-listen",
        action="store_true",
        help="额外启动无头 listen（仅自动 approve，不唤醒主会话）",
    )
    p_push_preview.add_argument("--restart-listener", action="store_true")

    p_watch = sub.add_parser("watch", help="[非生产] 后台监视 + AGENT_COLLAB_WAKE（勿用于链路1）")
    p_watch.add_argument("--req-id", required=True)
    p_watch.add_argument("--poll-sec", type=int, default=55)
    p_watch.add_argument("--stop", action="store_true")

    p_listen = sub.add_parser("listen", help="无头监听（仅自动 approve，降级）")
    p_listen.add_argument("--req-id", required=True)
    p_listen.add_argument("--auto-approve", action="store_true")
    p_listen.add_argument("--stop", action="store_true")
    p_listen.add_argument("--poll-sec", type=int, default=55)

    p_recover = sub.add_parser("recover-intent", help="消费队列中遗留 pending intent")
    p_recover.add_argument("--req-id", required=True)
    p_recover.add_argument("--timeout", type=int, default=10)
    p_recover.add_argument("--start-listener", action="store_true")
    p_recover.add_argument(
        "--emit-wake",
        action="store_true",
        help="[已废弃] 写入 inbox 并打印 AGENT_COLLAB_WAKE；请改用阻塞 wait",
    )

    p_push_state = sub.add_parser("push-state", help="同步协作 phase 到 Agent")
    p_push_state.add_argument("--req-id", required=True)

    p_wait = sub.add_parser("wait", help="链路1 主路径：阻塞等待企微协作意图（同一回合）")
    p_wait.add_argument("--req-id", required=True)
    p_wait.add_argument("--timeout", type=int, default=3600)
    p_wait.add_argument("--poll-sec", type=int, default=55)

    p_digest = sub.add_parser("digest", help="企微联调群消息 → PRD digest（链路2）")
    p_digest.add_argument("--req-id", required=True)
    p_digest.add_argument("--window", default="48h")
    p_digest.add_argument("--no-images", action="store_true")

    p_meeting_legacy = sub.add_parser(
        "meeting-legacy",
        help="[废弃] pre-pipeline 会议纪要 → PRD（无 req_id）",
    )
    p_meeting_legacy.add_argument("--meeting-url", required=True)
    p_meeting_legacy.add_argument("--prd-url", required=True)
    p_meeting_legacy.add_argument("--skip-preflight", action="store_true")

    p_check = sub.add_parser("check-config", help="凭证 / 权限自检")
    p_check.add_argument("--url", default=None)
    p_check.add_argument("--skip-update-probe", action="store_true")

    p_approve = sub.add_parser("approve", help="写回 PRD（链路2 成功后自动 resync）")
    p_approve.add_argument("--patch", default=None)
    p_approve.add_argument("--approver", default=None)
    p_approve.add_argument("--req-id", default=None)
    p_approve.add_argument("--prd-url", default=None, help="[废弃] pre-pipeline")
    p_approve.add_argument("--pull-intent-id", type=int, default=None)
    p_approve.add_argument("--note", default="")
    p_approve.add_argument("--force", action="store_true")
    p_approve.add_argument("--skip-resync", action="store_true")
    p_approve.add_argument("--tier", type=int, choices=(1, 2, 3), default=None)
    p_approve.add_argument("--mode", choices=("agent-chat", "terminal"), default="agent-chat")
    p_approve.add_argument("--chat-confirm", default="")
    p_approve.add_argument("--confirmed-by", default="")
    p_approve.add_argument("--skip-preflight", action="store_true")

    p_resync = sub.add_parser("resync", help="PRD diff 增量回灌 spec/tasks")
    p_resync.add_argument("--req-id", required=True)
    p_resync.add_argument("--patch", default=None)
    p_resync.add_argument("--tier", type=int, choices=(1, 2, 3), default=None)

    p_finalize = sub.add_parser("finalize-plan", help="Agent 修订 plan.json 后重算 human_summary + dry-run")
    p_finalize.add_argument("--patch", required=True)
    p_finalize.add_argument("--prd-url", default=None)
    p_finalize.add_argument("--req-id", default=None)
    p_finalize.add_argument("--allow-append", action="store_true")

    p_test = sub.add_parser("test", help="lark-cli fetch + dry-run 连通性测试")
    p_test.add_argument("--url", default=None)
    p_test.add_argument("--skip-update-dry-run", action="store_true")

    args = parser.parse_args()

    if args.command == "bootstrap":
        argv: list[str] = []
        if args.prd_url:
            argv.extend(["--prd-url", args.prd_url])
        if args.meeting_url:
            argv.extend(["--meeting-url", args.meeting_url])
        if args.slug:
            argv.extend(["--slug", args.slug])
        if args.req_id:
            argv.extend(["--req-id", args.req_id])
        if args.apply_scope_hint:
            argv.append("--apply-scope-hint")
        if args.scope_hint_json:
            argv.extend(["--scope-hint-json", args.scope_hint_json])
        if args.project:
            argv.extend(["--project", args.project])
        if args.target:
            argv.extend(["--target", args.target])
        if args.surfaces:
            argv.extend(["--surfaces", args.surfaces])
        return _run("collab_bootstrap.py", argv)

    if args.command == "binding-check":
        return _run("collab_binding_check.py", ["--req-id", args.req_id])

    if args.command == "meeting":
        argv = ["--req-id", args.req_id]
        if args.skip_preflight:
            argv.append("--skip-preflight")
        return _run("meeting_prepare.py", argv)

    if args.command == "meeting-revise":
        return _run("meeting_revise_prepare.py", ["--req-id", args.req_id])

    if args.command == "push-preview":
        argv = ["--req-id", args.req_id, "--patch", args.patch]
        for m in args.mention:
            argv.extend(["--mention", m])
        if getattr(args, "headless_listen", False):
            argv.append("--headless-listen")
        if getattr(args, "restart_listener", False):
            argv.append("--restart-listener")
        return _run("collab_push_preview.py", argv)

    if args.command == "watch":
        argv = ["--req-id", args.req_id, "--poll-sec", str(args.poll_sec)]
        if args.stop:
            argv.append("--stop")
        return _run("collab_watch.py", argv)

    if args.command == "listen":
        argv = ["--req-id", args.req_id, "--poll-sec", str(args.poll_sec)]
        if args.stop:
            argv.append("--stop")
        if args.auto_approve:
            argv.append("--auto-approve")
        return _run("collab_listen.py", argv)

    if args.command == "recover-intent":
        argv = ["--req-id", args.req_id, "--timeout", str(args.timeout)]
        if args.start_listener:
            argv.append("--start-listener")
        if getattr(args, "emit_wake", False):
            argv.append("--emit-wake")
        return _run("collab_recover_intent.py", argv)

    if args.command == "push-state":
        return _run("collab_push_state.py", ["--req-id", args.req_id])

    if args.command == "wait":
        return _run(
            "collab_wait.py",
            ["--req-id", args.req_id, "--timeout", str(args.timeout), "--poll-sec", str(args.poll_sec)],
        )

    if args.command == "digest":
        digest_argv = ["--req-id", args.req_id, "--window", args.window]
        if args.no_images:
            digest_argv.append("--no-images")
        return _run("collab_digest.py", digest_argv)

    if args.command == "meeting-legacy":
        meeting_argv = ["--meeting-url", args.meeting_url, "--prd-url", args.prd_url]
        if args.skip_preflight:
            meeting_argv.append("--skip-preflight")
        return _run("feishu_prd_sync.py", meeting_argv)

    if args.command == "check-config":
        check_argv: list[str] = []
        if args.url:
            check_argv.extend(["--url", args.url])
        if args.skip_update_probe:
            check_argv.append("--skip-update-probe")
        return _run("collab_check_config.py", check_argv)

    if args.command == "approve":
        argv = []
        if args.patch:
            argv.extend(["--patch", args.patch])
        if args.approver:
            argv.extend(["--approver", args.approver])
        if args.prd_url:
            argv.extend(["--prd-url", args.prd_url])
        elif args.req_id:
            argv.extend(["--req-id", args.req_id])
        else:
            print("ERROR: approve 需要 --prd-url 或 --req-id", file=sys.stderr)
            return 1
        if args.pull_intent_id is not None:
            argv.extend(["--pull-intent-id", str(args.pull_intent_id)])
        if args.note:
            argv.extend(["--note", args.note])
        if args.force:
            argv.append("--force")
        if args.skip_resync:
            argv.append("--skip-resync")
        if args.tier is not None:
            argv.extend(["--tier", str(args.tier)])
        argv.extend(["--mode", args.mode])
        if args.chat_confirm:
            argv.extend(["--chat-confirm", args.chat_confirm])
        if args.confirmed_by:
            argv.extend(["--confirmed-by", args.confirmed_by])
        if args.skip_preflight:
            argv.append("--skip-preflight")
        return _run("collab_approve.py", argv)

    if args.command == "finalize-plan":
        argv = ["--patch", args.patch]
        if args.prd_url:
            argv.extend(["--prd-url", args.prd_url])
        elif args.req_id:
            argv.extend(["--req-id", args.req_id])
        else:
            print("ERROR: finalize-plan 需要 --prd-url 或 --req-id", file=sys.stderr)
            return 1
        if args.allow_append:
            argv.append("--allow-append")
        return _run("finalize_plan.py", argv)

    if args.command == "resync":
        resync_argv = ["--req-id", args.req_id]
        if args.patch:
            resync_argv.extend(["--patch", args.patch])
        if args.tier is not None:
            resync_argv.extend(["--tier", str(args.tier)])
        return _run("prd_resync.py", resync_argv)

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
