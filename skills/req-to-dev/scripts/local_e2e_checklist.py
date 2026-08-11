#!/usr/bin/env python3
"""E2E 用例清单 init / update / gate 校验。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parent / "lib"
sys.path.insert(0, str(_LIB))

from collab_common import find_change_dir  # noqa: E402
from local_e2e_case_factory import seed_api_contract_e2e_cases  # noqa: E402
from local_e2e_gate import gate_local_e2e, init_checklist, update_case  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="local-e2e 必跑用例清单")
    parser.add_argument("--req-id", required=True)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="初始化 e2e_checklist.json")

    p_up = sub.add_parser("update", help="更新单条用例状态")
    p_up.add_argument("--case-id", required=True)
    p_up.add_argument("--status", required=True, choices=("pass", "fail", "pending", "blocked"))
    p_up.add_argument("--note", default="")

    sub.add_parser("gate", help="门禁校验（advance 前调用）")

    sub.add_parser("seed-contract", help="输出 api-contract e2e_cases 草案（贝壳币上传）")

    args = parser.parse_args()

    if args.command == "seed-contract":
        import json

        cases = seed_api_contract_e2e_cases()
        print("# 粘贴至 handoff/api-contract.yaml 的 e2e_cases:")
        print(json.dumps(cases, ensure_ascii=False, indent=2))
        return 0

    change_dir = find_change_dir(args.req_id)

    if args.command == "init":
        data = init_checklist(change_dir)
        print(f"✓ {change_dir / 'tests/e2e_checklist.json'} ({len(data.get('cases', {}))} cases)")
        return 0

    if args.command == "update":
        update_case(change_dir, args.case_id, args.status, args.note)
        print(f"✓ {args.case_id} → {args.status}")
        return 0

    if args.command == "gate":
        ok, errors = gate_local_e2e(change_dir)
        if ok:
            print("✓ E2E 门禁通过")
            return 0
        for e in errors:
            print(f"✗ {e}", file=sys.stderr)
        return 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
