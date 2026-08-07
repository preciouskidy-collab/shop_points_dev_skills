---
name: local-stack-troubleshooting
description: "本地联调栈（方案 B）与 local-e2e-test 阶段踩坑沉淀与验收清单"
version: "1.0.0"
category: playbooks
tags:
  - local
  - nginx
  - e2e
  - troubleshooting
commands: []
---

# 本地联调栈 · 踩坑与排障（方案 B）

> **适用阶段**：`local-stack-up` → `local-e2e-test`  
> **首次联调实录**：`20260806-req-f092cf8e`（服务基金商城黄字提示）

Pipeline 走到本环节时，Agent **必须先读本文件**，再执行 `local_stack_up.py` / 浏览器 E2E。

---

## 一、推荐拓扑（默认 `--nginx-port 8088`）

```
浏览器 → http://integral.ttb.test.ke.com:8088   （联调 nginx）
  ├─ /activity-proxy/*  →  本地 lottery :8080  （profile=test）
  ├─ /integral-proxy/*  →  test01 shop-points
  ├─ /loginUser/*       →  test01 shop-points
  └─ 页面 / HMR         →  webpack dev :9393

浏览器 → http://local.ttb.test.ke.com:80        （CAS 反代 nginx，需 sudo 单独起）
  └─ /*                 →  本地 lottery :8080   （CAS 登录回跳）
```

**两个 nginx 实例、两个端口，不要混用：**

| 实例 | 端口 | server_name | 用途 |
|------|------|-------------|------|
| 联调网关 | **8088**（默认，免 sudo） | `integral.ttb.test.ke.com` | H5 页面 + API 代理 |
| CAS 反代 | **80**（需 `sudo`） | `local.ttb.test.ke.com` | CAS 登录 ticket 回跳 |

模板：`skills/req-to-dev/config/nginx/cas-local.conf.template`

---

## 二、启动前检查清单（Agent 必做）

```bash
# 1. hosts（本地联调需要；见下文「hosts 陷阱」）
grep -E 'integral|local\.ttb' /etc/hosts

# 2. 三端口
lsof -i :8088 -i :8080 -i :9393 | grep LISTEN

# 3. H5 入口 200（注意端口）
curl -sS -o /dev/null -w '%{http_code}\n' \
  'http://integral.ttb.test.ke.com:8088/fuwujin-mall/index?shopCode=TJDY0101'

# 4. bundle 完整（约 7MB，小于 3MB 说明 nginx 截断）
curl -sS -o /tmp/bundle.js -w '%{size_download}\n' \
  'http://integral.ttb.test.ke.com:8088/static/js/bundle.js'

# 5. order/preview 不因 CORS 403（带 Origin 模拟浏览器 POST）
curl -sS -o /tmp/preview.txt -w '%{http_code}\n' -X POST \
  'http://integral.ttb.test.ke.com:8088/activity-proxy/api/mall/order/preview' \
  -H 'Content-Type: application/json' \
  -H 'Origin: http://integral.ttb.test.ke.com:8088' \
  -d '{"productId":153,"subjectId":"TJDY0101","price":100,"quantity":1,"attach":{}}'
# 期望 200 或业务未登录码，绝不能是 403 + "Invalid CORS request"
```

---

## 三、踩坑实录（症状 → 原因 → 处理）

### 坑 1：`integral.ttb.test.ke.com` 不带端口打不开 / 跳到 CAS / 404

| 项 | 说明 |
|----|------|
| **症状** | `http://integral.ttb.test.ke.com/store-points/...`（无端口）以前能开，加 hosts 后不行 |
| **原因** | hosts 把域名指到 `127.0.0.1`；本机 **80** 上是 CAS 反代（lottery API），不是测试环境 H5 |
| **处理** | 本地联调 **必须带 `:8088`**；访问测试环境时 **注释掉** hosts 里 `integral.ttb.test.ke.com` 那一行 |
| **与 CORS/bundle 修复无关** | 那是 8088 联调栈内部问题，不导致 80 端口 store-points 失效 |

### 坑 2：`502 Bad Gateway`

| 项 | 说明 |
|----|------|
| **症状** | 浏览器或 curl 访问 `:8088` 返回 502 |
| **原因** | webpack dev **:9393 未启动**（会话结束、终端关了、只起了 nginx） |
| **处理** | `local_stack_up.py` 全量启动，或 `cd store-integral-h5/client-integral && BUILD_ENV=development npx craco start` |

### 坑 3：页面一直 loading / 白屏 / React 不渲染

| 项 | 说明 |
|----|------|
| **症状** | 标题「门店积分」但永远转圈；`bundle.js` 下载不完整 |
| **原因** | nginx 代理大文件时写 `/opt/homebrew/var/run/nginx/proxy_temp` **Permission denied**，响应被截断（~2MB 而非 ~7MB） |
| **处理** | 模板已配置 `proxy_temp_path` 到 `changes/<req_id>/tests/local-stack/nginx/proxy_temp`；`location /` 已加 `proxy_buffering off`。验证见检查清单 §4 |
| **日志特征** | `nginx/logs/error.log` 出现 `open() ".../proxy_temp/..." failed (13: Permission denied)` |

### 坑 4：兑换弹层 `serverError 403` / `Invalid CORS request`

