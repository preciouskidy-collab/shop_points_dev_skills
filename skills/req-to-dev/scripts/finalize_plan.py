#!/usr/bin/env python3
"""Agent 修订 plan.json 后：校验 str_replace + 重算 human_summary + lark-cli dry-run。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parent / "lib"
sys.path.insert(0, str(_LIB))

from collab_common import find_change_dir, load_state, patch_dir  # noqa: E402
from lark_cli import validate_plan_for_apply  # noqa: E402
from patch_builder import (  # noqa: E402
    build_human_summary_pipeline,
    build_human_summary_pre_pipeline,
    chat_confirm_phrase,
    finalize_plan_patch,
)
from prd_sync_session import resolve_pre_pipeline_patch  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Agent 修订 plan 后重算预览（须 str_replace，禁止 append）")
    parser.add_argument("--patch", required=True)
    parser.add_argument("--prd-url", default=None, help="链路 1 pre-pipeline")
    parser.add_argument("--req-id", default=None, help="链路 2 pipeline")
    parser.add_argument("--allow-append", action="store_true", help="不推荐：允许 append 写回")
    args = parser.parse_args()

    if bool(args.prd_url) == bool(args.req_id):
        print("ERROR: --prd-url 与 --req-id 二选一", file=sys.stderr)
        return 1

    pdir: Path
    prd_url: str
    nonce: str

    try:
        if args.prd_url:
            pdir, session, prd_url = resolve_pre_pipeline_patch(args.prd_url, args.patch)
            meta = json.loads((pdir / "meta.json").read_text(encoding="utf-8"))
            nonce = meta.get("approval_nonce", "")
            session_id = session.get("session_id", meta.get("session_id", ""))
            prd_md = (pdir / "prd_snapshot.md").read_text(encoding="utf-8")

            def rebuild(plan: dict) -> str:
                return build_human_summary_pre_pipeline(
                    args.patch,
                    session_id,
                    prd_url,
                    plan,
                    source_label="飞书会议纪要",
                    approval_nonce=nonce,
                    prd_md=prd_md,
                )
        else:
            change_dir = find_change_dir(args.req_id)
            pdir = patch_dir(change_dir, args.patch)
            state = load_state(change_dir)
            prd_url = state.get("trigger", {}).get("url", "")
            meta = json.loads((pdir / "meta.json").read_text(encoding="utf-8"))
            nonce = meta.get("approval_nonce", "")
            prd_md = (pdir / "prd_snapshot.md").read_text(encoding="utf-8")
            req_id = meta.get("req_id", args.req_id)

            def rebuild(plan: dict) -> str:
                return build_human_summary_pipeline(
                    args.patch,
                    req_id,
                    plan,
                    source_label="企微联调群",
                    approval_nonce=nonce,
                    prd_md=prd_md,
                )

        plan_path = pdir / "plan.json"
        if not plan_path.exists():
            print(f"ERROR: 缺少 {plan_path}", file=sys.stderr)
            return 1
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        validate_plan_for_apply(plan, allow_append=args.allow_append)
        finalize_plan_patch(pdir=pdir, prd_url=prd_url, plan=plan, rebuild_summary=rebuild)
    except (RuntimeError, FileNotFoundError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    print(f"✓ finalize-plan 完成: {pdir}")
    print(f"✓ dry-run 见 {pdir / 'dry_run.log'}")
    print(f"✓ 确认语: `{chat_confirm_phrase(args.patch, nonce)}`")
    print("\n--- human_summary ---")
    print((pdir / "human_summary.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
