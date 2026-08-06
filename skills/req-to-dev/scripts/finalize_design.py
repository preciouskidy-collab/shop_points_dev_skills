#!/usr/bin/env python3
"""Agent 修订 design_plan.json 后：校验 + human_summary + 本地 dry-run 预览。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parent / "lib"
sys.path.insert(0, str(_LIB))

from collab_common import find_change_dir, load_state  # noqa: E402
from design_plan_builder import (  # noqa: E402
    design_chat_confirm_phrase,
    design_patch_dir,
    finalize_design_patch,
    snapshot_design_files,
    validate_design_plan,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="技术方案 finalize-design")
    parser.add_argument("--req-id", required=True)
    parser.add_argument("--patch", required=True)
    args = parser.parse_args()

    change_dir = find_change_dir(args.req_id)
    state = load_state(change_dir)
    req_id = state.get("req_id", args.req_id)
    pdir = design_patch_dir(change_dir, args.patch)
    plan_path = pdir / "design_plan.json"
    if not plan_path.exists():
        print(f"ERROR: 缺少 {plan_path}", file=sys.stderr)
        return 1

    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    try:
        validate_design_plan(plan)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    snapshots = snapshot_design_files(change_dir, pdir)
    try:
        finalize_design_patch(
            pdir=pdir,
            plan=plan,
            req_id=req_id,
            patch_id=args.patch,
            change_dir=change_dir,
            snapshots=snapshots,
        )
    except (ValueError, FileNotFoundError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    meta = json.loads((pdir / "meta.json").read_text(encoding="utf-8"))
    nonce = meta.get("approval_nonce", "")
    print(f"✓ finalize-design 完成: {pdir}")
    print(f"✓ dry-run 见 {pdir / 'dry_run.log'}")
    print(f"✓ 确认语: `{design_chat_confirm_phrase(args.patch, nonce)}`")
    print("\n--- human_summary ---")
    print((pdir / "human_summary.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
