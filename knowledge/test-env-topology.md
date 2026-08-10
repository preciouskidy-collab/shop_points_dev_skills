---
name: test-env-topology
description: "门店积分测试环境 URL、登录方式与联调拓扑"
version: "0.3.0"
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
| H5 门店积分 V2 首页（本地联调） | `http://integral.ttb.test.ke.com:8088/store-pointsV2/index?shopCode=TJDY0101&shopCodeInnerTest=TJDY0101` | **贝壳币等业务验收主入口**（非 fuwujin-mall） |
| H5 服务基金商城（本地联调） | `http://integral.ttb.test.ke.com:8088/fuwujin-mall/index?shopCode=TJDY0101&shopCodeInnerTest=TJDY0101` | 积分商城混合支付等场景 |
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

## 测试可用数据（Pipeline 默认）

> **单源真相**：脚本常量 `skills/req-to-dev/scripts/lib/local_config.py`；可选覆盖 `secrets.local.json` → `test_env_fixtures`。

| 维度 | 字段 | 默认值 | 说明 |
|------|------|--------|------|
| 城市 | `city_name` | **天津市** | PC 列表/弹窗「规则城市」筛选 |
| 城市 | `city_code` | **120000** | API `cityCode`、上传 Excel 城市列 |
| 门店 | `shop_code` | **TJDY0101** | H5 URL、上传模板门店编码列 |
| 门店 | `shop_code_inner_test` | **TJDY0101** | H5 `shopCodeInnerTest` 参数 |

**使用约定**

- **H5 E2E**：URL 带 `shopCode=TJDY0101&shopCodeInnerTest=TJDY0101`（已写入各 playbook 入口）
- **PC E2E**：城市活动列表筛选 **天津市**；贝壳币/积分上传 Excel 使用门店 **TJDY0101**
- **勿混用其他城市/门店**，除非本需求 PRD 明确要求或你在 `test_env_fixtures` 中显式覆盖

```python
# 脚本内读取
from local_config import load_test_env_fixtures, test_env_fixtures_summary
fixtures = load_test_env_fixtures()
# city_name=天津市, city_code=120000, shop_code=TJDY0101
```

```json
// secrets.local.json 可选覆盖（一般不必改）
{
  "test_env_fixtures": {
    "city_name": "天津市",
    "city_code": 120000,
    "shop_code": "TJDY0101",
    "shop_code_inner_test": "TJDY0101"
  }
}
```

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

## H5 贝壳币页面（门店积分 V2）

> 代码：`store-integral-h5/client-integral` · 路由 `router/index.js`

| 层级 | 本地联调 URL | 说明 |
|------|----------------|------|
| 首页 | `http://integral.ttb.test.ke.com:8088/store-pointsV2/index?shopCode=TJDY0101&shopCodeInnerTest=TJDY0101` | 门店积分 V2 首页 |
| 入口 | 首页「尊享权益」区 **贝壳币 icon** | `StartRightsV2`：`item.id === 4` → 跳转贝壳币页 |
| 贝壳币主页 | `http://integral.ttb.test.ke.com:8088/store-points/beikebi/index?shopCode=TJDY0101` | 月度汇总 + **活动卡片**（线下活动实发/预估） |
| 发放明细 | `http://integral.ttb.test.ke.com:8088/store-points/beikebi/history?shopCode=TJDY0101` | 按账期汇总；展开可看活动发币明细 |

**路径对照（路由前缀 `/store-points/...`，非 `/store-pointsV2/`）**

| 路由 | 组件 |
|------|------|
| `/store-pointsV2/index` | `views/HomeV2` |
| `/store-points/beikebi/index` | `views/BeiKeBi/Index` |
| `/store-points/beikebi/history` | `views/BeiKeBi/History` |

**关联 API**（H5 经 nginx `/integral-proxy/shop-points/v2/web/...`）

| API | 用途 |
|-----|------|
| `GET /keCoin/monthPeriodList` | 月度账期 Tab |
| `GET /keCoin/activityEstimate` | 活动卡片列表 |
| `GET /keCoin/periodRecord` | 某账期发币明细分页 |

**PC 上传 Excel 后 H5 验收**：贝壳币主页选对应账期（如 `2026M9`）→ 活动卡片应出现「线下活动配置」及实发金额；必要时进 `history` 看明细行（门店 `TJDY0101`）。

**明细缺账期时**：先查 Apollo `mockCurrentTime` 与申诉期/发币日规则 → `playbooks/apollo-mock-time.md`。

## Apollo Mock 时间（贝壳币账期可见性）

测试环境通过 Apollo **TEST** 环境 `shop-points` / `application` 的 **`mockCurrentTime`** 控制「当前时间」。申诉期为每月 1–5 日；明细页在申诉期后才出现当月记录；mock 日在每月 10 号前/后决定可见账期回退 1 或 2 个月。

完整 SOP（含 Portal 链接、**业务开关**发布、验证 API）：`playbooks/apollo-mock-time.md`

## E2E 前置条件

1. `dayu-deploy` 阶段全部目标模块已「运行中」且刷新后仍保持
2. 后端日志无启动异常
3. 若涉及 Apollo 新配置，需确认测试环境已同步

## AgentBrowser 登录提示

1. 打开目标 URL
2. 若跳转 CAS 登录 → `fill` 工号/密码 → 提交
3. 登录成功后用 `snapshot -i` 确认页面元素
4. 使用 `--session-name req-to-dev-<name>` 复用登录态，避免重复登录
