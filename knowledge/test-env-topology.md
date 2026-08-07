---
name: test-env-topology
description: "门店积分测试环境 URL、登录方式与联调拓扑"
version: "0.2.0"
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
| H5 门店积分（test01） | `http://integral.ttb.test.ke.com/store-pointsV2/index?shopCode=TJDY0101&shopCodeInnerTest=TJDY0101` | C 端门店积分首页 V2（**需 hosts 未劫持 integral**） |
| H5 服务基金商城（本地联调） | `http://integral.ttb.test.ke.com:8088/fuwujin-mall/index?shopCode=TJDY0101&shopCodeInnerTest=TJDY0101` | Pipeline `local-e2e-test` H5 入口 |
| PC 管理端（本地联调） | `http://point-pc.ttb.test.ke.com:8089/integral2/activity-config/city` | Pipeline `local-e2e-test` PC 入口 |
| PC 管理端 | `https://point-pc.ttb.test.ke.com/integral2/activity-config/city` | B 端活动配置等城市维度管理 |

> `/store-points/index` 会 redirect 到 `store-pointsV2/index`，与 `fuwujin-mall` 是不同业务模块。

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

### 测试环境（大禹 / test01）

```
浏览器 (H5/PC)
    ↓ HTTPS
CDN / 网关 (ttb.test.ke.com)
    ↓
shop-points（门店积分 API）
    ↓ Dubbo（商城场景）
shop-points-lottery（积分商城 API）
```

### 本地联调（方案 B · nginx，对前端代码零侵入）

```
浏览器 → integral.ttb.test.ke.com:8088 (H5 联调 nginx)
  ├─ /activity-proxy/* → lottery :8080 (profile=test)
  ├─ /integral-proxy/* → shop-points :8081 (本地，默认)
  ├─ /loginUser/*      → shop-points :8081
  └─ 页面/HMR → webpack :9393

浏览器 → point-pc.ttb.test.ke.com:8089 (PC 联调 nginx)
  ├─ /shop-points/*    → shop-points :8081
  ├─ /activity-proxy/* → lottery :8080
  ├─ /api/*            → agent-lego test01（远程）
  ├─ /loginUser/info   → agent-lego test01（远程）
  └─ 页面/HMR → PC webpack :3000

CAS 回跳 → local.ttb.test.ke.com:80 (CAS nginx, sudo) → lottery :8080
```

启动（**全栈联调推荐显式 surfaces**）：

```bash
python3 skills/req-to-dev/scripts/local_stack_up.py \
  --req-id <id> --surfaces h5,pc --nginx-port 8088 --pc-nginx-port 8089
python3 skills/req-to-dev/scripts/local_stack_check.py \
  --req-id <id> --surfaces h5,pc
```

**排障**：`playbooks/local-stack-troubleshooting.md`（hosts、bundle 截断、CORS 403、surfaces 跳过 PC、npm ci 等）

### hosts 与测试环境共存

| hosts 含 `127.0.0.1 integral.ttb.test.ke.com` | 效果 |
|-----------------------------------------------|------|
| 访问 `integral...` **无端口** | 打到本机 **80**（CAS/lottery），**不是** test01 H5 |
| 访问 `integral...:8088` | H5 本地联调栈 |
| 访问 `point-pc...:8089` | PC 本地联调栈 |
| 注释 integral / point-pc 行 | 恢复 test01 解析 |

## E2E 前置条件

1. `dayu-deploy` 阶段全部目标模块已「运行中」且刷新后仍保持
2. 后端日志无启动异常
3. 若涉及 Apollo 新配置，需确认测试环境已同步

## AgentBrowser 登录提示

1. 打开目标 URL
2. 若跳转 CAS 登录 → `fill` 工号/密码 → 提交
3. 登录成功后用 `snapshot -i` 确认页面元素
4. 使用 `--session-name req-to-dev-<name>` 复用登录态，避免重复登录
