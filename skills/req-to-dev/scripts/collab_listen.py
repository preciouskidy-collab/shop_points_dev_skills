#!/usr/bin/env python3
"""无头降级：仅自动 approve。链路1 生产请用 collab_wait 阻塞 wait（主会话同一回合）。"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

_LIB = Path(__file__).resolve().parent / "lib"
_SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_LIB))
sys.path.insert(0, str(_SCRIPTS))

from collab_common import append_log, find_change_dir, project_root  # noqa: E402
from collab_listener import listener_paths, stop_listener  # noqa: E402
from collab_wait import wait_for_intent  # noqa: E402


def _log_line(log_file: Path, message: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {message}\n")


def _save_intent(change_dir: Path, intent: dict) -> Path:
    _, _, latest = listener_paths(change_dir)
    latest.write_text(json.dumps(intent, ensure_ascii=False, indent=2), encoding="utf-8")
    return latest


def _run_auto_approve(req_id: str, intent_id: int) -> int:
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
            req_id,
            "--pull-intent-id",
            str(intent_id),
        ],
        cwd=str(project_root()),
        capture_output=True,
        text=True,
    )
    if proc.stdout:
        print(proc.stdout, end="")
    if proc.stderr:
        print(proc.stderr, end="", file=sys.stderr)
    return proc.returncode


def listen_loop(
    req_id: str,
    *,
    auto_approve: bool = True,
    poll_sec: int = 55,
) -> None:
    change_dir = find_change_dir(req_id)
    _, log_file, _ = listener_paths(change_dir)
    _log_line(log_file, f"LISTEN start req_id={req_id} auto_approve={auto_approve} (headless)")

    while True:
        intent = wait_for_intent(req_id, timeout=poll_sec + 5, poll_sec=poll_sec)
        if intent.get("status") == "timeout":
            continue

        action = intent.get("action")
        intent_id = intent.get("id")
        _save_intent(change_dir, intent)
        _log_line(log_file, f"INTENT action={action} id={intent_id}")
        append_log(change_dir, f"LISTEN intent {action} id={intent_id}")
        print(json.dumps(intent, ensure_ascii=False), flush=True)

        if action == "approve" and auto_approve and intent_id is not None:
            rc = _run_auto_approve(req_id, int(intent_id))
            _log_line(log_file, f"AUTO_APPROVE exit={rc} intent_id={intent_id}")
            if rc == 0:
                append_log(change_dir, f"AUTO_APPROVE ok intent_id={intent_id}")
            else:
                append_log(change_dir, f"AUTO_APPROVE failed intent_id={intent_id} rc={rc}")
        elif action == "meeting_revise":
            _log_line(
                log_file,
                "meeting_revise 已落盘；主会话请阻塞 wait 后 meeting-revise（口令 /整理评审）",
            )
        elif action == "tech_revise":
            _log_line(
                log_file,
                "tech_revise 已落盘；主会话请阻塞 wait 后 tech-revise（口令 /整理方案）",
            )
        elif action == "plan_approve":
            _log_line(log_file, "plan_approve 已落盘；主会话请 approve-design")


def main() -> int:
    parser = argparse.ArgumentParser(description="无头监听：仅自动 approve（降级）")
    parser.add_argument("--req-id", required=True)
    parser.add_argument("--auto-approve", action="store_true", help="收到 approval_intent 自动 approve")
    parser.add_argument("--poll-sec", type=int, default=55)
    parser.add_argument("--stop", action="store_true", help="停止该 req_id 的后台监听")
    args = parser.parse_args()

    try:
        change_dir = find_change_dir(args.req_id)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    if args.stop:
        stopped = stop_listener(change_dir)
        print("✓ 已停止监听" if stopped else "ℹ 无运行中的监听")
        return 0

    try:
        listen_loop(args.req_id, auto_approve=args.auto_approve, poll_sec=args.poll_sec)
    except KeyboardInterrupt:
        _, log_file, _ = listener_paths(change_dir)
        _log_line(log_file, "LISTEN interrupted")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
