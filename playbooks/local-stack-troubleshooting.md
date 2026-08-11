---
name: local-stack-troubleshooting
description: "本地联调栈（方案 B）与 local-e2e-test 阶段踩坑沉淀与验收清单"
version: "1.1.0"
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
> **首次联调实录**：`20260806-req-f092cf8e`（服务基金商城 + 积分/商城管理端全栈）  
> Pipeline 走到本环节时，Agent **必须先读本文件**，再执行 `local_stack_up.py` / `local_stack_check.py` / 浏览器 E2E。

---

## 零、Agent 执行顺序（Harness 复利）

```
1. 读本文件 §二 检查清单
2. local_stack_up.py --surfaces h5,pc   # 全栈联调默认显式带 surfaces，勿只靠 impact.md
3. local_stack_check.py --req-id <id>   # 必须 exit 0 再进入 E2E
4. local-e2e-browser-test.md 按 impact surfaces 选入口验收
```

**原则**：`impact.md` 的 `surfaces` 描述**需求改动面**，不等于「本地只起一半栈」。全栈联调验收时一律 `--surfaces h5,pc`，除非明确只需单端。

**R7 自愈（Agent 必读）**：栈/E2E 阻塞时 Agent **自行** `local_stack_check` → 复用健康网关 / 杀端口重试 / 重启服务，**禁止**把 `lsof`、杀进程甩给用户。见 `guardrails/pipeline-redlines.md` R7。

---

## 一、推荐拓扑（默认 `--nginx-port 8088` + `--pc-nginx-port 8089`）

```
浏览器 → http://integral.ttb.test.ke.com:8088   （H5 联调 nginx）
  ├─ /activity-proxy/*  →  本地 lottery :8080
  ├─ /integral-proxy/*  →  本地 shop-points :8081
  ├─ /loginUser/*       →  本地 shop-points :8081
  └─ 页面 / HMR         →  webpack dev :9393

浏览器 → http://point-pc.ttb.test.ke.com:8089   （PC 联调 nginx）
  ├─ /shop-points/*     →  本地 shop-points :8081（保留 URI 前缀，勿 trailing slash 剥路径）
  ├─ /activity-proxy/*  →  本地 lottery :8080
  ├─ /api/*             →  远程 agent-lego **test01**
  ├─ /loginUser/info    →  远程 agent-lego **test01**（非 dev01）
  └─ 页面 / HMR         →  PC webpack :3000

浏览器 → http://local.ttb.test.ke.com:80        （CAS 反代 nginx，需 sudo 单独起）
  └─ /*                 →  本地 lottery :8080
```

| 实例 | 端口 | server_name | 用途 |
|------|------|-------------|------|
| H5 联调网关 | **8088** | `integral.ttb.test.ke.com` | H5 页面 + API |
| PC 联调网关 | **8089** | `point-pc.ttb.test.ke.com` | 积分/商城管理端 |
| CAS 反代 | **80**（sudo） | `local.ttb.test.ke.com` | CAS 登录回跳 |
| lottery | **8080** | — | shop-points-lottery |
| shop-points | **8081** | — | 积分主服务 |
| H5 webpack | **9393** | — | store-integral-h5/client-integral |
| PC webpack | **3000** | — | store-integral/client |

---

## 二、启动前 / 恢复会话检查清单（Agent 必做）

