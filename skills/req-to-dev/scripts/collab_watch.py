"""[非生产主路径] 后台监视 + AGENT_COLLAB_WAKE。链路1 请用 collab_wait 阻塞 wait（单轮结束无法 notify 唤起）。"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

_LIB = Path(__file__).resolve().parent / "lib"
sys.path.insert(0, str(_LIB))

from collab_common import append_log, find_change_dir, project_root  # noqa: E402
from collab_inbox import load_watch_state, persist_intent, save_watch_state, watch_paths  # noqa: E402
from collab_listener import listener_paths  # noqa: E402
from collab_wait import wait_for_intent  # noqa: E402

WAKE_PREFIX = "AGENT_COLLAB_WAKE"


def _log_line(log_file: Path, message: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {message}\n")


def _emit_wake(req_id: str, intent: dict, inbox_path: Path) -> None:
    payload = {
        "req_id": req_id,
        "action": intent.get("action"),
        "intent_id": intent.get("id"),
        "patch": intent.get("patchId"),
        "inbox": str(inbox_path.relative_to(project_root())),
    }
    print(f"{WAKE_PREFIX} {json.dumps(payload, ensure_ascii=False)}", flush=True)


def watch_loop(req_id: str, *, poll_sec: int = 55) -> None:
    change_dir = find_change_dir(req_id)
    pid_file, log_file, inbox_path = watch_paths(change_dir)
    _, _, latest_path = listener_paths(change_dir)
    watch_state = load_watch_state(change_dir)

    pid_file.write_text(str(os.getpid()), encoding="utf-8")
    _log_line(log_file, f"WATCH start req_id={req_id} pid={os.getpid()}")
    append_log(change_dir, f"WATCH armed req_id={req_id}")
    print(f"collab_watch armed req_id={req_id}", flush=True)

    try:
        while True:
            intent = wait_for_intent(req_id, timeout=poll_sec + 5, poll_sec=poll_sec)
            if intent.get("status") == "timeout":
                continue

            intent_id = intent.get("id")
            if intent_id is not None and intent_id == watch_state.get("last_emitted_intent_id"):
                continue

            persist_intent(change_dir, intent)
            watch_state["last_emitted_intent_id"] = intent_id
            save_watch_state(change_dir, watch_state)

            action = intent.get("action")
            _log_line(log_file, f"INTENT action={action} id={intent_id}")
            append_log(change_dir, f"WATCH intent {action} id={intent_id}")
            _emit_wake(req_id, intent, inbox_path)
    finally:
        pid_file.unlink(missing_ok=True)
        _log_line(log_file, "WATCH stopped")


def stop_watch(change_dir: Path) -> bool:
    pid_file, _, _ = watch_paths(change_dir)
    if not pid_file.exists():
        return False
    try:
        pid = int(pid_file.read_text(encoding="utf-8").strip())
        os.kill(pid, 15)
    except (OSError, ValueError):
        pass
    pid_file.unlink(missing_ok=True)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="主会话协作监视：意图到达时发 AGENT_COLLAB_WAKE（须在 Cursor 监控终端后台运行）",
    )
    parser.add_argument("--req-id", required=True)
    parser.add_argument("--poll-sec", type=int, default=55)
    parser.add_argument("--stop", action="store_true")
    args = parser.parse_args()

    try:
        change_dir = find_change_dir(args.req_id)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    if args.stop:
        stopped = stop_watch(change_dir)
        print("✓ 已停止 watch" if stopped else "ℹ 无运行中的 watch")
        return 0

    try:
        watch_loop(args.req_id, poll_sec=args.poll_sec)
    except KeyboardInterrupt:
        _, log_file, _ = watch_paths(change_dir)
        _log_line(log_file, "WATCH interrupted")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
