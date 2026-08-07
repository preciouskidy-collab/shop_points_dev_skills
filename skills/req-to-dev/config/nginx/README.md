# 本地 nginx 网关（方案 B）

由 `skills/req-to-dev/scripts/local_stack_up.py` 读取 `local-gateway.conf.template`，
渲染到 `changes/<req_id>/tests/local-stack/nginx/local-gateway.conf`。

**不修改** 各前端/后端业务仓库。

**排障手册**：[`playbooks/local-stack-troubleshooting.md`](../../playbooks/local-stack-troubleshooting.md)

## 模板文件

| 文件 | 用途 |
|------|------|
| `local-gateway.conf.template` | 双网关：H5 `:8088` + PC `:8089` |
| `integral-local.conf.template` | **已废弃**，保留仅供对照；请用 `local-gateway` |
| `cas-local.conf.template` | CAS 回跳（本机 `:80`，需 sudo）→ lottery |

## hosts

```
127.0.0.1 integral.ttb.test.ke.com local.ttb.test.ke.com point-pc.ttb.test.ke.com
```

**警告**：`integral` / `point-pc` 指到本机后，不带端口的 URL 不再访问 test01。本地联调请用 **`:8088`（H5）/ `:8089`（PC）**。

## 依赖

```bash
brew install nginx
```

## 端口

| 端口 | 服务 | 说明 |
|------|------|------|
| **8088** | H5 联调 nginx | `--nginx-port 8088` |
| **8089** | PC 联调 nginx | `--pc-nginx-port 8089` |
| **8080** | lottery | `mvn spring-boot:run` profile=test |
| **8081** | shop-points | 默认本地，`PORT=8081` |
| **9393** | H5 webpack | `craco start` |
| **3000** | PC webpack | `store-integral/client` |
| **80** | CAS nginx | 单独 sudo 启动 |

## 路由摘要

### H5（`integral.ttb.test.ke.com:8088`）

| 路径 | 默认目标 |
|------|----------|
| `/` | webpack :9393 |
| `/activity-proxy/` | lottery :8080 |
| `/integral-proxy/` | shop-points :8081（`--remote-shop-points` 时 test01） |
| `/loginUser/` | shop-points :8081 |

### PC（`point-pc.ttb.test.ke.com:8089`）

| 路径 | 默认目标 |
|------|----------|
| `/` | PC webpack :3000 |
| `/shop-points/` | shop-points :8081 |
| `/activity-proxy/` | lottery :8080 |
| `/api/` | agent-lego test01（远程） |
| `/loginUser/info` | agent-lego test01（远程） |
| `/shop-points-calc/` | shop-points-calc test01（远程） |

## 模板内已修复的坑（勿删）

1. **`proxy_temp_path`**：避免 bundle ~7MB 被截断
2. **`location /` → `proxy_buffering off`**：webpack 大文件流式代理
3. **`/activity-proxy/` → `proxy_set_header Origin ""`**：避免 lottery CORS 403
4. **`/shop-points`、`/integral-proxy/` → `proxy_set_header Origin ""`**：避免本地 shop-points CORS 403
5. **PC `/shop-points` 的 `proxy_pass` 无尾部斜杠**：保留 `/shop-points` URI 前缀（否则 404）
6. **`/loginUser/info` → test01**（非 dev01）

## 启动示例

```bash
python3 skills/req-to-dev/scripts/local_stack_up.py \
  --req-id <id> --surfaces h5,pc --nginx-port 8088 --pc-nginx-port 8089

python3 skills/req-to-dev/scripts/local_stack_check.py \
  --req-id <id> --surfaces h5,pc
```

访问：

- H5: `http://integral.ttb.test.ke.com:8088/fuwujin-mall/index?shopCode=TJDY0101`
- PC: `http://point-pc.ttb.test.ke.com:8089/integral2/activity-config/city`
