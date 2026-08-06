---
name: local-e2e-browser-test
description: "使用 Cursor 内置浏览器 MCP 在本地前后端执行 E2E 验收"
version: "0.1.0"
category: playbooks
tags:
  - e2e
  - local
  - cursor-browser
commands: []
---

# Skill: 本地 E2E（Cursor 内置浏览器）

## 适用时机

`local-stack-up` 成功后。

**跳过条件**：`frontend_scope: none`。

## 前置条件

- `tests/local_stack_report.md` 记录栈已启动
- `handoff/frontend-handoff.md` §6 或 `handoff/api-contract.yaml` 的 `e2e_cases` 已就绪

## 浏览器工具

**默认且推荐**：Cursor 内置浏览器 MCP（`cursor-ide-browser`），**不使用** AgentBrowser。

| 操作 | MCP 工具 |
|------|----------|
| 打开页面 | `browser_navigate` |
| 读页面结构 | `browser_snapshot` |
| 点击 / 输入 | `browser_click` / `browser_type` / `browser_fill` |
| 截图验证 | `browser_take_screenshot` |

## 测试入口

优先使用 `impact.md` 中的 `local_frontend_url`；未配置时：

| 端 | 默认 |
|----|------|
| H5 | `http://localhost:3000`（以 frontend-design 为准） |
| PC | `http://localhost:8080`（以 frontend-design 为准） |

API 请求应命中 `local_backend_url`（默认 `http://local.ttb.test.ke.com`）。

## 步骤

1. 加载 `e2e_cases` 用例列表
2. 按用例执行 navigate → snapshot → 交互 → 断言
3. 失败时截图 + 记录 console；修复后重跑本阶段（无需大禹）
4. 产出 `tests/local_e2e_report.md`

## 与大禹路径的关系

- `integration_mode: local`（默认）：本阶段为 **唯一** 页面 E2E
- 用户选择在 `deploy-approve` 部署大禹后，可额外跑 `e2e-browser-test`（AgentBrowser 或 Cursor 浏览器访问 test01）

## 质量标准

- 所有 P0 `e2e_cases` 通过
- 报告含截图路径或 snapshot 摘要
