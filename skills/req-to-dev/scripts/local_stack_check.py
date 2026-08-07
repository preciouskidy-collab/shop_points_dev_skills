#!/usr/bin/env python3
"""本地联调栈健康检查（启动后验收、会话恢复、排障复检）。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parent / "lib"
sys.path.insert(0, str(_LIB))

from local_stack import (  # noqa: E402
    collect_stack_health,
    is_port_open,
    load_stack_config,
    validate_stack_health,
)


def _port_row(label: str, port: int, required: bool) -> str:
    open_ = is_port_open(port)
    mark = "✓" if open_ else ("✗" if required else "—")
    return f"  {mark} {label} :{port} {'LISTEN' if open_ else 'down'}"


def main() -> int:
    parser = argparse.ArgumentParser(description="本地联调栈健康检查")
    parser.add_argument("--req-id", required=True)
    parser.add_argument("--surfaces", default=None, help="覆盖 impact surfaces，如 h5,pc")
    parser.add_argument("--skip-h5", action="store_true")
    parser.add_argument("--skip-pc", action="store_true")
    parser.add_argument("--skip-lottery", action="store_true")
    parser.add_argument("--remote-shop-points", action="store_true")
    args = parser.parse_args()

    overrides: dict = {}
    if args.surfaces:
        overrides["surfaces"] = args.surfaces
    if args.skip_h5:
        overrides["skip_h5"] = True
    if args.skip_pc:
        overrides["skip_pc"] = True
    if args.skip_lottery:
        overrides["skip_lottery"] = True
    if args.remote_shop_points:
        overrides["remote_shop_points"] = True

    try:
        cfg = load_stack_config(args.req_id, **overrides)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    print(f"本地联调栈检查 · req={cfg.req_id} · surfaces={', '.join(cfg.surfaces)}")
    print("\n端口:")
    if not cfg.skip_h5:
        print(_port_row("H5 nginx", cfg.nginx_port, True))
        print(_port_row("H5 webpack", cfg.frontend_port, True))
    if not cfg.skip_pc:
        print(_port_row("PC nginx", cfg.pc_nginx_port, True))
        print(_port_row("PC webpack", cfg.pc_port, True))
    if not cfg.skip_lottery:
        print(_port_row("lottery", cfg.lottery_port, True))
    if cfg.local_shop_points:
        print(_port_row("shop-points", cfg.shop_points_port, True))

    print("\nHTTP:")
    health = collect_stack_health(cfg)
    for key, val in health.items():
        mark = "✓" if val in (True, 200) else ("~" if val in (302, 401) else "✗")
        print(f"  {mark} {key}: {val}")

    errors = validate_stack_health(cfg, health)
    if errors:
        print("\n✗ 未通过:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        print(
            "\n排障: playbooks/local-stack-troubleshooting.md",
            file=sys.stderr,
        )
        return 1

    print("\n✓ 全部检查通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
