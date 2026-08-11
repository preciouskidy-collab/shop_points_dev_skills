---
name: dayu-deploy
description: "通过 Cursor 内置浏览器 MCP 在大禹平台构建部署测试环境，按 deploy_modules 顺序执行"
version: "0.2.0"
category: playbooks
tags:
  - deploy
  - dayu
  - cursor-browser
commands: []
---

# Skill: 大禹测试环境部署（Cursor 内置浏览器）

> **红线**：大禹部署与后续 E2E **仅** 使用 `cursor-ide-browser` MCP（Glass **Browser Tab**）。**禁止** `agent-browser`、Playwright、本机 Chrome。

## 适用时机

`commit-push` 完成后，在 `e2e-browser-test` 之前（`integration_mode: dayu`）。

## 前置条件

- 各目标仓库已 push `feature/<name>` 到远程
- `handoff/frontend-handoff.md` 或 `impact/impact.md` 中 `deploy_modules` 已明确
- `skills/req-to-dev/config/secrets.local.json` 已配置大禹凭证
- Cursor **Browser Automation = Browser Tab**

## 浏览器工具

| 操作 | MCP 工具 |
|------|----------|
| 打开大禹 | `browser_navigate` → `https://dayu.ke.com/env/module?name=shop-points-test01` |
| 读页面 | `browser_snapshot` |
| 点击 / 填表 | `browser_click` / `browser_fill` |
| 刷新轮询 | `browser_navigate`（同 URL）或刷新后 `browser_snapshot` |
| 截图 | `browser_take_screenshot` |

## 部署顺序

读取 `deploy_modules`，严格按 `knowledge/dayu-platform.md` 顺序：

1. `shop-points`
2. `shop-points-lottery`（仅 `mall_scope != none`）
3. `store-integral-cdn`
4. `store-integral-h5-cdn`

## 部署耗时与轮询

- **后端（Java/Spring Boot）**: ~1-3 分钟
- **前端 CDN（PC/H5）**: ~5-15 分钟
- **轮询节奏**: 每 **5 分钟** `browser_navigate` 刷新大禹页，`browser_snapshot` 看模块标题是否仍为「更新中」

## 单模块操作流程

1. `browser_navigate` 打开大禹环境页
2. 若需登录 → `browser_fill` 工号/密码 → `browser_click` 登录
3. `browser_snapshot` 找到目标模块 → 点「构建部署」
4. 选择分支 `feature/<name>` → **分支正确性校验（必须）**
5. 点「构建并部署」→ 等待 modal 关闭 → 截图取证

### 分支正确性校验（必须）

点「构建并部署」前，从 `browser_snapshot` 确认：

| 模块 | GIT 仓库后缀 | 分支 |
|------|--------------|------|
| shop-points | `shop-points.git` | `feature/<name>` |
| shop-points-lottery | `shop-points-lottery.git` | `feature/<name>` |
| store-integral-cdn | `store-integral.git` | `feature/<name>` |
| store-integral-h5-cdn | `store-integral-h5.git` | `feature/<name>` |

**只有 git 后缀和分支都 match 才允许提交构建**。用 snapshot 中模块卡片旁的「构建部署」链接定位，**不要**依赖固定 DOM 索引。

## 轮询

部署后每 5 分钟：

1. `browser_navigate` 刷新大禹页（或浏览器刷新）
2. `browser_snapshot` 检查各模块 h4 标题是否含「更新中」
3. 全部「运行中」后结束轮询

## 成功判定

每个模块必须：

1. 显示 **「运行中」** 标签
2. **刷新页面后**标签仍存在

否则记为失败，查后端日志：`/data0/www/applogs/<项目名>`

## 失败处理

1. `browser_take_screenshot` + 摘录日志写入 `deploy/dayu_deploy_report.md`
2. `run_workflow.py fail --reason "dayu deploy failed: <module>"`
3. 修复后重新 `commit-push` → 重跑 `dayu-deploy`

## 产出

`deploy/dayu_deploy_report.md`（模块表 + 截图路径）。

## 质量标准

- 不跳过刷新验证步骤
- 不按错误顺序部署（后端必须在前端之前）
- 凭证从 secrets 读取，不出现在报告和日志中
- **禁止** agent-browser / 本机 Chrome 替代 Cursor 内置浏览器
