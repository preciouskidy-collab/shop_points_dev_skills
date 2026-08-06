"""技术方案评审：本地 design_plan.json 构建、预览与应用。"""

from __future__ import annotations

import json
import re
import secrets
from pathlib import Path
from typing import Any

from collab_common import append_log, iso_now, save_state

DESIGN_TARGETS = (
    "handoff/api-contract.yaml",
    "tech-design/tech-design.md",
    "tech-design/frontend-design.md",
)

_AGENT_PENDING_DIFF = (
    "待 Agent 对照 design_prompt.md 与方案快照撰写 design_plan.json（updates[] + str_replace），"
    "完成后执行 finalize-design 重算预览。"
)


def new_approval_nonce() -> str:
    return secrets.token_hex(3)


def design_chat_confirm_phrase(patch_id: str, nonce: str, approver_placeholder: str = "<姓名>") -> str:
    return f"确认方案 {patch_id} {nonce} approver {approver_placeholder}"


def parse_design_chat_confirm_phrase(text: str) -> dict[str, str] | None:
    m = re.search(
        r"确认方案\s+(design-patch-\d+)\s+([a-fA-F0-9]+)\s+approver\s+(\S+)",
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


def next_design_patch_id(change_dir: Path, state: dict) -> tuple[str, int]:
    collab = state.setdefault("collaboration", {})
    tdr = collab.setdefault("tech_design_review", {})
    seq = int(tdr.get("last_patch_seq", 0)) + 1
    patch_id = f"design-patch-{seq:03d}"
    return patch_id, seq


def design_patch_dir(change_dir: Path, patch_id: str) -> Path:
    path = change_dir / "collaboration" / patch_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def collect_design_updates(plan: dict) -> list[dict]:
    updates = plan.get("updates")
    if isinstance(updates, list) and updates:
        return [u for u in updates if isinstance(u, dict)]
    single = plan.get("update")
    if isinstance(single, dict) and single.get("target"):
        return [single]
    return []


def _apply_str_replace(text: str, pattern: str, content: str) -> str | None:
    if not pattern:
        return None
    if pattern in text:
        return text.replace(pattern, content, 1)
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if pattern == stripped or pattern in stripped or stripped in pattern:
            return text.replace(line, content, 1)
    return None


def preview_file_after_update(file_text: str, upd: dict) -> str | None:
    if upd.get("command") != "str_replace":
        return None
    pattern = (upd.get("pattern") or "").strip()
    if not pattern:
        return None
    result = _apply_str_replace(file_text, pattern, upd.get("content", ""))
    return result if result is not None and result != file_text else None


def snapshot_design_files(change_dir: Path, pdir: Path) -> dict[str, str]:
    snapshots: dict[str, str] = {}
    snap_root = pdir / "snapshots"
    snap_root.mkdir(parents=True, exist_ok=True)
    for rel in DESIGN_TARGETS:
        src = change_dir / rel
        if not src.exists():
            continue
        text = src.read_text(encoding="utf-8")
        snapshots[rel] = text
        (snap_root / rel.replace("/", "__")).write_text(text, encoding="utf-8")
    return snapshots


def preview_design_plan(change_dir: Path, plan: dict, snapshots: dict[str, str] | None = None) -> dict[str, str]:
    previews: dict[str, str] = {}
    base = snapshots or {}
    if not base:
        for rel in DESIGN_TARGETS:
            p = change_dir / rel
            if p.exists():
                base[rel] = p.read_text(encoding="utf-8")
    for upd in collect_design_updates(plan):
        target = upd.get("target")
        if not target or target not in base:
            continue
        after = preview_file_after_update(base[target], upd)
        if after is not None:
            base[target] = after
            previews[target] = after
    return previews


def apply_design_plan(change_dir: Path, plan: dict) -> list[str]:
    applied: list[str] = []
    for upd in collect_design_updates(plan):
        if upd.get("command") != "str_replace":
            raise ValueError(f"仅支持 str_replace，收到: {upd.get('command')}")
        target = upd.get("target")
        if not target:
            raise ValueError("update 缺少 target")
        path = change_dir / target
        if not path.exists():
            raise FileNotFoundError(f"目标文件不存在: {target}")
        text = path.read_text(encoding="utf-8")
        pattern = (upd.get("pattern") or "").strip()
        content = upd.get("content", "")
        new_text = _apply_str_replace(text, pattern, content)
        if new_text is None:
            raise ValueError(f"无法在 {target} 中定位 pattern: {pattern[:80]}")
        path.write_text(new_text, encoding="utf-8")
        applied.append(target)
    return applied


def validate_design_plan(plan: dict, *, require_updates: bool = True) -> None:
    if plan.get("plan_source") == "agent_pending":
        raise ValueError("plan 仍为 agent_pending，请先由 Agent 填写 design_plan.json")
    updates = collect_design_updates(plan)
    if require_updates and not updates:
        if not plan.get("frozen") and plan.get("plan_source") != "confirmed":
            raise ValueError("design_plan.json 缺少 updates；无文件变更时请设 plan_source=confirmed")
    for upd in updates:
        if upd.get("command") != "str_replace":
            raise ValueError("技术方案修订仅支持 str_replace")
        if not upd.get("target"):
            raise ValueError("每条 update 须含 target")
        if not (upd.get("pattern") or "").strip():
            raise ValueError("str_replace 须含 pattern")


def build_agent_pending_design_plan(*, patch_id: str, extra: dict | None = None) -> dict:
    plan: dict[str, Any] = {
        "version": 1,
        "source": "tech_design_review",
        "plan_source": "agent_pending",
        "design_diff_summary": _AGENT_PENDING_DIFF,
        "changes": [],
        "updates": [],
    }
    if extra:
        plan.update(extra)
    plan.setdefault("patch_id", patch_id)
    return plan


def build_human_summary_design(
    patch_id: str,
    req_id: str,
    plan: dict,
    *,
    approval_nonce: str,
    previews: dict[str, str] | None = None,
) -> str:
    lines = [
        f"# {patch_id} 技术方案预览 · `{req_id}`",
        "",
        f"验证码: `{approval_nonce}`",
        "",
    ]
    diff = (plan.get("design_diff_summary") or plan.get("consensus_summary") or "").strip()
    if diff:
        lines.extend(["## 方案修订摘要", "", diff, ""])

    if plan.get("plan_source") == "agent_pending" or not collect_design_updates(plan):
        lines.extend(
            [
                "## 状态",
                "",
                _AGENT_PENDING_DIFF,
                "",
            ]
        )
    else:
        for upd in collect_design_updates(plan):
            target = upd.get("target", "")
            pattern = (upd.get("pattern") or "").strip()
            content = upd.get("content", "")
            lines.extend(
                [
                    f"## 拟修订 · `{target}`",
                    "",
                    f"- **原文**：`{pattern[:200]}{'…' if len(pattern) > 200 else ''}`",
                    f"- **改为**：`{content or '(删除)'}`",
                    "",
                ]
            )
        if previews:
            lines.append("## 修改后预览（本地模拟）")
            lines.append("")
            for target, text in previews.items():
                excerpt = text[:2500] + ("…" if len(text) > 2500 else "")
                lines.extend([f"### {target}", "", "```", excerpt, "```", ""])

    lines.append("## 变更项")
    lines.append("")
    for i, item in enumerate(plan.get("changes", []), 1):
        lines.append(f"{i}. {item.get('summary', item)}")
    hint = design_chat_confirm_phrase(patch_id, approval_nonce)
    lines.extend(
        [
            "",
            "请在 **企微群**回复以下格式以确认技术方案：",
            f"  `{hint}`",
            "",
            "需修订请发送：`/整理方案`",
        ]
    )
    return "\n".join(lines) + "\n"


def finalize_design_patch(
    *,
    pdir: Path,
    plan: dict,
    req_id: str,
    patch_id: str,
    change_dir: Path,
    snapshots: dict[str, str],
) -> None:
    validate_design_plan(plan)
    plan_path = pdir / "design_plan.json"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    meta = json.loads((pdir / "meta.json").read_text(encoding="utf-8"))
    nonce = meta.get("approval_nonce", "")
    previews = preview_design_plan(change_dir, plan, snapshots)
    summary = build_human_summary_design(
        patch_id,
        req_id,
        plan,
        approval_nonce=nonce,
        previews=previews,
    )
    (pdir / "human_summary.md").write_text(summary, encoding="utf-8")
    dry = {
        "preview_targets": list(previews.keys()),
        "updates_count": len(collect_design_updates(plan)),
        "finalized_at": iso_now(),
    }
    (pdir / "dry_run.log").write_text(json.dumps(dry, ensure_ascii=False, indent=2), encoding="utf-8")


def finalize_design_round(
    change_dir: Path,
    state: dict,
    pdir: Path,
    *,
    patch_id: str,
    seq: int,
    req_id: str,
    plan: dict,
    design_prompt: str,
    meta_extra: dict,
    log_message: str,
) -> None:
    snapshots = snapshot_design_files(change_dir, pdir)
    plan_path = pdir / "design_plan.json"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    nonce = meta_extra.get("approval_nonce") or new_approval_nonce()
    meta_extra["approval_nonce"] = nonce

    (pdir / "design_prompt.md").write_text(design_prompt, encoding="utf-8")

    if plan.get("plan_source") != "agent_pending" and collect_design_updates(plan):
        try:
            finalize_design_patch(
                pdir=pdir,
                plan=plan,
                req_id=req_id,
                patch_id=patch_id,
                change_dir=change_dir,
                snapshots=snapshots,
            )
        except ValueError as e:
            print(f"WARN: finalize-design 预览失败: {e}")
    else:
        summary = build_human_summary_design(patch_id, req_id, plan, approval_nonce=nonce)
        (pdir / "human_summary.md").write_text(summary, encoding="utf-8")
        print("ℹ plan 为 agent_pending，跳过 dry-run 预览")

    meta = {
        "patch_id": patch_id,
        "seq": seq,
        "req_id": req_id,
        "preview_type": "tech_design",
        "status": "draft",
        "approver": None,
        "approved_at": None,
        "approval_note": None,
        **meta_extra,
    }
    (pdir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    collab = state.setdefault("collaboration", {})
    tdr = collab.setdefault("tech_design_review", {})
    tdr["last_patch_seq"] = seq
    tdr.setdefault("patches", {})[patch_id] = {"status": "draft", "prepared_at": iso_now()}
    collab["phase"] = "tech_design_review"
    save_state(change_dir, state)
    append_log(change_dir, log_message)
