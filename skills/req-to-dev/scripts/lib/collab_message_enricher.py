"""联调群消息预处理：image 类型解析 signUrl、下载、视觉描述。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from chatarchive_client import (
    download_signed_file,
    get_file_by_md5,
    is_chatarchive_configured,
    load_chatarchive_config,
)
from llm_client import describe_image, is_llm_available, load_llm_config
from sender_roles import resolve_sender_role

_IMAGE_MSG_TYPES = frozenset({"image", "picture", "img"})
_EXT_BY_MIME = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
}


def _message_type(message: dict[str, Any]) -> str:
    return str(
        message.get("msgType")
        or message.get("msg_type")
        or message.get("messageType")
        or message.get("message_type")
        or ""
    ).strip().lower()


def parse_image_payload(content: str) -> dict[str, Any] | None:
    content = (content or "").strip()
    if not content.startswith("{"):
        return None
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    md5 = data.get("md5sum") or data.get("md5Sum")
    if md5:
        return data
    return None


def is_image_message(message: dict[str, Any]) -> bool:
    if _message_type(message) in _IMAGE_MSG_TYPES:
        return True
    raw = (message.get("content") or message.get("message_content") or "").strip()
    return parse_image_payload(raw) is not None


def message_raw_content(message: dict[str, Any]) -> str:
    return (message.get("content") or message.get("message_content") or "").strip()


def message_display_content(message: dict[str, Any]) -> str:
    return str(message.get("display_content") or message_raw_content(message)).strip()


def _guess_ext(file_meta: dict[str, Any], local_path: Path) -> str:
    ext = str(file_meta.get("fileTypeExt") or "").strip()
    if ext:
        return ext if ext.startswith(".") else f".{ext}"
    return local_path.suffix or ".png"


def enrich_collab_messages(
    messages: list[dict],
    *,
    images_dir: Path,
    resolve_images: bool = True,
    use_vision: bool = True,
) -> tuple[list[dict], dict[str, Any]]:
    """
    为 image 消息补充 display_content（含视觉描述）。
    返回 (enriched_messages, stats)。
    """
    enriched: list[dict] = []
    stats: dict[str, Any] = {
        "image_total": 0,
        "image_resolved": 0,
        "image_vision_ok": 0,
        "image_failed": 0,
        "failures": [],
    }

    archive_cfg = load_chatarchive_config()
    llm_cfg = load_llm_config()
    archive_ok = is_chatarchive_configured(archive_cfg)
    vision_ok = use_vision and is_llm_available(llm_cfg)

    for message in messages:
        item = dict(message)
        if not is_image_message(message):
            enriched.append(item)
            continue

        stats["image_total"] += 1
        payload = parse_image_payload(message_raw_content(message)) or {}
        md5sum = str(payload.get("md5sum") or payload.get("md5Sum") or "").strip().lower()
        role = resolve_sender_role(message)

        if not md5sum:
            item["display_content"] = "[图片]（无 md5sum，无法解析存档）"
            enriched.append(item)
            stats["image_failed"] += 1
            stats["failures"].append({"md5sum": md5sum, "error": "missing_md5sum"})
            continue

        if not resolve_images:
            item["display_content"] = f"[图片] md5={md5sum}（已跳过图片解析 --no-images）"
            item["image_meta"] = {"md5sum": md5sum, "skipped": True}
            enriched.append(item)
            continue

        if not archive_ok:
            item["display_content"] = (
                f"[图片] md5={md5sum}（未配置 collab.chatarchive.secret，无法换取 URL）"
            )
            enriched.append(item)
            stats["image_failed"] += 1
            stats["failures"].append({"md5sum": md5sum, "error": "chatarchive_not_configured"})
            continue

        try:
            file_meta = get_file_by_md5(md5sum, archive_cfg)
            sign_url = str(file_meta.get("signUrl") or file_meta.get("signOpenUrl") or "")
            ext = str(file_meta.get("fileTypeExt") or "png").lstrip(".")
            local_name = f"chat-{md5sum}.{ext}"
            local_path = images_dir / local_name
            download_signed_file(sign_url, local_path, timeout_sec=int(archive_cfg.get("timeout_sec", 60)))
            stats["image_resolved"] += 1

            vision_summary = ""
            if vision_ok:
                try:
                    vision_summary = describe_image(
                        local_path,
                        role=role,
                        cfg=llm_cfg,
                    ).strip()
                    stats["image_vision_ok"] += 1
                except Exception as e:
                    vision_summary = f"（视觉描述失败: {e}）"
                    stats["failures"].append({"md5sum": md5sum, "error": f"vision: {e}"})
            else:
                vision_summary = "（未配置 LLM，仅下载图片未做视觉分析）"

            rel_path = f"images/{local_name}"
            item["image_meta"] = {
                "md5sum": md5sum,
                "filesize": payload.get("filesize") or file_meta.get("fileSize"),
                "sign_url": sign_url,
                "local_path": rel_path,
                "file_type": _guess_ext(file_meta, local_path).lstrip("."),
                "vision_summary": vision_summary,
            }
            item["display_content"] = "\n".join(
                [
                    f"[图片·{item['image_meta']['file_type']}] 本地: {rel_path}",
                    f"视觉描述: {vision_summary}" if vision_summary else "",
                ]
            ).strip()
        except Exception as e:
            item["display_content"] = f"[图片] md5={md5sum}（解析失败: {e}）"
            stats["image_failed"] += 1
            stats["failures"].append({"md5sum": md5sum, "error": str(e)})

        enriched.append(item)

    return enriched, stats


def format_image_enrichment_report(stats: dict[str, Any]) -> str:
    lines = [
        f"- 图片消息: {stats.get('image_total', 0)}",
        f"- 已下载: {stats.get('image_resolved', 0)}",
        f"- 视觉分析成功: {stats.get('image_vision_ok', 0)}",
        f"- 失败: {stats.get('image_failed', 0)}",
    ]
    failures = stats.get("failures") or []
    if failures:
        lines.append("")
        lines.append("失败明细:")
        for f in failures[:10]:
            lines.append(f"  - md5={f.get('md5sum')}: {f.get('error')}")
    return "\n".join(lines)
