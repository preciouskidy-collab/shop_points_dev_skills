---
name: api-contract
description: "在详设之前单独产出 API 协议规范草案，供 tech-design 与 frontend-design 并行引用"
version: "0.1.0"
category: playbooks
tags:
  - api-contract
  - protocol
commands: []
---

# Skill: API 协议规范（api-contract）

## 适用时机

**`scope-eval` 完成之后、`tech-design` / `frontend-design` 之前**。

本阶段**只定对外接口边界**，不写库表、不写 UI 组件树。

**跳过条件**：`impact/impact.md` 中 `api_change: none`（纯 UI 或无 HTTP 变更）。

## 输入

- `request/spec.md`、`request/prd.md`（相关 API 章节）
- `impact/impact.md`（`api_change`、`frontend_scope`）
- `knowledge/rpc-contracts`（已有接口，避免重复发明）

## 步骤

1. 根据 `api_change` 判定：`none` 跳过；`extend` 列增量字段/错误码；`new` 列完整新接口
2. 每个接口分配稳定 `id`（供 frontend-design 引用）
3. 填写路径、方法、请求/响应 JSON 示例、错误码、兼容性说明
4. 产出 `handoff/api-contract.yaml`，`version: draft`
5. 若有前端：在 `e2e_cases` 草案中写 1–2 条与接口相关的验收点（细节在 frontend-design 展开）

## 产出

| 文件 | 说明 |
|------|------|
| `handoff/api-contract.yaml` | 机器可读协议草案 |

模板：`skills/req-to-dev/references/api-contract-template.yaml`

## 质量标准

- 字段名/类型/必填与 PRD 一致；不确定处标 `TODO` 进 plan-approve 讨论
- `extend` 必须写清老客户端兼容策略
- 不在本阶段写 Controller 类名、表结构（留给 tech-design）

## 下游

- `tech-design`：后端实现方案**不得**修改已定义字段语义，只能补充实现细节
- `frontend-design`：通过 `apis[].id` 引用本文件
- `plan-approve`：与本阶段产物一并审批后冻结
