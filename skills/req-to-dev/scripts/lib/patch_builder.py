"""联调 / 会议纪要 PRD patch 公共构建与落盘。"""

from __future__ import annotations

import json
import re
import secrets
from pathlib import Path
from typing import Any

from collab_common import append_log, iso_now, save_state
from lark_cli import update_dry_run


def new_approval_nonce() -> str:
    return secrets.token_hex(3)


def chat_confirm_phrase(patch_id: str, nonce: str, approver_placeholder: str = "<姓名>") -> str:
    return f"确认 {patch_id} {nonce} approver {approver_placeholder}"


def build_append_plan(
    *,
    source: str,
    items: list[str],
    prd_url: str,
    patch_id: str,
    section_title: str,
    extra: dict[str, Any] | None = None,
) -> dict:
    changes = [{"type": f"{source}_item", "summary": item} for item in items]
    content_lines = [f"## {section_title} · {patch_id}", ""]
    if items:
        content_lines.extend(f"- {item}" for item in items)
    else:
        content_lines.append("- （待补充变更项）")
    content_lines.append("")

    plan: dict[str, Any] = {
        "version": 1,
        "source": source,
        "prd_url": prd_url,
        "changes": changes,
        "update": {
            "command": "append",
            "doc_format": "markdown",
            "content": "\n".join(content_lines),
        },
    }
    if extra:
        plan.update(extra)
    return plan


def build_human_summary(
    patch_id: str,
    plan: dict,
    *,
    source_label: str,
    approve_hint: str,
    header: str,
) -> str:
    lines = [header, "", f"来源：**{source_label}**", ""]
    for i, item in enumerate(plan.get("changes", []), 1):
        lines.append(f"{i}. {item.get('summary', item)}")
    lines.extend(
        [
            "",
            "请在 **Agent 对话**中回复以下格式以确认写回 PRD：",
            f"  `{approve_hint}`",
            "",
            "Agent 收到你的原话后，将代你执行 approve（须一字不差包含 patch 编号与验证码）。",
        ]
    )
    return "\n".join(lines) + "\n"


def build_human_summary_pre_pipeline(
    patch_id: str,
    session_id: str,
    prd_url: str,
    plan: dict,
    *,
    source_label: str,
    approval_nonce: str,
) -> str:
    header = "\n".join(
        [
            f"# {patch_id} 预览",
            "",
            "**阶段：PRD 定稿（Pipeline init 之前，尚无 req_id）**",
            f"session: `{session_id}`",
            f"验证码: `{approval_nonce}`",
        ]
    )
    hint = chat_confirm_phrase(patch_id, approval_nonce)
    return build_human_summary(
        patch_id,
        plan,
        source_label=source_label,
        approve_hint=hint,
        header=header,
    )


def build_human_summary_pipeline(
    patch_id: str,
    req_id: str,
    plan: dict,
    *,
    source_label: str,
    approval_nonce: str,
) -> str:
    header = f"# {patch_id} 预览 · `{req_id}`\n\n验证码: `{approval_nonce}`"
    hint = chat_confirm_phrase(patch_id, approval_nonce)
    return build_human_summary(
        patch_id,
        plan,
        source_label=source_label,
        approve_hint=hint,
        header=header,
    )


def extract_meeting_items(meeting_md: str) -> list[str]:
    items: list[str] = []
    for line in meeting_md.splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        text = re.sub(r"^[-*•]\s+", "", text)
        text = re.sub(r"^\d+[.)]\s+", "", text)
        text = re.sub(r"^会议纪要[:：]\s*", "", text)
        if len(text) >= 3:
            items.append(text)

    seen: set[str] = set()
    unique: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


_REMOVAL = re.compile(r"(?:不需要|去掉|删除|移除)[了]?(?P<body>.+?)[。；]?$")


def _score_prd_line(line: str, keywords: list[str], removal_body: str) -> int:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return -1000
    if stripped.startswith("!["):
        return -1000
    if stripped.startswith("```"):
        return -500

    score = 0
    for kw in keywords:
        if kw in stripped:
            score += 15
    if "红字" in removal_body:
        if "红字提示" in stripped:
            score += 80
        elif "红字" in stripped:
            score += 40
    if "提示" in removal_body and "提示" in stripped:
        score += 25
    # 纯文本行优先于含 URL 的行
    if "http://" in stripped or "https://" in stripped:
        score -= 30
    return score


def try_str_replace_from_meeting(items: list[str], prd_md: str) -> dict | None:
    """会议纪要含「不需要/删除…」时，尝试匹配 PRD 行并生成 str_replace plan。"""
    prd_lines = [ln for ln in prd_md.splitlines() if ln.strip()]
    best: tuple[int, str, str] | None = None

    for item in items:
        m = _REMOVAL.search(item)
        if not m:
            continue
        body = m.group("body")
        keywords: list[str] = []
        if "红字" in body:
            keywords.extend(["红字提示", "红字"])
        if "服务基金" in body:
            keywords.append("服务基金")
        if "权益积分" in body:
            keywords.append("权益积分")
        if not keywords:
            frag = re.findall(r"[\u4e00-\u9fff]{2,}", body)
            keywords.extend(frag[:3])

        for line in prd_lines:
            score = _score_prd_line(line, keywords, body)
            if score <= 0:
                continue
            if best is None or score > best[0]:
                best = (score, line.strip(), item)

    if not best:
        return None
    _, pattern, reason = best
    return {
        "command": "str_replace",
        "doc_format": "markdown",
        "pattern": pattern,
        "content": "",
        "matched_line": pattern,
        "reason": reason,
    }


