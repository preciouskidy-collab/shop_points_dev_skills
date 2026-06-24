---
name: frontend-design
description: "在 api-contract 冻结草案后产出前端技术设计，与 tech-design 逻辑并行"
version: "0.1.0"
category: playbooks
tags:
  - frontend
  - design
commands: []
---

# Skill: 前端技术设计（frontend-design）

## 适用时机

**`api-contract` 完成之后**（与 `tech-design` **逻辑并行**；Pipeline 顺序上位于 tech-design 之后）。

**跳过条件**：`impact/impact.md` 中 `frontend_scope: none`。

## 输入

- `handoff/api-contract.yaml` — **必须先存在**（协议草案）
- `request/spec.md`、`request/prd.md`、`images/`
- `impact/impact.md`（surfaces、页面路径）
- `knowledge/frontend-atlas.md`

## 步骤

1. 加载 `api-contract.yaml`，确认本需求涉及的 `apis[].id`
2. 按 `surfaces` 列出页面、路由、文件路径（完整路径）
3. 描述交互、空态/错误态、字段展示映射（后端字段 → UI）
4. 填写 E2E 验收草案表
5. 产出 `tech-design/frontend-design.md`

模板：`skills/req-to-dev/references/frontend-design-template.md`

## 产出

| 文件 | 说明 |
|------|------|
| `tech-design/frontend-design.md` | 前端技术设计（plan-approve 审批物） |

## 质量标准

- **禁止**在本文件重新定义 API 字段（一律引用 `api-contract` 的 api id）
- 每个 P0 页面至少 1 条 E2E 草案
- 明确 Won't Do（前端不做）

## 下游

- `plan-approve` 与 `tech-design.md`、`api-contract.yaml` 一并审批
- `frontend-coding` 按本文 + 契约实现
