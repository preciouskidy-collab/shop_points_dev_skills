"""企微联调群消息 sender 系统号 → 角色映射（digest 摘要用）。"""

from __future__ import annotations

import json
from typing import Any

from collab_common import CONFIG_DIR

# 默认角色映射（可通过 secrets.local.json / agent.yaml 覆盖）
DEFAULT_SENDER_ROLES: dict[str, str] = {
    "31449898": "RD",
    "31175736": "FE",
    "29198147": "PM",
    "26670281": "RD负责人",
    "20233755": "RDLeader",
}

ROLE_DESCRIPTIONS: dict[str, str] = {
    "RD": "后端研发",
    "FE": "前端研发",
    "PM": "产品经理",
    "RD负责人": "后端负责人",
    "RDLeader": "研发负责人",
}


def load_sender_roles() -> dict[str, str]:
    """合并默认映射与本地配置 collab.sender_roles。"""
    roles = dict(DEFAULT_SENDER_ROLES)

    secrets = CONFIG_DIR / "secrets.local.json"
    if secrets.exists():
        data = json.loads(secrets.read_text(encoding="utf-8"))
        if isinstance(data.get("collab"), dict) and isinstance(data["collab"].get("sender_roles"), dict):
            roles.update({str(k): str(v) for k, v in data["collab"]["sender_roles"].items()})

    for name in ("agent.local.yaml", "agent.yaml"):
        p = CONFIG_DIR / name
        if not p.exists():
            continue
        try:
            import yaml  # type: ignore

            data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            collab = data.get("collab") or {}
            if isinstance(collab.get("sender_roles"), dict):
                roles.update({str(k): str(v) for k, v in collab["sender_roles"].items()})
        except ImportError:
            break

    return roles


def resolve_sender_role(message: dict[str, Any], roles: dict[str, str] | None = None) -> str:
    """从消息 dict 解析角色标签。"""
    roles = roles or load_sender_roles()
    sender_id = str(
        message.get("senderId")
        or message.get("sender_id")
        or message.get("sender")
        or ""
    ).strip()
    if sender_id and sender_id in roles:
        return roles[sender_id]
    sender_name = (message.get("senderName") or message.get("sender_name") or "").strip()
    if sender_name:
        return sender_name
    if sender_id:
        return f"未知·{sender_id}"
    return "未知"


def format_sender_roles_legend(roles: dict[str, str] | None = None) -> str:
    """生成角色说明，供 digest_prompt / LLM system 使用。"""
    roles = roles or load_sender_roles()
    lines = ["| 系统号 | 角色 | 说明 |", "|--------|------|------|"]
    for sender_id, role in sorted(roles.items(), key=lambda x: x[1]):
        desc = ROLE_DESCRIPTIONS.get(role, "")
        lines.append(f"| {sender_id} | {role} | {desc} |")
    return "\n".join(lines)


def format_collab_messages_md(messages: list[dict], roles: dict[str, str] | None = None) -> str:
    """将群消息格式化为带角色标签的 Markdown 列表。"""
    from collab_message_enricher import message_display_content  # noqa: WPS433

    roles = roles or load_sender_roles()
    lines: list[str] = []
    for m in messages:
        content = message_display_content(m)
        if not content:
            continue
        role = resolve_sender_role(m, roles)
        ts = m.get("createdAt") or m.get("created_at") or ""
        prefix = f"[{ts}] " if ts else ""
        lines.append(f"- {prefix}[{role}] {content}")
    return "\n".join(lines)
