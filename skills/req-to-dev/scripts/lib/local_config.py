"""项目内本地凭证（skills/req-to-dev/config/，均已 gitignore）。"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

_SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_DIR = _SCRIPT_DIR.parent.parent / "config"
SECRETS_PATH = CONFIG_DIR / "secrets.local.json"
AGENT_LOCAL_PATH = CONFIG_DIR / "agent.local.yaml"
LARK_CLI_HOME = CONFIG_DIR / "lark-cli-home"
LARK_CLI_CONFIG_PATH = LARK_CLI_HOME / ".lark-cli" / "config.json"

# 历史路径（只读回退，新配置请写入 secrets.local.json）
LEGACY_FEISHU_CONFIG = Path.home() / ".shop-points-dev-skills" / "feishu-config.json"
LEGACY_LARK_CLI_CONFIG = Path.home() / ".lark-cli" / "config.json"


def load_secrets() -> dict[str, Any]:
    if not SECRETS_PATH.exists():
        return {}
    try:
        data = json.loads(SECRETS_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def save_secrets(data: dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    SECRETS_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def resolve_feishu_credentials(
    app_id: str = "",
    app_secret: str = "",
) -> tuple[str, str]:
    """飞书 app_id / app_secret：参数 > secrets.local.json > 历史 ~/.shop-points-dev-skills。"""
    if app_id and app_secret:
        _persist_feishu_credentials(app_id, app_secret)
        return app_id, app_secret

    secrets = load_secrets()
    feishu = secrets.get("feishu") or {}
    sid = str(feishu.get("app_id", "")).strip()
    sec = str(feishu.get("app_secret", "")).strip()
    if sid and sec and not sid.startswith("你的"):
        return sid, sec

    if LEGACY_FEISHU_CONFIG.exists():
        try:
            data = json.loads(LEGACY_FEISHU_CONFIG.read_text(encoding="utf-8"))
            sid = str(data.get("app_id", "")).strip()
            sec = str(data.get("app_secret", "")).strip()
            if sid and sec:
                _persist_feishu_credentials(sid, sec)
                return sid, sec
        except json.JSONDecodeError:
            pass

    return "", ""


def feishu_config_path() -> Path:
    """对外展示/错误提示用的首选配置路径。"""
    return SECRETS_PATH


def _persist_feishu_credentials(app_id: str, app_secret: str) -> None:
    secrets = load_secrets()
    secrets["feishu"] = {"app_id": app_id, "app_secret": app_secret}
    save_secrets(secrets)


def lark_cli_profile(secrets: dict[str, Any] | None = None) -> str:
    secrets = secrets if secrets is not None else load_secrets()
    lark = secrets.get("lark_cli") or {}
    return str(lark.get("profile") or "shop-points-dev")


def ensure_lark_cli_config() -> Path:
    """从 secrets.local.json 生成项目内 lark-cli 配置（明文 appSecret，可提交目录已 gitignore）。"""
    app_id, app_secret = resolve_feishu_credentials()
    if not app_id or not app_secret:
        raise RuntimeError(
            f"未找到飞书凭证。请在 {SECRETS_PATH} 添加 feishu.app_id / feishu.app_secret，"
            f"或复制 secrets.local.json.example 后填写。"
        )

    profile = lark_cli_profile()
    desired = {
        "apps": [
            {
                "name": profile,
                "appId": app_id,
                "appSecret": app_secret,
                "brand": "feishu",
                "users": [],
            }
        ]
    }

    LARK_CLI_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if LARK_CLI_CONFIG_PATH.exists():
        try:
            current = json.loads(LARK_CLI_CONFIG_PATH.read_text(encoding="utf-8"))
            apps = current.get("apps") or []
            for app in apps:
                if app.get("name") == profile and app.get("appId") == app_id:
                    stored = app.get("appSecret")
                    if stored == app_secret or (
                        isinstance(stored, str) and stored and stored != "****"
                    ):
                        return LARK_CLI_CONFIG_PATH
        except json.JSONDecodeError:
            pass

    LARK_CLI_CONFIG_PATH.write_text(
        json.dumps(desired, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return LARK_CLI_CONFIG_PATH


def lark_cli_subprocess_env() -> dict[str, str]:
    """lark-cli 子进程环境：HOME 指向项目内 lark-cli-home。"""
    ensure_lark_cli_config()
    env = os.environ.copy()
    env["HOME"] = str(LARK_CLI_HOME.resolve())
    return env


def load_merged_yaml_section(section: str) -> dict[str, Any]:
    """合并 agent.yaml.example + agent.local.yaml + secrets.local.json 中的某一段。"""
    merged: dict[str, Any] = {}

    for name in ("agent.yaml.example", "agent.local.yaml"):
        path = CONFIG_DIR / name
        if not path.exists():
            continue
        try:
            import yaml  # type: ignore

            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if isinstance(data.get(section), dict):
                merged.update(data[section])
        except ImportError:
            break
        except Exception:
            continue

    secrets = load_secrets()
    if isinstance(secrets.get(section), dict):
        merged.update(secrets[section])
    return merged


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="项目内本地凭证工具")
    parser.add_argument("--ensure-lark-cli", action="store_true", help="从 secrets 生成 lark-cli-home 配置")
    args = parser.parse_args()
    if args.ensure_lark_cli:
        path = ensure_lark_cli_config()
        print(path)
    else:
        parser.print_help()