```bash
# 0. 一键健康检查（推荐：会话恢复、启动后复检）
python3 skills/req-to-dev/scripts/local_stack_check.py \
  --req-id <req_id> --surfaces h5,pc

# 1. hosts
grep -E 'integral|local\.ttb|point-pc' /etc/hosts

# 2. 六个关键端口（后端+前端+双 nginx 都要在）
lsof -nP -iTCP -sTCP:LISTEN | grep -E ':(8088|8089|8080|8081|9393|3000)\s'

# 3. H5 入口 200
curl -sS -o /dev/null -w '%{http_code}\n' \
  'http://integral.ttb.test.ke.com:8088/fuwujin-mall/index?shopCode=TJDY0101'

# 4. PC 入口 200
curl -sS -o /dev/null -w '%{http_code}\n' \
  'http://point-pc.ttb.test.ke.com:8089/integral2/activity-config/city'

# 5. bundle 完整（约 7MB，小于 3MB 说明 nginx 截断）
curl -sS -o /tmp/bundle.js -w '%{size_download}\n' \
  'http://integral.ttb.test.ke.com:8088/static/js/bundle.js'

# 6. H5 preview 不因 CORS 403
curl -sS -o /dev/null -w '%{http_code}\n' -X POST \
  'http://integral.ttb.test.ke.com:8088/activity-proxy/api/mall/order/preview' \
  -H 'Content-Type: application/json' \
  -H 'Origin: http://integral.ttb.test.ke.com:8088' \
  -d '{"productId":153,"subjectId":"TJDY0101","price":100,"quantity":1,"attach":{}}'

# 7. PC shop-points POST 不因 CORS 403
curl -sS -o /dev/null -w '%{http_code}\n' -X POST \
  'http://point-pc.ttb.test.ke.com:8089/shop-points/manage/common/permission/projects' \
  -H 'Content-Type: application/json' \
  -H 'Origin: http://point-pc.ttb.test.ke.com:8089' -d '{}'
# 期望 200/302/401 或业务码，绝不能 403 + Invalid CORS request

# 8. PC 登录探活（必须 test01，503 说明代理目标错或 VPN 不通）
curl -sS -o /dev/null -w '%{http_code}\n' \
  'http://point-pc.ttb.test.ke.com:8089/loginUser/info'
```

**假启动告警**：若 `:8088`/`:8089` 在监听但 `:9393`/`:3000` 不在 → 网关返回 **502**，后端 health 仍可能 200。务必看 webpack 端口。

---

## 三、踩坑实录（症状 → 原因 → 处理）

### 坑 1：`integral.ttb.test.ke.com` 不带端口打不开 / 跳到 CAS / 404

| 项 | 说明 |
|----|------|
| **症状** | 无端口 URL 以前能开，加 hosts 后不行 |
| **原因** | hosts 把域名指到 `127.0.0.1`；本机 **80** 是 CAS/lottery，不是 test01 H5 |
| **处理** | 本地联调 **必须带 `:8088`（H5）/ `:8089`（PC）**；访问 test01 时注释 hosts 中对应行 |

### 坑 2：`502 Bad Gateway`（H5 或 PC）

| 项 | 说明 |
|----|------|
| **症状** | `:8088` 或 `:8089` 返回 502，但 `:8080`/`:8081` 正常 |
| **原因** | **webpack 未启动**（`:9393` H5 / `:3000` PC）；常见于终端关闭、只起了 nginx+后端 |
| **处理** | `local_stack_up.py --surfaces h5,pc` 全量启动；或手动 `npm start`（见坑 14） |
| **验证** | `local_stack_check.py` 中 `h5_webpack_direct` / `pc_webpack_direct` 须为 200 |

### 坑 3：页面 loading / 白屏 / bundle 截断

| 项 | 说明 |
|----|------|
| **症状** | `bundle.js` ~2MB 而非 ~7MB |
| **原因** | nginx `proxy_temp` Permission denied |
| **处理** | 模板已设 `proxy_temp_path` 到 change 目录 + `proxy_buffering off`；查 `nginx/logs/error.log` |

### 坑 4：H5 兑换 `order/preview` → 403 Invalid CORS request

| 项 | 说明 |
|----|------|
| **原因** | 浏览器 POST 带 Origin；本地 lottery CORS 白名单不含联调域名 |
| **处理** | nginx `/activity-proxy/` 已 `proxy_set_header Origin ""` |
| **验证** | 检查清单 §6 |

### 坑 5：CAS 登录后 chrome-error / local.ttb 404

| 项 | 说明 |
|----|------|
| **处理** | sudo 起 CAS 反代（`cas-local.conf.template`），全路径反代 lottery:8080 |

### 坑 6：`brew install nginx` 极慢

| 项 | 说明 |
|----|------|
| **处理** | 配置 `http_proxy` / `all_proxy` 后再 brew |

