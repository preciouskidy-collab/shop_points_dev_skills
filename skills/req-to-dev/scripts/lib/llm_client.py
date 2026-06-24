"""OpenAI 兼容 Chat Completions（联调 digest AI 摘要 + PRD 比对）。"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

from collab_common import CONFIG_DIR


def load_llm_config() -> dict:
    cfg: dict[str, Any] = {
        "enabled": True,
        "base_url": os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        "api_key": os.environ.get("OPENAI_API_KEY", ""),
        "model": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        "timeout_sec": 120,
    }

    secrets = CONFIG_DIR / "secrets.local.json"
    if secrets.exists():
        data = json.loads(secrets.read_text(encoding="utf-8"))
        if isinstance(data.get("llm"), dict):
            cfg.update({k: v for k, v in data["llm"].items() if v is not None})

    for name in ("agent.local.yaml", "agent.yaml"):
        p = CONFIG_DIR / name
        if not p.exists():
            continue
        try:
            import yaml  # type: ignore

            data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            if isinstance(data.get("llm"), dict):
                cfg.update({k: v for k, v in data["llm"].items() if v is not None})
        except ImportError:
            pass

    return cfg


def is_llm_available(cfg: dict | None = None) -> bool:
    cfg = cfg or load_llm_config()
    if cfg.get("enabled") is False:
        return False
    return bool(str(cfg.get("api_key", "")).strip())


def _extract_json(text: str) -> dict:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    return json.loads(text)


def chat_completion_json(
    *,
    system: str,
    user: str,
    cfg: dict | None = None,
) -> dict:
    cfg = cfg or load_llm_config()
    if not is_llm_available(cfg):
        raise RuntimeError(
            "未配置 LLM。请在 skills/req-to-dev/config/secrets.local.json 添加 llm.api_key，"
            "或设置环境变量 OPENAI_API_KEY。"
        )

    base = str(cfg.get("base_url", "")).rstrip("/")
    url = f"{base}/chat/completions"
    payload = {
        "model": cfg.get("model", "gpt-4o-mini"),
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cfg['api_key']}",
        },
        method="POST",
    )
    timeout = int(cfg.get("timeout_sec", 120))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"LLM HTTP {e.code}: {detail}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"LLM 请求失败: {e}") from e

    choices = body.get("choices") or []
    if not choices:
        raise RuntimeError(f"LLM 空响应: {body}")
    content = choices[0].get("message", {}).get("content", "")
    if not content:
        raise RuntimeError(f"LLM 无 content: {body}")
    return _extract_json(content)
