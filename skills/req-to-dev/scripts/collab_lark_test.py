#!/usr/bin/env python3
"""lark-cli 飞书 PRD 连通性测试（仅 lark-cli，不降级）。"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

_LIB = Path(__file__).resolve().parent / "lib"
sys.path.insert(0, str(_LIB))

from lark_cli import check_available, fetch, update_dry_run  # noqa: E402


DEFAULT_URL = "https://beike.feishu.cn/wiki/CKFdwt35oitbqPkU690cVMnln3g?from=from_copylink"


def main() -> int:
    parser = argparse.ArgumentParser(description="测试 lark-cli fetch / update dry-run")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--skip-update-dry-run", action="store_true")
    args = parser.parse_args()

    ok, binary = check_available()
    if not ok:
        print(f"ERROR: {binary}", file=sys.stderr)
        return 1

    print(f"✓ lark-cli: {binary}")

    out = args.output
    if out is None:
        tmp = tempfile.NamedTemporaryFile(prefix="lark-fetch-", suffix=".md", delete=False)
        out = Path(tmp.name)
        tmp.close()

    try:
        fetch(args.url, out)
    except RuntimeError as e:
        print(f"ERROR: fetch 失败\n{e}", file=sys.stderr)
        return 2

    text = out.read_text(encoding="utf-8")
    print(f"✓ fetch 成功 → {out} ({len(text)} chars)")
    print("\n--- 前 800 字预览 ---")
    print(text[:800])

    if args.skip_update_dry_run:
        return 0

    import json

    plan = {
        "version": 1,
        "update": {
            "command": "append",
            "doc_format": "markdown",
            "content": "## lark-cli 连通性测试\n\n本段为 collab_lark_test dry-run，不会实际写入。\n",
        },
    }
    plan_path = out.with_suffix(".plan.json")
    log_path = out.with_suffix(".dry_run.log")
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        update_dry_run(args.url, plan_path, log_path=log_path)
    except RuntimeError as e:
        print(f"ERROR: update dry-run 失败\n{e}", file=sys.stderr)
        return 3

    print(f"✓ update dry-run 成功，日志: {log_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
