"""协作 bootstrap 仓库推断与 scope_hint 应用。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_REPOS = {
    "backend": {
        "shop-points": "/Users/qidi/IdeaProjects/shop-points",
        "shop-points-lottery": "/Users/qidi/IdeaProjects/shop-points-lottery",
    },
    "frontend": {
        "pc": "/Users/qidi/IdeaProjects/store-integral",
        "h5": "/Users/qidi/IdeaProjects/store-integral-h5",
    },
}

SCOPE_HINT_FILENAME = "scope_hint.json"
SCOPE_HINT_TEMPLATE = {
    "project": None,
    "target_path": None,
    "frontend_scope": "partial",
    "mall_scope": "none",
    "surfaces": ["pc"],
    "integration_mode": "local",
    "e2e_browser": "cursor",
    "deploy_modules": ["shop-points"],
    "inference_note": "待 Cursor 对照 PRD + knowledge/project-atlas.md 填写",
}


def detect_project(target_path: str) -> str:
    p = target_path.lower().rstrip("/")
    if "shop-points-lottery" in p:
        return "shop-points-lottery"
    return "shop-points"


def build_repos_state(
    backend_target: str,
    *,
    frontend_pc: str | None = None,
    frontend_h5: str | None = None,
    branch: str,
) -> dict:
    return {
        "backend": {
            "shop-points": {
                "path": backend_target,
                "project": detect_project(backend_target),
                "branch": branch,
            }
        },
        "frontend": {
            "pc": {
                "path": frontend_pc or DEFAULT_REPOS["frontend"]["pc"],
                "dayu_module": "store-integral-cdn",
                "branch": branch,
            },
            "h5": {
                "path": frontend_h5 or DEFAULT_REPOS["frontend"]["h5"],
                "dayu_module": "store-integral-h5",
                "branch": branch,
            },
        },
    }


def apply_scope_hint(state: dict, hint: dict[str, Any], *, branch: str | None = None) -> dict:
    """将 scope_hint.json 写入 pipeline_state。"""
    branch = branch or state.get("branch") or f"feature/{state['req_id']}"
    project = hint.get("project") or "shop-points"
    default_backend = DEFAULT_REPOS["backend"].get(
        project, DEFAULT_REPOS["backend"]["shop-points"]
    )
    target_path = hint.get("target_path") or default_backend

    frontend_pc = None
    frontend_h5 = None
    surfaces = hint.get("surfaces") or ["h5"]
    if "pc" in surfaces:
        frontend_pc = DEFAULT_REPOS["frontend"]["pc"]
    if "h5" in surfaces:
        frontend_h5 = DEFAULT_REPOS["frontend"]["h5"]

    state["target_path"] = target_path
    state["project"] = project
    state["branch"] = branch
    state["surfaces"] = surfaces
    state["repos"] = build_repos_state(
        target_path,
        frontend_pc=frontend_pc,
        frontend_h5=frontend_h5,
        branch=branch,
    )
    state["scope_hint"] = hint
    return state


def write_scope_hint_template(change_dir: Path) -> Path:
    path = change_dir / SCOPE_HINT_FILENAME
    if not path.exists():
        path.write_text(
            json.dumps(SCOPE_HINT_TEMPLATE, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return path


def load_scope_hint(change_dir: Path) -> dict[str, Any] | None:
    path = change_dir / SCOPE_HINT_FILENAME
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not data.get("project") and not data.get("target_path"):
        return None
    return data
