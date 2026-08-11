"""Pipeline 终态阶段：默认 local 模式在 local-e2e-test 结束，不自动进入 commit-push。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any


def parse_impact_meta(change_dir: Path) -> dict:
    """从 impact/impact.md frontmatter 读取元数据（与 run_workflow 默认值对齐）。"""
    defaults = {
        "frontend_scope": "partial",
        "api_change": "extend",
        "mall_scope": "none",
        "integration_mode": "local",
    }
    impact_file = change_dir / "impact" / "impact.md"
    if not impact_file.exists():
        return defaults

    text = impact_file.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return defaults

    end = text.find("---", 3)
    if end == -1:
        return defaults

    meta = dict(defaults)
    for line in text[3:end].strip().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, _, val = stripped.partition(":")
        key = key.strip()
        val = val.strip().strip("\"'")
        if val:
            meta[key] = val
    return meta


def terminal_stage_id(change_dir: Path) -> str:
    """
    返回 Pipeline 终态阶段 ID。

    - impact.pipeline_terminal：显式覆盖
    - integration_mode=dayu：终态 release（含 commit-push / dayu / e2e-browser）
    - 默认 local：终态 local-e2e-test（E2E 通过后自动结束，不进入 commit-push）
    """
    meta = parse_impact_meta(change_dir)
    explicit = meta.get("pipeline_terminal")
    if explicit:
        return explicit
    if meta.get("integration_mode", "local") == "dayu":
        return "release"
    return "local-e2e-test"


def is_terminal_stage(change_dir: Path, stage_id: str) -> bool:
    return stage_id == terminal_stage_id(change_dir)


def pipeline_is_complete(state: dict, change_dir: Path) -> bool:
    if state.get("pipeline_status") == "completed":
        return True
    terminal = terminal_stage_id(change_dir)
    for stage in state.get("stages", []):
        if stage.get("id") == terminal:
            return stage.get("status") == "completed"
    return False


def finalize_pipeline(
    change_dir: Path,
    state: dict,
    *,
    terminal_stage_id_value: str,
    log_fn,
    duration_fn,
) -> None:
    """将 Pipeline 标记为在终态阶段完成，跳过后续阶段。"""
    stages = state.get("stages", [])
    terminal_idx = next(
        (i for i, s in enumerate(stages) if s.get("id") == terminal_stage_id_value),
        len(stages) - 1,
    )
    now = datetime.now().isoformat()

    for i, stage in enumerate(stages):
        if i > terminal_idx and stage.get("status") not in ("completed", "skipped"):
            stage["status"] = "skipped"
            stage["completed_at"] = now
            stage["skip_reason"] = f"pipeline_terminal={terminal_stage_id_value}"

    state["current_stage"] = terminal_idx
    state["pipeline_status"] = "completed"
    state["terminal_stage"] = terminal_stage_id_value
    state["completed_at"] = now
    state["updated_at"] = now

    (change_dir / "pipeline_state.json").write_text(
        __import__("json").dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    created = state.get("created_at", "")
    total_dur = duration_fn(created, now)
    log_fn(change_dir, f"PIPELINE COMPLETED at {terminal_stage_id_value} (总耗时 {total_dur})")

    summary_file = change_dir / "summary.md"
    with open(summary_file, "w", encoding="utf-8") as f:
        f.write(f"# Change 摘要: {state['name']}\n\n")
        f.write(f"状态: ✅ 已完成（终态: `{terminal_stage_id_value}`）\n\n")
        f.write("## 阶段记录\n\n")
        for s in stages:
            status = s.get("status", "pending")
            if status == "completed":
                mark = "✅"
            elif status == "skipped":
                mark = "⏭"
            else:
                mark = status
            f.write(f"- {mark} {s['id']}")
            if s.get("completed_at"):
                f.write(f" ({status} @ {s['completed_at']})")
            if s.get("skip_reason"):
                f.write(f" — {s['skip_reason']}")
            f.write("\n")


def terminal_completion_message(change_dir: Path, state: dict) -> list[str]:
    terminal = state.get("terminal_stage") or terminal_stage_id(change_dir)
    lines = [
        f"✅ Pipeline 已完成（终态: {terminal}）",
        f"Change 目录: {change_dir}",
    ]
    if terminal == "local-e2e-test":
        lines.append(
            "后续 commit-push / dayu-deploy 未自动执行；"
            "需要推送代码时请显式运行并见 playbooks/commit-push.md"
        )
    return lines
