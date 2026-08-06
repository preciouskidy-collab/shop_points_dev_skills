#!/usr/bin/env python3
"""PRD 回灌：refetch PRD + 增量更新 spec/tasks（不改变 current_stage）。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_LIB = Path(__file__).resolve().parent / "lib"
sys.path.insert(0, str(_LIB))

from collab_common import append_log, find_change_dir, iso_now, load_state, save_state  # noqa: E402
from lark_cli import fetch  # noqa: E402
from pipeline_regress import apply_tier_regression, format_regression_message  # noqa: E402
from prd_tier import infer_prd_change_tier, write_tier_analysis  # noqa: E402


def _append_tasks(tasks_path: Path, patch_id: str, plan: dict) -> None:
    lines = []
    if tasks_path.exists():
        lines.append(tasks_path.read_text(encoding="utf-8").rstrip())
    lines.append(f"\n\n## 联调回灌 · {patch_id}\n")
    for item in plan.get("changes", []):
        lines.append(f"- [ ] {item.get('summary', item)}")
    tasks_path.parent.mkdir(parents=True, exist_ok=True)
    tasks_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def _append_spec(spec_path: Path, patch_id: str, note: str) -> None:
    block = f"\n\n## 联调变更 · {patch_id}\n\n{note.strip() or '见 tasks.md 联调回灌章节'}\n"
    if spec_path.exists():
        spec_path.write_text(spec_path.read_text(encoding="utf-8").rstrip() + block, encoding="utf-8")
    else:
        spec_path.write_text(f"# Spec\n{block}", encoding="utf-8")


def _resolve_patch_meta(collab_dir: Path, patch_id: str | None) -> tuple[str, dict]:
    if patch_id:
        meta_path = collab_dir / patch_id / "meta.json"
        if not meta_path.exists():
            raise FileNotFoundError(f"patch 不存在: {patch_id}")
        return patch_id, json.loads(meta_path.read_text(encoding="utf-8"))

    candidates = sorted(collab_dir.glob("patch-*/meta.json"), reverse=True)
    for mp in candidates:
        m = json.loads(mp.read_text(encoding="utf-8"))
        if m.get("ready_for_resync"):
            return m["patch_id"], m
    raise RuntimeError("无 ready_for_resync 的 patch")


def run_prd_resync(
    change_dir: Path,
    state: dict,
    *,
    req_id: str,
    prd_url: str,
    patch_id: str | None = None,
    tier_override: int | None = None,
) -> dict[str, Any]:
    """执行 PRD 回灌，返回摘要信息供调用方打印。"""
    collab_dir = change_dir / "collaboration"
    patch_id, meta = _resolve_patch_meta(collab_dir, patch_id)

    prd_path = change_dir / "request" / "prd.md"
    old_text = prd_path.read_text(encoding="utf-8") if prd_path.exists() else ""
    fetch(prd_url, prd_path)
    new_text = prd_path.read_text(encoding="utf-8")

    plan_path = collab_dir / patch_id / "plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8")) if plan_path.exists() else {"changes": []}
    approval_note = meta.get("approval_note", "") if meta else ""

    stages = state.get("stages", [])
    current_idx = state.get("current_stage", 0)
    resume_stage = stages[current_idx]["id"] if stages and 0 <= current_idx < len(stages) else "unknown"

    impact_path = change_dir / "impact" / "impact.md"
    impact_excerpt = impact_path.read_text(encoding="utf-8")[:2000] if impact_path.exists() else ""

    tier_analysis = infer_prd_change_tier(
        old_prd=old_text,
        new_prd=new_text,
        patch_id=patch_id,
        plan=plan,
        approval_note=approval_note,
        resume_stage=resume_stage,
        impact_excerpt=impact_excerpt,
        tier_override=tier_override,
        tier_analysis_path=collab_dir / patch_id / "tier_analysis.json",
    )
    write_tier_analysis(collab_dir / patch_id / "tier_analysis.json", tier_analysis)
    tier = tier_analysis["tier"]

    _append_tasks(change_dir / "request" / "tasks.md", patch_id, plan)
    spec_note = approval_note
    if tier_analysis.get("change_summary"):
        spec_note = f"{approval_note}\n\n**变更摘要（Tier-{tier}）**：{tier_analysis['change_summary']}"
    _append_spec(change_dir / "request" / "spec.md", patch_id, spec_note)

    handoff_stale = tier >= 2
    if tier >= 3 and impact_path.exists():
        rationale = tier_analysis.get("rationale", "")
        actions = tier_analysis.get("suggested_actions") or []
        action_lines = "\n".join(f"- {a}" for a in actions) if actions else "- 请 TL 复核 impact 并考虑重新 plan-approve"
        impact_path.write_text(
            impact_path.read_text(encoding="utf-8").rstrip()
            + f"\n\n## 联调范围变更 · {patch_id}\n\n"
            f"- **Tier-3**（Agent 语义分级）\n"
            f"- 摘要：{tier_analysis.get('change_summary', '')}\n"
            f"- 理由：{rationale}\n"
            f"- 建议动作：\n{action_lines}\n",
            encoding="utf-8",
        )

    regression = apply_tier_regression(
        state,
        tier=tier,
        patch_id=patch_id,
        change_summary=tier_analysis.get("change_summary", ""),
    )
    if regression and regression.get("awaiting_plan_approve"):
        collab = state.setdefault("collaboration", {})
        collab["phase"] = "tech_design_review"
        tdr = collab.setdefault("tech_design_review", {})
        tdr.pop("ended_at", None)
        tdr["started_at"] = tdr.get("started_at") or iso_now()
    current_stage_id = stages[state["current_stage"]]["id"]
    needs_collab_reapprove = bool(regression and regression.get("awaiting_plan_approve"))

    meta["status"] = "resync_done"
    meta["ready_for_resync"] = False
    meta["tier"] = tier
    meta["tier_analysis_file"] = f"{patch_id}/tier_analysis.json"
    (collab_dir / patch_id / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    state["prd_resync"] = {
        "last_sync_at": iso_now(),
        "last_patch": patch_id,
        "resume_stage": current_stage_id,
        "delta": {
            "tier": tier,
            "tier_source": tier_analysis.get("source", "agent"),
            "change_summary": tier_analysis.get("change_summary", ""),
            "rationale": tier_analysis.get("rationale", ""),
            "affects_api_contract": tier_analysis.get("affects_api_contract", tier >= 2),
            "affects_scope": tier_analysis.get("affects_scope", tier >= 3),
            "suggested_actions": tier_analysis.get("suggested_actions", []),
            "prd_updated": True,
            "spec_updated": True,
            "tasks_updated": True,
            "impact_updated": tier >= 3,
            "handoff_stale": handoff_stale,
            "needs_collab_reapprove": needs_collab_reapprove,
        },
    }
    if regression:
        state["prd_resync"]["regression"] = regression
    collab = state.setdefault("collaboration", {})
    collab.setdefault("patches", {})[patch_id] = {"status": "resync_done"}
    save_state(change_dir, state)
    append_log(
        change_dir,
        f"COLLAB prd_resync {patch_id} tier={tier} stage={current_stage_id}"
        + (f" regress→{regression['to_stage']}" if regression else ""),
    )

    return {
        "patch_id": patch_id,
        "tier": tier,
        "tier_analysis": tier_analysis,
        "prd_path": str(prd_path),
        "resume_stage": current_stage_id,
        "handoff_stale": handoff_stale,
        "needs_collab_reapprove": needs_collab_reapprove,
        "regression": regression,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="PRD resync")
    parser.add_argument("--req-id", required=True)
    parser.add_argument("--patch", default=None, help="默认取最新 ready_for_resync 的 patch")
    parser.add_argument("--tier", type=int, choices=(1, 2, 3), default=None, help="Agent 判定的 Tier，或已写入 tier_analysis.json")
    args = parser.parse_args()

    try:
        change_dir = find_change_dir(args.req_id)
        state = load_state(change_dir)
        req_id = state.get("req_id", args.req_id)
        prd_url = state.get("trigger", {}).get("url")
        if not prd_url:
            print("ERROR: pipeline_state.trigger.url 缺失", file=sys.stderr)
            return 1

        result = run_prd_resync(
            change_dir, state, req_id=req_id, prd_url=prd_url, patch_id=args.patch,
            tier_override=args.tier,
        )
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    analysis = result.get("tier_analysis") or {}
    print(f"✓ refetch {result['prd_path']}")
    print(f"✓ Tier-{result['tier']}（Agent 语义分级）: 已更新 spec/tasks")
    if analysis.get("change_summary"):
        print(f"  摘要: {analysis['change_summary']}")
    if analysis.get("rationale"):
        print(f"  理由: {analysis['rationale']}")
    for action in analysis.get("suggested_actions") or []:
        print(f"  → {action}")
    regression = result.get("regression")
    if regression:
        print(f"🔄 {format_regression_message(regression)}")
        if regression.get("tier") == 2:
            print(">>> 更新契约/详设后: python3 skills/req-to-dev/scripts/run_workflow.py approve --name <req_id>")
        elif regression.get("tier") == 1:
            print(">>> 确认改造点后: python3 skills/req-to-dev/scripts/run_workflow.py approve --name <req_id>")
            print(">>> 审批后：前端小改 → 快进到 E2E 复测")
        elif regression.get("tier") == 3:
            print(">>> 重跑分析链后 advance 至 plan-approve，再 approve")
    elif result.get("needs_collab_reapprove"):
        print("⚠ 联调变更需 plan-approve 前纳入契约/详设（当前 stage 尚未过审批点）")
    elif result["handoff_stale"]:
        print("⚠ handoff 可能过期，编码后请认真做契约对齐")
    print(f"✓ current_stage: {result['resume_stage']}")
    print("下一步: 按 tasks.md 继续当前阶段，完成后 run_workflow.py advance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
