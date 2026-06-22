#!/usr/bin/env python3
"""PRD 写回确认：默认 Agent 聊天交互；可选终端模式。"""

from __future__ import annotations

import argparse
import getpass
import json
import sys
from pathlib import Path
from typing import Any

_LIB = Path(__file__).resolve().parent / "lib"
sys.path.insert(0, str(_LIB))

from collab_common import append_log, find_change_dir, iso_now, load_state, normalize_feishu_url, save_state  # noqa: E402
from lark_cli import _plan_fingerprint, apply_prd  # noqa: E402
from prd_sync_session import append_session_log, resolve_pre_pipeline_patch, save_session  # noqa: E402

_CONFIRM_WORDS = ("确认", "同意", "approve", "可写回", "可以写回", "继续写回")


def _confirm(prompt: str) -> str:
    try:
        return input(prompt)
    except EOFError:
        return ""


def _validate_chat_confirm(chat_confirm: str, patch_id: str, nonce: str) -> str:
    text = chat_confirm.strip()
    if not text:
        raise ValueError("chat-confirm 为空")
    if patch_id not in text:
        raise ValueError(f"确认语须包含 patch 编号 `{patch_id}`")
    if nonce.lower() not in text.lower():
        raise ValueError(f"确认语须包含验证码 `{nonce}`（见 human_summary）")
    lowered = text.lower()
    if lowered in ("y", "yes") or any(w in text for w in _CONFIRM_WORDS):
        return text
    raise ValueError("确认语须明确表达同意，例如：「确认 patch-001 abc123 approver 周美琪」")


def _resolve_approval(
    args: argparse.Namespace,
    *,
    meta: dict,
    summary_path: Path,
    dry_log: Path,
    prd_url: str,
    context_label: str,
) -> tuple[str, str, str] | None:
    """返回 (confirmer, note, chat_confirm_text)；取消则 None。"""
    if summary_path.exists():
        print(summary_path.read_text(encoding="utf-8"))

    if not dry_log.exists() or "exit=0" not in dry_log.read_text(encoding="utf-8"):
        print("ERROR: dry_run 未通过，禁止写回 PRD", file=sys.stderr)
        raise SystemExit(1)

    print(f"【dry-run 日志】{dry_log}")
    print(f"【PRD】{prd_url}")
    print(f"\nPM designated approver: {args.approver}\n")

    nonce = meta.get("approval_nonce", "")
    if not nonce:
        print("ERROR: meta.json 缺少 approval_nonce，请重新执行 meeting/digest", file=sys.stderr)
        raise SystemExit(1)

    if args.mode == "agent-chat":
        if not args.chat_confirm:
            print(
                f"ERROR: Agent 聊天模式需要 --chat-confirm（用户原话，须含 {args.patch} 与验证码 {nonce}）",
                file=sys.stderr,
            )
            raise SystemExit(1)
        try:
            chat_text = _validate_chat_confirm(args.chat_confirm, args.patch, nonce)
        except ValueError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            raise SystemExit(1)
        confirmer = args.confirmed_by.strip() or args.approver
        note = args.note.strip() or chat_text
        return confirmer, note, chat_text

    if not sys.stdin.isatty():
        print(
            "ERROR: 终端模式需要 TTY；在 Cursor/Claude Code 请用默认 --mode agent-chat",
            file=sys.stderr,
        )
        raise SystemExit(1)

    if _confirm("PM 已确认，可写回 PRD？ [y/N]: ").strip().lower() != "y":
        print("已取消，未写 PRD。")
        return None

    confirmer = _confirm(f"确认人（记录用） [{getpass.getuser()}]: ").strip() or getpass.getuser()
    note = args.note.strip() or _confirm("补充说明（可空）: ").strip()
    return confirmer, note, ""


def _write_approval(
    approval_path: Path,
    *,
    context_type: str,
    context_id: str,
    patch_id: str,
    prd_url: str | None,
    approver: str,
    confirmer: str,
    note: str,
    plan_path: Path,
    mode: str,
    chat_confirm: str,
) -> None:
    record: dict[str, Any] = {
        "approved": True,
        "context_type": context_type,
        "context_id": context_id,
        "patch_id": patch_id,
        "approver": approver,
        "confirmed_by": confirmer,
        "approval_note": note,
        "approved_at": iso_now(),
        "plan_sha256": _plan_fingerprint(plan_path),
        "approval_mode": mode,
        "interactive": mode == "terminal",
    }
    if prd_url:
        record["prd_url"] = prd_url
    if mode == "agent-chat":
        record["channel"] = "agent-chat"
        record["user_chat_confirmation"] = chat_confirm
    approval_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")


