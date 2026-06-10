---
name: frontend-handoff
description: "后端编码完成后产出 FDH 前端交接文档与 api-contract.yaml，供前端开发与 E2E 使用"
version: "0.1.0"
category: playbooks
tags:
  - frontend
  - handoff
  - api-contract
commands: []
---

# Skill: 前端交接包（FDH）

## 适用时机

**`backend-coding` 完成后立即执行**，在 `frontend-coding` 之前。

FDH 是前端开发的唯一标准输入，必须基于后端**实际代码 diff** 生成，不等待后端审查/本地测。

**跳过条件**：`impact/impact.md` 中 `frontend_scope: none`。

## 输入

- `request/spec.md` — 需求规格与验收标准
- `tech-design/tech-design.md` — 技术方案
- `impact/impact.md` — 前端影响面
- 后端实际代码 diff（Controller、DTO、枚举）— **以代码为准，不只抄技术方案**

## 步骤

1. 加载 `knowledge/frontend-atlas.md` 确认目标页面路径
2. 扫描后端变更的 Controller / DTO，提取真实 API 契约
3. 对照 PRD 截图（`images/`）标注 UI 改造点
4. 按模板生成 `handoff/frontend-handoff.md`
5. 生成机器可读 `handoff/api-contract.yaml`
6. 将 E2E 用例写入 FDH §6，同步到 `api-contract.yaml` 的 `e2e_cases`

## 产出

| 文件 | 说明 |
|------|------|
| `handoff/frontend-handoff.md` | 人类可读交接文档 |
| `handoff/api-contract.yaml` | 机器可读 API + E2E 用例 |

模板见 `skills/req-to-dev/references/fdh-template.md`。

## FDH 必填章节

1. 变更摘要
2. 影响面矩阵（端 / 路由 / 组件路径 / 变更类型）
3. API 契约（含请求/响应示例、错误码）
4. UI 改造点（按页面）
5. 状态与数据流
6. **验收场景（E2E 用例表）** — `e2e-browser-test` 阶段直接使用
7. 部署依赖（`deploy_modules` 顺序）
8. Won't Do（前端）

## 质量标准

- API 路径/字段必须与后端代码一致，发现与技术方案不一致时以代码为准并标注
- 每个 P0 功能至少 1 条 E2E 用例
- 明确 PC / H5 各自改哪些文件（完整路径）
- `deploy_modules` 与 `impact.md` 保持一致
