---
name: local-e2e-browser-test
description: "使用 Cursor 内置浏览器 MCP 在本地前后端执行 E2E 验收"
version: "0.3.0"
category: playbooks
tags:
  - e2e
  - local
  - cursor-browser
commands: []
---

# Skill: 本地 E2E（Cursor 内置浏览器）

## 反模式（红线 R8.1 — 已发生过，禁止再犯）

| 反模式 | 后果 | 正确做法 |
|--------|------|----------|
| 用 Playwright / agent-browser / 本机 Chrome 跑 PC 弹窗、CAS 登录 | 与 Pipeline `e2e_browser: cursor` 不一致；占用用户 Chrome；Glass 面板不可见 | **仅** `cursor-ide-browser` MCP |
| 用户已开页面仍后台 Playwright/agent-browser「因为登录难」 | 双浏览器、状态不一致 | `browser_tabs` 绑 glass-browser → navigate → snapshot |
| 调用已删除的 `ab_h5_bypass_http.py` / `playwright_cas_login.py` | 脚本已移除；违反 R8.1 | `browser_navigate` → CAS 表单 `browser_fill` |
| 只 `open_resource` 不 `browser_navigate` | 用户看不到 Browser Tab | navigate + 说明右侧 Browser 面板 |
| 用 Cursor 对话「已上传」代替企微 `upload_confirm` | 违反 R5 / e2e-upload-collab | notify → **阻塞 wait** |

**为何上次「内置浏览器没生效」**：Agent 误走 Playwright / agent-browser（本机 Chrome）；Glass 需 **Browser Automation = Browser Tab** 且操作 **glass-browser** 视图，不能只在 agent 内部 tab 跑自动化。

## 适用时机

`local-stack-up`（方案 B nginx）**且启动验收通过**后。

**跳过条件**：`frontend_scope: none`。

> **踩坑排障（必读）**：[`local-stack-troubleshooting.md`](local-stack-troubleshooting.md)

## 前置条件

- `tests/local_stack_report.md` 记录栈已启动
- **`local_stack_check.py --surfaces h5,pc` exit 0**
- 排障文档 §二 检查清单已通过（尤其 webpack 端口、bundle 完整、preview/shop-points 非 CORS 403）
- `handoff/frontend-handoff.md` §6 用例已就绪
- `secrets.local.json` → `test_env_app` 可登录
- CAS 反代（本机 80）已起（若需浏览器 CAS 登录）

## 测试可用数据（默认）

见 `knowledge/test-env-topology.md` §测试可用数据。Pipeline **默认**：

| 维度 | 值 |
|------|-----|
| 城市 | **天津市**（`cityCode=120000`） |
| 门店 | **TJDY0101** |

- PC：规则城市筛 **天津市**；上传 Excel 门店列 `TJDY0101`
- H5：URL 已带 `shopCode=TJDY0101&shopCodeInnerTest=TJDY0101`

## 测试入口（按 impact surfaces 选择）

### H5（`surfaces` 含 `h5`）

**门店积分 V2 首页**（贝壳币、活动卡片等）：

```
http://integral.ttb.test.ke.com:8088/store-pointsV2/index?shopCode=TJDY0101&shopCodeInnerTest=TJDY0101
```

**贝壳币子页**（从首页「尊享权益」贝壳币 icon 进入，或直接深链）：

```
http://integral.ttb.test.ke.com:8088/store-points/beikebi/index?shopCode=TJDY0101
http://integral.ttb.test.ke.com:8088/store-points/beikebi/history?shopCode=TJDY0101
```

**服务基金积分商城**（混合支付等，非贝壳币主路径）：

```
http://integral.ttb.test.ke.com:8088/fuwujin-mall/index?shopCode=TJDY0101&shopCodeInnerTest=TJDY0101
```

详见 `knowledge/test-env-topology.md` §H5 贝壳币页面。

### PC（`surfaces` 含 `pc`）

**活动配置等城市维度管理**：

```
http://point-pc.ttb.test.ke.com:8089/integral2/activity-config/city
```

PC 登录依赖远程 agent-lego（`/api`、`/loginUser/info`），需 test01 可达。

| 不要用的入口 | 原因 |
|--------------|------|
| `localhost:9393` / `localhost:3000` | 绕过 nginx，与真实链路不一致 |
| `integral.ttb.test.ke.com` 无端口 | hosts 指向本机 80，是 CAS/lottery 不是 H5 |
| `/store-points/index` | 门店积分首页，非服务基金商城 |

## 浏览器工具