def _approve_pre_pipeline(args: argparse.Namespace) -> int:
    prd_url = normalize_feishu_url(args.prd_url)
    pdir, session, prd_url = resolve_pre_pipeline_patch(prd_url, args.patch)
    context_id = session["session_id"]

    meta_path = pdir / "meta.json"
    plan_path = pdir / "plan.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    status = meta.get("status")
    if status != "draft" and not (args.force and status == "prd_applied"):
        print(f"ERROR: patch 状态为 {status}，仅 draft 可 approve", file=sys.stderr)
        return 1

    print("=" * 54)
    print(f"  PRD 写回确认 · {args.patch} · pre-pipeline")
    print(f"  session: {context_id} · mode: {args.mode}")
    print("=" * 54)

    resolved = _resolve_approval(
        args,
        meta=meta,
        summary_path=pdir / "human_summary.md",
        dry_log=pdir / "dry_run.log",
        prd_url=prd_url,
        context_label=context_id,
    )
    if resolved is None:
        return 0
    confirmer, note, chat_confirm = resolved
    approved_at = iso_now()

    approval_path = pdir / "approval.json"
    _write_approval(
        approval_path,
        context_type="pre-pipeline",
        context_id=context_id,
        patch_id=args.patch,
        prd_url=prd_url,
        approver=args.approver,
        confirmer=confirmer,
        note=note,
        plan_path=plan_path,
        mode=args.mode,
        chat_confirm=chat_confirm,
    )

    print("\n正在执行 lark-cli apply（已通过审批）...")
    apply_prd(
        prd_url,
        plan_path,
        pdir / "apply.log",
        approval_path,
        context_id=context_id,
        patch_id=args.patch,
        context_type="pre-pipeline",
    )

    meta["status"] = "prd_applied"
    meta["approver"] = args.approver
    meta["approved_at"] = approved_at
    meta["approval_note"] = note
    meta["confirmed_by"] = confirmer
    meta["approval_mode"] = args.mode
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    session.setdefault("patches", {})[args.patch] = {"status": "prd_applied", "approved_at": approved_at}
    save_session(prd_url, session)
    append_session_log(prd_url, f"approve {args.patch} mode={args.mode} approver={args.approver}")

    print("✅ PRD 已更新（pre-pipeline 定稿完成）")
    return 0


def _approve_pipeline_collab(args: argparse.Namespace) -> int:
    change_dir = find_change_dir(args.req_id)
    state = load_state(change_dir)
    req_id = state.get("req_id") or state.get("name") or args.req_id
    prd_url = state.get("trigger", {}).get("url")
    if not prd_url:
        print("ERROR: pipeline_state.trigger.url 缺失", file=sys.stderr)
        return 1

    pdir = change_dir / "collaboration" / args.patch
    meta_path = pdir / "meta.json"
    plan_path = pdir / "plan.json"
    if not plan_path.exists():
        print(f"ERROR: 缺少 {plan_path}", file=sys.stderr)
        return 1

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    status = meta.get("status")
    if status != "draft" and not (args.force and status == "prd_applied"):
        print(f"ERROR: patch 状态为 {status}，仅 draft 可 approve", file=sys.stderr)
        return 1

    print("=" * 54)
    print(f"  PRD 写回确认 · {args.patch} · {req_id} · mode: {args.mode}")
    print("=" * 54)

    resolved = _resolve_approval(
        args,
        meta=meta,
        summary_path=pdir / "human_summary.md",
        dry_log=pdir / "dry_run.log",
        prd_url=prd_url,
        context_label=req_id,
    )
    if resolved is None:
        return 0
    confirmer, note, chat_confirm = resolved
    approved_at = iso_now()

    approval_path = pdir / "approval.json"
    _write_approval(
        approval_path,
        context_type="pipeline-collab",
        context_id=req_id,
        patch_id=args.patch,
        prd_url=None,
        approver=args.approver,
        confirmer=confirmer,
        note=note,
        plan_path=plan_path,
        mode=args.mode,
        chat_confirm=chat_confirm,
    )
    record = json.loads(approval_path.read_text(encoding="utf-8"))
    record["req_id"] = req_id
    approval_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n正在执行 lark-cli apply（已通过审批）...")
    apply_prd(
        prd_url,
        plan_path,
        pdir / "apply.log",
        approval_path,
        context_id=req_id,
        patch_id=args.patch,
        context_type="pipeline-collab",
    )

    meta["status"] = "prd_applied"
    meta["approver"] = args.approver
    meta["approved_at"] = approved_at
    meta["approval_note"] = note
    meta["confirmed_by"] = confirmer
    meta["approval_mode"] = args.mode
    meta["ready_for_resync"] = True
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    collab = state.setdefault("collaboration", {})
    collab.setdefault("patches", {})[args.patch] = {"status": "prd_applied", "approved_at": approved_at}
    save_state(change_dir, state)
    append_log(change_dir, f"COLLAB approve {args.patch} mode={args.mode} approver={args.approver}")

    print("✅ PRD 已更新")
    print(f"下一步: python3 prd_resync.py --req-id {req_id}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="PRD 写回确认（默认 Agent 聊天交互）")
    parser.add_argument("--patch", required=True)
    parser.add_argument("--approver", required=True)
    parser.add_argument("--req-id", default=None)
    parser.add_argument("--prd-url", default=None)
    parser.add_argument("--note", default="")
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--mode",
        choices=("agent-chat", "terminal"),
        default="agent-chat",
        help="agent-chat：用户在对话中确认后 Agent 代跑（默认）；terminal：本机终端输入 y",
    )
    parser.add_argument(
        "--chat-confirm",
        default="",
        help="agent-chat 模式：用户在对话中的原话（须含 patch 编号与 approval_nonce）",
    )
    parser.add_argument(
        "--confirmed-by",
        default="",
        help="agent-chat 模式：记录实际确认人（默认取 approver）",
    )
    args = parser.parse_args()

    if args.prd_url and args.req_id:
        print("ERROR: --prd-url 与 --req-id 二选一", file=sys.stderr)
        return 1
    if args.prd_url:
        return _approve_pre_pipeline(args)
    if args.req_id:
        return _approve_pipeline_collab(args)

    print("ERROR: 需要 --prd-url 或 --req-id", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
