---
name: local-stack-up
description: "启动本地后端与前端 dev server + nginx 网关（方案 B，对前端代码零侵入）"
version: "0.3.0"
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

## 架构（对前端 `src/` 零侵入）

**默认使用 `--nginx-port 8088`（免 sudo）**：

```
浏览器 → http://integral.ttb.test.ke.com:8088  （联调 nginx）
  ├─ /activity-proxy/*  →  本地 shop-points-lottery :8080  (profile=test)
  ├─ /integral-proxy/*  →  test01 shop-points
  ├─ /loginUser/*       →  test01 shop-points
  └─ 其余页面/HMR      →  webpack dev :9393

CAS 回跳（另需 sudo 起 80 端口反代，见排障文档）：
  local.ttb.test.ke.com:80 → lottery :8080
```

**不修改** `store-integral-h5` 业务代码或 `craco.config.js` 的 proxy target。

## 前置条件

1. **hosts**（本地联调需要；会劫持测试环境域名，见排障文档 §六）：
   ```
   127.0.0.1 integral.ttb.test.ke.com local.ttb.test.ke.com
   ```
2. **nginx**：`brew install nginx`（慢时可走本机代理，见排障文档 §坑 6）
3. **后端**：`shop-points-lottery` 可 `mvn spring-boot:run -Dspring-boot.run.profiles=test`（首次失败先 `mvn install -pl shop-points-lottery-start -am -DskipTests`）
4. **凭证**：`skills/req-to-dev/config/secrets.local.json` → `test_env_app`
5. **门店**：默认 `TJDY0101`（`shopCode` + `shopCodeInnerTest`）
6. **CAS 反代**（浏览器登录）：`config/nginx/cas-local.conf.template` + sudo 起 80 端口

## 一键启动

```bash
cd <shop_points_dev_skills 根目录>

python3 skills/req-to-dev/scripts/local_stack_up.py \
  --req-id <req_id> \
  --nginx-port 8088
```

可选参数：

| 参数 | 说明 |
|------|------|
| `--nginx-port 8088` | **推荐**，无 sudo |
| `--nginx-only` | 前后端已手动启动，只起 nginx |
| `--skip-lottery` / `--skip-frontend` | 跳过对应进程 |
| `--shop-code TJDY0101` | 覆盖默认门店 |

## 启动后验收（未通过勿进 E2E）

见 [`local-stack-troubleshooting.md`](local-stack-troubleshooting.md) §二：

- `:8088` H5 入口 HTTP 200
- `bundle.js` 约 7MB（非 2MB 截断）
- `order/preview` POST 非 CORS 403
- `:8080` lottery、`:9393` webpack 均在监听

## 停止

```bash
python3 skills/req-to-dev/scripts/local_stack_down.py --req-id <req_id>
# CAS 反代（若起过）：sudo nginx -s stop -p /tmp/cas-nginx -c /tmp/cas-nginx/cas.conf
```

## 产出

- `changes/<req_id>/tests/local_stack_report.md`
- `changes/<req_id>/tests/local_stack_state.json`（PID / URL）
- 渲染配置：`changes/<req_id>/tests/local-stack/nginx/integral-local.conf`

## H5 入口（E2E · 服务基金商城）

```
http://integral.ttb.test.ke.com:8088/fuwujin-mall/index?shopCode=TJDY0101&shopCodeInnerTest=TJDY0101
```

**注意**：`/store-points/...` 是门店积分首页，与 `fuwujin-mall` 不同；且不带 `:8088` 会打到本机 80（CAS/lottery），不是联调 H5。

## 质量标准

- 检查清单 §二 全部通过
- 报告中含停止命令与排障文档链接
