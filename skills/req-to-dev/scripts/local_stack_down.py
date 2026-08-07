#!/usr/bin/env python3
"""停止本地联调栈（方案 B）。"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parent / "lib"
sys.path.insert(0, str(_LIB))

from collab_common import append_log, find_change_dir  # noqa: E402
from local_stack import (  # noqa: E402
    find_nginx_bin,
    load_stack_state,
    nginx_prefix,
    stack_state_path,
    stop_process,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="停止本地联调栈")
    parser.add_argument("--req-id", required=True)
    args = parser.parse_args()

    change_dir = find_change_dir(args.req_id)
    state = load_stack_state(change_dir)
    if not state:
        print(f"ℹ 无状态文件: {stack_state_path(change_dir)}", file=sys.stderr)
        return 1

    nginx_bin = find_nginx_bin()
    prefix = nginx_prefix(change_dir)
    conf = prefix / "integral-local.conf"
    if nginx_bin and conf.exists():
        subprocess.run(
            [nginx_bin, "-s", "stop", "-p", str(prefix), "-c", str(conf)],
            capture_output=True,
        )
        print("✓ nginx 已 stop")

    for key in ("frontend", "lottery"):
        block = state.get(key) or {}
        pid = block.get("pid")
        if pid:
            stop_process(int(pid), key)
            print(f"✓ 已 SIGTERM {key} pid={pid}")

    stack_state_path(change_dir).unlink(missing_ok=True)
    append_log(change_dir, "LOCAL-STACK-DOWN")
    print("✓ 本地联调栈已停止")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
