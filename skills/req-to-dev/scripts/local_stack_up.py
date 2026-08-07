#!/usr/bin/env python3
"""启动本地联调栈（方案 B）：shop-points + lottery + H5/PC webpack + nginx 网关。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parent / "lib"
sys.path.insert(0, str(_LIB))

from collab_common import append_log  # noqa: E402
from local_config import SECRETS_PATH, load_test_env_app, test_env_app_configured  # noqa: E402
from local_stack import (  # noqa: E402
    collect_stack_health,
    ensure_node_modules,
    h5_entry_url,
    iso_now,
    load_stack_config,
    nginx_prefix,
    parse_impact_frontmatter,
    pc_entry_url,
    render_nginx_conf,
    save_stack_state,
    start_frontend,
    start_lottery,
    start_nginx,
    start_pc_frontend,
    start_shop_points,
    surfaces_skip_warnings,
    validate_stack_health,
    write_stack_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="本地联调栈启动（nginx 方案 B）")
    parser.add_argument("--req-id", required=True)
    parser.add_argument("--lottery-repo", default=None)
    parser.add_argument("--shop-points-repo", default=None)
    parser.add_argument("--h5-repo", default=None)
    parser.add_argument("--pc-repo", default=None)
    parser.add_argument("--shop-code", default=None)
    parser.add_argument("--nginx-port", type=int, default=None)
    parser.add_argument("--pc-nginx-port", type=int, default=None)
    parser.add_argument("--pc-port", type=int, default=None)
    parser.add_argument("--shop-points-port", type=int, default=None)
    parser.add_argument("--surfaces", default=None, help="覆盖 impact surfaces，如 h5,pc")
    parser.add_argument("--skip-lottery", action="store_true")
    parser.add_argument("--skip-shop-points", action="store_true")
    parser.add_argument("--skip-h5", action="store_true")
    parser.add_argument("--skip-pc", action="store_true")
    parser.add_argument("--skip-frontend", action="store_true", help="等同 --skip-h5")
    parser.add_argument("--remote-shop-points", action="store_true")
    parser.add_argument(
        "--nginx-only",
        action="store_true",
        help="仅渲染并启动 nginx（各进程已手动启动）",
    )
    args = parser.parse_args()

    overrides: dict = {
        "skip_lottery": args.skip_lottery,
        "skip_h5": args.skip_h5 or args.skip_frontend,
        "skip_pc": args.skip_pc,
    }
    if args.skip_shop_points:
        overrides["skip_shop_points"] = True
    if args.lottery_repo:
        overrides["lottery_repo"] = args.lottery_repo
    if args.shop_points_repo:
        overrides["shop_points_repo"] = args.shop_points_repo
    if args.h5_repo:
        overrides["h5_repo"] = args.h5_repo
    if args.pc_repo:
        overrides["pc_repo"] = args.pc_repo
    if args.shop_code:
        overrides["shop_code"] = args.shop_code
    if args.nginx_port:
        overrides["nginx_port"] = args.nginx_port
    if args.pc_nginx_port:
        overrides["pc_nginx_port"] = args.pc_nginx_port
    if args.pc_port:
        overrides["pc_port"] = args.pc_port
    if args.shop_points_port:
        overrides["shop_points_port"] = args.shop_points_port
    if args.surfaces:
        overrides["surfaces"] = args.surfaces
    if args.remote_shop_points:
        overrides["remote_shop_points"] = True

    nginx_only = args.nginx_only

    try:
        cfg = load_stack_config(args.req_id, **overrides)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    impact = parse_impact_frontmatter(cfg.change_dir)
    for warning in surfaces_skip_warnings(cfg, impact, args.surfaces):
        print(f"WARN: {warning}", file=sys.stderr)

    log_dir = cfg.change_dir / "tests" / "local-stack" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    prefix = nginx_prefix(cfg.change_dir)

    print(f"✓ 方案 B 本地网关 · req={cfg.req_id}")
    print(f"  surfaces: {', '.join(cfg.surfaces)}")
    print(f"  shop-points: {'本地 :' + str(cfg.shop_points_port) if cfg.local_shop_points else '远程 test01'}")
    if not cfg.skip_h5:
        print(f"  H5 入口: {h5_entry_url(cfg)}")
    if not cfg.skip_pc:
        print(f"  PC 入口: {pc_entry_url(cfg)}")
    print(f"  lottery 仓库: {cfg.lottery_repo}")
    print(f"  shop-points 仓库: {cfg.shop_points_repo}")
    if not cfg.skip_h5:
        print(f"  H5 仓库: {cfg.h5_repo}")
    if not cfg.skip_pc:
        print(f"  PC 仓库: {cfg.pc_client_dir}")

    if test_env_app_configured():
        user, _ = load_test_env_app()
        print(f"✓ 测试账号已配置: {user} ({SECRETS_PATH} → test_env_app)")
    else:
        print(
            f"WARN: 未配置 test_env_app，E2E 登录需填写 {SECRETS_PATH}",
            file=sys.stderr,
        )

    state: dict = {"req_id": cfg.req_id, "started_at": iso_now(), "urls": {}}

    try:
        if nginx_only or cfg.skip_shop_points or not cfg.local_shop_points:
            reason = "nginx_only" if nginx_only else (
                "remote" if not cfg.local_shop_points else "skipped"
            )
            print(f"ℹ 跳过 shop-points 本地启动 ({reason})")
            state["shop_points"] = {"status": "skipped", "reason": reason}
        else:
            print("… 启动 shop-points (profile=test, :8081) …")
            state["shop_points"] = start_shop_points(cfg, log_dir)
            print(
                f"✓ shop-points :{cfg.shop_points_port} "
                f"({state['shop_points'].get('status')})"
            )

        if nginx_only or cfg.skip_lottery:
            print("ℹ 跳过 lottery 启动")
            state["lottery"] = {"status": "skipped"}
        else:
            print("… 启动 shop-points-lottery (profile=test) …")
            state["lottery"] = start_lottery(cfg, log_dir)
            print(f"✓ lottery :{cfg.lottery_port} ({state['lottery'].get('status')})")

        if nginx_only or cfg.skip_h5:
            print("ℹ 跳过 H5 webpack")
            state["frontend"] = {"status": "skipped"}
        else:
            ensure_node_modules(cfg.h5_repo, "H5 frontend")
            print("… 启动 H5 webpack dev (craco) …")
            state["frontend"] = start_frontend(cfg, log_dir)
            print(
                f"✓ H5 frontend :{cfg.frontend_port} "
                f"({state['frontend'].get('status')})"
            )

        if nginx_only or cfg.skip_pc:
            print("ℹ 跳过 PC webpack")
            state["pc_frontend"] = {"status": "skipped"}
        else:
            ensure_node_modules(cfg.pc_client_dir, "PC frontend")
            print("… 启动 PC webpack dev (npm start) …")
            state["pc_frontend"] = start_pc_frontend(cfg, log_dir)
            print(
                f"✓ PC frontend :{cfg.pc_port} "
                f"({state['pc_frontend'].get('status')})"
            )

        conf_path = render_nginx_conf(cfg, prefix)
        print(f"✓ nginx 配置: {conf_path}")
        state["nginx"] = start_nginx(cfg, prefix, conf_path)
        ports_msg = []
        if not cfg.skip_h5:
            ports_msg.append(f"H5:{cfg.nginx_port}")
        if not cfg.skip_pc:
            ports_msg.append(f"PC:{cfg.pc_nginx_port}")
        print(f"✓ nginx 监听 {', '.join(ports_msg)}")

        if not cfg.skip_h5:
            state["urls"]["h5_entry"] = h5_entry_url(cfg)
        if not cfg.skip_pc:
            state["urls"]["pc_entry"] = pc_entry_url(cfg)

        health = collect_stack_health(cfg)
        state["health"] = health
        health_errors = validate_stack_health(cfg, health)
        if health_errors:
            state["health_errors"] = health_errors
            print("\n✗ 健康检查未通过:", file=sys.stderr)
            for err in health_errors:
                print(f"  - {err}", file=sys.stderr)
            print(
                "  排障: playbooks/local-stack-troubleshooting.md",
                file=sys.stderr,
            )
            print(
                "  复检: python3 skills/req-to-dev/scripts/local_stack_check.py "
                f"--req-id {cfg.req_id}",
                file=sys.stderr,
            )

        save_stack_state(cfg.change_dir, state)
        report = write_stack_report(cfg, state)
        append_log(cfg.change_dir, f"LOCAL-STACK-UP nginx scheme B → {report}")

        print(f"\n✓ 报告: {report}")
        if health_errors:
            return 1
        print(f"\n--- 下一步 ---")
        print(f"1. 阅读排障手册: playbooks/local-stack-troubleshooting.md")
        if not cfg.skip_h5:
            print(f"2. H5 验收: bundle ~7MB、preview 非 403")
            print(f"3. H5 浏览器: {state['urls'].get('h5_entry')}")
        if not cfg.skip_pc:
            print(f"4. PC 浏览器: {state['urls'].get('pc_entry')}（/api 走远程 lego）")
        print(f"5. local-e2e-test 或 Cursor 浏览器验收")
        print(
            f"\n停止: python3 skills/req-to-dev/scripts/local_stack_down.py "
            f"--req-id {cfg.req_id}"
        )
        return 0

    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
