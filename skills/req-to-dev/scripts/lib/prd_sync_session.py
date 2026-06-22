"""Pre-Pipeline 会议纪要 → PRD 工作区（init 之前，无 req_id）。"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from collab_common import normalize_feishu_url

PRD_SYNC_BASE = Path("prd-sync")


def prd_token(prd_url: str) -> str:
    url = normalize_feishu_url(prd_url)
    m = re.search(r"/(?:wiki|docx)/([A-Za-z0-9]+)", url)
    return m.group(1)[:16] if m else "unknown"


def session_id_for(prd_url: str) -> str:
    return f"prd-{prd_token(prd_url)}"


def session_root(prd_url: str) -> Path:
    return PRD_SYNC_BASE / prd_token(prd_url)


def patch_dir(prd_url: str, patch_id: str) -> Path:
    p = session_root(prd_url) / "patches" / patch_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def load_session(prd_url: str) -> dict:
    prd_url = normalize_feishu_url(prd_url)
    root = session_root(prd_url)
    path = root / "session.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        data["prd_url"] = normalize_feishu_url(data.get("prd_url", prd_url))
        return data

    return {
        "phase": "pre-pipeline",
        "session_id": session_id_for(prd_url),
        "prd_url": prd_url,
        "last_patch_seq": 0,
        "patches": {},
        "note": "PRD 定稿阶段，尚未 run_workflow init，无 req_id",
    }


def save_session(prd_url: str, session: dict) -> None:
    root = session_root(prd_url)
    root.mkdir(parents=True, exist_ok=True)
    session["updated_at"] = datetime.now().isoformat()
    (root / "session.json").write_text(
        json.dumps(session, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def append_session_log(prd_url: str, message: str) -> None:
    log_file = session_root(prd_url) / "session.log"
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {message}\n")


def next_patch(session: dict) -> tuple[str, int]:
    seq = int(session.get("last_patch_seq", 0)) + 1
    return f"patch-{seq:03d}", seq


def resolve_pre_pipeline_patch(prd_url: str, patch_id: str) -> tuple[Path, dict, str]:
    prd_url = normalize_feishu_url(prd_url)
    session = load_session(prd_url)
    pdir = patch_dir(prd_url, patch_id)
    if not (pdir / "plan.json").exists():
        raise FileNotFoundError(f"找不到 patch: {pdir}")
    return pdir, session, prd_url
