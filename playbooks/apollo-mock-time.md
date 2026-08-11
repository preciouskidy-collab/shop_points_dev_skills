---
name: apollo-mock-time
description: "测试环境 Apollo mockCurrentTime 调整 SOP：贝壳币明细账期可见性、申诉期与发布属性（业务开关）"
version: "1.0.0"
category: playbooks
tags:
  - apollo
  - mock-time
  - test-env
  - e2e
  - keCoin
  - shop-points
commands: []
---

# Apollo Mock 时间调整 SOP

> **按需加载**：`skills_loader.py search "apollo mock"` 或 `search "贝壳币明细"`；Pipeline `local-e2e-test` / `e2e-browser-test` 阶段自动附带本 playbook。

## 红线 R8.2 — 唯一正确改时间方式

**必须**在 **Apollo Portal 网页**（建议用 **Cursor 内置浏览器**打开）修改并 **业务开关** 发布 `mockCurrentTime`。

| 禁止（无效 / 破坏本地栈） | 原因 |
|---------------------------|------|
| `mvn spring-boot:run -DmockCurrentTime=...` | 本地进程参数不替代 TEST Apollo；易导致 8081 启动失败 |
| `--mockCurrentTime=` / `application.yml` 本地覆盖 | E2E 验收的是 TEST 配置下发，不是 JVM 属性 |
| 杀 shop-points / `local_stack_up` 重启「换时间」 | **错误**：Apollo 发布后实例会**自动拉取/热加载**配置，**无需**也不应重启 `:8081` |
| 未在 Portal 确认「已发布」就继续 E2E | CDP 点按钮易漏「业务开关」或二次「发布」；须读表核对 Value |

本地联调栈 `:8081` 仍消费 TEST Apollo；**改时间 = Portal 改独立 key `mockCurrentTime` + 业务开关发布 + 等 1–3 分钟同步**，**禁止**重启服务。

### 发布后无需重启（必读）

shop-points 接入 Apollo 客户端后，**配置发布成功 → 实例自动感知新 `mockCurrentTime`**（通常 1–3 分钟内）。Agent **禁止**在改 mock 后执行：

- `kill` / 重启本地 `:8081` shop-points
- `local_stack_up` 仅为「让栈吃到新 mock」而重启
- 任何企图用 JVM 启动参数覆盖 Apollo 的做法

**正确等待方式**：Portal「实例列表」观察非最新配置数降为 0，或调 `monthPeriodList` / PC 弹窗账期 / H5 页面验证，而非重启进程。

### E2E 贝壳币上传：两阶段改 mock（禁止搞反）

| 阶段 | 用例 | 建议 `mockCurrentTime` | 期望现象 |
|------|------|------------------------|----------|
| 1 | `E2E-PC-02` 申诉期**外**负向 | `2026-10-11 10:00:00`（当月 6 日及以后） | PC 提交拦截「仅在申诉期内可上传」 |
| 2 | `E2E-PC-01c` 申诉期**内**成功上传 | `2026-10-03 10:00:00`（当月 1–5 日） | 弹窗账期 `2026M9`，列表终态已生效 |
| 3 | `APOLLO-MOCK-01` + `E2E-H5-02` 明细 | 再发布为 `2026-10-11 10:00:00`（发币日 10 号之后） | `beikebi/history` 出现 `2026年9月` 汇总 |

每阶段须：**保存 → 提交变更 → 发布属性=业务开关 → 发布 → 等同步 → API/页面验证**，再跑对应用例。不可在未验证 Portal 行状态为「已发布」时标 `APOLLO-MOCK-01` PASS。

## 何时需要改 mock 时间

| 现象 | 可能原因 |
|------|----------|
| H5 **奖励记录 / 发放明细** 缺某账期（如已上传 `2026M9` 但列表只到 `2026M8`） | mock 时间仍在申诉期内或发币日前 |
| `activityEstimate` 有当月活动卡片，但 `monthPeriodList` 无对应账期 | 同上（预估与明细可见规则不同） |
| 跨账期、申诉期边界 E2E | 需将 mock 拨到目标日期 |
| PC 上传贝壳币成功，H5 主页有实发，明细页无当月 | 典型 mock 时间过早 |

**默认测试门店**：`TJDY0101`（见 `knowledge/test-env-topology.md` §测试可用数据）

## 配置位置

| 项 | 值 |
|----|-----|
| Portal | `http://test-apollo.portal.life.ke.com/config.html#/appid=shop-points&env=TEST&cluster=default&namespace=application` |
| AppId | `shop-points` |
| 环境 | **TEST**（shop-points 不在 FAT） |
| Cluster | `default` |
| Namespace | `application` |
| Key | **`mockCurrentTime`**（独立 String 配置项，非 `disbursement` JSON 内嵌字段） |
| 格式 | `yyyy-MM-dd HH:mm:ss`，例：`2026-10-11 10:00:00` |

## 业务规则（为何 mock 日期影响明细）

