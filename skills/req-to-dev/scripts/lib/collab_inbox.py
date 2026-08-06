"""主会话 inbox / watch 状态落盘。"""

from __future__ import annotations

import json
from pathlib import Path


def watch_paths(change_dir: Path) -> tuple[Path, Path, Path]:
    collab = change_dir / "collaboration"
    collab.mkdir(parents=True, exist_ok=True)
    return (
        collab / "watch.pid",
        collab / "watch.log",
        collab / "inbox.json",
    )


def watch_state_path(change_dir: Path) -> Path:
    return change_dir / "collaboration" / "watch_state.json"


def load_watch_state(change_dir: Path) -> dict:
    path = watch_state_path(change_dir)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_watch_state(change_dir: Path, state: dict) -> None:
    watch_state_path(change_dir).write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def save_inbox(inbox_path: Path, intent: dict) -> None:
    inbox_path.write_text(json.dumps(intent, ensure_ascii=False, indent=2), encoding="utf-8")


def load_inbox(change_dir: Path) -> dict | None:
    _, _, inbox_path = watch_paths(change_dir)
    if not inbox_path.exists():
        return None
    return json.loads(inbox_path.read_text(encoding="utf-8"))


def persist_intent(change_dir: Path, intent: dict) -> Path:
    """落盘 inbox + latest_intent，供主会话 wait 返回后读取。"""
    from collab_listener import listener_paths

    _, _, inbox_path = watch_paths(change_dir)
    save_inbox(inbox_path, intent)
    _, _, latest_path = listener_paths(change_dir)
    latest_path.write_text(json.dumps(intent, ensure_ascii=False, indent=2), encoding="utf-8")
    return inbox_path
