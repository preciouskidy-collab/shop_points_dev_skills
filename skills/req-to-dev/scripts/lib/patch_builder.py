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


def parse_chat_confirm_phrase(text: str) -> dict[str, str] | None:
    """从「确认 patch-002 abc123 approver 齐迪」解析 patch / nonce / approver。"""
    m = re.search(
        r"确认\s+(patch-\d+)\s+([a-fA-F0-9]+)\s+approver\s+(\S+)",
        text.strip(),
        re.I,
    )
    if not m:
        return None
    return {
        "patch": m.group(1),
        "nonce": m.group(2),
        "approver": m.group(3),
    }


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


def preview_prd_after_plan(prd_md: str, plan: dict) -> str | None:
    """本地模拟 str_replace，供 human_summary / dry-run 展示修改后 PRD。"""
    upd = plan.get("update") or {}
    if upd.get("command") != "str_replace":
        return None
    pattern = (upd.get("pattern") or "").strip()
    if not pattern:
        return None
    content = upd.get("content", "")
    if pattern in prd_md:
        return prd_md.replace(pattern, content, 1)
    for line in prd_md.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if pattern == stripped or pattern in stripped or stripped in pattern:
            return prd_md.replace(line, content, 1)
    return None


def build_human_summary(
    patch_id: str,
    plan: dict,
    *,
    source_label: str,
    approve_hint: str,
    header: str,
    prd_md: str = "",
) -> str:
    lines = [header, "", f"来源：**{source_label}**", ""]
    consensus = (plan.get("consensus_summary") or "").strip()
    if consensus:
        lines.extend(["## 联调共识摘要", "", consensus, ""])
    prd_diff = (plan.get("prd_diff_summary") or "").strip()
    if prd_diff:
        lines.extend(["## PRD 差异 / 拟修订", "", prd_diff, ""])

    update_cmd = (plan.get("update") or {}).get("command", "append")
    if prd_md and update_cmd == "str_replace":
        after = preview_prd_after_plan(prd_md, plan)
        if after is not None and after != prd_md:
            lines.extend(["## 修改后 PRD 预览（dry-run）", "", after, ""])
        upd = plan.get("update") or {}
        pattern = (upd.get("pattern") or "").strip()
        content = upd.get("content", "")
        if pattern:
            lines.extend(
                [
                    "## 拟执行替换",
                    "",
                    f"- **原文**：`{pattern}`",
                    f"- **改为**：`{content or '(删除该行)'}`",
                    "",
                ]
            )

    lines.append("## 变更项")
    lines.append("")
    for i, item in enumerate(plan.get("changes", []), 1):
        lines.append(f"{i}. {item.get('summary', item)}")
    lines.extend(
        [
            "",
            "请在 **Agent 对话**中回复以下格式以确认写回 PRD：",
            f"  `{approve_hint}`",
            "",
            "Agent 收到你的原话后，将代你执行 approve（须一字不差包含 patch 编号与验证码），"
            "并**自动 prd resync** 回灌 spec/tasks。",
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
    prd_md: str = "",
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
        prd_md=prd_md,
    )


def build_human_summary_pipeline(
    patch_id: str,
    req_id: str,
    plan: dict,
    *,
    source_label: str,
    approval_nonce: str,
    prd_md: str = "",
) -> str:
    header = f"# {patch_id} 预览 · `{req_id}`\n\n验证码: `{approval_nonce}`"
    hint = chat_confirm_phrase(patch_id, approval_nonce)
    return build_human_summary(
        patch_id,
        plan,
        source_label=source_label,
        approve_hint=hint,
        header=header,
        prd_md=prd_md,
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


_MEETING_LLM_SYSTEM = """你是 PRD 维护助手。根据飞书会议纪要与我提供的 PRD 正文：
1. 理解会议达成的需求变更
2. 对照 PRD，定位需要修改的原文（pattern 必须是 PRD 中存在的完整一行原文）
3. 输出 str_replace 修订，使 approve 后直接修改 PRD 正文（禁止仅 append 变更记录节）

输出严格 JSON：
{
  "consensus_summary": "- 要点",
  "prd_diff_summary": "- PRD 差异说明",
  "changes": [
    {
      "summary": "变更说明",
      "update": {
        "command": "str_replace",
        "pattern": "PRD 中要替换的整行原文",
        "content": "替换后的整行"
      }
    }
  ]
}

若需删除某段描述，content 为删除该段后的整行；若需删整行则 content 为空字符串。
无法 str_replace 时 changes 可为空，但须填写 prd_diff_summary 说明原因。"""


_REMOVAL = re.compile(
    r"(?:不需要|去掉|删除|移除)[了]?(?P<body>.+?)[。；]?$|"
    r"需求中(?:不)?需要(?P<body2>.+?)[。；]?$"
)


def _extract_removal_keywords(body: str) -> list[str]:
    keywords: list[str] = []
    if "红字" in body:
        keywords.extend(["红字提示", "红字"])
    if "服务基金" in body:
        keywords.append("服务基金")
    if "权益积分" in body:
        keywords.append("权益积分")
    if "前端" in body:
        keywords.extend(["前端绿字提醒", "前端绿字", "绿字提醒", "前端"])
    if "提示" in body or "提醒" in body:
        keywords.extend(["提醒", "提示"])
    if not keywords:
        frag = re.findall(r"[\u4e00-\u9fff]{2,}", body)
        keywords.extend(frag[:3])
    return keywords


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
    if "前端" in removal_body:
        if "前端" in stripped:
            score += 40
        if "绿字" in stripped:
            score += 20
        if ("提醒" in stripped or "提示" in stripped) and (
            "提醒" in removal_body or "提示" in removal_body
        ):
            score += 35
    if "提示" in removal_body and "提示" in stripped:
        score += 25
    if "提醒" in removal_body and "提醒" in stripped:
        score += 25
    # 纯文本行优先于含 URL 的行
    if "http://" in stripped or "https://" in stripped:
        score -= 30
    return score


def _apply_removal_to_line(line: str, removal_body: str, item: str) -> str:
    """按「不需要/删除」语义生成替换后整行（非整行删除时保留主句）。"""
    stripped = line.strip()
    wants_no_frontend_hint = "前端" in removal_body or (
        "前端" in item and ("提示" in removal_body or "提醒" in removal_body)
    )
    if wants_no_frontend_hint and "前端" in stripped:
        new_line = re.sub(
            r"[。；]?\s*同时\s*前端[^。；]*(?:提醒|提示)[^。；]*",
            "",
            stripped,
        )
        new_line = re.sub(
            r"[。；]?\s*前端(?:绿字)?(?:提醒|提示)[：:][^。；]*",
            "",
            new_line,
        )
        new_line = new_line.strip().rstrip("；")
        if new_line and not new_line.endswith("。"):
            new_line += "。"
        if new_line and new_line != stripped:
            return new_line

    if "红字" in removal_body and "红字" in stripped:
        parts = re.split(r"(?<=[。；])", stripped)
        kept = "".join(p for p in parts if "红字" not in p).strip()
        if kept and kept != stripped:
            return kept

    return ""


def try_str_replace_from_meeting(items: list[str], prd_md: str) -> dict | None:
    """会议纪要含「不需要/删除…」时，尝试匹配 PRD 行并生成 str_replace plan。"""
    prd_lines = [ln for ln in prd_md.splitlines() if ln.strip()]
    best: tuple[int, str, str] | None = None

    for item in items:
        m = _REMOVAL.search(item)
        if not m:
            continue
        body = (m.group("body") or m.group("body2") or "").strip()
        keywords = _extract_removal_keywords(body)

        for line in prd_lines:
            score = _score_prd_line(line, keywords, body)
            if score <= 0:
                continue
            if best is None or score > best[0]:
                best = (score, line.strip(), item)

    if not best:
        return None
    _, pattern, reason = best
    m_reason = _REMOVAL.search(reason)
    removal_body = (m_reason.group("body") or m_reason.group("body2") or "").strip() if m_reason else ""
    content = _apply_removal_to_line(pattern, removal_body, reason)
    return {
        "command": "str_replace",
        "doc_format": "markdown",
        "pattern": pattern,
        "content": content,
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
    use_llm: bool = True,
) -> dict:
    items = extract_meeting_items(meeting_md)

    if use_llm:
        from llm_client import chat_completion_json, is_llm_available, load_llm_config  # noqa: WPS433

        cfg = load_llm_config()
        if is_llm_available(cfg):
            prd_excerpt = prd_md if len(prd_md) <= 14000 else prd_md[:14000] + "\n\n…（PRD 已截断）"
            user = "\n".join(
                [
                    f"## patch_id\n{patch_id}",
                    "",
                    "## 会议纪要",
                    meeting_md,
                    "",
                    "## 当前 PRD Markdown",
                    prd_excerpt,
                ]
            )
            try:
                payload = chat_completion_json(
                    system=_MEETING_LLM_SYSTEM,
                    user=user,
                    cfg=cfg,
                )
                plan = _plan_from_llm_payload(
                    payload, prd_md=prd_md, prd_url=prd_url, patch_id=patch_id
                )
                plan["source"] = "feishu_prd_sync"
                plan["meeting_url"] = meeting_url
                if plan.get("update", {}).get("command") == "str_replace":
                    plan["plan_source"] = "llm"
                    return plan
                print("WARN: LLM 未生成 str_replace，回退启发式")
            except Exception as e:
                print(f"WARN: LLM meeting 规划失败，回退启发式: {e}")

    str_replace = try_str_replace_from_meeting(items, prd_md)

    extra = {"meeting_url": meeting_url}
    if str_replace:
        matched = str_replace["matched_line"]
        content = str_replace["content"]
        prd_diff = (
            f"- 定位 PRD 行：`{matched}`\n"
            f"- 拟改为：`{content or '(删除整行)'}`"
        )
        return {
            "version": 1,
            "source": "feishu_prd_sync",
            "plan_source": "heuristic",
            "prd_url": prd_url,
            "meeting_url": meeting_url,
            "prd_diff_summary": prd_diff,
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
    plan["plan_source"] = "heuristic_fallback_append"
    plan["prd_diff_summary"] = (
        "未能自动匹配 PRD 行进行 str_replace；已降级为文末追加变更记录。"
        "请修订 plan.json 为 str_replace 后重新 digest，或人工改正文。"
    )
    plan["update"]["content"] = plan["update"]["content"].replace(
        f"## 会议纪要变更 · {patch_id}\n",
        f"## 会议纪要变更 · {patch_id}{content_extra}",
        1,
    )
    return plan


_NOISE = re.compile(
    r"^(ok|okay|好的|好哒|收到|嗯|行|可以|没问题|👌|👍|🆗)$",
    re.I,
)
_COLOR_TO = re.compile(
    r"(?:把|将)?(?:前端|页面|UI|文案)?(?:的)?(?P<src>红|黄|绿|蓝)(?:字|色)?"
    r"(?:提示|文案)?(?:改成|改为|换成|改)(?:为|成)?(?:前端|页面|UI|文案)?(?:的)?"
    r"(?P<dst>红|黄|绿|蓝)(?:字|色)?",
    re.I,
)


def _filter_chat_messages(messages: list[dict]) -> list[str]:
    texts: list[str] = []
    for m in messages:
        content = (m.get("content") or m.get("message_content") or "").strip()
        if not content or content.startswith("/"):
            continue
        if _NOISE.match(content):
            continue
        texts.append(content)
    return texts


def _heuristic_consensus_summary(texts: list[str]) -> str:
    if not texts:
        return "（时间窗内无有效联调共识，请补充群聊或扩大 --window）"

    color_ops: list[tuple[str, str]] = []
    other: list[str] = []
    for t in texts:
        m = _COLOR_TO.search(t)
        if m:
            color_ops.append((m.group("src"), m.group("dst")))
        else:
            other.append(t)

    bullets: list[str] = []
    if color_ops:
        src0, dst_final = color_ops[0]
        for _, dst in color_ops[1:]:
            dst_final = dst
        bullets.append(
            f"前端提示/文案颜色：由「{src0}色」调整为「{dst_final}色」（联调群多轮确认后的最终态）"
        )
    for t in other:
        if t not in bullets:
            bullets.append(t)
    return "\n".join(f"- {b}" for b in bullets)


def _apply_color_replace(prd_md: str, src_color: str, dst_color: str) -> dict | None:
    prd_lines = [ln for ln in prd_md.splitlines() if ln.strip()]
    src_token = f"{src_color}字"
    dst_token = f"{dst_color}字"
    best_line: str | None = None
    best_score = -1
    for line in prd_lines:
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith("!["):
            continue
        score = 0
        if src_token in stripped:
            score += 50
        elif src_color in stripped and ("提示" in stripped or "文案" in stripped or "色" in stripped):
            score += 30
        elif src_color in stripped:
            score += 10
        if score > best_score:
            best_score = score
            best_line = stripped
    if not best_line or best_score <= 0:
        return None
    new_line = best_line.replace(src_token, dst_token)
    if src_token not in best_line and src_color in best_line:
        new_line = best_line.replace(f"{src_color}色", f"{dst_color}色").replace(
            src_color, dst_color
        )
    if new_line == best_line:
        return None
    return {
        "command": "str_replace",
        "doc_format": "markdown",
        "pattern": best_line,
        "content": new_line,
        "matched_line": best_line,
        "reason": f"联调共识：{src_color}→{dst_color}",
    }


def _plan_from_str_replace(
    *,
    str_replace: dict,
    prd_url: str,
    patch_id: str,
    consensus_summary: str,
    prd_diff_summary: str,
    plan_source: str,
) -> dict:
    matched = str_replace["matched_line"]
    content = str_replace["content"]
    return {
        "version": 1,
        "source": "collab_digest",
        "plan_source": plan_source,
        "prd_url": prd_url,
        "consensus_summary": consensus_summary,
        "prd_diff_summary": prd_diff_summary,
        "changes": [
            {
                "type": "consensus",
                "summary": "联调共识摘要（已凝练，非原始群消息）",
            },
            {
                "type": "str_replace",
                "summary": f"PRD 修订: {str_replace['reason']}",
            },
            {
                "type": "str_replace_detail",
                "summary": f"`{matched}` → `{content}`",
            },
        ],
        "update": {
            "command": "str_replace",
            "doc_format": "markdown",
            "pattern": str_replace["pattern"],
            "content": content,
        },
    }


def _plan_from_consensus_append(
    *,
    prd_url: str,
    patch_id: str,
    consensus_summary: str,
    prd_diff_summary: str,
    plan_source: str,
) -> dict:
    body = [
        f"## 联调共识 · {patch_id}",
        "",
        "### 摘要",
        consensus_summary,
        "",
        "### PRD 差异说明",
        prd_diff_summary or "（未能自动定位 PRD 可替换行，请 PM 确认后人工修订 PRD 正文）",
        "",
    ]
    return {
        "version": 1,
        "source": "collab_digest",
        "plan_source": plan_source,
        "prd_url": prd_url,
        "consensus_summary": consensus_summary,
        "prd_diff_summary": prd_diff_summary,
        "changes": [
            {"type": "consensus", "summary": line.strip("- ")[:200]}
            for line in consensus_summary.splitlines()
            if line.strip()
        ],
        "update": {
            "command": "append",
            "doc_format": "markdown",
            "content": "\n".join(body),
        },
    }


def _resolve_str_replace_pattern(pattern: str, prd_md: str) -> str | None:
    if pattern in prd_md:
        return pattern
    for line in prd_md.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if pattern in stripped or stripped in pattern:
            return stripped
    return None


def _plan_from_llm_payload(
    payload: dict,
    *,
    prd_md: str,
    prd_url: str,
    patch_id: str,
) -> dict:
    consensus = (payload.get("consensus_summary") or "").strip()
    prd_diff = (payload.get("prd_diff_summary") or payload.get("prd_diff") or "").strip()
    changes = payload.get("changes") or []

    for item in changes:
        upd = item.get("update") or {}
        cmd = upd.get("command", "str_replace")
        if cmd != "str_replace":
            continue
        pattern = (upd.get("pattern") or "").strip()
        content = upd.get("content", "")
        if not pattern:
            continue
        resolved = _resolve_str_replace_pattern(pattern, prd_md)
        if not resolved:
            continue
        return _plan_from_str_replace(
            str_replace={
                "command": "str_replace",
                "doc_format": "markdown",
                "pattern": resolved,
                "content": content,
                "matched_line": resolved,
                "reason": item.get("summary") or "按联调共识修订 PRD",
            },
            prd_url=prd_url,
            patch_id=patch_id,
            consensus_summary=consensus,
            prd_diff_summary=prd_diff,
            plan_source="llm",
        )

    if not consensus:
        raise RuntimeError("LLM 未返回 consensus_summary")
    return _plan_from_consensus_append(
        prd_url=prd_url,
        patch_id=patch_id,
        consensus_summary=consensus,
        prd_diff_summary=prd_diff or "LLM 未能生成可自动 str_replace 的 PRD 定位，已追加共识摘要供人工修订。",
        plan_source="llm",
    )


def build_collab_plan_heuristic(
    messages: list[dict],
    prd_md: str,
    *,
    prd_url: str,
    patch_id: str,
) -> dict:
    texts = _filter_chat_messages(messages)
    consensus = _heuristic_consensus_summary(texts)

    str_replace = None
    color_ops: list[tuple[str, str]] = []
    for t in texts:
        m = _COLOR_TO.search(t)
        if m:
            color_ops.append((m.group("src"), m.group("dst")))
    if color_ops:
        src0, dst_final = color_ops[0]
        for _, dst in color_ops[1:]:
            dst_final = dst
        str_replace = _apply_color_replace(prd_md, src0, dst_final)

    if not str_replace:
        items = [re.sub(r"^[-*•]\s+", "", ln).strip() for ln in consensus.splitlines() if ln.strip()]
        str_replace = try_str_replace_from_meeting(items, prd_md)

    prd_diff = ""
    if str_replace:
        prd_diff = (
            f"- 定位 PRD 行：`{str_replace['matched_line']}`\n"
            f"- 拟改为：`{str_replace['content']}`"
        )
        return _plan_from_str_replace(
            str_replace=str_replace,
            prd_url=prd_url,
            patch_id=patch_id,
            consensus_summary=consensus,
            prd_diff_summary=prd_diff,
            plan_source="heuristic",
        )

    return _plan_from_consensus_append(
        prd_url=prd_url,
        patch_id=patch_id,
        consensus_summary=consensus,
        prd_diff_summary="未能自动匹配 PRD 行进行 str_replace；已写入联调共识摘要，请 PM 确认定位。",
        plan_source="heuristic",
    )


_COLLAB_LLM_SYSTEM = """你是 PRD 维护助手。根据企微联调群聊天记录与飞书 PRD 正文：
1. 忽略 OK/好的/收到等确认语与重复扯皮，凝练「联调共识」摘要（markdown 列表）
2. 对照 PRD，找出与共识不一致或 PRD 未写清之处
3. 优先输出可在 PRD 中精确 str_replace 的修订（pattern 必须是 PRD 中存在的完整一行原文）

输出严格 JSON：
{
  "consensus_summary": "- 要点1\\n- 要点2",
  "prd_diff_summary": "- PRD 差异说明（markdown 列表）",
  "changes": [
    {
      "summary": "变更说明",
      "update": {
        "command": "str_replace",
        "pattern": "PRD 中要替换的整行原文",
        "content": "替换后的整行"
      }
    }
  ]
}

若无法 str_replace，changes 可为空，但 consensus_summary 与 prd_diff_summary 必须填写。"""


def build_collab_plan(
    messages: list[dict],
    prd_md: str,
    *,
    prd_url: str,
    patch_id: str,
    use_llm: bool = True,
) -> tuple[dict, str]:
    """返回 (plan, plan_source_label)。"""
    from llm_client import chat_completion_json, is_llm_available, load_llm_config  # noqa: WPS433

    raw_md = _format_collab_messages_md(messages)
    cfg = load_llm_config()

    if use_llm and is_llm_available(cfg):
        prd_excerpt = prd_md if len(prd_md) <= 14000 else prd_md[:14000] + "\n\n…（PRD 已截断）"
        user = "\n".join(
            [
                f"## patch_id\n{patch_id}",
                "",
                "## 联调群消息",
                raw_md or "（无消息）",
                "",
                "## 当前 PRD Markdown",
                prd_excerpt,
            ]
        )
        try:
            payload = chat_completion_json(system=_COLLAB_LLM_SYSTEM, user=user, cfg=cfg)
            plan = _plan_from_llm_payload(payload, prd_md=prd_md, prd_url=prd_url, patch_id=patch_id)
            return plan, "llm"
        except Exception as e:
            print(f"WARN: LLM 规划失败，回退启发式: {e}")

    plan = build_collab_plan_heuristic(messages, prd_md, prd_url=prd_url, patch_id=patch_id)
    return plan, plan.get("plan_source", "heuristic")


def _format_collab_messages_md(messages: list[dict]) -> str:
    lines = []
    for m in messages:
        sender = m.get("senderId") or m.get("sender_id") or "unknown"
        content = (m.get("content") or m.get("message_content") or "").strip()
        if not content:
            continue
        ts = m.get("createdAt") or m.get("created_at") or ""
        prefix = f"[{ts}] " if ts else ""
        lines.append(f"- {prefix}[{sender}] {content}")
    return "\n".join(lines)


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

    prd_md = ""
    prd_snap = change_dir / "request" / "prd.md"
    if prd_snap.exists():
        prd_md = prd_snap.read_text(encoding="utf-8")

    summary_path = pdir / "human_summary.md"
    summary_path.write_text(
        build_human_summary_pipeline(
            patch_id, req_id, plan, source_label=source_label, approval_nonce=nonce, prd_md=prd_md
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
    prd_md = ""
    prd_snap = pdir / "prd_snapshot.md"
    if prd_snap.exists():
        prd_md = prd_snap.read_text(encoding="utf-8")
    summary_path.write_text(
        build_human_summary_pre_pipeline(
            patch_id,
            session_id,
            prd_url,
            plan,
            source_label=source_label,
            approval_nonce=nonce,
            prd_md=prd_md,
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
