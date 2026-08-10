---
name: pipeline-redlines
description: "执行 req-to-dev Pipeline 时 Agent 必须遵守的流程红线（先于一切编码动作加载）"
version: "1.2.0"
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

## Agent 自检清单（进入 backend-coding 前）

- [ ] `approve-design` 已成功（或 `collaboration/tech_design_review` 有 `design_applied`）
- [ ] 未在技术方案评审前修改目标仓库业务代码
- [ ] `impact.integration_mode` 为 `local`（除非用户要求 dayu）
- [ ] 企微 **技术方案评审** 消息已 push 且已 wait 处理 intent（或用户 `--chat-confirm`）
