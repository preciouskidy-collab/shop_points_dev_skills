---
name: pipeline-redlines
description: "执行 req-to-dev Pipeline 时 Agent 必须遵守的流程红线（先于一切编码动作加载）"
version: "1.3.0"
category: guardrails
tags:
  - pipeline
  - harness
  - wecom
  - plan-approve
  - tech-design-review
  - redline
commands: []
---

# Pipeline 流程红线（Harness SDLC）

> **适用**：`run_workflow.py` 驱动的 req-to-dev 全链路。违反任一条视为流程事故。

## R0 · stage 与企微 phase 对照

| Pipeline stage | 企微 `collaboration.phase` | 群消息 |
|----------------|---------------------------|--------|
| **`plan-approve`** | **`tech_design_review`** | **技术方案评审** · design-patch-NNN |

- `collab-tech-design-sync prepare` / `finalize-design` 后即 `push-state phase=tech_design_review`
- **`push-preview` 发送到企微时，已是技术方案评审阶段**（不是「预览完才进入评审」）
- 唯一人工阻塞点：**技术方案企微评审**（`approve-design` 解锁编码）
- **已取消** `deploy-approve`：本地 E2E 通过后 `advance` 直接进入 `commit-push`

## R1 · 企微推送不可漏

| 场景 | 必须执行 |
|------|----------|
| PRD 定稿（链路1） | `finalize-plan` → **`push-preview`** → **阻塞 `wait`** |
| 技术方案评审（plan-approve / tech_design_review） | `finalize-design` → **`push-preview`** → **阻塞 `wait`** |

- `push-preview` 成功须看到 `Webhook 已发送至已绑定群`
- 技术方案群标题为 **「技术方案评审」**（非「预览」）
- 漏推不得进入审批/编码；须重跑 `push-preview`

## R2 · 企微推送后同一回合阻塞 wait（禁止结束回合）

`push-preview` 之后 **同一 Agent 回合内** 必须：

```bash
python3 skills/req-to-dev/sub_skills/collab-prd-sync/scripts/collab_prd_sync.py wait \
  --req-id <req_id> --timeout 3600
```

| 返回 | 同一回合动作 |
|------|--------------|
| `approve` | PRD 写回 `approve --pull-intent-id` |
| `plan_approve` | 技术方案 `approve-design --pull-intent-id` |
| `meeting_revise` | PRD 修订 → finalize-plan → push-preview → **再 wait** |
| `tech_revise` | 技术方案修订 → finalize-design → push-preview → **再 wait** |
| `timeout` | **立即再跑 wait**（仍在本回合） |

**禁止**：

- `block_until_ms=0` 后台 watch
- push-preview 后 **结束对话**，等用户在 Cursor 聊天框输入再继续
- 未收到 intent 却自行 `approve-design` / `run_workflow approve`

**原因**：单轮对话结束后 Cursor **无法**被企微意图唤起；必须在本回合长轮询 `wait` 直到收到 intent 或用户在本对话降级确认。

降级：用户在本对话发出带验证码的确认语 → `--chat-confirm`（仍须用户原话）。

## R2.2 · wait 禁止 action 过滤（PRD / 技术方案评审）

`push-preview` 后的阻塞 wait **必须接收全部协作 intent**，禁止加 `--action` 只等某一种。

| 正确 | 错误（流程事故） |
|------|------------------|
| `collab_prd_sync.py wait --req-id <id> --timeout 3600` | `collab_wait.py wait --action approve` |
| 收到 `meeting_revise` → 走修订循环 | 丢弃 `meeting_revise`，企微 `/整理评审` 无响应 |

**修订循环（允许多次）**：用户可在企微**反复**发 `/整理评审`（PRD）或 `/整理方案`（技术方案）。每次 wait 返回 `meeting_revise` / `tech_revise` 时，同一回合内：

```
meeting-revise / tech-revise → 写 plan → finalize → push-preview → 再 wait（仍无 --action）
```

直到收到 `approve` / `plan_approve` 才结束评审。

**禁止动机**：不得为「跳过未消费的旧 intent」而对 wait 加 `--action approve`——这会屏蔽合法的 `/整理评审`，表现为 `WARN: 收到非目标 action=meeting_revise`。

**E2E 人工上传**是唯一允许 action 过滤的场景：`collab_e2e_upload.py wait`（仅等 `upload_confirm`），与 PRD/技术方案评审 **不是同一条 wait 命令**。

