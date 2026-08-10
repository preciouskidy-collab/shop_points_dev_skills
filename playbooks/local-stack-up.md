---
name: local-stack-up
description: "启动本地后端与前端 dev server + nginx 网关（方案 B，对前端代码零侵入）"
version: "0.5.0"
category: playbooks
tags:
  - local
  - integration
  - nginx
commands: []
---

# Skill: 本地联调栈启动（方案 B · nginx）

## 适用时机

`backend-test-local` 通过后，`local-e2e-test` 之前。

> **踩坑排障（必读）**：[`local-stack-troubleshooting.md`](local-stack-troubleshooting.md)  
> **启动后必跑**：`local_stack_check.py`（exit 0 才进入 E2E）

## 架构（对业务代码零侵入）

```
浏览器 → integral.ttb.test.ke.com:8088  （H5）
  ├─ /activity-proxy/*  →  lottery :8080
  ├─ /integral-proxy/*  →  shop-points :8081
  ├─ /loginUser/*       →  shop-points :8081
  └─ 页面/HMR          →  webpack :9393

浏览器 → point-pc.ttb.test.ke.com:8089  （PC 积分/商城管理端）
  ├─ /shop-points/*     →  shop-points :8081
  ├─ /activity-proxy/*  →  lottery :8080
  ├─ /api/*             →  agent-lego test01（远程）
  ├─ /loginUser/info    →  agent-lego test01（远程）
  └─ 页面/HMR          →  PC webpack :3000
```

## 前置条件

1. **hosts**：`127.0.0.1 integral.ttb.test.ke.com local.ttb.test.ke.com point-pc.ttb.test.ke.com`
2. **nginx**：`brew install nginx`
3. **后端**：lottery + shop-points 可 `mvn spring-boot:run -Dspring-boot.run.profiles=test`（首次需 `mvn install`，见排障 §坑7）
4. **前端依赖**：各 client 目录已 `npm ci`（脚本会在缺 craco 时自动 ci）
5. **凭证**：`secrets.local.json` → `test_env_app`
6. **测试数据**：默认城市 **天津市**（120000）、门店 **TJDY0101**（见 `knowledge/test-env-topology.md`）

## 一键启动（推荐）

```bash
cd <shop_points_dev_skills 根目录>

# ★ 全栈联调：显式 --surfaces h5,pc（勿仅靠 impact.md，见排障坑13）
python3 skills/req-to-dev/scripts/local_stack_up.py \
  --req-id <req_id> \
  --surfaces h5,pc \
  --nginx-port 8088 \
  --pc-nginx-port 8089

# 健康验收（必须 exit 0）
python3 skills/req-to-dev/scripts/local_stack_check.py \
  --req-id <req_id> --surfaces h5,pc
```

其他模式：

```bash
# 仅 PC
python3 skills/req-to-dev/scripts/local_stack_up.py \
  --req-id <req_id> --surfaces pc --skip-h5

# 远程 shop-points（排查本地后端）
python3 skills/req-to-dev/scripts/local_stack_up.py \
  --req-id <req_id> --surfaces h5,pc --remote-shop-points

# 仅 nginx（进程已手动起）
python3 skills/req-to-dev/scripts/local_stack_up.py \
  --req-id <req_id> --surfaces h5,pc --nginx-only
```

| 参数 | 说明 |
|------|------|
| `--surfaces h5,pc` | **全栈联调推荐显式传入**；覆盖 impact.md |
| `--skip-h5` / `--skip-pc` | 跳过对应 webpack |
| `--remote-shop-points` | shop-points 走远程 test01 |
| `--nginx-only` | 只渲染/重载 nginx |

`impact.md` 仍用于：`mall_scope=none` 跳过 lottery、`frontend_scope=none` 跳过所有前端。  
**但 `surfaces` 不应单独决定「起不起 PC」**——全栈验收时由 CLI `--surfaces h5,pc` 覆盖。

## 启动后验收

1. `local_stack_up.py` exit 0（含内置健康检查）
2. `local_stack_check.py` exit 0
3. 排障文档 §二 检查清单（bundle、CORS POST）

## 停止

```bash
python3 skills/req-to-dev/scripts/local_stack_down.py --req-id <req_id>
```

## 产出

- `changes/<req_id>/tests/local_stack_report.md`
- `changes/<req_id>/tests/local_stack_state.json`
- `changes/<req_id>/tests/local-stack/nginx/local-gateway.conf`
- `changes/<req_id>/tests/local-stack/logs/*.log`

## 入口

| 端 | URL |
|----|-----|
| H5 服务基金商城 | `http://integral.ttb.test.ke.com:8088/fuwujin-mall/index?shopCode=TJDY0101&shopCodeInnerTest=TJDY0101` |
| PC 管理端 | `http://point-pc.ttb.test.ke.com:8089/integral2/activity-config/city` |

## 质量标准

- `local_stack_check.py` 全部通过
- 报告含双入口 URL、health 与停止命令
- 前端仓库 **无** 误改的 `package-lock.json`（只用 `npm ci`）
