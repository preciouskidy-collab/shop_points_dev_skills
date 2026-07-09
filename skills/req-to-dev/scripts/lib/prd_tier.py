"""PRD 联调回灌变更级别（Tier）— 由 Cursor/Claude Agent 判定，脚本仅落盘与校验。"""

from __future__ import annotations

import difflib
import json
from pathlib import Path
from typing import Any

TIER_AGENT_GUIDE = """## Tier 定义（取最高严重级别，输出 1、2 或 3）

**Tier-1 — 轻量变更（实现层可就地消化）**
- 文案、提示语、空态说明、样式/圆角/间距等纯 UI 呈现
- 不改变对外 HTTP 接口的路径、请求/响应字段、错误码、业务规则
- 不扩大需求范围（无新页面、新模块、新服务、新部署单元）

**Tier-2 — 契约/规则变更（契约与实现对齐需复核）**
- 修改或新增 API 字段、错误码、枚举、校验规则、兼容性策略
- 业务规则变化但范围不变（仍是同一页面/同一服务边界）

**Tier-3 — 范围变更（方案层可能作废，建议重新 plan-approve）**
- 新增页面/路由、新微服务、新部署模块、跨服务联动
- 显著扩大 frontend_scope / api_change / deploy_modules 影响面

## 判定原则
1. 以语义与工程影响为准，不要被 PRD 里「新增」等字样误导。
2. 若 patch 计划与 diff 冲突，以对 Pipeline 实际影响更大者为准。
3. 不确定时：能在当前 stage 直接改代码 → Tier-1；需改 api-contract → Tier-2；需重跑 scope-eval/详设 → Tier-3。

## Agent 输出 tier_analysis.json 格式
```json
{
  "tier": 1,
  "change_summary": "一句话概括本次 PRD 变更",
  "rationale": "2-4 句判定理由",
  "affects_api_contract": false,
  "affects_scope": false,
  "suggested_actions": ["建议的后续动作，1-3 条"]
}
```
"""