## R2.3 · 修订 intent 必须消费（禁止重复拉取）

| intent `action` | 消费时机 | 命令 |
|-----------------|----------|------|
| `approve` | `collab_approve.py` | `approve --pull-intent-id <id>` |
| `plan_approve` | `approve_design.py` | `approve-design --pull-intent-id <id>` |
| **`meeting_revise`** | **`meeting_revise_prepare.py` 成功后** | **`meeting-revise --pull-intent-id <id>`** |
| **`tech_revise`** | **`tech_design_revise_prepare.py` 成功后** | **`tech-revise --pull-intent-id <id>`** |

- wait 返回 JSON 后 **同一回合** 执行 `collab_handle_intent.py`（或带 `--pull-intent-id` 的子命令）
- **禁止**手动 `AgentClient.consume_intent` 绕过 prepare
- **禁止**为跳过旧 intent 而对 wait 加 `--action approve`（见 R2.2）
- 未消费时 wait **会反复返回同一 `intent_id`**（流程事故）

## R2.1 · 企微修订口令（PRD vs 技术方案分轨）

| 阶段 | `collaboration.phase` | 通过（企微） | **需修订（企微）** | intent `action` |
|------|----------------------|--------------|-------------------|-----------------|
| PRD 评审 | `prd_review` | `确认 patch-NNN <nonce> approver <姓名>` | **`/整理评审`** | `meeting_revise` |
| 技术方案 | `tech_design_review` | `确认 design-patch-NNN <nonce> approver <姓名>` | **`/整理方案`** | `tech_revise` |

- 技术方案阶段 **禁止** 使用 `/整理评审`（会误路由为 PRD `meeting_revise`）。
- 修订交互：在群里补充文字意见 → 发修订口令 → Agent 拉群消息 → 出新 preview → 再发确认语。
- Agent API 须按 `push-state` 中的 `phase` / `reviseCommand` / `expectedReviseIntent` 解析（见 `knowledge/collab-intent-routing.md`）。

完整 SOP：`playbooks/wecom-collab-review.md`

## R5 · E2E 人工上传：企微通知 + 同一回合阻塞 wait

PC/H5 E2E 需用户 **手动选文件**（Excel 上传等）时：

```bash
# 1. 打开弹窗后 notify
python3 skills/req-to-dev/scripts/collab_e2e_upload.py notify \
  --req-id <req_id> --label "<上传说明>"

# 2. 同一回合立即阻塞 wait（禁止结束对话）
python3 skills/req-to-dev/scripts/collab_e2e_upload.py wait \
  --req-id <req_id> --timeout 3600
```

| 返回 | 同一回合动作 |
|------|--------------|
| `action=upload_confirm` | 继续浏览器操作（点「确定」、H5 验收） |
| `timeout` | 立即再跑 `wait` |

**禁止**：notify 后结束回合等用户在 Cursor 聊天框回复；**仅**接受企微群 `upload_confirm`（Agent API 不可用则阻塞并报错，无对话降级）。

详见 `playbooks/e2e-upload-collab.md`。

## R3 · 先方案后编码（设计阶段禁止写业务代码）

**顺序（不可颠倒）**：

```
break-down → scope-eval → api-contract → tech-design ║ frontend-design
    → [企微技术方案评审（plan-approve / tech_design_review）通过]
    → backend-coding → frontend-coding → …
```

在 **技术方案评审通过之前**（即 `approve-design` 成功之前）：

| 禁止 | 允许 |
|------|------|
| 检出/创建目标仓库 feature 分支并写业务代码 | 只读探索、写 `changes/<req_id>/` 内文档 |
| `mvn compile` 验收新功能代码 | 写 spec / impact / api-contract / tech-design |
| 修改 store-integral / shop-points 业务文件 | `collab-prd-sync` PRD 同步 |

解锁编码的唯一路径：`collab-tech-design-sync approve-design`（或带 `--pull-intent-id`）。

**禁止**直接 `run_workflow.py approve` 跳过企微方案评审。

## R4 · 验收默认本地栈 + Cursor 内置浏览器

`impact/impact.md` 默认：

```yaml
integration_mode: local
e2e_browser: cursor
```

