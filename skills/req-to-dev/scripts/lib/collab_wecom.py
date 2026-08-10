"""企微协作评审：修订口令、wait 红线说明（PRD vs 技术方案分轨）。"""

from __future__ import annotations

# 生产路径：仅企微群发送，Agent API 解析为对应 intent（须与 phase 一致）
REVISE_COMMAND_PRD = "/整理评审"  # → meeting_revise（phase=prd_review）
REVISE_COMMAND_TECH = "/整理方案"  # → tech_revise（phase=tech_design_review）

# 自然语言别名（Agent API 可选支持，与上表同 action）
REVISE_ALIASES_PRD = ("整理评审反馈", "整理 PRD 评审")
REVISE_ALIASES_TECH = ("整理技术方案", "整理方案评审", "方案修订")


def revise_command_for_phase(phase: str | None) -> str:
    if phase == "tech_design_review":
        return REVISE_COMMAND_TECH
    return REVISE_COMMAND_PRD


def revise_intent_for_phase(phase: str | None) -> str:
    if phase == "tech_design_review":
        return "tech_revise"
    return "meeting_revise"


def wait_cli(req_id: str, timeout: int = 3600) -> str:
    return (
        "python3 skills/req-to-dev/sub_skills/collab-prd-sync/scripts/collab_prd_sync.py wait "
        f"--req-id {req_id} --timeout {timeout}"
    )


def push_preview_wait_footer(req_id: str, *, phase: str | None = None) -> list[str]:
    """push-preview 成功后 Agent 必须打印；禁止结束回合。"""
    revise = revise_command_for_phase(phase)
    cli = wait_cli(req_id)
    return [
        "",
        "--- 【红线】push-preview 后同一回合必须阻塞 wait，禁止结束对话 ---",
        f"  {cli}",
        "",
        "收到 intent 后同一回合立即处理（勿结束对话）：",
        "  plan_approve     → approve-design --pull-intent-id <id>",
        f"  tech_revise      → tech-revise（企微发 {REVISE_COMMAND_TECH}）→ finalize-design → push-preview → 再 wait",
        f"  meeting_revise   → meeting-revise（企微发 {REVISE_COMMAND_PRD}）→ finalize-plan → push-preview → 再 wait",
        "  status=timeout   → 同一回合立即再跑 wait",
        "",
        "  禁止 collab_wait.py --action approve（会屏蔽 meeting_revise；/整理评审 允许多次）",
        f"技术方案阶段需修订：企微发 `{revise}`（勿用 {REVISE_COMMAND_PRD}）",
        "单轮对话结束后无法靠企微唤起 Cursor；结束回合 = 流程事故。",
    ]


def wecom_review_interaction_table() -> list[str]:
    return [
        "| 阶段 | phase | 确认通过 | 需修订（企微） | wait 返回 action |",
        "|------|-------|----------|----------------|------------------|",
        f"| PRD 评审 | `prd_review` | `确认 patch-NNN <nonce> approver <姓名>` | `{REVISE_COMMAND_PRD}` | `meeting_revise` |",
        f"| 技术方案 | `tech_design_review` | `确认 design-patch-NNN <nonce> approver <姓名>` | `{REVISE_COMMAND_TECH}` | `tech_revise` |",
        "",
        "修订轮：可在群里补充文字意见 → 发修订口令 → Agent 拉群消息写入 revise_prompt → 出新 preview → 再确认。",
    ]
