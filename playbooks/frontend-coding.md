---
name: frontend-coding
description: "基于 plan-approve 冻结的 api-contract 与 frontend-design 修改 store-integral(PC) 或 store-integral-h5(H5)"
version: "0.2.0"
category: playbooks
tags:
  - frontend
  - react
  - coding
commands: []
---

# Skill: 前端编码

## 适用时机

**`plan-approve` 通过后**即可执行（与 `backend-coding` 逻辑并行；Pipeline 顺序上位于后端编码之后）。

**禁止**脱离已审批契约与前端方案自行猜接口。

**跳过条件**：`frontend_scope: none`。

## 前置依赖（plan-approve 冻结）

| 依赖 | 说明 |
|------|------|
| `handoff/api-contract.yaml` | API 契约草案（审批后冻结） |
| `tech-design/frontend-design.md` | 前端技术设计（页面、交互、文件路径） |
| `impact/impact.md` | surfaces、deploy_modules |

后端代码尚未落地时，可用 **mock / 测试环境旧接口** 先行开发。

## 输入

- `handoff/api-contract.yaml`
- `tech-design/frontend-design.md`
- `knowledge/frontend-atlas.md`

## 步骤

1. 加载阶段资源：`skills_loader.py context --stage frontend-coding`
2. 按 `frontend-design.md` §1 定位文件与路由
3. PC：`store-integral/client/`；H5：`store-integral-h5/client-integral/`
4. 按 `api-contract.yaml` 接入接口（PC `keFetch`，H5 `axiosRequestAssistant`）
5. 按 `frontend-design.md` §2–§4 完成 UI
6. 本地验证：`npm start` + `npm run build`

## 编码原则

- **严格按 frontend-design 范围**，不自行扩展
- API 路径/字段以 **api-contract** 为准；与后端实现冲突时先记 delta，等 `frontend-handoff` 对齐
- 新增路由必须在 `router/index` 注册
- 空态、加载态、错误态必须处理

## 产出

- 前端仓库代码 diff
- `pipeline.log` 记录改动文件列表

## 质量标准

- 本地 build 通过
- API 与 `api-contract.yaml` 一致（或与已知 delta 一致并待 verify）
- 不引入新 HTTP 库
