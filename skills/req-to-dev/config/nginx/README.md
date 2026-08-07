# 本地 nginx 网关（方案 B）

由 `skills/req-to-dev/scripts/local_stack_up.py` 读取 `integral-local.conf.template`，
渲染到 `changes/<req_id>/tests/local-stack/nginx/integral-local.conf`。

**不修改** `store-integral-h5` 仓库。

**排障手册**：[`playbooks/local-stack-troubleshooting.md`](../../playbooks/local-stack-troubleshooting.md)

## 模板文件

| 文件 | 用途 |
|------|------|
| `integral-local.conf.template` | 联调网关（默认 `:8088`）→ webpack + lottery + test01 |
| `cas-local.conf.template` | CAS 回跳（本机 `:80`，需 sudo）→ lottery |

## hosts

```
127.0.0.1 integral.ttb.test.ke.com local.ttb.test.ke.com
```

**警告**：`integral` 指到本机后，不带端口的 URL 不再访问 test01。本地联调请用 **`:8088`**；访问测试环境时注释该行。详见排障文档 §六。

## 依赖

```bash
# 慢时可先 export 本机代理
brew install nginx
```

## 端口

| 端口 | 服务 | 说明 |
|------|------|------|
| **8088** | 联调 nginx | 默认，`local_stack_up.py --nginx-port 8088`，免 sudo |
| **80** | CAS nginx | 单独 sudo 启动 `cas-local.conf.template` |
| **8080** | lottery | `spring-boot:run` profile=test |
| **9393** | webpack | `craco start` |

## 模板内已修复的坑（勿删）

1. **`proxy_temp_path` / `client_body_temp_path`**：指向 `changes/.../nginx/` 下可写目录，避免 bundle ~7MB 被截断
2. **`location /` → `proxy_buffering off`**：webpack 大文件流式代理
3. **`/activity-proxy/` → `proxy_set_header Origin ""`**：避免 lottery CORS 403（`order/preview`）

## 启动示例

```bash
python3 skills/req-to-dev/scripts/local_stack_up.py \
  --req-id <id> --nginx-port 8088
```

访问：

```
http://integral.ttb.test.ke.com:8088/fuwujin-mall/index?shopCode=TJDY0101&shopCodeInnerTest=TJDY0101
```

CAS（另开终端，需 sudo）：

```bash
mkdir -p /tmp/cas-nginx/logs
cp skills/req-to-dev/config/nginx/cas-local.conf.template /tmp/cas-nginx/cas.conf
sudo /opt/homebrew/bin/nginx -p /tmp/cas-nginx -c /tmp/cas-nginx/cas.conf
```