- **申诉期**：每月 **1–5 日 0 点**（Apollo 另有 `appealDeadline` 等项，测试以实际配置为准）
- **贝壳币明细页**（`beikebi/history`）：申诉期结束后才出现**当月**账期汇总
- **可见账期算法**（`ShopKeCoinV2Service.resolveLatestVisibleMonthPeriod`）：
  - 发币日 `execDayOfMonth` 默认 **10**
  - mock 日 **≤ 10**：最新可见账期 = mock 月 **回退 2 个月**
  - mock 日 **> 10**：最新可见账期 = mock 月 **回退 1 个月**

| mockCurrentTime | monthPeriodList 最新账期（示例） | 能否看到 2026M9 |
|-----------------|----------------------------------|-----------------|
| `2026-10-01` | 到 `2026M8` | 否 |
| `2026-10-11` | 含 `2026M9` | 是 |

上传账期 `2026M9` 的 Excel 后，若要在明细页验收，mock 宜设在 **10 月 11 日之后**（且已过申诉期）。

## 操作步骤（Agent / 人工）

### 1. 修改配置

1. 打开 Portal，登录（需内网/VPN）
2. 确认左上角环境为 **TEST**，应用 `shop-points`，Namespace `application`
3. 过滤或搜索 `mockCurrentTime`
4. 编辑 Value → 保存（行状态变为 **未发布** / **改**）

### 2. 发布（关键：选「业务开关」）

1. 点击 **提交变更**（或 Namespace 级发布入口）
2. 在变更对比中确认：`mockCurrentTime` 旧值 → 新值
3. **发布属性** 选择 **`业务开关`**（**不要**选「业务变更」）
   - 选「业务开关」后：弹窗标题变为「发布」，按钮为 **发布**，**无需**关联发布计划
   - 选「业务变更」：需关联发布计划，TEST 环境易卡住或无法提交
4. Release Name 可沿用自动生成（如 `20260807203748-release`）
5. 点击 **发布**，等待成功（行状态变为 **已发布**）

### 3. 等待实例同步（勿重启服务）

- TEST 环境 shop-points 约 **6** 个实例；发布后通常 **1–3 分钟** 内**自动**拉取新配置（热更新，**不需要**重启 shop-points）
- Portal「实例列表」可查看「使用非最新配置」数量，应逐步降为 0
- 本地 `:8081` 与远程 TEST 实例行为一致：改 mock **只走 Portal 发布**，禁止 `kill 8081` / `local_stack_up` 换时间

### 4. 验证

**API**（H5 nginx 或 test01，需登录态）：

```http
GET /integral-proxy/shop-points/v2/web/keCoin/monthPeriodList?shopCode=TJDY0101
```

期望：`data` 中含目标账期，例如：

```json
{
  "period": "2026M9",
  "periodName": "2026年9月",
  "pendingKeCoinAmount": "300.00",
  "totalKeCoinAmount": "300.00"
}
```

**H5 页面**：

```
http://integral.ttb.test.ke.com:8088/store-points/beikebi/history?shopCode=TJDY0101&shopCodeInnerTest=TJDY0101
```

## 踩坑清单

| 问题 | 处理 |
|------|------|
| 改了值但接口仍旧时间 | 仅保存未 **发布**；或实例尚未同步 |
| 提交变更无反应 / 配置没有变化 | 重新打开提交弹窗；确认 Changes 表有 `mockCurrentTime` 行 |
| 业务变更无法发布 | 改选 **业务开关** |
| TEST 紧急发布报错 | TEST 不支持 `isEmergencyPublish`；用正常发布 + 业务开关 |
| 改 `disbursement` JSON 里的 mock 无效 | 改独立 key **`mockCurrentTime`** |
| 主页有卡片、明细无账期 | mock 拨到发币日之后 + 申诉期之后（见上表）；**不要**重启服务，等 Apollo 同步 |
| Agent 改 mock 后重启了 shop-points | **无效且错误**；撤销重启，仅等 1–3 分钟并查 `monthPeriodList` |
| 一次 mock 想同时过 PC 负向 + 申诉期内上传 | 须**分两次发布**（先申诉期外，再申诉期内），见「两阶段改 mock」 |

## Agent 浏览器操作提示

- **打开 Portal 必须用 Cursor 内置浏览器 MCP**（`browser_navigate`），与 `local-e2e-test` 同一 Browser Tab 会话；**禁止**用 Playwright 开 Portal
- Apollo Portal 为 Angular 页面；发布弹窗内「发布」按钮在请求进行中会 `disabled`，需等待
- 可用 CDP 读表：`document.querySelectorAll('tr')` 过滤 `mockCurrentTime` 确认 **已发布** 与 Value
- 发布后可 `fetch('/apps/shop-points/envs/TEST/clusters/default/namespaces/application/releases/active')` 检查 release 内 `\"mockCurrentTime\":\"2026-10-11...\"`

## 关联文档

- 测试拓扑与贝壳币 URL：`knowledge/test-env-topology.md` §H5 贝壳币页面
- 本地 E2E 上传 + H5 联动：`playbooks/local-e2e-browser-test.md` §PC 上传后 H5 联动验收
- 部署前 Apollo 检查：`playbooks/release-validation.md`

## 发现本 playbook

```bash
python3 skills_loader.py search "apollo mock"
python3 skills_loader.py search "mockCurrentTime"
python3 skills_loader.py resolve --stage local-e2e-test --project shop-points
```
