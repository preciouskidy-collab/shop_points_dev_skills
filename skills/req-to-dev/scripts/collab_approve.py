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
sys.path.insert(0, str(Path(__file__).resolve().parent))  # 同目录 import

from collab_check_config import _print_report, run_check  # noqa: E402
from agent_client import AgentClient  # noqa: E402
from collab_common import append_log, find_change_dir, iso_now, load_state, normalize_feishu_url, save_state  # noqa: E402
from lark_cli import _plan_fingerprint, apply_prd, validate_plan_for_apply  # noqa: E402
from patch_builder import parse_chat_confirm_phrase  # noqa: E402
from prd_resync import run_prd_resync  # noqa: E402
from prd_sync_session import append_session_log, resolve_pre_pipeline_patch, save_session  # noqa: E402


def _is_link1_meeting(state: dict, meta: dict) -> bool:
    return (
        state.get("trigger", {}).get("type") == "meeting"
        or meta.get("source") == "feishu_meeting"
    )


def _apply_pull_intent(args: argparse.Namespace) -> None:
    if not getattr(args, "pull_intent_id", None):
        return
    client = AgentClient.from_config()
    intent = client.consume_intent(int(args.pull_intent_id))
    payload = json.loads(intent.get("payloadJson") or "{}")
    if not args.patch:
        args.patch = intent.get("patchId") or payload.get("patch_id")
    if not args.approver:
        args.approver = payload.get("approver")
    if not args.chat_confirm:
        args.chat_confirm = payload.get("chat_confirm", "")
    args.mode = "agent-chat"


def _load_collab_settings() -> dict:
    from collab_common import CONFIG_DIR  # noqa: WPS433

    for name in ("agent.local.yaml", "agent.yaml"):
        p = CONFIG_DIR / name
        if p.exists():
            try:
                import yaml  # type: ignore

                data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
                return data.get("collab", {})
            except ImportError:
                break
    secrets = CONFIG_DIR / "secrets.local.json"
    if secrets.exists():
        data = json.loads(secrets.read_text(encoding="utf-8"))
        return data.get("collab", {})
    return {}


