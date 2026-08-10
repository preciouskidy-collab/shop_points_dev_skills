"""E2E 人工上传协作：会话落盘与确认语匹配。"""

from __future__ import annotations

import json
import re
import secrets
from pathlib import Path

from collab_common import append_log, iso_now

DEFAULT_CONFIRM_PHRASES = (
    "已上传",
    "文件已选好",
    "文件已上传",
    "上传完成",
    "我上传了",
    "上传好了",
)

SESSION_FILE = "e2e_upload_session.json"


def session_path(change_dir: Path) -> Path:
    collab = change_dir / "collaboration"
    collab.mkdir(parents=True, exist_ok=True)
    return collab / SESSION_FILE


def load_session(change_dir: Path) -> dict | None:
    path = session_path(change_dir)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_session(change_dir: Path, session: dict) -> Path:
    path = session_path(change_dir)
    path.write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8")
    append_log(change_dir, f"E2E_UPLOAD session {session.get('upload_id')} status={session.get('status')}")
    return path


def new_upload_id() -> str:
    return f"upload-{secrets.token_hex(4)}"


def upload_confirm_phrase(upload_id: str, nonce: str) -> str:
    return f"确认 {upload_id} {nonce} 已上传"


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", text.strip().lower())


def matches_upload_confirm(text: str, session: dict) -> bool:
    raw = text.strip()
    if not raw:
        return False
    upload_id = session.get("upload_id")
    nonce = session.get("nonce")
    if upload_id and nonce:
        expected = upload_confirm_phrase(upload_id, nonce)
        if raw == expected or normalize_text(raw) == normalize_text(expected):
            return True
    phrases = session.get("confirm_phrases") or list(DEFAULT_CONFIRM_PHRASES)
    norm = normalize_text(raw)
    for p in phrases:
        if normalize_text(p) in norm or norm in normalize_text(p):
            return True
    return False


def message_text(msg: dict) -> str:
    for key in ("content", "text", "markdown", "body"):
        val = msg.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def synthesize_intent_from_message(req_id: str, session: dict, msg: dict, text: str) -> dict:
    return {
        "id": None,
        "reqId": req_id,
        "action": "upload_confirm",
        "intent_type": "e2e_upload_intent",
        "source": "wecom_message",
        "upload_id": session.get("upload_id"),
        "message_id": msg.get("id"),
        "sender_id": msg.get("senderId") or msg.get("sender_id"),
        "text": text,
        "received_at": iso_now(),
    }
