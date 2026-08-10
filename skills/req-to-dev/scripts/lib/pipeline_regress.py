"""PRD resync 后按 Tier 强制回退 Pipeline stage。"""

from __future__ import annotations

from typing import Any

from collab_common import iso_now

# Tier → 回退目标 stage（须与 skills.json pipeline.stages 一致）
TIER_REGRESSION_TARGET: dict[int, str] = {
    1: "plan-approve",
    2: "plan-approve",
    3: "scope-eval",
}

# plan-approve 重审模式：light = 仅审联调改造点；full = 审协议 + 全栈详设
REAPPROVE_MODE: dict[int, str] = {
    1: "light",
    2: "full",
    3: "full",
}

PLAN_APPROVE_STAGE = "plan-approve"


def _stage_index(stages: list[dict], stage_id: str) -> int:
    for i, stage in enumerate(stages):
        if stage["id"] == stage_id:
            return i
    raise ValueError(f"Pipeline 中无 stage: {stage_id}")


def regression_target_for_tier(tier: int) -> str | None:
    return TIER_REGRESSION_TARGET.get(tier)


def reapprove_mode_for_tier(tier: int) -> str:
    return REAPPROVE_MODE.get(tier, "full")


def should_regress_for_tier(tier: int, current_idx: int, target_idx: int) -> bool:
    """Tier-1 仅在已过 plan-approve 后才回退；Tier-2/3 沿用原规则。"""
    if current_idx < target_idx:
        return False
    if tier == 1:
        plan_idx = target_idx  # plan-approve
        return current_idx > plan_idx
    return True


def apply_tier_regression(
    state: dict,
    *,
    tier: int,
    patch_id: str,
    change_summary: str = "",
) -> dict[str, Any] | None:
    """
    按 Tier 回退 Pipeline current_stage。

    - Tier-1：若已过 plan-approve（含 E2E/release 后）→ 回退 plan-approve，**轻量重审**（仅改造点）
    - Tier-2：若已过 plan-approve → 回退 plan-approve，**全量重审**（含协议）
    - Tier-3：若已过 scope-eval → 回退 scope-eval，重跑分析/详设链

    若当前尚未到达目标 stage，则不回退指针。
    """
    target_id = regression_target_for_tier(tier)
    if not target_id:
        return None

    stages: list[dict] = state["stages"]
    current_idx = int(state.get("current_stage", 0))
    target_idx = _stage_index(stages, target_id)
    from_stage = stages[current_idx]["id"]

    if not should_regress_for_tier(tier, current_idx, target_idx):
        return None

    for i in range(target_idx, len(stages)):
        stage = stages[i]
        stage["status"] = "pending"
        stage["started_at"] = None
        stage["completed_at"] = None
        stage["retry_count"] = 0
        stage["fail_reason"] = None

    stages[target_idx]["status"] = "running"
    stages[target_idx]["started_at"] = iso_now()
    state["current_stage"] = target_idx

    reapprove_mode = reapprove_mode_for_tier(tier)
    awaiting = target_id == PLAN_APPROVE_STAGE

    regression = {
        "applied": True,
        "tier": tier,
        "patch_id": patch_id,
        "from_stage": from_stage,
        "to_stage": target_id,
        "change_summary": change_summary,
        "reapprove_mode": reapprove_mode,
        "awaiting_plan_approve": awaiting,
        "applied_at": iso_now(),
    }
    prd_resync = state.setdefault("prd_resync", {})
    prd_resync["regression"] = regression
    return regression


def clear_collab_regression(state: dict) -> bool:
    """plan-approve 通过后清除联调回退待审标记。"""
    prd = state.get("prd_resync") or {}
    regression = prd.get("regression") or {}
    if not regression.get("awaiting_plan_approve"):
        return False

    regression["awaiting_plan_approve"] = False
    regression["cleared_at"] = iso_now()
    prd["regression"] = regression

    delta = prd.setdefault("delta", {})
    delta["handoff_stale"] = False
    delta["needs_collab_reapprove"] = False
    state["prd_resync"] = prd
    return True


def format_regression_message(regression: dict[str, Any]) -> str:
    tier = regression.get("tier")
    to_stage = regression.get("to_stage")
    from_stage = regression.get("from_stage")
    mode = regression.get("reapprove_mode", "full")
    if tier == 1 and mode == "light":
        return (
            f"Tier-1：Pipeline 已从 {from_stage} 回退至 **{to_stage}**（轻量重审），"
            "仅审联调改造点 / UI·E2E，不重审 API 协议。"
        )
    if tier == 2:
        return (
            f"Tier-2：Pipeline 已从 {from_stage} 回退至 **{to_stage}**，"
            "请更新 api-contract / 详设后全量重新审批。"
        )
    if tier == 3:
        return (
            f"Tier-3：Pipeline 已从 {from_stage} 回退至 **{to_stage}**，"
            "请重跑 scope-eval → api-contract → 详设 → plan-approve。"
        )
    return f"Pipeline 已回退至 {to_stage}（Tier-{tier}）。"


def plan_approve_prompt_lines(state: dict) -> list[str]:
    """根据联调回退模式返回 plan-approve 审批包说明行。"""
    regression = (state.get("prd_resync") or {}).get("regression") or {}
    mode = regression.get("reapprove_mode", "full")
    if mode == "light":
        return [
            ">>> 联调轻量重审（Tier-1）：仅审改造点，**无需重审 API 协议/详设**",
            "    - request/spec.md 联调变更章节 + request/tasks.md 回灌项",
            "    - collaboration/patch-NNN/tier_analysis.json 变更摘要",
            "    - handoff/frontend-handoff.md § UI 改造点 / § E2E（如有前端）",
            "    - 审批后：按 tasks 改前端（或极小改动）→ 快进到 E2E 复测",
        ]
    return [
        ">>> 请向用户展示以下内容（协议 + 详设，**仅文档，尚未编码**）：",
        "    - request/spec.md                    需求规格",
        "    - impact/impact.md                   影响范围（api_change / frontend_scope / integration_mode）",
        "    - handoff/api-contract.yaml          API 协议（api_change≠none）",
        "    - tech-design/tech-design.md         后端技术方案",
        "    - tech-design/frontend-design.md     前端技术设计（frontend_scope≠none）",
        "",
        ">>> 然后必须企微推送技术方案并同一回合阻塞 wait（见 guardrails/pipeline-redlines.md R1/R2）",
        ">>> plan-approve 通过前禁止修改目标仓库业务代码",
    ]
