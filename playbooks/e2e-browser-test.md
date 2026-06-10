---
name: e2e-browser-test
description: "基于 FDH 验收场景，使用 agent-browser 在测试环境页面执行 E2E 自测"
version: "0.1.0"
category: playbooks
tags:
  - e2e
  - agent-browser
  - test-env
commands: []
---

# Skill: 测试环境 E2E 浏览器自测

## 适用时机

`dayu-deploy` 全部模块部署成功后。

**跳过条件**：`impact/impact.md` 中 `frontend_scope: none`。

## 前置条件

- `deploy/dayu_deploy_report.md` 全部模块 ✅
- `handoff/frontend-handoff.md` §6 或 `handoff/api-contract.yaml` 的 `e2e_cases` 已就绪
- `secrets.local.json` 中 `test_env_app` 凭证已配置

## 测试入口

| 端 | URL |
|----|-----|
| H5 | `http://integral.ttb.test.ke.com/store-pointsV2/index?shopCode=TJDY0101&shopCodeInnerTest=TJDY0101` |
| PC | `https://point-pc.ttb.test.ke.com/integral2/activity-config/city` |

详见 `knowledge/test-env-topology.md`。

## AgentBrowser 初始化

```bash
export AGENT_BROWSER_EXECUTABLE_PATH="$HOME/.agent-browser/browsers/chrome-149.0.7827.55/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"
export AGENT_BROWSER_HEADED=1
export AGENT_BROWSER_SESSION_NAME="req-to-dev-<change-name>-h5"

# ⚠️ H5 测试环境是 HTTP，必须放行 CAS 回调链路上的所有 http origin（见下节）
export AGENT_BROWSER_ARGS="--unsafely-treat-insecure-origin-as-secure=http://integral.ttb.test.ke.com,http://shop-points-lottery.shop-points-test01.ttb.test.ke.com,http://shop-points-lottery.shop-points-test01.ttb.test.ke.com:80,http://shop-points.shop-points-test01.ttb.test.ke.com,http://shop-points.shop-points-test01.ttb.test.ke.com:80,--disable-features=HttpsFirstMode,HttpsUpgrades,HttpsFirstBalancedMode,--disable-web-security,--allow-running-insecure-content,--ignore-certificate-errors,--test-type,--remote-allow-origins=*"

# H5 必须手机模式（在打开页面之前设置）
agent-browser close
agent-browser --args "$AGENT_BROWSER_ARGS" open about:blank
agent-browser set device "iPhone 12"
agent-browser open "http://integral.ttb.test.ke.com/fuwujin-mall/index?shopCode=TJDY0101&shopCodeInnerTest=TJDY0101"

# 或一键：close + 手机模式 + CAS 登录（员工 → 账号登录 → 填表）
python3 skills/req-to-dev/scripts/ab_h5_bypass_http.py
```

### HTTP 不安全连接页（登录后常见）

**现象**：CAS 登录（HTTPS）成功后跳回 `http://integral.ttb.test.ke.com`，Chrome 弹出「此网站不支持安全连接」，需点 **「继续访问网站」**。CLI 可能报 `ERR_BLOCKED_BY_CLIENT` 或停在 `chrome-error://chromewebdata/`。

**原因**：不是广告拦截，是 Chrome 对 HTTP 站点的安全策略；登录重定向会再次触发。

**处理（二选一，推荐 A）**：

**A. 启动参数放行（推荐，可免手点）**——`--args` 仅在 **新启动浏览器** 时生效：

```bash
agent-browser close   # 若 daemon 已在跑，必须先 close
agent-browser --args "$AGENT_BROWSER_ARGS" open "http://integral.ttb.test.ke.com/fuwujin-mall/index?shopCode=TJDY0101&shopCodeInnerTest=TJDY0101"
agent-browser wait --load networkidle
```

**B. 兜底（极少需要）**：`python3 skills/req-to-dev/scripts/ab_h5_bypass_http.py proceed-only`（osascript 点原生按钮，需 macOS「辅助功能」权限）。`find role button click` 对 `chrome-error` 无效，**不要依赖手点**。

**注意**：

- 大禹部署与 H5 E2E 建议用 **不同** `AGENT_BROWSER_SESSION_NAME`（如 `req-to-dev-<name>` vs `req-to-dev-<name>-h5`）。
- 不要随便 `agent-browser close` 后不带 `--args` 再 open H5，否则会再次撞上 HTTP 拦截。
- H5 内点击 React 按钮优先用：`agent-browser find role button click --name "去兑换"`（比 `click @eN` 稳）。
- **多 Tab 说明**：CAS 登录会依次跳转 `integral` → `shop-points-lottery` / `shop-points` → `test-login`，Chrome 常把中间站留在新 Tab；调试时多次 `open` 也会堆积。`ab_h5_bypass_http.py` 登录成功后会 `close_extra_tabs` 只留 H5 主 Tab；手动清理可用 `agent-browser tab list` + `agent-browser tab close 1`。

## 执行流程

### 1. 登录（每端首次）

**H5 端**须先 `set device "iPhone 12"`（或 `iPhone 14`），再打开入口 URL。

**CAS 登录顺序（固定，不可跳步）**：

1. 等待 CAS 页 **「加载中...」消失**（`networkidle` 后 SPA 仍需 1–3s）
2. 点击 **员工**（手机模式：`find role button click --name "员工"`；PC 模式：点 `.p-account-name` 员工卡片）
3. 点击 **账号登录**（PC 扫码页需切换 Tab；**手机模式**选员工后通常直接进入账号表单，可跳过）
4. `fill` 工号 / 密码 → `find role button click --name "登录"`（PC 端按钮文案可能带空格：`登 录`）

```bash
agent-browser set device "iPhone 12"
agent-browser open "<H5入口URL>" \
  && agent-browser wait --load networkidle \
  && agent-browser snapshot -i

# 登录成功后 screenshot 取证
agent-browser screenshot "tests/e2e-login-h5.png"
```

使用 `--session-name` 复用登录态，同端后续用例无需重复登录。

### 2. 逐条执行 E2E 用例

对 `e2e_cases` 或 FDH §6 中每条用例：

```bash
# 导航到目标页面（若不在当前页）
agent-browser open "<url>" && agent-browser wait --load networkidle

# 执行操作（click / fill / scroll 等）
agent-browser snapshot -i
agent-browser click @eN

# 断言：snapshot 确认期望文案/元素存在
agent-browser get text @eM
agent-browser screenshot "tests/e2e-<case-id>.png"
```

### 3. 失败时取证

- 截图当前页面
- 若为接口问题：到大禹终端查 `/data0/www/applogs/shop-points` 日志
- 记录 Network 错误（可用 `agent-browser eval` 查页面状态）

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
