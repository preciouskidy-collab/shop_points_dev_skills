"""企微协作 intent 消费（修订轮必须在 prepare 成功后 consume，避免 wait 重复拉取）。"""

from __future__ import annotations

import sys
from typing import Any

from agent_client import AgentClient


def consume_collab_intent(
    intent_id: int,
    *,
    req_id: str | None = None,
    expected_actions: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """
    消费 Agent 意图队列中的 pending intent。

    - approve / plan_approve：由 collab_approve / approve_design 消费
    - meeting_revise / tech_revise：**必须**在 meeting-revise / tech-revise prepare 成功后调用
    """
    client = AgentClient.from_config()
    intent = client.consume_intent(int(intent_id))
    action = intent.get("action")
    iid = intent.get("reqId") or intent.get("req_id")
    if req_id and iid and iid != req_id:
        raise RuntimeError(
            f"intent req_id 不匹配: intent={iid!r} expected={req_id!r} intent_id={intent_id}"
        )
    if expected_actions and action not in expected_actions:
        print(
            f"WARN: intent action={action!r} 不在预期 {expected_actions}，仍已消费 intent_id={intent_id}",
            file=sys.stderr,
        )
    status = intent.get("status")
    print(f"✓ intent 已消费: id={intent_id} action={action} status={status}", file=sys.stderr)
    return intent


def consume_revise_intent(intent_id: int, *, req_id: str, action: str) -> dict[str, Any]:
    """修订轮 intent 消费（meeting_revise / tech_revise）。"""
    if action not in ("meeting_revise", "tech_revise"):
        raise ValueError(f"非修订 intent: {action}")
    return consume_collab_intent(
        intent_id,
        req_id=req_id,
        expected_actions=(action,),
    )
