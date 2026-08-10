#!/usr/bin/env python3
"""技术方案确认：应用 design_plan + 解锁 plan-approve。"""

from __future__ import annotations

import argparse
import getpass
import json
import subprocess
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parent / "lib"
_SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_LIB))
sys.path.insert(0, str(_SCRIPTS))

from agent_client import AgentClient  # noqa: E402
from collab_common import append_log, find_change_dir, iso_now, load_state, save_state  # noqa: E402
from design_plan_builder import (  # noqa: E402
    apply_design_plan,
    collect_design_updates,
    design_patch_dir,
    parse_design_chat_confirm_phrase,
    validate_design_plan,
)
from pipeline_regress import clear_collab_regression  # noqa: E402


def _apply_pull_intent(args: argparse.Namespace) -> None:
    if not getattr(args, "pull_intent_id", None):
        return
    client = AgentClient.from_config()
    intent = client.consume_intent(int(args.pull_intent_id))
    if intent.get("action") != "plan_approve":
        raise RuntimeError(f"intent action 应为 plan_approve，收到: {intent.get('action')}")
    payload = json.loads(intent.get("payloadJson") or "{}")
    if not args.patch:
        args.patch = intent.get("patchId") or payload.get("patch_id")
    if not args.approver:
        args.approver = payload.get("approver")
    if not args.chat_confirm:
        args.chat_confirm = payload.get("chat_confirm", "")


def main() -> int:
    parser = argparse.ArgumentParser(description="技术方案 approve-design")
    parser.add_argument("--req-id", required=True)
    parser.add_argument("--patch", default=None)
    parser.add_argument("--approver", default=None)
    parser.add_argument("--chat-confirm", default=None)
    parser.add_argument("--pull-intent-id", type=int, default=None)
    parser.add_argument("--note", default="")
    args = parser.parse_args()

    try:
        _apply_pull_intent(args)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    change_dir = find_change_dir(args.req_id)
    state = load_state(change_dir)
    req_id = state.get("req_id", args.req_id)
    collab = state.setdefault("collaboration", {})

    patch_id = args.patch or collab.get("tech_design_review", {}).get("active_patch")
    if args.chat_confirm:
        parsed = parse_design_chat_confirm_phrase(args.chat_confirm)
        if parsed:
            patch_id = parsed.get("patch") or patch_id
            if not args.approver:
                args.approver = parsed["approver"].strip("<>")
    if not patch_id:
        print("ERROR: 缺少 --patch", file=sys.stderr)
        return 1

    pdir = design_patch_dir(change_dir, patch_id)
    meta_path = pdir / "meta.json"
    if not meta_path.exists():
        print(f"ERROR: 缺少 {meta_path}", file=sys.stderr)
        return 1
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    if not args.approver and not args.pull_intent_id:
        args.approver = getpass.getuser()
        print(f"WARN: 无 --chat-confirm / --pull-intent-id，使用 approver={args.approver}")

    plan_path = pdir / "design_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    try:
        updates = collect_design_updates(plan)
        if updates:
            validate_design_plan(plan)
            applied = apply_design_plan(change_dir, plan)
        else:
            validate_design_plan(plan, require_updates=False)
            applied = []
    except (ValueError, FileNotFoundError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    approved_at = iso_now()
    meta["status"] = "design_applied"
    meta["approver"] = args.approver
    meta["approved_at"] = approved_at
    meta["approval_note"] = args.note
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    (pdir / "approval.json").write_text(
        json.dumps(
            {
                "req_id": req_id,
                "patch_id": patch_id,
                "approver": args.approver,
                "approved_at": approved_at,
                "applied_targets": applied,
                "chat_confirm": args.chat_confirm,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    collab["phase"] = "idle"
    tdr = collab.setdefault("tech_design_review", {})
    tdr["ended_at"] = approved_at
    tdr.setdefault("patches", {})[patch_id] = {"status": "design_applied", "approved_at": approved_at}
    state["plan_design_unlocked"] = True
    state["plan_design_unlocked_at"] = approved_at
    state["plan_design_patch"] = patch_id
    save_state(change_dir, state)
    append_log(change_dir, f"TECH-DESIGN approve {patch_id} targets={applied}")

    print(f"✓ 已应用方案修订: {', '.join(applied) or '(无 updates)'}")

    try:
        from collab_push_state import push_state_for_change  # noqa: WPS433

        push_state_for_change(change_dir, state)
        print("✓ 已 push-state phase=idle")
    except RuntimeError as e:
        print(f"WARN: push-state 失败: {e}")

    stages = state.get("stages", [])
    idx = int(state.get("current_stage", 0))
    current = stages[idx] if stages and 0 <= idx < len(stages) else {}
    if current.get("id") == "plan-approve" and current.get("status") == "running":
        if clear_collab_regression(state):
            save_state(change_dir, state)
        wf = _SCRIPTS / "run_workflow.py"
        proc = subprocess.run(
            [sys.executable, str(wf), "approve", "--name", req_id],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            print(f"ERROR: run_workflow approve 失败: {proc.stderr or proc.stdout}", file=sys.stderr)
            return 1
        print(proc.stdout)
        print("✅ plan-approve 已通过，Pipeline 已进入编码阶段")
    else:
        print(
            f"ℹ 当前 stage={current.get('id')}，未自动 approve；"
            f"请手动: python3 run_workflow.py approve --name {req_id}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
