"""Pipeline 联调协作公共工具。"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

CHANGES_BASE = Path("changes")
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent.parent.parent.parent
CONFIG_DIR = _SCRIPT_DIR.parent.parent / "config"


def project_root() -> Path:
    return _PROJECT_ROOT


def find_change_dir(req_id: str) -> Path:
    exact = CHANGES_BASE / req_id
    if exact.is_dir():
        return exact

    candidates: list[Path] = []
    if not CHANGES_BASE.is_dir():
        raise FileNotFoundError(f"找不到 change 目录: {req_id}")
    for d in CHANGES_BASE.iterdir():
        if d.is_dir() and (d.name == req_id or d.name.endswith(f"-{req_id}")):
            candidates.append(d)

    if not candidates:
        raise FileNotFoundError(f"找不到 change 目录: {req_id}")

    for d in sorted(candidates, reverse=True):
        state_file = d / "pipeline_state.json"
        if not state_file.exists():
            continue
        state = json.loads(state_file.read_text(encoding="utf-8"))
        for key in ("req_id", "slug", "name"):
            if state.get(key) == req_id:
                return d

    return sorted(candidates, reverse=True)[0]


def load_state(change_dir: Path) -> dict:
    state_file = change_dir / "pipeline_state.json"
    if not state_file.exists():
        raise FileNotFoundError(f"pipeline_state.json 不存在: {state_file}")
    return json.loads(state_file.read_text(encoding="utf-8"))


def save_state(change_dir: Path, state: dict) -> None:
    state["updated_at"] = datetime.now().isoformat()
    state_file = change_dir / "pipeline_state.json"
    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def append_log(change_dir: Path, message: str) -> None:
    log_file = change_dir / "pipeline.log"
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {message}\n")


def next_patch_id(change_dir: Path, state: dict) -> tuple[str, int]:
    collab = state.setdefault("collaboration", {})
    seq = int(collab.get("last_patch_seq", 0)) + 1
    patch_id = f"patch-{seq:03d}"
    return patch_id, seq


def patch_dir(change_dir: Path, patch_id: str) -> Path:
    path = change_dir / "collaboration" / patch_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_window(window: str) -> datetime:
    m = re.fullmatch(r"(\d+)(h|d)", window.strip().lower())
    if not m:
        raise ValueError(f"window 格式无效: {window}，期望如 2h / 48h / 1d")
    amount = int(m.group(1))
    unit = m.group(2)
    hours = amount * (24 if unit == "d" else 1)
    return datetime.now(timezone.utc).replace(microsecond=0) - __import__("datetime").timedelta(hours=hours)


def effective_req_id(state: dict, change_dir: Path) -> str:
    for key in ("req_id", "slug", "name"):
        val = state.get(key)
        if val:
            return str(val)
    return change_dir.name


def normalize_feishu_url(url: str) -> str:
    return url.split("?")[0].strip().rstrip("/")