| 操作 | MCP 工具 |
|------|----------|
| 打开页面 | `browser_navigate` |
| 读页面结构 | `browser_snapshot` |
| 点击 / 输入 | `browser_click` / `browser_type` |
| 截图验证 | `browser_take_screenshot` |

## 登录（仅 Cursor 内置浏览器）

1. `browser_tabs` → `browser_navigate` 打开 H5 入口（**:8088**）或 PC 入口
2. 若跳 CAS（**同一 Browser Tab 内完成，禁止另开 Chrome**）：
   - `browser_snapshot` → 点 **员工** → 点 **账号登录**
   - `browser_fill` 填 `secrets.local.json` → `test_env_app` 工号、密码 → 点 **登录**
3. 回跳后 `browser_snapshot` 确认进入业务页；同会话复用登录态
4. CAS 回跳依赖本机 80 CAS 反代（见排障文档 §四）

**禁止**：Playwright、`agent-browser`、`ab_h5_bypass_http.py`（已删除）、osascript 点原生 Chrome 按钮。

## 含文件上传的 E2E（企微通知 + 阻塞 wait）

**适用**：Excel 上传、S3 附件类（如 PC「上传贝壳币」）。Cursor 浏览器 **无法** 程序化 `input[type=file]`。

**主路径（企微 + 同一回合 wait）** — 详见 `playbooks/e2e-upload-collab.md`：

| 步骤 | 负责人 | 动作 |
|------|--------|------|
| 1 | Agent | 打开 PC 弹窗，确认账期/城市 |
| 2 | Agent | `collab_e2e_upload.py notify --req-id <id> --label "..."` → 企微推送 |
| 3 | Agent | **同一回合** `collab_e2e_upload.py wait --timeout 3600`（**禁止结束对话**） |
| 4 | **用户** | 企微群选文件上传后回复 `已上传` 或 notify 中的确认语 |
| 5 | Agent | 收到 `upload_confirm` → snapshot → 点「确定」→ 继续验收 |

```bash
python3 skills/req-to-dev/scripts/collab_e2e_upload.py notify \
  --req-id <req_id> --label "上传贝壳币 Excel"
python3 skills/req-to-dev/scripts/collab_e2e_upload.py wait \
  --req-id <req_id> --timeout 3600
```

**禁止**：在 Cursor 对话回复「已上传」代替企微确认；Agent API 不可用则阻塞，不得降级。

**测试 Excel**

- 复制官方模板（勿用 openpyxl 等改写，易破坏 EasyExcel 解析）
- 默认门店列：`TJDY0101`；城市：天津市 `120000`
- 可放在 `changes/<req_id>/tests/`（如 `e2e_kecoin_TJDY0101.xlsx`）

**PC 上传后 H5 联动验收** — 完整矩阵见 `playbooks/kecoin-upload-e2e-matrix.md`：

1. 记录 PC 弹窗 **upload_period**（如 `2026M9`）与活动 ID/城市
2. `beikebi/index` → **账期选择器切至 upload_period**（禁止用默认当月）→ 线下活动卡片 + 金额
3. `beikebi/history` → 展开 **同一 upload_period** → 明细行
4. 负向：`E2E-PC-02` 申诉期外提交 → `hasSaveError=true`

**明细无当月账期**（主页有卡片、history 缺账期）：读 `playbooks/apollo-mock-time.md`，调整 TEST Apollo `mockCurrentTime` 并选 **业务开关** 发布。

## 步骤

1. 加载 `frontend-handoff.md` §6 用例
2. navigate → 等待 bundle 加载完成（非永久 loading）
3. snapshot → 交互 → 断言（黄字提示 / 子选项显隐）
4. 点「去兑换」前确认 Network 中 `order/preview` 为 **200**（非 403）
5. 产出 `tests/local_e2e_report.md`

## 常见失败与对照

| 现象 | 见排障文档 |
|------|------------|
| 502 | §坑 2（9393 未起） |
| 永久 loading | §坑 3（bundle 截断） |
| serverError 403 | §坑 4（CORS） |
| 登录后白屏 | §坑 5（CAS 80） |
| 无支付方式区块 | §坑 8（preview 失败或测试数据） |
| history 无当月账期 / monthPeriodList 缺账期 | `apollo-mock-time.md`（mock 时间 + 业务开关发布） |

## 质量标准

- P0 用例通过，或在报告中记录阻塞原因（数据/登录/环境）
- 报告含 snapshot 或截图摘要
- 阻塞时引用排障文档章节，勿重复踩坑
