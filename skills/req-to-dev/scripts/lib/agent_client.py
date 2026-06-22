"""Agent Collab API 客户端。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from collab_common import CONFIG_DIR


def load_agent_config(config_path: Path | None = None) -> dict:
    if config_path is None:
        for name in ("agent.yaml", "agent.local.yaml"):
            p = CONFIG_DIR / name
            if p.exists():
                config_path = p
                break
        secrets = CONFIG_DIR / "secrets.local.json"
        if config_path is None and secrets.exists():
            data = json.loads(secrets.read_text(encoding="utf-8"))
            return data.get("agent", data)

    if config_path is None or not config_path.exists():
        return {"base_url": "http://localhost:8080", "timeout_sec": 30}

    try:
        import yaml  # type: ignore
    except ImportError:
        return json.loads(config_path.read_text(encoding="utf-8")).get("agent", {})

    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    return data.get("agent", data)


class AgentClient:
    def __init__(self, base_url: str, token: str | None = None, timeout_sec: int = 30):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout_sec = timeout_sec

    @classmethod
    def from_config(cls, config: dict | None = None) -> "AgentClient":
        cfg = config or load_agent_config()
        return cls(
            base_url=cfg.get("base_url", "http://localhost:8080"),
            token=cfg.get("token"),
            timeout_sec=int(cfg.get("timeout_sec", 30)),
        )

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.token:
            headers["X-Collab-Token"] = self.token
        return headers

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict:
        url = f"{self.base_url}{path}"
        if params:
            url = f"{url}?{urlencode({k: v for k, v in params.items() if v is not None})}"
        req = Request(url, headers=self._headers(), method="GET")
        try:
            with urlopen(req, timeout=self.timeout_sec) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Agent API {e.code}: {body}") from e
        except URLError as e:
            raise RuntimeError(f"Agent API 连接失败: {e}") from e

    def get_binding(self, req_id: str) -> dict:
        return self._get(f"/api/v1/collab/bindings/{req_id}")

    def list_messages(
        self,
        req_id: str,
        since: str | None = None,
        until: str | None = None,
        limit: int = 500,
    ) -> dict:
        return self._get(
            "/api/v1/collab/messages",
            {"req_id": req_id, "since": since, "until": until, "limit": limit},
        )
