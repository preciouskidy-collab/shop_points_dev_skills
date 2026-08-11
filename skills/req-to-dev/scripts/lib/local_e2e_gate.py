"""local-e2e-test 完成门禁：必跑用例须全部 PASS，禁止仅 API 冒烟即 advance。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from local_e2e_case_factory import (
    build_checklist_payload,
    is_kecoin_upload_matrix,
    validate_handoff_e2e_section,
)
from local_e2e_manifest import matrix_for_change, required_case_ids


def _parse_frontmatter(path: Path) -> dict:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    end = text.find("---", 3)
    if end == -1:
        return {}
    meta: dict[str, Any] = {}
    for line in text[3:end].splitlines():
        stripped = line.strip()
        if not stripped or ":" not in stripped:
            continue
        key, _, val = stripped.partition(":")
        key = key.strip()
        val = val.strip().strip("\"'")
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1]
            meta[key] = [v.strip().strip("'\"") for v in inner.split(",") if v.strip()]
        elif val:
            meta[key] = val
    return meta


def _load_impact_meta(change_dir: Path) -> dict:
    return _parse_frontmatter(change_dir / "impact" / "impact.md")


def _load_contract(change_dir: Path) -> dict:
    path = change_dir / "handoff" / "api-contract.yaml"
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    # 轻量解析 e2e_cases / apis 块（无 PyYAML 依赖）
    contract: dict[str, Any] = {"apis": [], "e2e_cases": []}
    if "keCoin" in text or "kecoin" in text.lower():
        contract["apis"].append({"path": "/keCoin/"})
    if "Excel" in text or "上传" in text:
        contract["e2e_cases"].append({"steps": ["上传 Excel"]})
    return contract


def checklist_path(change_dir: Path) -> Path:
    return change_dir / "tests" / "e2e_checklist.json"


def load_checklist(change_dir: Path) -> dict[str, Any]:
    path = checklist_path(change_dir)
    if not path.exists():
        return {"cases": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def save_checklist(change_dir: Path, data: dict[str, Any]) -> None:
    path = checklist_path(change_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def init_checklist(change_dir: Path) -> dict[str, Any]:
    meta = _load_impact_meta(change_dir)
    contract = _load_contract(change_dir)
    matrix = matrix_for_change(meta, contract)
    data = load_checklist(change_dir)
    existing = data.get("cases") or {}
    payload = build_checklist_payload(matrix, existing)
    data.update(payload)
    save_checklist(change_dir, data)
    return data


def update_case(change_dir: Path, case_id: str, status: str, note: str = "") -> None:
    data = init_checklist(change_dir)
    cases = data.setdefault("cases", {})
    if case_id not in cases:
        cases[case_id] = {"name": case_id, "phase": "", "note": ""}
    cases[case_id]["status"] = status
    if note:
        cases[case_id]["note"] = note
    save_checklist(change_dir, data)


def gate_local_e2e(change_dir: Path) -> tuple[bool, list[str]]:
    """
    返回 (通过, 错误列表)。
    未通过时 run_workflow advance 必须 exit 1。
    """
    meta = _load_impact_meta(change_dir)
    contract = _load_contract(change_dir)
    matrix = matrix_for_change(meta, contract)
    required = required_case_ids(matrix)
    data = init_checklist(change_dir)
    cases = data.get("cases", {})

    errors: list[str] = []
    pending: list[str] = []
    failed: list[str] = []

    for cid in required:
        entry = cases.get(cid) or {}
        status = entry.get("status", "pending")
        if status == "pass":
            continue
        if status in ("fail", "blocked"):
            failed.append(f"{cid} ({entry.get('name', '')})")
        else:
            pending.append(f"{cid} ({entry.get('name', '')})")

    if failed:
        errors.append(f"E2E 用例失败: {', '.join(failed)}")
    if pending:
        errors.append(
            "E2E 用例未完成（禁止仅 API/弹窗冒烟即 advance）: "
            + ", ".join(pending)
        )
        errors.append(
            "完整闭环须含: 企微 Excel 上传 → 申诉期负向(E2E-PC-02) → Apollo mockCurrentTime → "
            "H5 卡片+明细（须与 upload_period 同账期）。"
            "见 playbooks/kecoin-upload-e2e-matrix.md、apollo-mock-time.md、e2e-upload-collab.md"
        )

    if is_kecoin_upload_matrix(matrix):
        handoff = change_dir / "handoff" / "frontend-handoff.md"
        if handoff.exists():
            ho_errors = validate_handoff_e2e_section(
                handoff.read_text(encoding="utf-8"), matrix
            )
            errors.extend(ho_errors)
        ctx = data.get("test_context") or {}
        if not ctx.get("upload_period"):
            errors.append(
                "e2e_checklist.json 缺少 test_context.upload_period（请 local_e2e_checklist init 重新生成）"
            )

    report = change_dir / "tests" / "local_e2e_report.md"
    if report.exists():
        text = report.read_text(encoding="utf-8")
        if re.search(r"verdict:\s*\*\*PASS\*\*", text) and pending:
            errors.append(
                "local_e2e_report.md 标记 PASS 但 e2e_checklist.json 仍有 pending（报告与清单不一致）"
            )

    return len(errors) == 0, errors
