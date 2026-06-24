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


def _infer_tier(old_text: str, new_text: str) -> int:
    old_lines = {ln.strip() for ln in old_text.splitlines() if ln.strip()}
    new_lines = {ln.strip() for ln in new_text.splitlines() if ln.strip()}
    added = new_lines - old_lines
    joined = " ".join(added).lower()
    if any(k in joined for k in ("接口", "api", "字段", "错误码", "4001", "4002", "nullable")):
        return 2
    if any(k in joined for k in ("新增", "新页面", "新服务", "范围", "模块")):
        return 3
    return 1


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
) -> dict[str, Any]:
    """执行 PRD 回灌，返回摘要信息供调用方打印。"""
    collab_dir = change_dir / "collaboration"
    patch_id, meta = _resolve_patch_meta(collab_dir, patch_id)

    prd_path = change_dir / "request" / "prd.md"
    old_text = prd_path.read_text(encoding="utf-8") if prd_path.exists() else ""
    fetch(prd_url, prd_path)
    new_text = prd_path.read_text(encoding="utf-8")
    tier = _infer_tier(old_text, new_text)

    plan_path = collab_dir / patch_id / "plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8")) if plan_path.exists() else {"changes": []}
    approval_note = meta.get("approval_note", "") if meta else ""

    _append_tasks(change_dir / "request" / "tasks.md", patch_id, plan)
    _append_spec(change_dir / "request" / "spec.md", patch_id, approval_note)

    handoff_stale = tier >= 2
    if tier >= 3:
        impact_path = change_dir / "impact" / "impact.md"
        if impact_path.exists():
            impact_path.write_text(
                impact_path.read_text(encoding="utf-8").rstrip()
                + f"\n\n## 联调范围变更 · {patch_id}\n\n- Tier-3：请 TL 复核 impact\n",
                encoding="utf-8",
            )

    meta["status"] = "resync_done"
    meta["ready_for_resync"] = False
    (collab_dir / patch_id / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    stages = state.get("stages", [])
    current_idx = state.get("current_stage", 0)
    resume_stage = stages[current_idx]["id"] if stages and 0 <= current_idx < len(stages) else "unknown"

    state["prd_resync"] = {
        "last_sync_at": iso_now(),
        "last_patch": patch_id,
        "resume_stage": resume_stage,
        "delta": {
            "tier": tier,
            "prd_updated": True,
            "spec_updated": True,
            "tasks_updated": True,
            "impact_updated": tier >= 3,
            "handoff_stale": handoff_stale,
            "needs_collab_reapprove": tier >= 3,
        },
    }
    collab = state.setdefault("collaboration", {})
    collab.setdefault("patches", {})[patch_id] = {"status": "resync_done"}
    save_state(change_dir, state)
    append_log(change_dir, f"COLLAB prd_resync {patch_id} tier={tier} resume={resume_stage}")

    return {
        "patch_id": patch_id,
        "tier": tier,
        "prd_path": str(prd_path),
        "resume_stage": resume_stage,
        "handoff_stale": handoff_stale,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="PRD resync")
    parser.add_argument("--req-id", required=True)
    parser.add_argument("--patch", default=None, help="默认取最新 ready_for_resync 的 patch")
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
            change_dir, state, req_id=req_id, prd_url=prd_url, patch_id=args.patch
        )
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    print(f"✓ refetch {result['prd_path']}")
    print(f"✓ Tier-{result['tier']}: 已更新 spec/tasks")
    if result["handoff_stale"]:
        print("⚠ handoff 可能过期，请视情况补跑 frontend-handoff")
    print(f"✓ resume_stage: {result['resume_stage']} (current_stage 未改变)")
    print("下一步: 按 tasks.md 继续当前阶段，完成后 run_workflow.py advance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
