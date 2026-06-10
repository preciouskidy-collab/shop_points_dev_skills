---
name: frontend-coding
description: "基于 FDH 交接文档修改 store-integral(PC) 或 store-integral-h5(H5) 前端代码"
version: "0.1.0"
category: playbooks
tags:
  - frontend
  - react
  - coding
commands: []
---

# Skill: 前端编码

## 适用时机

`frontend-handoff` 产出 FDH 后执行。**必须加载 FDH，禁止脱离交接文档自行猜接口。**

**跳过条件**：`frontend_scope: none`。

## 前置依赖

| 依赖 | 说明 |
|------|------|
| `handoff/frontend-handoff.md` | 改造点、API 契约、E2E 用例 |
| `handoff/api-contract.yaml` | 机器可读契约 |
| 后端代码已提交到工作区 | FDH 与代码一致 |

## 输入

- `handoff/frontend-handoff.md`
- `handoff/api-contract.yaml`
- `knowledge/frontend-atlas.md`

## 步骤

1. 加载阶段资源：`skills_loader.py context --stage frontend-coding`
2. 按 FDH §2 影响面矩阵定位文件
3. PC 改动在 `store-integral/client/`，H5 在 `store-integral-h5/client-integral/`
4. 按 FDH §3 API 契约接入接口（PC 用 `keFetch`，H5 用 `axiosRequestAssistant`）
5. 按 FDH §4 完成 UI 改造
6. 本地验证：
   - PC：`cd store-integral && npm start`
   - H5：`cd store-integral-h5/client-integral && npm start`
7. 构建验证：
   - PC：`cd store-integral && npm run build`
   - H5：`cd store-integral-h5/client-integral && npm run build`

## 编码原则

- **严格按 FDH 范围**，不自行扩展功能
- 新增路由必须在 `router/index` 注册
- 复用现有组件和工具方法
- 空态、加载态、错误态必须处理

## 产出

- 前端仓库代码 diff
- `pipeline.log` 记录改动文件列表

## 质量标准

- 本地 build 通过
- API 路径与 FDH / 后端代码一致
- 不引入新 HTTP 库