def _finish_link1_approve(change_dir: Path, state: dict, req_id: str) -> None:
    prd_url = state.get("trigger", {}).get("url")
    if prd_url:
        from lark_cli import fetch  # noqa: WPS433

        prd_path = change_dir / "request" / "prd.md"
        prd_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fetch(prd_url, prd_path)
            append_log(change_dir, "PRD_REVIEW refetch request/prd.md")
            print("✓ 本地 request/prd.md 已从飞书 refetch")
        except RuntimeError as e:
            print(f"WARN: refetch 本地 PRD 失败: {e}")

    collab = state.setdefault("collaboration", {})
    collab["phase"] = "idle"
    pr = collab.setdefault("prd_review", {})
    pr["ended_at"] = iso_now()
    save_state(change_dir, state)
    append_log(change_dir, "PRD_REVIEW ended phase=idle")

    try:
        from collab_push_state import push_state_for_change  # noqa: WPS433

        push_state_for_change(change_dir, state)
        print("✓ 已 push-state phase=idle")
    except RuntimeError as e:
        print(f"WARN: push-state 失败: {e}")

    cfg = _load_collab_settings()
    if cfg.get("auto_advance_after_prd_approve"):
        print("\n正在 auto_advance（collab.auto_advance_after_prd_approve=true）...")
        import subprocess

        proc = subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parent / "run_workflow.py"), "advance", "--name", req_id],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            print(f"WARN: auto advance 失败: {proc.stderr or proc.stdout}")
        else:
            print(proc.stdout)
    else:
        print("\n--- 链路1 定稿完成 ---")
        print("phase=idle；开发前请显式 advance 或 run_workflow init 后续阶段")

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
    return text


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
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    try:
        validate_plan_for_apply(plan, allow_append=args.allow_append)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    status = meta.get("status")
    if status != "draft" and not (args.force and status == "prd_applied"):
        print(f"ERROR: patch 状态为 {status}，仅 draft 可 approve", file=sys.stderr)
        return 1

    # 预检：凭证 / 权限
    if not args.skip_preflight:
        preflight = run_check(test_url=prd_url)
        if not preflight.ok:
            _print_report(preflight)
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
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    link1 = _is_link1_meeting(state, meta)
    try:
        validate_plan_for_apply(plan, allow_append=args.allow_append)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    status = meta.get("status")
    if status != "draft" and not (args.force and status == "prd_applied"):
        print(f"ERROR: patch 状态为 {status}，仅 draft 可 approve", file=sys.stderr)
        return 1

    # 预检：凭证 / 权限
    if not args.skip_preflight:
        preflight = run_check(test_url=prd_url)
        if not preflight.ok:
            _print_report(preflight)
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
    if getattr(args, "pull_intent_id", None):
        record["pull_intent_id"] = args.pull_intent_id
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
    meta["ready_for_resync"] = not link1
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    collab = state.setdefault("collaboration", {})
    collab.setdefault("patches", {})[args.patch] = {"status": "prd_applied", "approved_at": approved_at}
    save_state(change_dir, state)
    append_log(change_dir, f"COLLAB approve {args.patch} mode={args.mode} approver={args.approver}")

    print("✅ PRD 已更新")

    if link1:
        _finish_link1_approve(change_dir, state, req_id)
        return 0

    if not args.skip_resync:
        print(f"\n正在自动 prd resync · {args.patch} ...")
        try:
            result = run_prd_resync(
                change_dir,
                state,
                req_id=req_id,
                prd_url=prd_url,
                patch_id=args.patch,
                tier_override=getattr(args, "tier", None),
            )
            print(f"✅ prd resync 完成 · Tier-{result['tier']} · patch {result['patch_id']}")
            analysis = result.get("tier_analysis") or {}
            if analysis.get("change_summary"):
                print(f"   摘要: {analysis['change_summary']}")
            regression = result.get("regression")
            if regression:
                from pipeline_regress import format_regression_message  # noqa: WPS433

                print(f"🔄 {format_regression_message(regression)}")
            elif result.get("needs_collab_reapprove"):
                print("⚠ 变更需在 plan-approve 前更新契约/详设")
            elif result["handoff_stale"]:
                print("⚠ handoff 可能过期，编码后请认真做契约对齐")
            print(f"✓ current_stage: {result['resume_stage']}")
        except Exception as e:
            print(f"ERROR: 自动 resync 失败: {e}", file=sys.stderr)
            print(f"请手动: python3 prd_resync.py --req-id {req_id} --patch {args.patch}", file=sys.stderr)
            return 1
    else:
        print(f"下一步: python3 prd_resync.py --req-id {req_id} --patch {args.patch}")
    return 0


def _apply_chat_confirm_args(args: argparse.Namespace) -> None:
    if not args.chat_confirm:
        return
    parsed = parse_chat_confirm_phrase(args.chat_confirm)
    if not parsed:
        return
    if not args.patch:
        args.patch = parsed["patch"]
    if not args.approver:
        args.approver = parsed["approver"]


def main() -> int:
    parser = argparse.ArgumentParser(description="PRD 写回确认（默认 Agent 聊天交互）")
    parser.add_argument("--patch", default=None)
    parser.add_argument("--approver", default=None)
    parser.add_argument("--req-id", default=None)
    parser.add_argument("--prd-url", default=None)
    parser.add_argument("--note", default="")
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--skip-resync",
        action="store_true",
        help="链路 2 approve 成功后不自动 prd resync（默认自动 resync）",
    )
    parser.add_argument(
        "--tier",
        type=int,
        choices=(1, 2, 3),
        default=None,
        help="PRD resync Tier（Agent 判定；或已写入 patch/tier_analysis.json）",
    )
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
    parser.add_argument(
        "--allow-append",
        action="store_true",
        help="不推荐：允许 append 写回（默认仅 str_replace 就地修改）",
    )
    parser.add_argument(
        "--skip-preflight", action="store_true",
        help="跳过凭证 / 权限预检（调试用）",
    )
    parser.add_argument(
        "--pull-intent-id",
        type=int,
        default=None,
        help="从 Agent 消费 approval_intent 并自动填充 patch/approver/chat-confirm",
    )
    args = parser.parse_args()
    _apply_pull_intent(args)
    _apply_chat_confirm_args(args)

    if not args.patch or not args.approver:
        print(
            "ERROR: 需要 --patch 与 --approver，或在 --chat-confirm 中使用"
            "「确认 patch-NNN <nonce> approver <姓名>」格式",
            file=sys.stderr,
        )
        return 1

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
