"""local-e2e-test 必跑用例清单（Single Source of Truth，advance 门禁）。"""

from __future__ import annotations

from typing import Any

# 线下活动贝壳币上传（含 PC 上传 + Apollo mock + H5 联动）完整闭环
KECOIN_OFFLINE_FULL_MATRIX: list[dict[str, Any]] = [
    {
        "id": "API-01",
        "name": "shop-points health",
        "phase": "stack",
        "required": True,
    },
    {
        "id": "API-02",
        "name": "GET keCoin/period",
        "phase": "stack",
        "required": True,
    },
    {
        "id": "E2E-PC-01a",
        "name": "PC 登录 + 正确活动/城市 + 上传贝壳币弹窗（记录 upload_period）",
        "phase": "pc_ui",
        "required": True,
        "playbook": "playbooks/kecoin-upload-e2e-matrix.md",
    },
    {
        "id": "E2E-PC-01b",
        "name": "企微 notify → 用户选 Excel → wait upload_confirm",
        "phase": "pc_upload_collab",
        "required": True,
        "playbook": "playbooks/e2e-upload-collab.md",
    },
    {
        "id": "E2E-PC-01c",
        "name": "申诉期内点确定 + 上传列表轮询至已生效(102)",
        "phase": "pc_upload_submit",
        "required": True,
        "depends_on": ["E2E-PC-01b"],
        "playbook": "playbooks/kecoin-upload-e2e-matrix.md",
    },
    {
        "id": "E2E-PC-02",
        "name": "申诉期外提交拦截（hasSaveError=true，无新已生效记录）",
        "phase": "pc_upload_negative",
        "required": True,
        "playbook": "playbooks/kecoin-upload-e2e-matrix.md",
        "depends_on": ["E2E-PC-01a"],
    },
    {
        "id": "APOLLO-MOCK-01",
        "name": "TEST Apollo mockCurrentTime 调至发币日/申诉期后（业务开关发布）",
        "phase": "apollo",
        "required": True,
        "playbook": "playbooks/apollo-mock-time.md",
    },
    {
        "id": "E2E-H5-01",
        "name": "H5 beikebi/index 切换至上传账期 → 线下活动卡片与金额",
        "phase": "h5_ui",
        "required": True,
        "depends_on": ["E2E-PC-01c", "APOLLO-MOCK-01"],
        "playbook": "playbooks/kecoin-upload-e2e-matrix.md",
    },
    {
        "id": "E2E-H5-02",
        "name": "H5 beikebi/history 上传账期明细（与 upload_period 一致）",
        "phase": "h5_ui",
        "required": True,
        "depends_on": ["APOLLO-MOCK-01"],
        "playbook": "playbooks/kecoin-upload-e2e-matrix.md",
    },
]

# 通用最小集（无文件上传类需求可降级，但本需求不适用）
MINIMAL_MATRIX: list[dict[str, Any]] = [
    {"id": "API-01", "name": "shop-points health", "phase": "stack", "required": True},
    {"id": "E2E-SMOKE-01", "name": "主入口页面可打开", "phase": "ui", "required": True},
]


def matrix_for_change(impact_meta: dict, contract: dict | None = None) -> list[dict[str, Any]]:
    """按需求特征选择 E2E 必跑矩阵。"""
    contract = contract or {}
    e2e_cases = contract.get("e2e_cases") or []
    apis = contract.get("apis") or []
    has_kecoin_upload = any(
        "keCoin" in str(a.get("path", "")) or "kecoin" in str(a.get("id", "")).lower()
        for a in apis
    )
    has_upload_case = any(
        "上传" in " ".join(c.get("steps") or []) or "Excel" in str(c.get("expected", ""))
        for c in e2e_cases
    )
    if has_kecoin_upload or has_upload_case:
        return KECOIN_OFFLINE_FULL_MATRIX
    return MINIMAL_MATRIX


def required_case_ids(matrix: list[dict[str, Any]]) -> list[str]:
    return [c["id"] for c in matrix if c.get("required", True)]
