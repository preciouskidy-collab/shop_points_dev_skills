"""lark-cli 封装（飞书 PRD 读写统一适配器）。"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from collab_common import CONFIG_DIR, project_root
from local_config import ensure_lark_cli_config, lark_cli_subprocess_env, load_secrets


def load_lark_config() -> dict:
    data = load_secrets()
    if "lark_cli" in data:
        return data["lark_cli"]

    for name in ("agent.yaml.example", "agent.local.yaml", "agent.yaml"):
        p = CONFIG_DIR / name
        if not p.exists():
            continue
        try:
            import yaml  # type: ignore
            data = yaml.safe_load(p.read_text(encoding="utf-8"))
            if data and "lark_cli" in data:
                return data["lark_cli"]
        except ImportError:
            pass

    return {"binary": "lark-cli"}


def resolve_binary(cfg: dict | None = None) -> str:
    cfg = cfg or load_lark_config()
    binary = cfg.get("binary", "lark-cli")
    path = shutil.which(binary)
    if path:
        return path
    if Path(binary).exists():
        return str(Path(binary).resolve())
    raise RuntimeError(
        f"未找到 lark-cli: {binary}\n"
        "请执行: npm install -g @larksuite/cli\n"
        f"并配置 secrets.local.json 中 feishu 段，或运行: bash skills/req-to-dev/scripts/setup_lark_cli.sh"
    )


def _run(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    try:
        ensure_lark_cli_config()
        env = lark_cli_subprocess_env()
    except RuntimeError:
        env = None
    return subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def fetch(url: str, output_path: Path, cfg: dict | None = None) -> None:
    """lark-cli docs +fetch → 写入 markdown 文件。"""
    cfg = cfg or load_lark_config()
    binary = resolve_binary(cfg)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    args = [
        binary,
        "docs",
        "+fetch",
        "--doc",
        url,
        "--doc-format",
        "markdown",
        "--format",
        cfg.get("fetch_format", "pretty"),
    ]
    result = _run(args, cwd=project_root())
    if result.returncode != 0:
        raise RuntimeError(
            "lark-cli fetch 失败\n"
            f"cmd: {' '.join(args)}\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

    text = result.stdout.strip()
    if not text and result.stderr.strip():
        text = result.stderr.strip()

    if cfg.get("fetch_format", "pretty") == "json":
        try:
            payload = json.loads(text)
            text = (
                payload.get("data", {})
                .get("document", {})
                .get("markdown", text)
            )
        except json.JSONDecodeError:
            pass

    if not text:
        raise RuntimeError("lark-cli fetch 返回空内容")
    output_path.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")


def _load_plan(plan_path: Path) -> dict:
    return json.loads(plan_path.read_text(encoding="utf-8"))


def _collect_plan_updates(plan: dict) -> list[dict]:
    """从 plan.json 解析待执行的 update 列表（支持单条 update 或 updates 数组）。"""
    updates = plan.get("updates")
    if isinstance(updates, list):
        out = [u for u in updates if isinstance(u, dict) and u.get("command")]
        if out:
            return out

    upd = plan.get("update")
    if isinstance(upd, dict) and upd.get("command"):
        return [upd]

    lines = ["## 联调变更", ""]
    for item in plan.get("changes", []):
        if isinstance(item, dict) and item.get("update"):
            out_item = item["update"]
            if isinstance(out_item, dict) and out_item.get("command"):
                return [out_item]
        summary = item.get("summary", str(item)) if isinstance(item, dict) else str(item)
        lines.append(f"- {summary}")
    content = "\n".join(lines).strip() + "\n"
    if plan.get("changes"):
        return [{"command": "append", "doc_format": "markdown", "content": content}]
    return []


def _plan_to_update_args(plan: dict) -> tuple[str, str, str, str | None]:
    """从 plan.json 解析单条 update（兼容旧调用方）。"""
    updates = _collect_plan_updates(plan)
    if not updates:
        return "append", "markdown", "", None
    upd = updates[0]
    return (
        upd.get("command", "append"),
        upd.get("doc_format", "markdown"),
        upd.get("content", ""),
        upd.get("pattern"),
    )


def validate_plan_for_apply(plan: dict, *, allow_append: bool = False) -> None:
    """approve 前校验：PRD 定稿/联调写回须就地修改正文，禁止 append 变更记录节。"""
    if plan.get("plan_source") == "agent_pending":
        raise RuntimeError(
            "plan 仍为 agent_pending：Agent 须先对照材料撰写 plan.json（str_replace），"
            "再执行 finalize-plan。"
        )
    updates = _collect_plan_updates(plan)
    if not updates:
        raise RuntimeError("plan.json 缺少 update/updates，无法写回 PRD。")

    for i, upd in enumerate(updates, 1):
        cmd = upd.get("command", "")
        if cmd == "append" and not allow_append:
            raise RuntimeError(
                f"第 {i} 条变更为 append（文末追加），不符合 PRD 定稿/联调写回规范。\n"
                "应使用 str_replace 就地修改 PRD 正文（或多条 updates[]），"
                "禁止追加「会议纪要变更记录」类章节。\n"
                "调试可加 --allow-append（不推荐）。"
            )
        if cmd == "str_replace" and not (upd.get("pattern") or "").strip():
            raise RuntimeError(f"第 {i} 条 str_replace 缺少 pattern（须为 PRD 中存在的原文）。")


def _validate_approval(
    approval_path: Path,
    plan_path: Path,
    context_id: str,
    patch_id: str,
    context_type: str = "pipeline-collab",
) -> dict:
    """校验 collab_approve 生成的审批文件，防止绕过交互式确认直接写 PRD。"""
    if not approval_path.exists():
        raise RuntimeError(
            "缺少审批文件 approval.json。\n"
            "真实 PRD 写回必须经 collab_approve.py 交互确认（终端输入 y）。"
        )
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    if not approval.get("approved"):
        raise RuntimeError("approval.json 未标记 approved=true")

    aid = approval.get("context_id") or approval.get("req_id")
    if aid != context_id or approval.get("patch_id") != patch_id:
        raise RuntimeError("approval.json 与当前 context/patch 不匹配")
    if approval.get("context_type") and approval.get("context_type") != context_type:
        raise RuntimeError("approval.json context_type 不匹配")

    if approval.get("plan_sha256") != _plan_fingerprint(plan_path):
        raise RuntimeError("plan.json 已变更，请重新 digest 并审批后再写回")

    dry_log = approval_path.parent / "dry_run.log"
    if not dry_log.exists():
        raise RuntimeError("缺少 dry_run.log，请先执行 digest/meeting")
    if "exit=0" not in dry_log.read_text(encoding="utf-8"):
        raise RuntimeError("dry_run 未通过，禁止写回 PRD")
    return approval


def _plan_fingerprint(plan_path: Path) -> str:
    import hashlib

    data = plan_path.read_bytes()
    return hashlib.sha256(data).hexdigest()


def _update(url: str, plan_path: Path, dry_run: bool, log_path: Path, cfg: dict | None = None) -> None:
    cfg = cfg or load_lark_config()
    binary = resolve_binary(cfg)
    plan = _load_plan(plan_path)
    updates = _collect_plan_updates(plan)
    if not updates:
        raise RuntimeError("plan.json 无有效 update/updates")

    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_chunks: list[str] = []
    last_result: subprocess.CompletedProcess[str] | None = None

    for idx, upd in enumerate(updates, 1):
        command = upd.get("command", "append")
        doc_format = upd.get("doc_format", "markdown")
        content = upd.get("content", "")
        pattern = upd.get("pattern")

        args = [
            binary,
            "docs",
            "+update",
            "--api-version",
            "v2",
            "--doc",
            url,
            "--command",
            command,
            "--doc-format",
            doc_format,
            "--content",
            content,
        ]
        if pattern:
            args.extend(["--pattern", pattern])
        if dry_run:
            args.append("--dry-run")

        result = _run(args, cwd=project_root())
        last_result = result
        log_chunks.extend(
            [
                f"=== update {idx}/{len(updates)} ===",
                f"$ {' '.join(args)}",
                f"exit={result.returncode}",
                "--- stdout ---",
                result.stdout or "",
                "--- stderr ---",
                result.stderr or "",
                "",
            ]
        )
        if result.returncode != 0:
            log_path.write_text("\n".join(log_chunks), encoding="utf-8")
            raise RuntimeError(f"lark-cli update 失败（第 {idx} 条），详见 {log_path}")

    log_path.write_text("\n".join(log_chunks), encoding="utf-8")
    if last_result and last_result.returncode != 0:
        raise RuntimeError(f"lark-cli update 失败，详见 {log_path}")


def update_dry_run(url: str, plan_path: Path, log_path: Path, cfg: dict | None = None) -> None:
    """仅 dry-run 预览，不会写 PRD。"""
    _update(url, plan_path, dry_run=True, log_path=log_path, cfg=cfg)


def apply_prd(
    url: str,
    plan_path: Path,
    log_path: Path,
    approval_path: Path,
    context_id: str,
    patch_id: str,
    context_type: str = "pipeline-collab",
    cfg: dict | None = None,
    *,
    req_id: str | None = None,
) -> None:
    """真实写回 PRD：必须携带 collab_approve 生成的 approval.json。"""
    cid = req_id or context_id
    _validate_approval(approval_path, plan_path, cid, patch_id, context_type)
    _update(url, plan_path, dry_run=False, log_path=log_path, cfg=cfg)


def update(url: str, plan_path: Path, dry_run: bool, log_path: Path, cfg: dict | None = None) -> None:
    """兼容入口：仅允许 dry_run=True。"""
    if dry_run:
        update_dry_run(url, plan_path, log_path, cfg=cfg)
        return
    raise RuntimeError(
        "禁止直接 apply PRD。\n"
        "请使用 collab_approve.py 交互审批后写回。"
    )


def check_available(cfg: dict | None = None) -> tuple[bool, str]:
    try:
        binary = resolve_binary(cfg)
        result = _run([binary, "--help"])
        return result.returncode == 0, binary
    except RuntimeError as e:
        return False, str(e)
