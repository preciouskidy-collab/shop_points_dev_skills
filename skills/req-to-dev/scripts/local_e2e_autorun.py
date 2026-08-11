#!/usr/bin/env python3
"""
本地 E2E 自动验收（默认假定 VPN 已连通，带重试）。

产出: changes/<req_id>/tests/local_e2e_report.md
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

_LIB = Path(__file__).resolve().parent / "lib"
sys.path.insert(0, str(_LIB))

from collab_common import find_change_dir  # noqa: E402
from local_e2e_gate import init_checklist, update_case  # noqa: E402
from local_stack import (  # noqa: E402
    collect_stack_health,
    load_stack_config,
    shop_points_kecoin_period_url,
    validate_stack_health,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _http_get(url: str, timeout: int = 15) -> int | None:
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return None


def stack_check_with_retries(cfg, *, retries: int = 5, delay_sec: int = 8) -> tuple[dict, list[str]]:
    last_errors: list[str] = []
    health: dict = {}
    for attempt in range(1, retries + 1):
        health = collect_stack_health(cfg)
        errors = validate_stack_health(cfg, health)
        if not errors:
            return health, []
        last_errors = errors
        if attempt < retries:
            print(
                f"WARN: stack check 第 {attempt}/{retries} 次未通过，{delay_sec}s 后重试…",
                file=sys.stderr,
            )
            time.sleep(delay_sec)
    return health, last_errors


def main() -> int:
    parser = argparse.ArgumentParser(description="本地 E2E 自动验收")
    parser.add_argument("--req-id", required=True)
    parser.add_argument("--retries", type=int, default=5)
    parser.add_argument("--retry-delay", type=int, default=8)
    args = parser.parse_args()

    change_dir = find_change_dir(args.req_id)
    init_checklist(change_dir)
    cfg = load_stack_config(args.req_id)

    health, errors = stack_check_with_retries(
        cfg,
        retries=args.retries,
        delay_sec=args.retry_delay,
    )

    cases: list[tuple[str, str, str, str]] = []
    stack_ok = not errors

    if stack_ok:
        cases.append(("CHK-01", "local_stack_check", "PASS", "全部健康检查通过（含 VPN 重试）"))
    else:
        cases.append(("CHK-01", "local_stack_check", "FAIL", "; ".join(errors[:3])))

    sp_health = health.get("shop_points_health")
    cases.append(
        (
            "API-01",
            "shop-points health",
            "PASS" if sp_health == 200 else "FAIL",
            f"HTTP {sp_health}",
        )
    )

    if sp_health == 200:
        update_case(change_dir, "API-01", "pass", f"HTTP {sp_health}")
    else:
        update_case(change_dir, "API-01", "fail", f"HTTP {sp_health}")

    kecoin_url = shop_points_kecoin_period_url(cfg)
    kecoin_status = health.get("kecoin_period_api")
    if kecoin_status is None:
        kecoin_status = _http_get(kecoin_url)
    cases.append(
        (
            "API-02",
            "GET keCoin/period",
            "PASS" if kecoin_status == 200 else "FAIL",
            f"HTTP {kecoin_status} · {kecoin_url}",
        )
    )

    if kecoin_status == 200:
        update_case(change_dir, "API-02", "pass", f"HTTP {kecoin_status}")
    else:
        update_case(change_dir, "API-02", "fail", f"HTTP {kecoin_status}")

    pc_entry = f"http://point-pc.ttb.test.ke.com:{cfg.pc_nginx_port}/integral2/activity-config/city"
    pc_status = health.get("pc_nginx_entry") or _http_get(pc_entry)
    login_status = health.get("pc_login_user_info")
    ui_verdict = "PASS" if pc_status == 200 and login_status in (200, 302, 401) else "FAIL"
    if login_status is None and pc_status == 200:
        ui_verdict = "WARN"
    cases.append(
        (
            "E2E-PC-01",
            "PC 活动配置入口 + loginUser",
            ui_verdict,
            f"entry={pc_status} loginUser={login_status} url={pc_entry}",
        )
    )

    fail_count = sum(1 for c in cases if c[2] == "FAIL")
    warn_count = sum(1 for c in cases if c[2] == "WARN")
    # autorun 永不单独标 PASS：完整闭环以 e2e_checklist.json gate 为准（R6.1）
    if fail_count > 0:
        verdict = "FAIL"
    else:
        verdict = "INCOMPLETE"

    lines = [
        f"# Local E2E Report · {args.req_id}",
        "",
        f"generated_at: {_now_iso()}",
        f"surfaces: {', '.join(cfg.surfaces)}",
        f"verdict: **{verdict}**",
        f"mode: autorun（API/栈探测 only；完整 E2E 见 e2e_checklist.json + R6.1）",
        "",
        "## 用例结果",
        "",
        "| ID | 用例 | 结果 | 说明 |",
        "|----|------|------|------|",
    ]
    for cid, name, result, note in cases:
        mark = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️"}.get(result, result)
        lines.append(f"| {cid} | {name} | {mark} {result} | {note} |")

    lines.extend(
        [
            "",
            "## 健康检查明细",
            "",
            "```json",
            json.dumps(health, ensure_ascii=False, indent=2),
            "```",
            "",
        ]
    )

    report_path = change_dir / "tests" / "local_e2e_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"✓ report: {report_path}")
    print(f"verdict: {verdict}")

    if verdict == "FAIL":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
