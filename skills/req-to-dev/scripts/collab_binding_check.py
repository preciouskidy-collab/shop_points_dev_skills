#!/usr/bin/env python3
"""校验企微群已绑定 req_id，并写回 pipeline_state.collaboration。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parent / "lib"
sys.path.insert(0, str(_LIB))

from collab_common import ensure_active_binding, find_change_dir, load_state  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="校验联调群绑定")
    parser.add_argument("--req-id", required=True)
    args = parser.parse_args()

    try:
        change_dir = find_change_dir(args.req_id)
        state = load_state(change_dir)
        req_id = state.get("req_id", args.req_id)
        group_id = ensure_active_binding(change_dir, state, req_id)
    except (RuntimeError, FileNotFoundError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    print(f"✓ req_id: {req_id}")
    print(f"✓ group_id: {group_id}")
    print("✓ status: active")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
