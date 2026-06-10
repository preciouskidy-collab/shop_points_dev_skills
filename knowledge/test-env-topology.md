---
name: test-env-topology
description: "门店积分测试环境 URL、登录方式与联调拓扑"
version: "0.1.0"
category: knowledge
tags:
  - test-env
  - e2e
  - integration
commands: []
---

# 测试环境拓扑

## 页面入口

| 端 | URL | 用途 |
|----|-----|------|
| H5 门店积分 | `http://integral.ttb.test.ke.com/store-pointsV2/index?shopCode=TJDY0101&shopCodeInnerTest=TJDY0101` | C 端门店积分首页 V2 |
| PC 管理端 | `https://point-pc.ttb.test.ke.com/integral2/activity-config/city` | B 端活动配置等城市维度管理 |

## 测试账号

从 `skills/req-to-dev/config/secrets.local.json` 读取：

```json
{
  "test_env_app": {
    "username": "<工号>",
    "password": "<密码>"
  }
}
```

**注意**：测试环境业务登录凭证与大禹平台部署凭证是两套，不要混用。

## 测试门店

| 字段 | 值 |
|------|-----|
| shopCode | `TJDY0101` |
| shopCodeInnerTest | `TJDY0101` |

H5 URL 已内置上述参数，E2E 可直接使用。

## 联调拓扑

```
浏览器 (H5/PC)
    ↓ HTTPS
CDN / 网关 (ttb.test.ke.com)
    ↓
shop-points（门店积分 API）
    ↓ Dubbo（商城场景）
shop-points-lottery（积分商城 API）
```

## E2E 前置条件

1. `dayu-deploy` 阶段全部目标模块已「运行中」且刷新后仍保持
2. 后端日志无启动异常
3. 若涉及 Apollo 新配置，需确认测试环境已同步

## AgentBrowser 登录提示

1. 打开目标 URL
2. 若跳转 CAS 登录 → `fill` 工号/密码 → 提交
3. 登录成功后用 `snapshot -i` 确认页面元素
4. 使用 `--session-name req-to-dev-<name>` 复用登录态，避免重复登录
