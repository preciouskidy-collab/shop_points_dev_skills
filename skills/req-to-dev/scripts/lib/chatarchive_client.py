"""企微会话存档图片：通过 wekehome getFileMd5 换取 signUrl。"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from collab_common import CONFIG_DIR

DEFAULT_BASE_URL = "http://app-center-wekehome-manager.ttb.test.ke.com"
DEFAULT_CORP_NAME = "bei_ke"
DEFAULT_BIZ_CODE = "group-operation"
DEFAULT_APP_ID = "group-operation"


def load_chatarchive_config() -> dict[str, Any]:
    cfg: dict[str, Any] = {
        "base_url": DEFAULT_BASE_URL,
        "corp_name": DEFAULT_CORP_NAME,
        "biz_code": DEFAULT_BIZ_CODE,
        "app_id": DEFAULT_APP_ID,
        "secret": "",
        "timeout_sec": 30,
    }

    secrets = CONFIG_DIR / "secrets.local.json"
    if secrets.exists():
        data = json.loads(secrets.read_text(encoding="utf-8"))
        collab = data.get("collab") or {}
        if isinstance(collab.get("chatarchive"), dict):
            for k, v in collab["chatarchive"].items():
                if v is None:
                    continue
                if k == "secret" and not str(v).strip():
                    continue
                cfg[k] = v

    for name in ("agent.local.yaml", "agent.yaml"):
        p = CONFIG_DIR / name
        if not p.exists():
            continue
        try:
            import yaml  # type: ignore

            data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            collab = data.get("collab") or {}
            if isinstance(collab.get("chatarchive"), dict):
                cfg.update({k: v for k, v in collab["chatarchive"].items() if v is not None})
        except ImportError:
            break

    return cfg


def is_chatarchive_configured(cfg: dict[str, Any] | None = None) -> bool:
    cfg = cfg or load_chatarchive_config()
    return bool(str(cfg.get("secret", "")).strip())


def compute_sign_v2(*, biz_code: str, app_id: str, secret: str, timestamp_ms: int) -> str:
    raw = f"bizCode={biz_code}&appId={app_id}&secret={secret}&timestamp={timestamp_ms}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def get_file_by_md5(md5sum: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """调用 getFileMd5，返回 data 字段（含 signUrl）。"""
    cfg = cfg or load_chatarchive_config()
    secret = str(cfg.get("secret", "")).strip()
    if not secret:
        raise RuntimeError(
            "未配置会话存档密钥。请在 secrets.local.json → collab.chatarchive.secret 填写。"
        )

    biz_code = str(cfg.get("biz_code", DEFAULT_BIZ_CODE))
    app_id = str(cfg.get("app_id", DEFAULT_APP_ID))
    corp_name = str(cfg.get("corp_name", DEFAULT_CORP_NAME))
    base_url = str(cfg.get("base_url", DEFAULT_BASE_URL)).rstrip("/")
    timeout = int(cfg.get("timeout_sec", 30))

    ts = int(time.time() * 1000)
    sign_v2 = compute_sign_v2(biz_code=biz_code, app_id=app_id, secret=secret, timestamp_ms=ts)

    params = urllib.parse.urlencode(
        {
            "corpName": corp_name,
            "md5Sum": md5sum,
            "bizCode": biz_code,
        }
    )
    url = f"{base_url}/api/v2/open/chatarchive/file/getFileMd5?{params}"
    headers = {
        "appId": app_id,
        "timestamp": str(ts),
        "signV2": sign_v2,
        "bizCode": biz_code,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"chatarchive HTTP {e.code}: {detail}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"chatarchive 请求失败: {e}") from e

    errno = str(body.get("errno", body.get("code", "")))
    if errno not in ("0", "200", ""):
        raise RuntimeError(f"chatarchive 业务错误: {body}")

    data = body.get("data")
    if not isinstance(data, dict):
        raise RuntimeError(f"chatarchive 响应缺少 data: {body}")

    sign_url = data.get("signUrl") or data.get("signOpenUrl")
    if not sign_url:
        raise RuntimeError(f"chatarchive 未返回 signUrl: {data}")

    return data


def download_signed_file(sign_url: str, dest: Path, *, timeout_sec: int = 60) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(sign_url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            dest.write_bytes(resp.read())
    except urllib.error.URLError as e:
        raise RuntimeError(f"下载图片失败: {e}") from e
    return dest