def _truncate(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n\n…（已截断，原长 {len(text)} 字符）"


def _diff_excerpt(old_text: str, new_text: str, *, max_lines: int = 120) -> str:
    """生成供 Agent 阅读的 unified diff 摘要。"""
    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()
    diff = list(
        difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile="prd_before",
            tofile="prd_after",
            lineterm="",
        )
    )
    if not diff:
        return "（PRD 文本无行级差异）"
    if len(diff) <= max_lines:
        return "\n".join(diff)
    head = diff[: max_lines // 2]
    tail = diff[-(max_lines // 2) :]
    omitted = len(diff) - len(head) - len(tail)
    return "\n".join(head + [f"…（省略 {omitted} 行 diff）…"] + tail)


def _plan_summary(plan: dict) -> str:
    lines = []
    for item in plan.get("changes") or []:
        if isinstance(item, dict):
            lines.append(f"- {item.get('summary', item.get('type', item))}")
        else:
            lines.append(f"- {item}")
    diff = plan.get("prd_diff_summary")
    if diff:
        lines.append("")
        lines.append(str(diff).strip())
    return "\n".join(lines) if lines else "（无 patch changes）"


def build_tier_prompt(
    *,
    patch_id: str,
    plan: dict,
    approval_note: str,
    resume_stage: str,
    old_prd: str,
    new_prd: str,
    impact_excerpt: str = "",
) -> str:
    parts = [
        "# Tier 分级 Prompt · PRD resync",
        "",
        f"patch_id: `{patch_id}`",
        "",
        TIER_AGENT_GUIDE,
        "",
        "## 当前 Pipeline stage（resync 后将继续）",
        resume_stage or "unknown",
        "",
        "## 联调 patch 计划（plan.json）",
        _plan_summary(plan),
        "",
        "## 审批说明（approval_note）",
        approval_note.strip() or "（无）",
        "",
        "## PRD unified diff",
        _diff_excerpt(old_prd, new_prd),
        "",
        "## PRD 变更后全文摘录",
        _truncate(new_prd, 8000),
    ]
    if impact_excerpt.strip():
        parts.extend(["", "## 当前 impact.md 摘录", _truncate(impact_excerpt, 2000)])
    parts.extend(
        [
            "",
            "## 下一步",
            f"1. 根据上文判定 Tier，写入 `{patch_id}/tier_analysis.json`（见上方 JSON 格式）",
            f"2. 或执行 resync 时传 `--tier 1|2|3`",
        ]
    )
    return "\n".join(parts) + "\n"


def write_tier_prompt(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def load_tier_analysis(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError(f"tier_analysis.json 须为 JSON 对象: {path}")
    return normalize_tier_analysis(data)


def normalize_tier_analysis(data: dict[str, Any], *, source: str = "agent") -> dict[str, Any]:
    tier_raw = data.get("tier")
    try:
        tier = int(tier_raw)
    except (TypeError, ValueError) as e:
        raise RuntimeError(f"tier 须为 1/2/3，实际: {tier_raw!r}") from e
    if tier not in (1, 2, 3):
        raise RuntimeError(f"tier 须为 1/2/3，实际: {tier}")

    actions = data.get("suggested_actions") or []
    if not isinstance(actions, list):
        actions = [str(actions)]

    return {
        "tier": tier,
        "change_summary": str(data.get("change_summary", "")).strip(),
        "rationale": str(data.get("rationale", "")).strip(),
        "affects_api_contract": bool(data.get("affects_api_contract", tier >= 2)),
        "affects_scope": bool(data.get("affects_scope", tier >= 3)),
        "suggested_actions": [str(a).strip() for a in actions if str(a).strip()],
        "source": str(data.get("source") or source),
    }


def infer_prd_change_tier(
    *,
    old_prd: str,
    new_prd: str,
    patch_id: str,
    plan: dict | None = None,
    approval_note: str = "",
    resume_stage: str = "",
    impact_excerpt: str = "",
    tier_override: int | None = None,
    tier_analysis_path: Path | None = None,
) -> dict[str, Any]:
    """
    加载 Agent 已写入的 tier_analysis.json，或使用 CLI --tier 覆盖。
    若两者皆无，写出 tier_prompt.md 并抛出 RuntimeError。
    """
    plan = plan or {}

    if tier_override is not None:
        if tier_override not in (1, 2, 3):
            raise RuntimeError(f"--tier 须为 1/2/3，实际: {tier_override}")
        return normalize_tier_analysis(
            {
                "tier": tier_override,
                "change_summary": plan.get("prd_diff_summary") or f"PRD 回灌 · {patch_id}",
                "rationale": "由 resync --tier 指定",
                "affects_api_contract": tier_override >= 2,
                "affects_scope": tier_override >= 3,
                "suggested_actions": [],
                "source": "cli",
            },
            source="cli",
        )

    if tier_analysis_path is not None:
        loaded = load_tier_analysis(tier_analysis_path)
        if loaded is not None:
            return loaded

    if tier_analysis_path is not None:
        write_tier_prompt(
            tier_analysis_path.parent / "tier_prompt.md",
            build_tier_prompt(
                patch_id=patch_id,
                plan=plan,
                approval_note=approval_note,
                resume_stage=resume_stage,
                old_prd=old_prd,
                new_prd=new_prd,
                impact_excerpt=impact_excerpt,
            ),
        )

    raise RuntimeError(
        f"缺少 Tier 判定：请 Agent 根据 {patch_id}/tier_prompt.md 写入 tier_analysis.json，"
        f"或在 resync 时传 --tier 1|2|3"
    )


def write_tier_analysis(path, analysis: dict[str, Any]) -> None:
    """将 Tier 分析落盘到 patch 目录，便于审计。"""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    normalized = normalize_tier_analysis(analysis)
    p.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
