#!/usr/bin/env python3
"""启动本地联调栈（方案 B）：lottery + webpack dev + nginx 网关。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parent / "lib"
sys.path.insert(0, str(_LIB))

from collab_common import append_log, project_root  # noqa: E402
from local_config import SECRETS_PATH, load_test_env_app, test_env_app_configured  # noqa: E402
from local_stack import (  # noqa: E402
    h5_entry_url,
    http_status,
    iso_now,
    load_stack_config,
    nginx_prefix,
    parse_impact_frontmatter,
    render_nginx_conf,
    save_stack_state,
    start_frontend,
    start_lottery,
    start_nginx,
    write_stack_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="本地联调栈启动（nginx 方案 B）")
    parser.add_argument("--req-id", required=True)
    parser.add_argument("--lottery-repo", default=None)
    parser.add_argument("--h5-repo", default=None)
    parser.add_argument("--shop-code", default=None)
    parser.add_argument("--nginx-port", type=int, default=None)
    parser.add_argument("--skip-lottery", action="store_true")
    parser.add_argument("--skip-frontend", action="store_true")
    parser.add_argument("--nginx-only", action="store_true", help="仅渲染并启动 nginx（前后端已手动启动）")
    args = parser.parse_args()

    overrides = {
        "skip_lottery": args.skip_lottery or args.nginx_only,
        "skip_frontend": args.skip_frontend or args.nginx_only,
    }
    if args.lottery_repo:
        overrides["lottery_repo"] = args.lottery_repo
    if args.h5_repo:
        overrides["h5_repo"] = args.h5_repo
    if args.shop_code:
        overrides["shop_code"] = args.shop_code
    if args.nginx_port:
        overrides["nginx_port"] = args.nginx_port

    try:
        cfg = load_stack_config(args.req_id, **overrides)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    impact = parse_impact_frontmatter(cfg.change_dir)
    if impact.get("frontend_scope") == "none":
        cfg.skip_frontend = True

    log_dir = cfg.change_dir / "tests" / "local-stack" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    prefix = nginx_prefix(cfg.change_dir)

    print(f"✓ 方案 B 本地网关 · req={cfg.req_id}")
    print(f"  H5 入口（nginx）: {h5_entry_url(cfg)}")
    print(f"  lottery 仓库: {cfg.lottery_repo}")
    print(f"  H5 仓库: {cfg.h5_repo}")

    if test_env_app_configured():
        user, _ = load_test_env_app()
        print(f"✓ 测试账号已配置: {user} ({SECRETS_PATH} → test_env_app)")
    else:
        print(f"WARN: 未配置 test_env_app，E2E 登录需填写 {SECRETS_PATH}", file=sys.stderr)

    state: dict = {"req_id": cfg.req_id, "started_at": iso_now(), "urls": {}}

    try:
        if cfg.skip_lottery:
            print("ℹ 跳过 lottery 启动")
            state["lottery"] = {"status": "skipped"}
        else:
            print("… 启动 shop-points-lottery (profile=test) …")
            state["lottery"] = start_lottery(cfg, log_dir)
            print(f"✓ lottery :{cfg.lottery_port} ({state['lottery'].get('status')})")

        if cfg.skip_frontend:
            print("ℹ 跳过 frontend dev server")
            state["frontend"] = {"status": "skipped"}
        else:
            print("… 启动 webpack dev (craco :9393) …")
            state["frontend"] = start_frontend(cfg, log_dir)
            print(f"✓ frontend :{cfg.frontend_port} ({state['frontend'].get('status')})")

        conf_path = render_nginx_conf(cfg, prefix)
        print(f"✓ nginx 配置: {conf_path}")
        state["nginx"] = start_nginx(cfg, prefix, conf_path)
        print(f"✓ nginx 监听 :{cfg.nginx_port} server_name={cfg.h5_host}")

        entry = h5_entry_url(cfg)
        if cfg.nginx_port != 80:
            entry = entry.replace(f"http://{cfg.h5_host}", f"http://{cfg.h5_host}:{cfg.nginx_port}")
        state["urls"]["h5_entry"] = entry

        h5_status = http_status(entry)
        state["health"] = {
            "h5_entry_http": h5_status,
            "frontend_direct": http_status(f"http://127.0.0.1:{cfg.frontend_port}/"),
            "lottery_port_open": state["lottery"].get("status") != "skipped",
        }

        save_stack_state(cfg.change_dir, state)
        report = write_stack_report(cfg, state)
        append_log(cfg.change_dir, f"LOCAL-STACK-UP nginx scheme B → {report}")

        print(f"\n✓ 报告: {report}")
        print(f"\n--- 下一步 ---")
        print(f"1. 阅读排障手册: playbooks/local-stack-troubleshooting.md")
        print(f"2. 验收检查清单（bundle ~7MB、preview 非 403）")
        print(f"3. 浏览器打开: {entry}")
        print(f"4. CAS 登录（账号见 {SECRETS_PATH} → test_env_app；需 CAS 反代见排障 §四）")
        print(f"5. local-e2e-test 或 Cursor 浏览器验收")
        print(f"\n停止: python3 skills/req-to-dev/scripts/local_stack_down.py --req-id {cfg.req_id}")
        return 0

    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
