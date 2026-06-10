---
name: dayu-platform
description: "大禹测试环境部署：模块映射、构建部署 SOP、成功判定与日志路径"
version: "0.1.0"
category: knowledge
tags:
  - deploy
  - dayu
  - test-env
commands: []
---

# 大禹平台 — 测试环境部署

## 环境入口

- **环境名**：`shop-points-test01`
- **模块页 URL**：`https://dayu.ke.com/env/module?name=shop-points-test01`
- **凭证**：从 `skills/req-to-dev/config/secrets.local.json` 读取 `dayu.username` / `dayu.password`（**禁止写入仓库**）

## 模块映射

| 大禹模块名 | 本地仓库路径 | 默认分支 | 日志目录（后端） |
|------------|-------------|----------|------------------|
| `shop-points` | `/Users/qidi/IdeaProjects/shop-points` | master | `/data0/www/applogs/shop-points` |
| `shop-points-lottery` | `/Users/qidi/IdeaProjects/shop-points-lottery` | master | `/data0/www/applogs/shop-points-lottery` |
| `store-integral-cdn` | `/Users/qidi/IdeaProjects/store-integral` | master | — |
| `store-integral-h5-cdn` | `/Users/qidi/IdeaProjects/store-integral-h5` | master | — |

## 部署顺序

按 `impact/impact.md` 中的 `deploy_modules` 依次部署：

```
1. shop-points              （门店积分后端有改动时）
2. shop-points-lottery      （仅 mall_scope != none，即商城相关需求）
3. store-integral-cdn       （PC 前端有改动时）
4. store-integral-h5-cdn    （H5 前端有改动时）
```

**规则**：后端先于前端；`shop-points-lottery` 仅在积分商城相关需求时出现。

## 单模块部署步骤

1. 打开环境模块页（见上 URL）
2. 若弹出登录页 → 使用 `secrets.local.json` 中的大禹账号登录
3. 找到目标模块卡片
4. 点击 **「构建部署」**
5. 选择分支：`feature/<需求名称>`（与 Pipeline 分支名一致）
6. 点击 **「构建并部署」**
7. 等待构建完成

## 成功判定（硬性）

必须同时满足：

1. 模块卡片显示 **「运行中」** 标签
2. **刷新大禹页面后**，「运行中」标签仍然存在

仅构建成功但刷新后标签消失 → 视为 **部署失败**，需查日志并重试。

## 后端日志查看

1. 点击对应后端项目的 **「终端」** 按钮
2. 执行：`cd /data0/www/applogs/<项目名>`
3. 查看最新日志文件（如 `application.log`）

项目名与模块名一致：`shop-points` 或 `shop-points-lottery`。

## AgentBrowser 环境变量

部署与 E2E 使用本地 `agent-browser` CLI：

```bash
export AGENT_BROWSER_EXECUTABLE_PATH="$HOME/.agent-browser/browsers/chrome-149.0.7827.55/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"
export AGENT_BROWSER_HEADED=1
export AGENT_BROWSER_SESSION_NAME="req-to-dev-<change-name>"
```

## 常见失败场景

| 现象 | 处理 |
|------|------|
| 分支列表找不到 feature 分支 | 确认 `commit-push` 已完成且远程已 push |
| 前端构建失败 | 检查大禹 `BUILD_PROJECTS` 环境变量是否包含正确 client |
| 运行中标签刷新后消失 | 查后端 `/data0/www/applogs/` 启动错误 |
| 登录过期 | 重新登录大禹或复用 `--session-name` 持久化会话 |
