#!/usr/bin/env python3
"""
Pipeline 连续自动推进：review → test → local-stack-up → local-e2e-test。

在编码完成后调用，避免 Agent 中途结束回合、让用户手动跑 E2E。
local 模式（默认）在 local-e2e-test 通过后 Pipeline 自动终态，不进入 commit-push。

用法:
  python3 pipeline_autorun.py --req-id 20260810-prd
  python3 run_workflow.py continue --name 20260810-prd   # 转发入口
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parent / "lib"
_SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_LIB))

from collab_common import find_change_dir  # noqa: E402
from pipeline_stage_runners import execute_stage  # noqa: E402
from pipeline_terminal import pipeline_is_complete, terminal_stage_id  # noqa: E402

# 编码完成后可无人值守连续执行的阶段（至 local-e2e-test 止）
AUTORUN_STAGE_IDS = frozenset(
    {
        "backend-review",
        "frontend-review",
        "backend-test-local",
        "local-stack-up",
        "local-e2e-test",
    }
)


def _load_state(change_dir: Path) -> dict:
    path = change_dir / "pipeline_state.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _save_state(change_dir: Path, state: dict) -> None:
    (change_dir / "pipeline_state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _check_artifacts(change_dir: Path, artifacts: list[str]) -> list[str]:
    missing = []
    for rel in artifacts:
        if not (change_dir / rel).exists():
            missing.append(rel)
    return missing


def _advance(name: str) -> int:
    proc = subprocess.run(
        [sys.executable, str(_SCRIPTS / "run_workflow.py"), "advance", "--name", name],
        capture_output=True,
        text=True,
    )
    print(proc.stdout, end="")
    if proc.stderr:
        print(proc.stderr, file=sys.stderr, end="")
    return proc.returncode


def autorun(req_id: str, *, dry_run: bool = False) -> int:
    change_dir = find_change_dir(req_id)
    state = _load_state(change_dir)
    name = state.get("name", req_id)

    if pipeline_is_complete(state, change_dir):
        terminal = state.get("terminal_stage") or terminal_stage_id(change_dir)
        print(f"✓ Pipeline 已完成（终态: {terminal}）")
        return 0

    stages = state.get("stages", [])
    terminal = terminal_stage_id(change_dir)
    max_steps = len(stages) * 2
    steps = 0

    while steps < max_steps:
        steps += 1
        idx = int(state.get("current_stage", 0))
        current = stages[idx]
        stage_id = current.get("id", "")

        if pipeline_is_complete(state, change_dir):
            print(f"✓ autorun 完成，Pipeline 终态: {terminal}")
            return 0

        if stage_id not in AUTORUN_STAGE_IDS:
            if current.get("status") == "completed":
                code = _advance(name)
                if code != 0:
                    return code
                state = _load_state(change_dir)
                if pipeline_is_complete(state, change_dir):
                    print(f"✓ autorun 完成，Pipeline 终态: {terminal}")
                    return 0
                continue
            print(f"ℹ 当前阶段 {stage_id} 不在自动执行范围，停止")
            return 0

        if current.get("blocking"):
            print(f"BLOCKING: {stage_id} 需人工审批，autorun 停止")
            return 0

        # 加载 skills.json stage def 的 artifacts
        from run_workflow import STAGES, _should_skip_stage  # noqa: WPS433

        stage_def = STAGES[idx]
        skip, reason = _should_skip_stage(change_dir, stage_def)
        if skip:
            print(f"⏭ 跳过 {stage_id}: {reason}")
            if current.get("status") != "completed":
                current["status"] = "completed"
                _save_state(change_dir, state)
            code = _advance(name)
            if code != 0:
                return code
            state = _load_state(change_dir)
            if pipeline_is_complete(state, change_dir):
                print(f"✓ autorun 完成，Pipeline 终态: {terminal}")
                return 0
            continue

        artifacts = stage_def.get("artifacts") or []
        missing = _check_artifacts(change_dir, artifacts)

        if missing:
            print(f">>> 执行阶段 runner: {stage_id}（缺失: {', '.join(missing)}）")
            if dry_run:
                print(f"DRY-RUN: would execute {stage_id}")
                return 0
            ok, msg = execute_stage(stage_id, change_dir, state, req_id)
            print(msg)
            if not ok:
                print(f"ERROR: {stage_id} runner 失败", file=sys.stderr)
                return 1
            missing = _check_artifacts(change_dir, artifacts)
            if missing:
                print(f"ERROR: runner 后仍缺产出物: {missing}", file=sys.stderr)
                return 1

        if current.get("status") not in ("completed",):
            code = _advance(name)
            if code != 0:
                return code

        state = _load_state(change_dir)
        if pipeline_is_complete(state, change_dir):
            print(f"✓ autorun 完成，Pipeline 终态: {terminal}")
            return 0

    print("ERROR: autorun 超过最大步数", file=sys.stderr)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Pipeline 连续自动推进（review → E2E）")
    parser.add_argument("--req-id", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    return autorun(args.req_id, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
