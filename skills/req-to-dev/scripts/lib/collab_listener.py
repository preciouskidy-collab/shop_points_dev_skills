"""协作意图后台监听器（push-preview 后自动拉起）。"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from collab_common import find_change_dir, project_root


def listener_paths(change_dir: Path) -> tuple[Path, Path, Path]:
    collab = change_dir / "collaboration"
    collab.mkdir(parents=True, exist_ok=True)
    return (
        collab / "listener.pid",
        collab / "listener.log",
        collab / "latest_intent.json",
    )


def is_listener_running(change_dir: Path) -> bool:
    pid_file, _, _ = listener_paths(change_dir)
    if not pid_file.exists():
        return False
    try:
        pid = int(pid_file.read_text(encoding="utf-8").strip())
        os.kill(pid, 0)
        return True
    except (OSError, ValueError):
        pid_file.unlink(missing_ok=True)
        return False


def stop_listener(change_dir: Path) -> bool:
    pid_file, _, _ = listener_paths(change_dir)
    if not pid_file.exists():
        return False
    try:
        pid = int(pid_file.read_text(encoding="utf-8").strip())
        os.kill(pid, 15)
    except (OSError, ValueError):
        pass
    pid_file.unlink(missing_ok=True)
    return True


def start_listener(
    req_id: str,
    *,
    auto_approve: bool = True,
    scripts_dir: Path | None = None,
) -> int | None:
    """后台启动 collab_listen.py；已运行则返回已有 pid。"""
    change_dir = find_change_dir(req_id)
    pid_file, log_file, _ = listener_paths(change_dir)
    if is_listener_running(change_dir):
        return int(pid_file.read_text(encoding="utf-8").strip())

    scripts_dir = scripts_dir or Path(__file__).resolve().parent.parent
    listen_script = scripts_dir / "collab_listen.py"
    argv = [sys.executable, str(listen_script), "--req-id", req_id]
    if auto_approve:
        argv.append("--auto-approve")

    log_handle = open(log_file, "a", encoding="utf-8")
    proc = subprocess.Popen(
        argv,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        cwd=str(project_root()),
        start_new_session=True,
    )
    pid_file.write_text(str(proc.pid), encoding="utf-8")
    return proc.pid
