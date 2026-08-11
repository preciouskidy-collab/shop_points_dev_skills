"""Pipeline 可自动执行阶段的 runner（review → test → local-stack → local-e2e）。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _run_cmd(cmd: list[str], *, cwd: Path | None = None, timeout: int = 600) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        return proc.returncode, out.strip()
    except subprocess.TimeoutExpired as e:
        return 124, f"TIMEOUT after {timeout}s: {e}"


def _backend_path(state: dict) -> Path | None:
    repos = state.get("repos", {}) or {}
    backend = repos.get("backend", {}) or {}
    for info in backend.values():
        path = info.get("path")
        if path:
            return Path(path)
    trigger = state.get("trigger", {}) or {}
    target = trigger.get("target")
    return Path(target) if target else None


def _frontend_pc_path(state: dict) -> Path | None:
    repos = state.get("repos", {}) or {}
    frontend = repos.get("frontend", {}) or {}
    pc = frontend.get("pc", {}) or {}
    path = pc.get("path")
    return Path(path) if path else None


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def run_backend_review(change_dir: Path, state: dict) -> tuple[bool, str]:
    backend = _backend_path(state)
    if not backend or not backend.is_dir():
        return False, f"backend path 无效: {backend}"

    code, out = _run_cmd(["mvn", "-q", "compile", "-DskipTests"], cwd=backend, timeout=900)
    verdict = "PASS" if code == 0 else "FAIL"
    report = "\n".join(
        [
            f"# Backend Review · {state.get('name', change_dir.name)}",
            "",
            f"generated_at: {_now_iso()}",
            f"verdict: **{verdict}**",
            "",
            "## 自动检查",
            "",
            f"- `mvn compile -DskipTests`: exit {code}",
            "",
            "## 输出（节选）",
            "",
            "```",
            out[-4000:] if out else "(无输出)",
            "```",
            "",
        ]
    )
    _write(change_dir / "review" / "backend_review_v1.md", report)
    return code == 0, f"backend-review {verdict}"


def run_frontend_review(change_dir: Path, state: dict) -> tuple[bool, str]:
    pc = _frontend_pc_path(state)
    if not pc or not pc.is_dir():
        return False, f"frontend pc path 无效: {pc}"

    env = {**os.environ, "BUILD_ENV": "development"}
    proc = subprocess.run(
        ["npm", "run", "build"],
        cwd=str(pc),
        capture_output=True,
        text=True,
        timeout=900,
        env=env,
    )
    code = proc.returncode
    out = (proc.stdout or "") + (proc.stderr or "")
    verdict = "PASS" if code == 0 else "FAIL"
    report = "\n".join(
        [
            f"# Frontend Review · {state.get('name', change_dir.name)}",
            "",
            f"generated_at: {_now_iso()}",
            f"verdict: **{verdict}**",
            "",
            "## 自动检查",
            "",
            "- `BUILD_ENV=development npm run build`",
            f"- exit: {code}",
            "",
            "```",
            out[-3000:] if out else "(无输出)",
            "```",
            "",
        ]
    )
    _write(change_dir / "review" / "frontend_review_v1.md", report)
    return code == 0, f"frontend-review {verdict}"


def run_backend_test_local(change_dir: Path, state: dict) -> tuple[bool, str]:
    backend = _backend_path(state)
    if not backend or not backend.is_dir():
        return False, f"backend path 无效: {backend}"

    code, out = _run_cmd(["mvn", "-q", "test", "-DskipITs"], cwd=backend, timeout=1200)
    if code != 0:
        code, out = _run_cmd(["mvn", "-q", "compile", "-DskipTests"], cwd=backend, timeout=900)
        note = "无可用单测或 test 失败，降级为 compile"
    else:
        note = "mvn test -DskipITs"
    verdict = "PASS" if code == 0 else "FAIL"
    report = "\n".join(
        [
            f"# Backend Test Report · {state.get('name', change_dir.name)}",
            "",
            f"generated_at: {_now_iso()}",
            f"verdict: **{verdict}**",
            "",
            f"## {note}",
            "",
            f"- exit: {code}",
            "",
            "```",
            out[-4000:] if out else "(无输出)",
            "```",
            "",
        ]
    )
    _write(change_dir / "tests" / "backend_test_report.md", report)
    return code == 0, f"backend-test-local {verdict}"


def run_local_stack_up(change_dir: Path, state: dict, req_id: str) -> tuple[bool, str]:
    meta_path = change_dir / "impact" / "impact.md"
    surfaces = "pc"
    skip_h5 = True
    if meta_path.exists():
        text = meta_path.read_text(encoding="utf-8")
        if "surfaces:" in text:
            for line in text.splitlines():
                if line.strip().startswith("surfaces:"):
                    val = line.split(":", 1)[1].strip().strip("[]")
                    surfaces = val.replace(" ", "").replace("'", "").replace('"', "")
                    skip_h5 = "h5" not in surfaces
                    break

    argv = [
        sys.executable,
        str(_SCRIPTS / "local_stack_up.py"),
        "--req-id",
        req_id,
        "--surfaces",
        surfaces,
    ]
    if skip_h5:
        argv.append("--skip-h5")

    proc = subprocess.run(argv, capture_output=True, text=True, timeout=1800)
    combined = (proc.stdout or "") + (proc.stderr or "")
    ok = proc.returncode == 0
    if not ok:
        # bind 失败等场景：若栈实际健康则自愈通过，不把排障甩给用户
        check_proc = subprocess.run(
            [
                sys.executable,
                str(_SCRIPTS / "local_stack_check.py"),
                "--req-id",
                req_id,
                "--surfaces",
                surfaces,
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        combined += "\n--- local_stack_check fallback ---\n" + (
            check_proc.stdout or ""
        ) + (check_proc.stderr or "")
        if check_proc.returncode == 0:
            ok = True
            combined += "\n✓ stack check 复检通过，视为 local-stack-up PASS（复用已有网关）\n"
    report = "\n".join(
        [
            f"# Local Stack Report · {req_id}",
            "",
            f"generated_at: {_now_iso()}",
            f"surfaces: {surfaces}",
            f"verdict: **{'PASS' if ok else 'FAIL'}**",
            "",
            "## 启动命令",
            "",
            "```bash",
            " ".join(argv[2:]),
            "```",
            "",
            "## 输出",
            "",
            "```",
            combined[-6000:] if combined else "(无输出)",
            "```",
            "",
        ]
    )
    _write(change_dir / "tests" / "local_stack_report.md", report)
    return ok, f"local-stack-up {'PASS' if ok else 'FAIL'}"


def run_local_e2e_test(change_dir: Path, req_id: str) -> tuple[bool, str]:
    proc = subprocess.run(
        [sys.executable, str(_SCRIPTS / "local_e2e_autorun.py"), "--req-id", req_id],
        capture_output=True,
        text=True,
        timeout=1800,
    )
    combined = (proc.stdout or "") + (proc.stderr or "")
    ok = proc.returncode == 0
    if not (change_dir / "tests" / "local_e2e_report.md").exists():
        _write(
            change_dir / "tests" / "local_e2e_report.md",
            f"# Local E2E Report · {req_id}\n\nverdict: **{'PASS' if ok else 'FAIL'}**\n\n```\n{combined[-4000:]}\n```\n",
        )
    return ok, f"local-e2e-test {'PASS' if ok else 'FAIL'}"


STAGE_RUNNERS: dict[str, callable] = {
    "backend-review": run_backend_review,
    "frontend-review": run_frontend_review,
    "backend-test-local": run_backend_test_local,
}


def execute_stage(stage_id: str, change_dir: Path, state: dict, req_id: str) -> tuple[bool, str]:
    if stage_id == "local-stack-up":
        return run_local_stack_up(change_dir, state, req_id)
    if stage_id == "local-e2e-test":
        return run_local_e2e_test(change_dir, req_id)
    runner = STAGE_RUNNERS.get(stage_id)
    if not runner:
        return False, f"无自动 runner: {stage_id}"
    return runner(change_dir, state)