| 项 | 说明 |
|----|------|
| **症状** | 点「去兑换」失败；Network 里 `POST .../activity-proxy/api/mall/order/preview` → **403**，body 20 字节 |
| **原因** | 浏览器 POST 带 `Origin: http://integral.ttb.test.ke.com:8088`；本地 lottery `MvcConfig` 白名单只有 `fcn.ke.com` 等 |
| **处理** | 联调 nginx 的 `/activity-proxy/` 已加 `proxy_set_header Origin ""` 剥掉 Origin 再转发 |
| **验证** | 检查清单 §5 |

### 坑 5：CAS 登录后 `chrome-error` / `local.ttb.test.ke.com` 404

| 项 | 说明 |
|----|------|
| **症状** | 登录成功却白屏；URL 落在 `http://local.ttb.test.ke.com/login/cas?...` 或根路径 |
| **原因** | CAS 回跳目标是 **`local.ttb.test.ke.com:80`**，本机 80 无服务 |
| **处理** | 用 sudo 起 CAS 反代（见 `cas-local.conf.template`），**全路径**反代到 lottery:8080，不要只配 `/login/cas` |
| **配置陷阱** | heredoc 里 `proxy_pass ...8080\;` 多写反斜杠会报 `invalid number of arguments` |

### 坑 6：`brew install nginx` 极慢 / 失败

| 项 | 说明 |
|----|------|
| **处理** | 本机有代理时：`export https_proxy=http://127.0.0.1:7897 http_proxy=... all_proxy=socks5://...` 后再 `brew install nginx` |

### 坑 7：lottery 首次 `spring-boot:run` 编译失败

| 项 | 说明 |
|----|------|
| **处理** | 在 lottery 仓库：`mvn install -pl shop-points-lottery-start -am -DskipTests`，再 `mvn spring-boot:run -pl shop-points-lottery-start -Dspring-boot.run.profiles=test` |

### 坑 8：E2E 看不到「选择支付方式」/ 黄字提示

| 项 | 说明 |
|----|------|
| **原因 A** | 上面坑 4（403）导致 `orderPreview` 失败 |
| **原因 B** | 测试门店/商品无混合支付数据（如 TJDY0101 仅「花桥优惠券」productId=153） |
| **处理** | 先确认 preview 200；再向 PM 要支持「服务基金+权益积分」且服务基金余额为 0 的商品/门店 |

### 坑 9：入口路径混淆

| 路径 | 用途 |
|------|------|
| `/fuwujin-mall/index` | **服务基金积分商城**（本需求 E2E 入口） |
| `/store-points/index` | 门店积分首页（会 redirect 到 `store-pointsV2`） |
| `localhost:9393` | 仅调试 webpack，**不能**作最终 E2E（绕过 nginx） |

---

## 四、CAS 反代一次性配置（需 sudo）

```bash
mkdir -p /tmp/cas-nginx/logs
cp skills/req-to-dev/config/nginx/cas-local.conf.template /tmp/cas-nginx/cas.conf
sudo /opt/homebrew/bin/nginx -p /tmp/cas-nginx -c /tmp/cas-nginx/cas.conf
# 重载：sudo /opt/homebrew/bin/nginx -s reload -p /tmp/cas-nginx -c /tmp/cas-nginx/cas.conf
# 停止：sudo /opt/homebrew/bin/nginx -s stop -p /tmp/cas-nginx -c /tmp/cas-nginx/cas.conf
```

---

## 五、标准启动命令（复制即用）

```bash
cd <shop_points_dev_skills 根目录>

# 全栈（推荐）
python3 skills/req-to-dev/scripts/local_stack_up.py \
  --req-id <req_id> \
  --nginx-port 8088

# 前后端已手动启动，只补 nginx
python3 skills/req-to-dev/scripts/local_stack_up.py \
  --req-id <req_id> \
  --nginx-port 8088 \
  --nginx-only

# 停止
python3 skills/req-to-dev/scripts/local_stack_down.py --req-id <req_id>
```

**H5 入口（E2E）**：

```
http://integral.ttb.test.ke.com:8088/fuwujin-mall/index?shopCode=TJDY0101&shopCodeInnerTest=TJDY0101
```

**登录**：`secrets.local.json` → `test_env_app`；或 `ab_h5_bypass_http.py`（`H5_URL` 改为带 `:8088` 的入口）。

---

## 六、hosts 与测试环境共存策略

| 场景 | hosts 建议 |
|------|------------|
| 仅本地联调 | 保留 `127.0.0.1 integral.ttb.test.ke.com local.ttb.test.ke.com`，访问 **带 :8088** |
| 仅访问 test01 页面 | **删除或注释** `integral.ttb.test.ke.com` 行 |
| 两者切换频繁 | 用 `/etc/hosts` 注释切换，或联调固定 bookmark `:8088` 入口 |

---

## 七、产出与关联文档

| 文件 | 说明 |
|------|------|
| `changes/<req_id>/tests/local_stack_report.md` | 栈启动报告 |
| `changes/<req_id>/tests/local_e2e_report.md` | E2E 结果 |
| `playbooks/local-stack-up.md` | 启动 SOP |
| `playbooks/local-e2e-browser-test.md` | 浏览器验收 SOP |
| `knowledge/test-env-topology.md` | 测试环境 URL 与拓扑 |
| `skills/req-to-dev/config/nginx/README.md` | nginx 模板说明 |