### 坑 7：lottery / shop-points 首次 `spring-boot:run` 失败

| 项 | 说明 |
|----|------|
| **lottery** | `cd shop-points-lottery && mvn install -pl shop-points-lottery-start -am -DskipTests` |
| **shop-points** | `cd shop-points && mvn install -pl shop-points-start -am -DskipTests` |
| **典型报错** | `Could not find artifact ... shop-points-schedule:jar` → 未 install 子模块 |
| **环境** | 内网 VPN + Apollo；建议 `KAFKA_CONSUME_ENABLED=false SCHEDULE_ENABLED=false` |

### 坑 8：E2E 看不到支付方式 / 黄字提示

| 项 | 说明 |
|----|------|
| **原因 A** | 坑 4（preview 403） |
| **原因 B** | 测试门店无混合支付数据 |
| **处理** | 先确认 preview 200；向 PM 要测试商品/门店 |

### 坑 9：入口路径混淆

| 路径 | 用途 |
|------|------|
| `/fuwujin-mall/index` | 服务基金积分商城（H5 E2E） |
| `/store-points/index` | 门店积分首页（非本需求） |
| `localhost:9393` / `:3000` | 仅调试 webpack，**不作最终验收** |

### 坑 10：shop-points 端口 8081 冲突

| 项 | 说明 |
|----|------|
| **处理** | `lsof -i :8081`；或 `--shop-points-port 8082` 并重渲染 nginx |

### 坑 11：PC 管理端登录 / 列表空

| 项 | 说明 |
|----|------|
| **502** | 见坑 2（:3000 未起） |
| **503 loginUser/info** | 见坑 16（代理到 dev01 或 VPN 不通） |
| **403 POST** | 见坑 12 |
| **入口** | 必须 `http://point-pc.ttb.test.ke.com:8089/integral2/...` |

### 坑 12：PC `/shop-points/manage/...` POST → 403 Invalid CORS request

| 项 | 说明 |
|----|------|
| **原因** | 浏览器 Origin `point-pc:8089`；本地 shop-points CORS 仅 `fcn.ke.com` |
| **处理** | nginx `/shop-points` 与 H5 `/integral-proxy/` 已剥 Origin |
| **验证** | 检查清单 §7 |

### 坑 13：`impact.md` 仅 `surfaces: h5` → PC 被静默跳过

| 项 | 说明 |
|----|------|
| **症状** | `local_stack_up` 打印 `跳过 PC webpack`；管理端 502；用户以为全栈已起 |
| **原因** | 脚本按 `impact.md` 裁剪组件；H5 需求文档常只写 `h5` |
| **处理** | **全栈联调一律加 `--surfaces h5,pc`**；`local_stack_up` 会打印 WARN |
| **分工** | `surfaces` 在 E2E 阶段决定测哪些入口；**启动阶段**由 CLI 显式控制 |

### 坑 14：PC/H5 前端 `npm error could not determine executable to run`

| 项 | 说明 |
|----|------|
| **症状** | `npx craco start` 失败；`frontend-pc.log` 一行 npm error |
| **原因** | `node_modules` 缺失或未安装 |
| **处理** | `cd <client目录> && npm ci`（**禁止**随意 `npm install`） |
| **Harness** | `local_stack_up` 启动前自动 `npm ci`（缺 craco 时） |
| **启动命令** | PC：`npm start`（读 package.json）；H5：`npx craco start` |

### 坑 15：`package-lock.json` 与 master 不一致（勿提交误改）

| 项 | 说明 |
|----|------|
| **症状** | `git diff client/package-lock.json` 数万行 |
| **原因** | npm 7+ / 10 执行 `npm install` 将 lockfile v1 升为 v3，**非业务依赖变更** |
| **处理** | `git restore client/package-lock.json`；依赖安装用 **`npm ci`** |
| **禁止** | Agent 在前端仓库执行 `npm install` 升级 lockfile |

### 坑 16：PC `/loginUser/info` → 503

| 项 | 说明 |
|----|------|
| **症状** | 管理端无法拉用户信息 |
| **原因** | nginx 曾错误代理到 `agent-lego.shop-points-**dev01**`（不可达） |
| **处理** | 模板已改为 **test01**；改后 `local_stack_up` 重渲染 nginx |
| **验证** | 检查清单 §8 须 200/302 |

