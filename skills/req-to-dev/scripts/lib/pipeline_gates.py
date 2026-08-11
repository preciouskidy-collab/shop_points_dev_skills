"""Pipeline 流程门禁：防止跳过企微评审、设计前编码、错误验收路径。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from collab_wecom import (  # noqa: E402
    REVISE_COMMAND_PRD,
    REVISE_COMMAND_TECH,
    wait_cli,
    wecom_review_interaction_table,
)
from design_plan_builder import design_patch_dir


def _design_patches_applied(change_dir: Path, state: dict) -> list[str]:
    applied: list[str] = []
    collab = state.get("collaboration", {}) or {}
    tdr = collab.get("tech_design_review", {}) or {}
    for pid, info in (tdr.get("patches") or {}).items():
        if info.get("status") == "design_applied":
            applied.append(pid)

    collab_dir = change_dir / "collaboration"
    if collab_dir.is_dir():
        for pdir in sorted(collab_dir.glob("design-patch-*")):
            meta_path = pdir / "meta.json"
            if not meta_path.exists():
                continue
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if meta.get("status") == "design_applied":
                pid = meta.get("patch_id") or pdir.name
                if pid not in applied:
                    applied.append(pid)
    return applied


def has_design_review_approval(change_dir: Path, state: dict) -> bool:
    return bool(_design_patches_applied(change_dir, state))


def gate_plan_approve_direct(change_dir: Path, state: dict) -> tuple[bool, str]:
    """禁止未经 approve-design 直接 run_workflow approve plan-approve。"""
    if state.get("plan_design_unlocked"):
        return True, "plan_design_unlocked"
    applied = _design_patches_applied(change_dir, state)
    if applied:
        return True, f"design_applied: {', '.join(applied)}"
    return False, (
        "plan-approve 须先完成企微技术方案评审。\n"
        "正确路径：collab-tech-design-sync prepare → finalize-design → push-preview "
        "→ 同一回合阻塞 wait → approve-design（或 --chat-confirm）。\n"
        "禁止直接 run_workflow approve 跳过方案评审。"
    )


def gate_before_coding(change_dir: Path, state: dict) -> None:
    """进入 backend-coding 前校验 plan-approve 已合法解锁。"""
    stages = state.get("stages", [])
    plan_idx = next((i for i, s in enumerate(stages) if s.get("id") == "plan-approve"), None)
    if plan_idx is not None:
        plan_stage = stages[plan_idx]
        if plan_stage.get("status") != "completed":
            raise RuntimeError(
                f"plan-approve 未完成（status={plan_stage.get('status')}），禁止进入编码阶段。"
            )
    ok, reason = gate_plan_approve_direct(change_dir, state)
    if not ok:
        raise RuntimeError(reason)


def wecom_flow_lines(req_id: str, *, kind: str = "tech_design") -> list[str]:
    """Agent 在阻塞阶段须打印的企微流程说明。"""
    wait_cmd = wait_cli(req_id)
    if kind == "prd":
        return [
            ">>> 【红线】企微 PRD 评审（同一回合内完成，禁止结束回合）：",
            "    1. finalize-plan → push-preview",
            f"    2. 阻塞: {wait_cmd}",
            f"    3. meeting_revise（企微 `{REVISE_COMMAND_PRD}`）→ meeting-revise **--pull-intent-id <id>** → 再 push-preview → 再 wait",
            "    4. approve intent → approve --pull-intent-id",
            "    禁止：push-preview 后结束对话等用户在 Cursor 输入",
            "    禁止：collab_wait.py --action approve（会丢弃 meeting_revise，/整理评审 允许多次）",
            "",
            *wecom_review_interaction_table(),
        ]
    return [
        ">>> 【红线】企微技术方案评审（plan-approve = tech_design_review；push-preview 发群时即评审阶段）",
        "    1. collab-tech-design-sync prepare → 写 design_plan.json → finalize-design",
        "    2. push-preview --patch design-patch-NNN",
        f"    3. 阻塞: {wait_cmd}",
        "    4. plan_approve intent → approve-design --pull-intent-id <id>",
        f"    5. tech_revise（企微 `{REVISE_COMMAND_TECH}`，勿用 {REVISE_COMMAND_PRD}）",
        "       → tech-revise **--pull-intent-id <id>** → 修订 design_plan → finalize-design → push-preview → 再 wait",
        "",
        ">>> 【红线】plan-approve 通过前禁止：检出 feature 分支、修改 shop-points/store-integral 业务代码",
        "    仅允许写 changes/<req_id>/ 内 spec、impact、api-contract、tech-design",
        "",
        ">>> 降级：用户在本对话发确认语 → approve-design --chat-confirm \"<原话>\"",
        "",
        *wecom_review_interaction_table(),
    ]


def local_verification_lines() -> list[str]:
    return [
        ">>> 【默认验收】integration_mode=local（scope-eval 默认）",
        "    local-stack-up → local-e2e-test（**run_workflow continue** 自动连续执行）",
        "    → **Pipeline 自动终态**（local 模式 E2E 通过后结束，不自动 commit-push）",
        ">>> 需推送代码：显式执行 playbooks/commit-push.md（非 Pipeline 默认终态）",
        ">>> 大禹路径：将 impact.integration_mode 改为 dayu；部署/E2E 仍用 Cursor 内置浏览器（终态延至 release）",
        ">>> 连续推进: python3 skills/req-to-dev/scripts/run_workflow.py continue --name <req_id>",
    ]
