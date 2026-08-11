---
name: e2e-browser-test
description: "基于 FDH 验收场景，使用 Cursor 内置浏览器 MCP 在测试环境页面执行 E2E 自测"
version: "0.2.0"
category: playbooks
tags:
  - e2e
  - cursor-browser
  - test-env
commands: []
---

# Skill: 测试环境 E2E 浏览器自测（Cursor 内置浏览器）

> **红线 R8.1**：本阶段 **仅** 使用 `cursor-ide-browser` MCP（Glass **Browser Tab**）。**禁止** Playwright、agent-browser、本机 Chrome/Chromium 脚本做 CAS 登录或页面交互。

## 适用时机

`dayu-deploy` 全部模块部署成功后（`integration_mode: dayu`）。

**跳过条件**：`impact/impact.md` 中 `frontend_scope: none`。

本地联调栈验收见 `playbooks/local-e2e-browser-test.md`（`local-e2e-test` 阶段）。

## 前置条件

- `deploy/dayu_deploy_report.md` 全部模块 ✅
- `handoff/frontend-handoff.md` §6 或 `handoff/api-contract.yaml` 的 `e2e_cases` 已就绪
- `secrets.local.json` 中 `test_env_app` 凭证已配置
- Cursor **Browser Automation = Browser Tab**，操作 **glass-browser** 视图

## 测试入口

| 端 | URL |
|----|-----|
| H5 | `http://integral.ttb.test.ke.com/store-pointsV2/index?shopCode=TJDY0101&shopCodeInnerTest=TJDY0101` |
| PC | `https://point-pc.ttb.test.ke.com/integral2/activity-config/city` |

详见 `knowledge/test-env-topology.md`。

**默认测试数据**：城市 **天津市**（`cityCode=120000`）、门店 **TJDY0101**。

## 浏览器工具（唯一路径）

| 操作 | MCP 工具 |
|------|----------|
| 打开页面 | `browser_navigate` |
| 锁定会话 | `browser_lock` |
| 读页面结构 | `browser_snapshot` |
| 点击 / 输入 | `browser_click` / `browser_fill` |
| 截图验证 | `browser_take_screenshot` |

**禁止**：`playwright`、`ab_h5_bypass_http.py`、`agent-browser`、Selenium、独立 Chrome 进程（含「Chrome for Testing」）。

## 登录（CAS）

1. `browser_tabs` → `browser_navigate` 打开 H5/PC 入口
2. 若跳 CAS：**员工** → **账号登录** → 填 `test_env_app` 工号密码 → **登录**
3. 回跳后 `browser_snapshot` 确认已进入业务页
4. 同 Browser Tab 会话内复用登录态，后续用例无需重复登录

H5 建议在 Glass 中切换移动端视口（Browser 面板设备模拟），再打开 H5 URL。

## 执行流程

### 1. 逐条执行 E2E 用例

对 `e2e_cases` 或 FDH §6 中每条用例：

1. `browser_navigate` 到目标 URL（若不在当前页）
2. `browser_snapshot` → `browser_click` / `browser_fill` 执行操作
3. 再次 `browser_snapshot` 断言期望文案/元素
4. `browser_take_screenshot` 保存 `tests/e2e-<case-id>.png`

### 2. 失败时取证

- `browser_take_screenshot` 当前页面
- 若为接口问题：到大禹终端查 `/data0/www/applogs/shop-points` 日志
- 记录 snapshot 中的错误文案或缺失元素

## 产出

`tests/e2e_test_report.md`：

```markdown
# E2E Test Report

## Environment
shop-points-test01 | Branch: feature/<name>

## Summary
- Total: N | Pass: X | Fail: Y

## Results

| ID | 端 | 状态 | 说明 | 截图 |
|----|----|------|------|------|
| E2E-01 | H5 | ✅ PASS | 新字段展示正确 | tests/e2e-E2E-01.png |
| E2E-02 | PC | ❌ FAIL | 保存后列表未刷新 | tests/e2e-E2E-02-fail.png |

## Failures（如有）

### E2E-02
- 期望：...
- 实际：...
- 后端日志摘录：...
```

## 失败处理

1. `run_workflow.py fail --reason "e2e failed: E2E-02"`
2. Agent 修复代码 → 重新走 `commit-push` → `dayu-deploy` → `e2e-browser-test`
3. 最多重试 3 次，超限升级人工

## 质量标准

- 每条 P0 用例必须有 PASS/FAIL 结论和截图
- 不以 AI 主观判断替代页面取证
- 不调用生产/预发环境
