"""PRD 标题 → slug / req_id 工具。

与 shop-points-agent CollabMessageHandler 一致：req_id = {YYYYMMDD}-{slug}[-n]，
slug 仅允许小写 ASCII 字母、数字与连字符，禁止中文等非 ASCII 字符。
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

from collab_common import CHANGES_BASE

# 与 Agent 端 /init 校验对齐
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$")
REQ_ID_RE = re.compile(r"^[0-9]{8}-[a-z0-9][a-z0-9-]*[a-z0-9](?:-[0-9]+)?$")


def extract_prd_title(md: str) -> str:
    for line in md.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    for line in md.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("!["):
            return stripped[:80]
    return "untitled"


def _hash_slug(text: str, prefix: str = "req") -> str:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]
    return f"{prefix}-{digest}"


def slugify(text: str, max_len: int = 40) -> str:
    """PRD 标题 → ASCII slug；纯中文或无字母片段时回退 req-<hash8>。"""
    text = text.strip()
    if not text:
        return _hash_slug("untitled")

    ascii_slug = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    if len(ascii_slug) >= 3 and re.search(r"[a-z]", ascii_slug):
        return ascii_slug[:max_len].strip("-")

    return _hash_slug(text)[:max_len]


def normalize_slug(text: str, *, max_len: int = 40) -> str:
    """清洗用户 --slug 入参；非法时按标题规则或 hash 回退。"""
    raw = (text or "").strip()
    if not raw:
        raise ValueError("slug 不能为空")

    candidate = re.sub(r"[^a-zA-Z0-9]+", "-", raw).strip("-").lower()
    if SLUG_RE.match(candidate):
        return candidate[:max_len].strip("-")

    return slugify(raw, max_len=max_len)


def is_valid_slug(slug: str) -> bool:
    return bool(SLUG_RE.match((slug or "").strip()))


def is_valid_req_id(req_id: str) -> bool:
    return bool(REQ_ID_RE.match((req_id or "").strip()))


def format_req_id_error(slug_or_req_id: str) -> str:
    return (
        f"req_id 格式无效: {slug_or_req_id!r}，"
        "期望 YYYYMMDD-slug（slug 仅小写 a-z、0-9、连字符，禁止中文）"
    )


def generate_req_id(slug: str, changes_base: Path | None = None) -> str:
    slug = (slug or "").strip()
    if not is_valid_slug(slug):
        raise ValueError(format_req_id_error(slug))

    base_dir = changes_base or CHANGES_BASE
    today = datetime.now().strftime("%Y%m%d")
    base = f"{today}-{slug}"
    if not (base_dir / base).exists():
        return base
    n = 2
    while (base_dir / f"{base}-{n}").exists():
        n += 1
    return f"{base}-{n}"


def repair_change_dir_req_id(
    change_dir: Path,
    *,
    new_slug: str | None = None,
    title_source: str | None = None,
) -> tuple[str, str]:
    """将含非法 slug 的工作区重命名为合法 req_id，并更新 state / patch meta。"""
    from collab_common import load_state, save_state  # noqa: WPS433

    state = load_state(change_dir)
    old_req_id = state.get("req_id", change_dir.name)

    if title_source is None:
        prd_path = change_dir / "request" / "prd.md"
        if prd_path.exists():
            title_source = extract_prd_title(prd_path.read_text(encoding="utf-8"))
        else:
            title_source = state.get("slug") or old_req_id

    slug = normalize_slug(new_slug or title_source)
    new_req_id = generate_req_id(slug)
    if new_req_id == old_req_id and is_valid_req_id(old_req_id):
        return old_req_id, slug

    new_dir = change_dir.parent / new_req_id
    if new_dir.exists() and new_dir.resolve() != change_dir.resolve():
        raise RuntimeError(f"目标目录已存在: {new_dir}")

    state["req_id"] = new_req_id
    state["slug"] = slug
    state["name"] = new_req_id
    state["change_dir"] = str(new_dir)
    state["branch"] = f"feature/{new_req_id}"
    save_state(change_dir, state)

    for meta_path in (change_dir / "collaboration").glob("patch-*/meta.json"):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["req_id"] = new_req_id
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    for prompt_path in (change_dir / "collaboration").glob("patch-*/meeting_prompt.md"):
        text = prompt_path.read_text(encoding="utf-8")
        text = text.replace(f"req_id: {old_req_id}", f"req_id: {new_req_id}")
        prompt_path.write_text(text, encoding="utf-8")

    for summary_path in (change_dir / "collaboration").glob("patch-*/human_summary.md"):
        text = summary_path.read_text(encoding="utf-8")
        text = text.replace(f"`{old_req_id}`", f"`{new_req_id}`")
        summary_path.write_text(text, encoding="utf-8")

    if new_dir.resolve() != change_dir.resolve():
        change_dir.rename(new_dir)
        change_dir = new_dir
        save_state(change_dir, state)

    return new_req_id, slug
