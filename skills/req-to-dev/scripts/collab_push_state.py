#!/usr/bin/env python3
"""将 pipeline_state.collaboration 镜像同步到 Agent collab_req_state。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parent / "lib"
sys.path.insert(0, str(_LIB))

from agent_client import AgentClient  # noqa: E402
from collab_common import find_change_dir, load_state  # noqa: E402


def build_push_body(state: dict) -> dict:
    collab = state.get("collaboration", {})
    pr = collab.get("prd_review", {})
    return {
        "phase": collab.get("phase", "prd_review"),
        "revisionCursor": pr.get("revision_cursor"),
        "prdReviewEndedAt": pr.get("ended_at"),
        "collabStartedAt": (collab.get("collab") or {}).get("started_at"),
        "stateJson": json.dumps(collab, ensure_ascii=False),
    }


def push_state_for_change(change_dir: Path, state: dict | None = None) -> dict:
    state = state or load_state(change_dir)
    req_id = state.get("req_id") or change_dir.name
    client = AgentClient.from_config()
    body = build_push_body(state)
    return client.push_state(req_id, body)


def main() -> int:
    parser = argparse.ArgumentParser(description="同步协作 phase 到 Agent")
    parser.add_argument("--req-id", required=True)
    args = parser.parse_args()

    try:
        change_dir = find_change_dir(args.req_id)
        result = push_state_for_change(change_dir)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (RuntimeError, FileNotFoundError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