def build_meeting_plan(
    meeting_md: str,
    prd_md: str,
    *,
    prd_url: str,
    patch_id: str,
    meeting_url: str,
) -> dict:
    items = extract_meeting_items(meeting_md)
    str_replace = try_str_replace_from_meeting(items, prd_md)

    extra = {"meeting_url": meeting_url}
    if str_replace:
        matched = str_replace["matched_line"]
        # 若仅删除句中「红字提示」片段，保留前半句
        content = str_replace["content"]
        if "红字" in str_replace["reason"] and "红字" in matched:
            parts = re.split(r"(?<=[。；])", matched)
            kept = "".join(p for p in parts if "红字" not in p).strip()
            if kept and kept != matched:
                content = kept

        return {
            "version": 1,
            "source": "feishu_prd_sync",
            "prd_url": prd_url,
            "meeting_url": meeting_url,
            "changes": [
                {
                    "type": "str_replace",
                    "summary": f"按纪要修改: {str_replace['reason']}",
                },
                {
                    "type": "str_replace_detail",
                    "summary": f"PRD `{matched}` → `{content or '(删除整行)'}`",
                },
            ],
            "update": {
                "command": "str_replace",
                "doc_format": "markdown",
                "pattern": str_replace["pattern"],
                "content": content,
            },
        }

    content_extra = f"\n> 来源：[会议纪要]({meeting_url})\n"
    plan = build_append_plan(
        source="feishu_prd_sync",
        items=items,
        prd_url=prd_url,
        patch_id=patch_id,
        section_title="会议纪要变更",
        extra=extra,
    )
    plan["update"]["content"] = plan["update"]["content"].replace(
        f"## 会议纪要变更 · {patch_id}\n",
        f"## 会议纪要变更 · {patch_id}{content_extra}",
        1,
    )
    return plan


def finalize_patch(
    change_dir: Path,
    state: dict,
    pdir: Path,
    *,
    patch_id: str,
    seq: int,
    req_id: str,
    prd_url: str,
    plan: dict,
    source_label: str,
    meta_extra: dict,
    log_message: str,
    digest_prompt: str,
    notify: str,
) -> None:
    plan_path = pdir / "plan.json"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    nonce = meta_extra.get("approval_nonce") or new_approval_nonce()
    meta_extra["approval_nonce"] = nonce

    summary_path = pdir / "human_summary.md"
    summary_path.write_text(
        build_human_summary_pipeline(patch_id, req_id, plan, source_label=source_label, approval_nonce=nonce),
        encoding="utf-8",
    )

    (pdir / "digest_prompt.md").write_text(digest_prompt, encoding="utf-8")

    dry_log = pdir / "dry_run.log"
    try:
        update_dry_run(prd_url, plan_path, log_path=dry_log)
    except RuntimeError as e:
        print(f"WARN: dry-run 失败（可完善 plan.json 后重试 approve）: {e}")

    meta = {
        "patch_id": patch_id,
        "seq": seq,
        "req_id": req_id,
        "digest_at": iso_now(),
        "status": "draft",
        "approver": None,
        "approved_at": None,
        "approval_note": None,
        "ready_for_resync": False,
        **meta_extra,
    }
    (pdir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    collab = state.setdefault("collaboration", {})
    collab["last_patch_seq"] = seq
    collab.setdefault("patches", {})[patch_id] = {"status": "draft", "digest_at": meta["digest_at"]}
    save_state(change_dir, state)
    append_log(change_dir, log_message)

    print(f"✓ patch 已生成: {pdir}")
    print(f"✓ {notify}")
    print("\n--- human_summary 预览 ---")
    print(summary_path.read_text(encoding="utf-8"))


def finalize_pre_pipeline_patch(
    prd_url: str,
    session: dict,
    pdir: Path,
    *,
    patch_id: str,
    seq: int,
    plan: dict,
    source_label: str,
    meta_extra: dict,
    digest_prompt: str,
    notify: str,
) -> None:
    """Pre-Pipeline：会议纪要 → PRD，落盘到 prd-sync/（无 req_id）。"""
    from prd_sync_session import append_session_log, save_session  # noqa: WPS433

    session_id = session["session_id"]
    plan_path = pdir / "plan.json"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    summary_path = pdir / "human_summary.md"
    nonce = meta_extra.get("approval_nonce") or new_approval_nonce()
    meta_extra["approval_nonce"] = nonce
    summary_path.write_text(
        build_human_summary_pre_pipeline(
            patch_id, session_id, prd_url, plan, source_label=source_label, approval_nonce=nonce
        ),
        encoding="utf-8",
    )
    (pdir / "digest_prompt.md").write_text(digest_prompt, encoding="utf-8")

    dry_log = pdir / "dry_run.log"
    try:
        update_dry_run(prd_url, plan_path, log_path=dry_log)
    except RuntimeError as e:
        print(f"WARN: dry-run 失败（可完善 plan.json 后重试 approve）: {e}")

    meta = {
        "patch_id": patch_id,
        "seq": seq,
        "phase": "pre-pipeline",
        "session_id": session_id,
        "prd_url": prd_url,
        "digest_at": iso_now(),
        "status": "draft",
        "approver": None,
        "approved_at": None,
        "approval_note": None,
        **meta_extra,
    }
    (pdir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    session["last_patch_seq"] = seq
    session.setdefault("patches", {})[patch_id] = {
        "status": "draft",
        "digest_at": meta["digest_at"],
    }
    save_session(prd_url, session)
    append_session_log(prd_url, f"MEETING digest {patch_id}")

    print(f"✓ session: {session_id}（pre-pipeline，无 req_id）")
    print(f"✓ patch 已生成: {pdir}")
    print(f"✓ {notify}")
    print("\n--- human_summary 预览 ---")
    print(summary_path.read_text(encoding="utf-8"))
