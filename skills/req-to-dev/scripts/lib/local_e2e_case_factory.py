"""E2E 用例生成：从规范模板注入 test_context、步骤与断言（生成阶段 + init 共用）。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_SPECS_JSON = (
    Path(__file__).resolve().parents[2] / "references" / "kecoin-upload-e2e-cases.json"
)
_SPECS_YAML = (
    Path(__file__).resolve().parents[2] / "references" / "kecoin-upload-e2e-cases.yaml"
)


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        import yaml  # type: ignore
    except ImportError:
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    import json

    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def load_kecoin_e2e_specs() -> dict[str, Any]:
    data = _load_json(_SPECS_JSON)
    if data:
        return data
    return _load_yaml(_SPECS_YAML)


def is_kecoin_upload_matrix(matrix: list[dict[str, Any]]) -> bool:
    ids = {c.get("id") for c in matrix}
    return "E2E-PC-02" in ids and "E2E-H5-01" in ids


def _render(text: str, ctx: dict[str, Any]) -> str:
    out = text
    for key, val in ctx.items():
        out = out.replace("{{" + key + "}}", str(val))
    return out


def _render_list(items: list[Any], ctx: dict[str, Any]) -> list[str]:
    rendered: list[str] = []
    for item in items:
        if isinstance(item, str):
            rendered.append(_render(item, ctx))
    return rendered


def enrich_matrix_case(case_id: str, matrix_item: dict[str, Any], specs: dict[str, Any]) -> dict[str, Any]:
    """合并 manifest 项与规范模板中的步骤/断言。"""
    ctx = specs.get("test_context") or {}
    case_spec = (specs.get("cases") or {}).get(case_id) or {}
    enriched = dict(matrix_item)
    for field in ("preconditions", "steps", "expected", "assertions", "surface"):
        if field in case_spec:
            val = case_spec[field]
            if isinstance(val, list):
                enriched[field] = _render_list(val, ctx)
            elif isinstance(val, str):
                enriched[field] = _render(val, ctx)
            else:
                enriched[field] = val
    if specs.get("anti_patterns"):
        enriched["anti_patterns"] = [p.get("description", "") for p in specs["anti_patterns"]]
    return enriched


def build_checklist_payload(
    matrix: list[dict[str, Any]],
    existing_cases: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    生成/合并 e2e_checklist.json 结构。
    保留已有 status/note；新增字段从规范模板注入。
    """
    existing_cases = existing_cases or {}
    specs = load_kecoin_e2e_specs() if is_kecoin_upload_matrix(matrix) else {}
    ctx = specs.get("test_context") or {}

    cases: dict[str, Any] = {}
    for item in matrix:
        cid = item["id"]
        base = enrich_matrix_case(cid, item, specs) if specs else dict(item)
        prev = existing_cases.get(cid) or {}
        entry: dict[str, Any] = {
            "status": prev.get("status", "pending"),
            "name": base.get("name", cid),
            "phase": base.get("phase", ""),
            "note": prev.get("note", ""),
        }
        for field in (
            "preconditions",
            "steps",
            "expected",
            "assertions",
            "surface",
            "playbook",
            "depends_on",
            "anti_patterns",
        ):
            if field in base:
                entry[field] = base[field]
        cases[cid] = entry

    payload: dict[str, Any] = {
        "cases": cases,
        "matrix": [c["id"] for c in matrix],
    }
    if ctx:
        payload["test_context"] = ctx
        payload["feature"] = specs.get("feature", "kecoin_offline_upload")
        payload["spec_ref"] = "skills/req-to-dev/references/kecoin-upload-e2e-cases.json"
        if specs.get("anti_patterns"):
            payload["anti_patterns"] = specs["anti_patterns"]
    return payload


def seed_api_contract_e2e_cases() -> list[dict[str, Any]]:
    """api-contract 阶段：返回应写入 handoff/api-contract.yaml 的 e2e_cases 草案。"""
    specs = load_kecoin_e2e_specs()
    ctx = specs.get("test_context") or {}
    out: list[dict[str, Any]] = []
    for case_id, case in (specs.get("cases") or {}).items():
        if not case_id.startswith("E2E-"):
            continue
        steps = case.get("steps") or []
        out.append(
            {
                "id": case_id,
                "surface": case.get("surface", ""),
                "test_context_ref": "upload_period",
                "preconditions": _render_list(case.get("preconditions") or [], ctx),
                "steps": _render_list(steps, ctx),
                "expected": _render(str(case.get("expected", "")), ctx),
                "required": True,
            }
        )
    return out


def validate_handoff_e2e_section(handoff_text: str, matrix: list[dict[str, Any]]) -> list[str]:
    """frontend-handoff §6 与必跑矩阵对齐检查（init/gate 前可选调用）。"""
    if not is_kecoin_upload_matrix(matrix):
        return []
    errors: list[str] = []
    required_ui = [c["id"] for c in matrix if str(c.get("id", "")).startswith("E2E-")]
    for cid in required_ui:
        if cid not in handoff_text:
            errors.append(f"frontend-handoff.md §6 缺少用例 {cid}")
    if "upload_period" not in handoff_text and "账期" not in handoff_text:
        errors.append("frontend-handoff.md §6 未写明 upload_period / 账期切换（H5 须与上传账期一致）")
    if "E2E-PC-02" in required_ui and "申诉期外" not in handoff_text and "hasSaveError" not in handoff_text:
        errors.append("frontend-handoff.md §6 缺少申诉期外负向（E2E-PC-02 / hasSaveError）")
    if re.search(r"合肥|339", handoff_text) and "253" not in handoff_text:
        errors.append("frontend-handoff.md 测试数据疑似错城（合肥/339），默认应为天津/253/TJDY0101")
    return errors