| 模式 | 验收路径 |
|------|----------|
| **local（默认）** | `local-stack-up` → `local-e2e-test`（Cursor 浏览器 MCP）→ **`commit-push`**（无 deploy-approve）→ `release` |
| dayu（须用户明确要求） | 将 `integration_mode` 改为 `dayu` → `dayu-deploy` → `e2e-browser-test`（agent-browser） |

- 不得用「跳过大禹」为由跳过 `local-stack-up` / `local-e2e-test`
- 不得默认走 AgentBrowser + 大禹点击测试

## R6 · 编码后 Pipeline 连续推进（禁止中途断开）

编码完成（`frontend-handoff` 之后）**同一 Agent 回合内**须连续执行至 `local-e2e-test` 通过，**禁止**在 review / 本地栈 / E2E 之间结束回合让用户手动推进。

```bash
python3 skills/req-to-dev/scripts/run_workflow.py continue --name <req_id>
```

| 自动连续阶段 | 说明 |
|--------------|------|
| `backend-review` | `mvn compile` + 产出 review 报告 |
| `frontend-review` | `npm run build` + 产出 review 报告 |
| `backend-test-local` | `mvn test`（失败降级 compile） |
| `local-stack-up` | `local_stack_up.py` |
| `local-e2e-test` | `local_e2e_autorun.py`（VPN 默认连通，stack check 带重试） |

- **禁止**将 E2E 标为 BLOCKED 后结束回合等用户手动测
- **禁止**仅写 markdown 报告而不跑 `continue` / `local_e2e_autorun.py`
- Excel 上传等 **必须**人工选文件的场景仍走 `collab_e2e_upload`（R5），但 Agent 须在同一回合 notify → wait

## R6.1 · local-e2e-test 完整闭环清单（禁止偷工减料）

`local_e2e_autorun.py` **仅**覆盖 API/栈探测；**不得**以其 verdict 作为 `local-e2e-test` 完成依据。

**贝壳币上传类需求**（`api-contract` 含 `keCoin` 上传 / Excel）`tests/e2e_checklist.json` 须 **全部 PASS** 方可 `advance`：

| 用例 ID | 内容 |
|---------|------|
| `E2E-PC-01a` | PC 登录 + **正确活动/城市** + 弹窗（记录 `upload_period`） |
| `E2E-PC-01b` | **企微 notify → 用户选 Excel → 阻塞 wait `upload_confirm`** |
| `E2E-PC-01c` | **申诉期内**点确定 + 列表轮询至 **102 已生效** |
| `E2E-PC-02` | **申诉期外**提交 → `hasSaveError=true`（负向，不可跳过） |
| `APOLLO-MOCK-01` | TEST `mockCurrentTime` 调至发币日/申诉期后，**业务开关**发布 |
| `E2E-H5-01` | `beikebi/index` **切换至上传账期** → 线下活动卡片（禁止用默认 M10） |
| `E2E-H5-02` | `beikebi/history` **上传账期**明细（与 PC 账期一致） |

**账期/城市对齐（反模式沉淀）** → `playbooks/kecoin-upload-e2e-matrix.md`：

- H5 卡片页与明细页均须在 **upload_period** 下断言，不得用页面默认账期
- PC 活动规则城市须与 Excel 门店一致（例：天津市 253 + TJDY0101）
- 禁止仅 happy path：须含 `E2E-PC-02` 申诉期外拦截

```bash
python3 skills/req-to-dev/scripts/local_e2e_checklist.py --req-id <id> init
python3 skills/req-to-dev/scripts/local_e2e_checklist.py --req-id <id> gate   # advance 前必过
```

**禁止**：只打开弹窗、不跑企微上传协作就标 PASS；不调 Apollo mock 就验 H5 明细；跳过 H5 卡片/明细页；**H5 未切上传账期就标 PASS**；**跳过申诉期负向 E2E-PC-02**；**错城活动上传仍标 PASS**。

## R7 · 环境阻塞 Agent 自愈（禁止甩锅给用户）

`local-stack-up` / `local-e2e-test` / `continue` 遇阻塞时，**Agent 须在本回合内自行排障并修复**，不得仅输出「请手动查端口/日志」后结束回合。

