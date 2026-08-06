#!/usr/bin/env python3
"""技术方案评审 prepare：打包 plan-approve 审批包 + design_prompt。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parent / "lib"
sys.path.insert(0, str(_LIB))

from collab_common import (  # noqa: E402
    append_log,
    effective_req_id,
    ensure_active_binding,
    find_change_dir,
    iso_now,
    load_state,
    save_state,
)
from design_plan_builder import (  # noqa: E402
    DESIGN_TARGETS,
    build_agent_pending_design_plan,
    design_patch_dir,
    finalize_design_round,
    new_approval_nonce,
    next_design_patch_id,
    snapshot_design_files,
)
from sender_roles import format_sender_roles_legend  # noqa: E402


def _read_excerpt(path: Path, limit: int = 6000) -> str:
    if not path.exists():
        return f"（缺少 {path.name}）"
    text = path.read_text(encoding="utf-8")
    return text[:limit] + ("…" if len(text) > limit else "")


def main() -> int:
    parser = argparse.ArgumentParser(description="技术方案评审 prepare（plan-approve 阶段）")
    parser.add_argument("--req-id", required=True)
    args = parser.parse_args()

    change_dir = find_change_dir(args.req_id)
    state = load_state(change_dir)
    req_id = effective_req_id(state, change_dir)

    try:
        ensure_active_binding(change_dir, state, req_id)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    stages = state.get("stages", [])
    idx = int(state.get("current_stage", 0))
    current = stages[idx] if stages and 0 <= idx < len(stages) else {}
    if current.get("id") != "plan-approve" or current.get("status") != "running":
        print(
            f"WARN: 当前 stage={current.get('id')} status={current.get('status')}，"
            "建议在 plan-approve 阻塞时执行",
            file=sys.stderr,
        )

    patch_id, seq = next_design_patch_id(change_dir, state)
    pdir = design_patch_dir(change_dir, patch_id)
    snapshots = snapshot_design_files(change_dir, pdir)

    missing = [t for t in DESIGN_TARGETS if t not in snapshots]
    if missing:
        print(f"WARN: 以下方案文件尚未生成: {', '.join(missing)}", file=sys.stderr)

    plan = build_agent_pending_design_plan(patch_id=patch_id)
    nonce = new_approval_nonce()
    revision_round = 1

    collab = state.setdefault("collaboration", {})
    tdr = collab.setdefault("tech_design_review", {})
    tdr["started_at"] = tdr.get("started_at") or iso_now()
    tdr["revision_round"] = revision_round

    spec_excerpt = _read_excerpt(change_dir / "request" / "spec.md", 3000)
    impact_excerpt = _read_excerpt(change_dir / "impact" / "impact.md", 2000)

    design_prompt = "\n".join(
        [
            "# Design Prompt · 技术方案评审",
            "",
            f"req_id: {req_id}",
            f"patch: {patch_id}",
            "",
            "## 发言角色映射",
            format_sender_roles_legend(),
            "",
            "## spec 摘要",
            spec_excerpt,
            "",
            "## impact 摘要",
            impact_excerpt,
            "",
            "## 当前方案快照",
            "",
            *[
                f"### {rel}\n\n```\n{_read_excerpt(change_dir / rel, 5000)}\n```\n"
                for rel in DESIGN_TARGETS
            ],
            "",
            "## Agent 任务",
            "1. 综合企微讨论（如有）修订 `design_plan.json` 的 `updates[]`（str_replace + target）",
            "2. `finalize-design --patch` → `push-preview --preview-type tech_design`",
            "3. 阻塞 `wait`；收到 plan_approve intent → `approve-design`",
            "",
            "## design_plan.json 格式示例",
            "```json",
            json.dumps(
                {
                    "version": 1,
                    "source": "tech_design_review",
                    "plan_source": "agent",
                    "design_diff_summary": "修订 API 字段说明…",
                    "changes": [{"summary": "统一分页参数命名"}],
                    "updates": [
                        {
                            "target": "handoff/api-contract.yaml",
                            "command": "str_replace",
                            "pattern": "pageNo:",
                            "content": "pageNum:",
                        }
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            "```",
        ]
    )

    finalize_design_round(
        change_dir,
        state,
        pdir,
        patch_id=patch_id,
        seq=seq,
        req_id=req_id,
        plan=plan,
        design_prompt=design_prompt,
        meta_extra={
            "preview_type": "tech_design",
            "revision_round": revision_round,
            "approval_nonce": nonce,
            "plan_source": "agent_pending",
        },
        log_message=f"TECH-DESIGN prepare {patch_id}",
    )

    try:
        from collab_push_state import push_state_for_change  # noqa: WPS433

        push_state_for_change(change_dir, state)
        print("✓ 已 push-state phase=tech_design_review")
    except RuntimeError as e:
        print(f"WARN: push-state 失败: {e}")

    tdr["active_patch"] = patch_id
    save_state(change_dir, state)
    append_log(change_dir, f"TECH-DESIGN prepare {patch_id}")

    print(f"✓ patch: {patch_id}")
    print(f"✓ design_prompt: {pdir / 'design_prompt.md'}")
    print(f"✓ 下一步: Agent 写 design_plan.json → finalize-design → push-preview")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
