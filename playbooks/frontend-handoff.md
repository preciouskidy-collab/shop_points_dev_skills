---
name: frontend-handoff
description: "前后端编码完成后契约对齐：对照 plan-approve 冻结的 api-contract 与代码 diff，产出 verify 报告与瘦身 FDH"
version: "0.2.0"
category: playbooks
tags:
  - frontend
  - handoff
  - api-contract
  - contract-verify
commands: []
---

# Skill: 契约对齐（contract-verify）

> 阶段 ID 仍为 `frontend-handoff`（兼容 run_workflow）；职责为 **契约对齐**，不是从零发明 API。

## 适用时机

**`backend-coding` 与 `frontend-coding` 均完成后**执行，在审查之前。

**跳过条件**：`impact/impact.md` 中 `frontend_scope: none`。

## 输入

- `handoff/api-contract.yaml` — **plan-approve 已冻结**的契约草案
- `tech-design/frontend-design.md` — 已审批的前端方案
- 后端实际代码 diff（Controller、DTO、枚举）
- 前端实际代码 diff
- `request/spec.md`、`impact/impact.md`

## 步骤

1. 扫描后端变更的 Controller / DTO，与 `api-contract.yaml` **逐字段对比**
2. 扫描前端 API 调用与字段引用，与契约对比
3. 记录 delta（命名不一致、缺字段、多字段）→ `handoff/contract-verify-report.md`
4. 若有 delta：`status: drift`，列出修复建议；无 delta：`status: aligned`
5. 生成瘦身版 `handoff/frontend-handoff.md`：
   - §2 影响面矩阵、§4 UI 改造点、§6 E2E 用例（API 细节引用契约，不重复抄写）
6. 若实现与契约不一致且以**代码为准**：更新 `api-contract.yaml` 的 `version: verified` 并标注修订说明

## 产出

| 文件 | 说明 |
|------|------|
| `handoff/contract-verify-report.md` | 对齐结论与 delta 列表 |
| `handoff/frontend-handoff.md` | E2E / UI 清单（供 deploy-approve、e2e-browser-test） |
| `handoff/api-contract.yaml` | 必要时更新为 verified |

`contract-verify-report.md` 模板：

```markdown
# Contract Verify Report

status: aligned | drift
api_change: extend
checked_at: <ISO8601>

## Delta
- （无则写「无」）

## 结论
- ...
```

FDH 模板见 `skills/req-to-dev/references/fdh-template.md`（仅填 UI / E2E 相关章节）。

## 质量标准

- **不得**在未对比代码的情况下重写整套 API 契约
- delta 必须可追溯到具体文件/字段
- 每个 P0 功能至少 1 条 E2E 用例写入 FDH §6
- `deploy_modules` 与 `impact.md` 一致