| 阻塞类型 | Agent 必须尝试（按序） |
|----------|------------------------|
| nginx `bind()` / 端口占用 | 健康检查通过 → **复用现有网关**；未通过 → `kill` 占用进程 → 重试 `local_stack_up` |
| `local_stack_up` exit 1 | 自动跑 `local_stack_check.py`；复检通过则视为栈就绪 |
| shop-points 旧进程无 keCoin API | 检测 Controller 编译时间 → compile + 重启（`local_stack` 已内置） |
| webpack 未起导致 502 | 启动/等待 :3000 / :9393，再复检 |
| E2E checklist 未 PASS | 读失败项 → 按 **R8** 用 Cursor 浏览器 + Apollo Portal 修 mock/重跑；**禁止** Playwright / JVM mock |

**禁止**：把 `lsof`、杀进程、重跑栈/E2E 写成「请你执行」；除非需 **sudo / VPN / 人工选 Excel 文件** 等 Agent 无法代劳的场景。

排障手册：`playbooks/local-stack-troubleshooting.md` §二检查清单。

## R8 · local-e2e-test 路径红线（Cursor 浏览器 + Apollo Portal）

`local-e2e-test` 阶段有两条**唯一正确路径**，违反即视为流程失败，须回滚错误操作后按 playbook 重做。

### R8.1 · 必须用 Cursor 内置浏览器 MCP（禁止 Playwright / 外部 headless）

| 场景 | 唯一路径 |
|------|----------|
| `impact.e2e_browser: cursor` 或 `integration_mode: local` | **`cursor-ide-browser` MCP**：`browser_navigate` → `browser_lock` → `browser_snapshot` → `browser_click` / `browser_fill` |
| PC/H5 页面交互、CAS 登录、弹窗点确定 | 同上；登录态复用 Glass **Browser Tab** |
| 截图取证 | `browser_take_screenshot` |

**禁止**：

- 写/跑 `playwright`、Selenium、独立 `chromium.launch(headless=True)` 脚本作为 `local-e2e-test` 主路径
- 用户已打开 Glass 浏览器仍后台跑 Playwright「因为 CAS 难登」
- 仅用 `open_resource` 打开 URL 却不走 `browser_navigate` + snapshot 驱动（用户看不到面板）

**Glass 浏览器不可见时 Agent 须先**（同一回合，禁止甩锅）：

1. `browser_tabs` 确认绑定 **glass-browser** 视图（非仅 agent 内部 tab）
2. Settings → **Browser Automation = Browser Tab**；`Cmd+E` / Open Agents Window
3. `browser_navigate` 打开目标 URL → 告知用户看右侧 **Browser** 面板
4. 仍不可见再排障，**不得**降级 Playwright

Playbook：`playbooks/local-e2e-browser-test.md` §浏览器工具、§反模式。

### R8.2 · mockCurrentTime 仅 Apollo Portal 配置（禁止启动参数 / 本地 JVM 篡改）

申诉期正负向（`E2E-PC-01c` / `E2E-PC-02`）、H5 明细账期（`APOLLO-MOCK-01` / `E2E-H5-*`）依赖 TEST 环境 **`shop-points` / `application` / `mockCurrentTime`**，须：

1. **Cursor 内置浏览器**打开 Apollo Portal（见 `playbooks/apollo-mock-time.md`）
2. 编辑 `mockCurrentTime` → 保存 → **业务开关**发布
3. 等待 TEST 实例同步（1–3 分钟）后再继续 PC 提交 / H5 验收

**禁止**（均无效或会导致栈损坏，**不得**作为「自愈」手段）：

- `mvn spring-boot:run` 加 `-DmockCurrentTime=...` / `--mockCurrentTime=...`
- 改 `application.yml` / 环境变量冒充 Apollo mock
- 杀本地 `:8081` shop-points 企图用 JVM 参数「绕过申诉期」
- 未发布 Apollo 就标 `APOLLO-MOCK-01` PASS

本地 `:8081` shop-points 仍拉 TEST Apollo；**改时间 = 改 Portal 配置**，不是改本地进程启动参数。

Playbook：`playbooks/apollo-mock-time.md`（含 Agent 浏览器操作提示）。

## Agent 自检清单（进入 backend-coding 前）

- [ ] `approve-design` 已成功（或 `collaboration/tech_design_review` 有 `design_applied`）
- [ ] 未在技术方案评审前修改目标仓库业务代码
- [ ] `impact.integration_mode` 为 `local`（除非用户要求 dayu）
- [ ] 企微 **技术方案评审** 消息已 push 且已 wait 处理 intent（或用户 `--chat-confirm`）
