"""Agent Collab API 客户端。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
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


def _encode_path_segment(value: str) -> str:
    """路径段须 percent-encode，避免非 ASCII req_id 导致 urllib ASCII 编码失败。"""
    return quote(value, safe="")


class AgentClient:
    def __init__(self, base_url: str, timeout_sec: int = 30):
        self.base_url = base_url.rstrip("/")
        self.timeout_sec = timeout_sec

    @classmethod
    def from_config(cls, config: dict | None = None) -> "AgentClient":
        cfg = config or load_agent_config()
        return cls(
            base_url=cfg.get("base_url", "http://localhost:8080"),
            timeout_sec=int(cfg.get("timeout_sec", 30)),
        )

    def _headers(self) -> dict[str, str]:
        return {"Accept": "application/json"}

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        timeout_sec: int | None = None,
    ) -> dict:
        url = f"{self.base_url}{path}"
        if params:
            url = f"{url}?{urlencode({k: v for k, v in params.items() if v is not None})}"
        data = None
        headers = self._headers()
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = Request(url, data=data, headers=headers, method=method)
        timeout = timeout_sec if timeout_sec is not None else self.timeout_sec
        try:
            with urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")
                if not raw.strip():
                    return {}
                return json.loads(raw)
        except HTTPError as e:
            body_text = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Agent API {e.code}: {body_text}") from e
        except URLError as e:
            raise RuntimeError(f"Agent API 连接失败: {e}") from e

    def _get(self, path: str, params: dict[str, Any] | None = None, timeout_sec: int | None = None) -> dict:
        return self._request("GET", path, params=params, timeout_sec=timeout_sec)

    def _post(self, path: str, body: dict[str, Any], timeout_sec: int | None = None) -> dict:
        return self._request("POST", path, body=body, timeout_sec=timeout_sec)

    def get_binding(self, req_id: str) -> dict:
        return self._get(f"/api/v1/collab/bindings/{_encode_path_segment(req_id)}")

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

    def push_state(self, req_id: str, body: dict[str, Any]) -> dict:
        payload = {"reqId": req_id, **body}
        return self._post("/api/v1/collab/push-state", payload)

    def upsert_preview_session(self, body: dict[str, Any]) -> dict:
        return self._post("/api/v1/collab/preview-sessions", body)

    def notify(self, body: dict[str, Any]) -> dict:
        return self._post("/api/v1/collab/notify", body)

    def wait_intents(self, req_id: str, timeout_sec: int = 55) -> dict:
        return self._get(
            "/api/v1/collab/intents/wait",
            {"req_id": req_id, "timeout_sec": timeout_sec},
            timeout_sec=timeout_sec + 10,
        )

    def consume_intent(self, intent_id: int) -> dict:
        return self._post(f"/api/v1/collab/intents/{intent_id}/consume", {})