### 坑 17：PC `/shop-points/...` → 404（路径前缀被剥）

| 项 | 说明 |
|----|------|
| **症状** | 本地 shop-points 收到 `/manage/...` 而非 `/shop-points/manage/...` |
| **原因** | nginx `proxy_pass http://upstream/` **带尾部斜杠** 会剥 location 前缀 |
| **处理** | PC `/shop-points` 的 `proxy_pass` **无尾部斜杠**：`http://shop_points_local` |
| **对比** | H5 `/integral-proxy/` 需要剥前缀 → 保留 `proxy_pass .../` |

### 坑 18：`/shop-points/manage/upload/keCoin/period` 登录后 404

| 项 | 说明 |
|----|------|
| **症状** | 城市活动弹窗账期为空；浏览器 Network 中 period API **404**；未登录 curl 可能只见 **302** |
| **原因** | `spring-boot:run` **先于** `mvn compile` 启动，JVM 未加载 `KeCoinV2UploadController` |
| **判定** | `KeCoinV2UploadController.class` 修改时间 **晚于** `lsof -i :8081` 对应 Java 进程 `ps -o lstart` |
| **处理** | `local_stack_up`（`api_change: new` 时会自动 compile+重启）；或 `kill $(lsof -ti :8081)` 后重新 `spring-boot:run` |
| **预防** | `local_stack_check.py` 对 keCoin 需求会校验二进制是否落后于 `target/classes` |

---

## 四、CAS 反代（需 sudo）

```bash
mkdir -p /tmp/cas-nginx/logs
cp skills/req-to-dev/config/nginx/cas-local.conf.template /tmp/cas-nginx/cas.conf
sudo /opt/homebrew/bin/nginx -p /tmp/cas-nginx -c /tmp/cas-nginx/cas.conf
```

---

## 五、标准命令（复制即用）

```bash
cd <shop_points_dev_skills 根目录>

# ★ 全栈联调（推荐默认，显式 surfaces）
python3 skills/req-to-dev/scripts/local_stack_up.py \
  --req-id <req_id> \
  --surfaces h5,pc \
  --nginx-port 8088 \
  --pc-nginx-port 8089

# 健康复检（必须 exit 0 再 E2E）
python3 skills/req-to-dev/scripts/local_stack_check.py \
  --req-id <req_id> --surfaces h5,pc

# 仅 PC
python3 skills/req-to-dev/scripts/local_stack_up.py \
  --req-id <req_id> --surfaces pc --skip-h5

# 仅重载 nginx
python3 skills/req-to-dev/scripts/local_stack_up.py \
  --req-id <req_id> --surfaces h5,pc --nginx-only

# 停止
python3 skills/req-to-dev/scripts/local_stack_down.py --req-id <req_id>
```

**入口**：

- H5 商城：`http://integral.ttb.test.ke.com:8088/fuwujin-mall/index?shopCode=TJDY0101&shopCodeInnerTest=TJDY0101`
- PC 管理：`http://point-pc.ttb.test.ke.com:8089/integral2/activity-config/city`

---

## 六、hosts 策略

| 场景 | hosts |
|------|-------|
| 本地全栈联调 | `127.0.0.1 integral.ttb.test.ke.com local.ttb.test.ke.com point-pc.ttb.test.ke.com` |
| 仅 test01 页面 | 注释 `integral` / `point-pc` 行 |

---

## 七、产出与关联

| 文件 | 说明 |
|------|------|
| `changes/<req_id>/tests/local_stack_report.md` | 启动报告（含 health_errors） |
| `changes/<req_id>/tests/local-stack/logs/*.log` | 各进程日志 |
| `playbooks/local-stack-up.md` | 启动 SOP |
| `playbooks/local-e2e-browser-test.md` | E2E SOP |
| `skills/req-to-dev/scripts/local_stack_check.py` | 健康检查脚本 |
| `knowledge/test-env-topology.md` | 环境拓扑 |
