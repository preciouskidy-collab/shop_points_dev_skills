#!/usr/bin/env python3
"""凭证自检：缺失 / 有效 / 权限（PRD 同步链路）。

可作为 CLI 调用：
    python3 collab_check_config.py --url <PRD URL>

也可被其它脚本 import：
    from collab_check_config import run_check
    result = run_check(test_url, skip_update_probe=False)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional
from urllib.error import HTTPError, URLError


# ── 路径与依赖 ────────────────────────────────────────

_SCRIPT_DIR = Path(__file__).resolve().parent
_LIB = _SCRIPT_DIR / "lib"
_FEISHU_FETCHER = _SCRIPT_DIR.parent / "sub_skills" / "feishu-doc-fetcher" / "scripts"

sys.path.insert(0, str(_SCRIPT_DIR))  # 自导入 / 跨脚本 import
sys.path.insert(0, str(_LIB))
sys.path.insert(0, str(_FEISHU_FETCHER))

from lark_cli import _update as lark_update, check_available  # noqa: E402
from local_config import feishu_config_path, resolve_feishu_credentials  # noqa: E402
from feishu_fetcher import (  # noqa: E402
    FeishuAPIClient,
    TokenManager,
)

CONFIG_PATH = feishu_config_path()


DEFAULT_URL = "https://beike.feishu.cn/wiki/CKFdwt35oitbqPkU690cVMnln3g"

_URL_RE = re.compile(r"/(docx|docs|wiki)/([A-Za-z0-9]+)")


# ── 结果模型 ──────────────────────────────────────────

@dataclass
class CheckResult:
    ok: bool = True
    config_exists: bool = False
    config_path: str = ""
    app_id_masked: str = ""
    lark_cli_ok: bool = False
    lark_cli_path: str = ""
    token_valid: bool = False
    token_error: str = ""
    permissions: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


# ── 子检查 ────────────────────────────────────────────

def _mask_app_id(app_id: str) -> str:
    if not app_id:
        return ""
    if len(app_id) <= 8:
        return app_id[:3] + "***"
    return app_id[:6] + "***" + app_id[-3:]


def _parse_url(url: str) -> tuple[str, str]:
    """返回 (token, doc_type)；doc_type 为 'wiki' | 'docx'"""
    m = _URL_RE.search(url)
    if not m:
        raise ValueError(f"无法解析飞书 URL: {url}")
    return m.group(2), ("wiki" if m.group(1) == "wiki" else "docx")


_PERMISSION_DENIED_CODES = {99991663, 99991672, 230020}


def _classify_http_error(e: HTTPError, method: str) -> dict:
    """把 HTTPError 转成探测结果。

    规则：
    - 401/403 / 响应体带已知「无权限」code → ok=False（明确无权限）
    - 4xx + JSON 响应体 + code 非权限错误 → ok=True（权限过、仅业务错误，如「非资源发送方」）
    - 4xx + 非 JSON（如 HTML 404 "page not found"）→ ok=False, msg="endpoint_unavailable"
    - 5xx → ok=False, msg="server_error"
    """
    body_text = ""
    try:
        body_text = e.read().decode("utf-8", errors="ignore")
    except OSError:
        pass

    parsed: Optional[dict] = None
    if body_text:
        try:
            parsed = json.loads(body_text)
        except json.JSONDecodeError:
            pass

    if parsed and isinstance(parsed, dict) and "code" in parsed:
        feishu_code = parsed.get("code", e.code)
        msg = parsed.get("msg", "")
        if feishu_code in _PERMISSION_DENIED_CODES:
            return {"ok": False, "method": method, "code": feishu_code, "msg": msg or "permission denied"}
        return {"ok": True, "method": method, "code": feishu_code, "msg": f"已过权限检查（业务错误: {msg}）"}

    if 400 <= e.code < 500 and not parsed:
        return {"ok": False, "method": method, "code": e.code, "msg": f"endpoint_unavailable ({e.reason})"}
    if e.code >= 500:
        return {"ok": False, "method": method, "code": e.code, "msg": f"server_error ({e.reason})"}
    return {"ok": False, "method": method, "code": e.code, "msg": str(e)}


def _check_missing(result: CheckResult) -> bool:
    result.config_path = str(CONFIG_PATH)
    app_id, app_secret = resolve_feishu_credentials()
    result.config_exists = bool(app_id and app_secret) or CONFIG_PATH.exists()
    if app_id:
        result.app_id_masked = _mask_app_id(app_id)
    elif CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            feishu = data.get("feishu") or {}
            legacy_id = (data.get("app_id") or feishu.get("app_id") or "").strip()
            result.app_id_masked = _mask_app_id(legacy_id)
        except (json.JSONDecodeError, OSError) as e:
            result.app_id_masked = f"<parse error: {e}>"
    else:
        result.ok = False

    result.lark_cli_ok, result.lark_cli_path = check_available()
    if not result.lark_cli_ok:
        result.ok = False

    return result.config_exists and result.lark_cli_ok


def _check_validity(result: CheckResult, app_id: str, app_secret: str) -> bool:
    try:
        tm = TokenManager(app_id, app_secret)
        token = tm.get_token()
        result.token_valid = bool(token)
        if not result.token_valid:
            result.ok = False
        return result.token_valid
    except RuntimeError as e:
        result.token_error = str(e)
        result.token_valid = False
        result.ok = False
        return False


def _probe_write_only(test_url: str) -> dict:
    """lark-cli update --dry-run 探针 docx:document:write_only"""
    plan = {
        "version": 1,
        "update": {
            "command": "append",
            "doc_format": "markdown",
            "content": "<!-- check-config dry-run, no actual write -->\n",
        },
    }
    plan_fd, plan_path = tempfile.mkstemp(suffix=".json", prefix="check-config-plan-")
    try:
        with open(plan_fd, "w", encoding="utf-8") as f:
            json.dump(plan, f, ensure_ascii=False)
        plan_path = Path(plan_path)
        log_path = plan_path.with_suffix(".log")
        try:
            lark_update(test_url, plan_path, dry_run=True, log_path=log_path)
            return {"ok": True, "method": "lark-cli update --dry-run", "code": 0, "msg": "ok"}
        except RuntimeError as e:
            return {"ok": False, "method": "lark-cli update --dry-run", "code": 0, "msg": str(e)}
        finally:
            log_path.unlink(missing_ok=True)
    finally:
        Path(plan_path).unlink(missing_ok=True)


def _probe_permissions(
    result: CheckResult,
    app_id: str,
    app_secret: str,
    test_url: str,
    skip_update_probe: bool,
) -> None:
    api = FeishuAPIClient(TokenManager(app_id, app_secret))

    # ── docx:document:write_only（lark-cli） ──
    if skip_update_probe:
        result.permissions["docx:document:write_only"] = {
            "ok": True, "skipped": True,
            "method": "lark-cli update --dry-run (skipped)",
            "code": 0, "msg": "skipped",
        }
    else:
        info = _probe_write_only(test_url)
        result.permissions["docx:document:write_only"] = info
        if not info["ok"]:
            result.ok = False

    # ── wiki:wiki:readonly ──
    try:
        token, doc_type = _parse_url(test_url)
        if doc_type == "wiki":
            node = api.get_wiki_node(token)
            if node.get("obj_token"):
                result.permissions["wiki:wiki:readonly"] = {
                    "ok": True, "method": "GET /wiki/v2/spaces/get_node", "code": 0, "msg": "ok",
                }
            else:
                result.permissions["wiki:wiki:readonly"] = {
                    "ok": False, "method": "GET /wiki/v2/spaces/get_node",
                    "code": -1, "msg": "节点返回空",
                }
                result.ok = False
        else:
            result.permissions["wiki:wiki:readonly"] = {
                "ok": True, "skipped": True,
                "method": "GET /wiki/v2/spaces/get_node (URL 非 wiki)",
                "code": 0, "msg": "skipped (non-wiki URL)",
            }
    except HTTPError as e:
        result.permissions["wiki:wiki:readonly"] = _classify_http_error(e, "GET /wiki/v2/spaces/get_node")
        if not result.permissions["wiki:wiki:readonly"]["ok"]:
            result.ok = False
    except RuntimeError as e:
        result.permissions["wiki:wiki:readonly"] = {
            "ok": False, "method": "GET /wiki/v2/spaces/get_node",
            "code": 0, "msg": str(e),
        }
        result.ok = False

    # ── docx:document:readonly ──
    try:
        token, doc_type = _parse_url(test_url)
        if doc_type == "wiki":
            node = api.get_wiki_node(token)
            obj_token = node.get("obj_token", token)
        else:
            obj_token = token
        api.get_docx_content(obj_token)
        result.permissions["docx:document:readonly"] = {
            "ok": True, "method": "GET /docx/v1/documents/{id}/raw_content",
            "code": 0, "msg": "ok",
        }
    except HTTPError as e:
        result.permissions["docx:document:readonly"] = _classify_http_error(
            e, "GET /docx/v1/documents/{id}/raw_content"
        )
        if not result.permissions["docx:document:readonly"]["ok"]:
            result.ok = False
    except RuntimeError as e:
        result.permissions["docx:document:readonly"] = {
            "ok": False, "method": "GET /docx/v1/documents/{id}/raw_content",
            "code": 0, "msg": str(e),
        }
        result.ok = False

    # ── drive:drive:readonly ──
    try:
        resp = api.probe_drive_readonly()
        if resp.get("code") == 0:
            result.permissions["drive:drive:readonly"] = {
                "ok": True, "method": "GET /drive/v1/files?limit=1",
                "code": 0, "msg": "ok",
            }
        else:
            result.permissions["drive:drive:readonly"] = {
                "ok": False, "method": "GET /drive/v1/files?limit=1",
                "code": resp.get("code", -1), "msg": resp.get("msg", ""),
            }
            result.ok = False
    except HTTPError as e:
        result.permissions["drive:drive:readonly"] = _classify_http_error(e, "GET /drive/v1/files?limit=1")
        if not result.permissions["drive:drive:readonly"]["ok"]:
            result.ok = False
    except RuntimeError as e:
        result.permissions["drive:drive:readonly"] = {
            "ok": False, "method": "GET /drive/v1/files?limit=1",
            "code": 0, "msg": str(e),
        }
        result.ok = False

    # ── im:resource ──
    try:
        resp = api.probe_im_resource()
        if resp.get("code") == 0:
            result.permissions["im:resource"] = {
                "ok": True, "method": "GET /im/v1/files/{key}",
                "code": 0, "msg": "ok",
            }
        else:
            feishu_code = resp.get("code", -1)
            msg = resp.get("msg", "")
            if feishu_code in _PERMISSION_DENIED_CODES:
                result.permissions["im:resource"] = {
                    "ok": False, "method": "GET /im/v1/files/{key}",
                    "code": feishu_code, "msg": msg,
                }
                result.ok = False
            else:
                result.permissions["im:resource"] = {
                    "ok": True, "method": "GET /im/v1/files/{key}",
                    "code": feishu_code, "msg": f"已过权限检查（业务错误: {msg}）",
                }
    except HTTPError as e:
        result.permissions["im:resource"] = _classify_http_error(e, "GET /im/v1/files/{key}")
        if not result.permissions["im:resource"]["ok"]:
            result.ok = False
    except RuntimeError as e:
        result.permissions["im:resource"] = {
            "ok": False, "method": "GET /im/v1/files/{key}",
            "code": 0, "msg": str(e),
        }
        result.ok = False


# ── 主入口 ────────────────────────────────────────────

def run_check(
    test_url: str = DEFAULT_URL,
    skip_update_probe: bool = False,
) -> CheckResult:
    """主检查入口；可被其它脚本 import 调用。

    失败时 CheckResult.ok = False 并保留详细失败原因（permissions / token_error）。
    """
    result = CheckResult()

    if not _check_missing(result):
        return result

    app_id, app_secret = resolve_feishu_credentials()
    if not app_id or not app_secret:
        result.token_error = "secrets.local.json 缺少 feishu.app_id / feishu.app_secret"
        result.ok = False
        return result

    if not _check_validity(result, app_id, app_secret):
        return result

    _probe_permissions(result, app_id, app_secret, test_url, skip_update_probe)
    return result


def _print_report(result: CheckResult) -> None:
    print("=== 凭证自检（PRD 同步链路）===")
    print()

    print("[1/3] 凭证缺失检查")
    if result.config_exists:
        print(f"  ✓ 凭证文件 {result.config_path} 存在 (app_id={result.app_id_masked})")
    else:
        print(f"  ✗ 凭证文件 {result.config_path} 不存在")
        print("    提示: 复制 secrets.local.json.example 为 secrets.local.json 并填写 feishu 段")

    if result.lark_cli_ok:
        print(f"  ✓ lark-cli: {result.lark_cli_path}")
    else:
        print(f"  ✗ lark-cli 不可用: {result.lark_cli_path}")
    print()

    print("[2/3] 凭证有效性检查")
    if result.token_valid:
        print("  ✓ tenant_access_token 获取成功")
    else:
        print(f"  ✗ tenant_access_token 获取失败: {result.token_error or 'unknown'}")
    print()

    print("[3/3] 权限检查（5 项）")
    for scope, info in result.permissions.items():
        if info.get("skipped"):
            print(f"  - {scope}  (skipped: {info.get('msg', '')})")
        elif info["ok"]:
            print(f"  ✓ {scope}  ({info['method']})")
        else:
            prefix = f"code={info['code']}, " if info.get("code") else ""
            print(f"  ✗ {scope}  ({prefix}{info['msg']})")
    print()

    if result.ok:
        print("✓ 全部通过")
    else:
        failed = [s for s, i in result.permissions.items()
                  if not i.get("ok") and not i.get("skipped")]
        if failed:
            print(f"✗ 权限不足：{len(failed)}/5 未通过")
            print("  请到飞书开放平台开通：")
            for p in failed:
                print(f"    - {p}")
        elif not result.config_exists:
            print("✗ 凭证缺失：见 [1/3]")
        elif not result.lark_cli_ok:
            print("✗ lark-cli 不可用：见 [1/3]")
        elif not result.token_valid:
            print("✗ 凭证无效：见 [2/3]")


def main() -> int:
    parser = argparse.ArgumentParser(description="凭证 / 权限自检（PRD 同步链路）")
    parser.add_argument("--url", default=DEFAULT_URL, help="用于 docx / wiki 探针的 PRD URL")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式（Agent 解析用）")
    parser.add_argument("--skip-update-probe", action="store_true",
                        help="跳过 docx:document:write_only 探针（lark-cli 写权限）")
    args = parser.parse_args()

    result = run_check(args.url, args.skip_update_probe)

    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False))
    else:
        _print_report(result)

    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
