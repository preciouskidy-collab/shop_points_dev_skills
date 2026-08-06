---
name: local-stack-up
description: "启动本地后端与前端 dev server，供联调与 Cursor 浏览器 E2E"
version: "0.1.0"
category: playbooks
tags:
  - local
  - integration
commands: []
---

# Skill: 本地联调栈启动

## 适用时机

`backend-test-local` 通过后，`local-e2e-test` 之前。

**跳过条件**：无（纯后端需求仍须启动后端；`frontend_scope: none` 时跳过前端 dev server）。

## 前置条件

- `impact/impact.md` frontmatter 含 `integration_mode: local`（默认）
- 后端 `mvn compile` 已通过
- 本地 hosts / CAS：`local.ttb.test.ke.com` 可访问

## 步骤

1. 读取 `impact.md` → `local_backend_url`（默认 `http://local.ttb.test.ke.com`）、`local_frontend_url`
2. 后端：在目标仓库执行 `mvn spring-boot:run -DskipTests`（或项目约定命令），记录 PID
3. 前端（`frontend_scope != none`）：`npm start`，proxy 指向本地后端
4. 健康检查：curl 后端关键接口；前端首页可打开
5. 产出 `tests/local_stack_report.md`（PID、端口、启动命令、健康检查结果）

## 质量标准

- 后端健康检查通过
- 前端（如有）dev server 可访问
- 报告中记录停止命令（kill PID）
