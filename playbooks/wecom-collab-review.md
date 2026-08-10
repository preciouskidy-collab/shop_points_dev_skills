---
name: wecom-collab-review
description: "企微 PRD/技术方案评审交互：修订口令、确认语、push-preview 后阻塞 wait（禁止结束回合）"
version: "1.1.0"
category: harness
tags:
  - wecom
  - collab
  - plan-approve
  - prd-review
  - wait
commands: []
---

# 企微协作评审 SOP

## 核心约束

1. **`push-preview` 后同一 Cursor 回合内必须阻塞 `wait`**（`--timeout 3600`），收到 intent 后同一回合处理。
2. **禁止结束对话**再等企微——单轮结束后无法唤起 Cursor Agent。
3. PRD 与技术方案使用 **不同修订口令**，避免误路由。

## 交互表

| 阶段 | phase | 确认通过（企微原话） | 需修订（企微） | wait 返回 | Agent 同一回合动作 |
|------|-------|---------------------|----------------|-----------|-------------------|
| PRD 评审 | `prd_review` | `确认 patch-001 f4a63c approver 齐迪` | **`/整理评审`** | `meeting_revise` | `meeting-revise` → 写 plan → finalize-plan → push-preview → **再 wait** |
| 技术方案 | `tech_design_review` | `确认 design-patch-001 ae9b8e approver 齐迪` | **`/整理方案`** | `tech_revise` | `tech-revise` → 写 design_plan → finalize-design → push-preview → **再 wait** |
| 技术方案通过 | `tech_design_review` | 同上确认语 | — | `plan_approve` | `approve-design --pull-intent-id <id>` |

## 技术方案阶段如何修订

1. 在企微群阅读 preview，**用文字说明**要改什么（接口、页面、范围等）。
2. 发送 **`/整理方案`**（不是 `/整理评审`）。
3. Cursor Agent（须仍在 wait 回合内）收到 `tech_revise` intent：
   - `collab_tech_design_sync.py tech-revise --req-id <id>`
   - 对照 `revise_prompt.md` 修订 `design_plan.json`
   - `finalize-design` → `push-preview` → **再 `wait`**
4. 满意后发确认语 → `plan_approve` → `approve-design` 解锁编码。

## 阻塞 wait 命令

```bash
python3 skills/req-to-dev/sub_skills/collab-prd-sync/scripts/collab_prd_sync.py wait \
  --req-id <req_id> --timeout 3600
```

`timeout` 时：**同一回合立即再跑 wait**，不要结束对话。

**禁止**对 PRD/技术方案评审 wait 加 `--action`（例如 `--action approve`）。必须同时接收 `approve`、`meeting_revise`、`tech_revise`、`plan_approve`。

## 多次 `/整理评审`（修订循环）

**允许多次**。评审不满意时，在企微补充文字意见后发 `/整理评审`（PRD）或 `/整理方案`（技术方案）即可；Agent 在同一 wait 回合内应：

1. 收到 `meeting_revise` / `tech_revise`
2. `meeting-revise` / `tech-revise` → 写 plan → `finalize-plan` / `finalize-design`
3. `push-preview`（新 patch、新 nonce）
4. **再阻塞 wait**（仍不带 `--action`）

循环直到 PM 发确认语。

## 常见事故：wait 加了 `--action approve`

| 现象 | 原因 |
|------|------|
| 企微发 `/整理评审` 后 Cursor 无响应 | Agent 用了 `collab_wait.py --action approve`，`meeting_revise` 被过滤 |
| 日志 `WARN: 收到非目标 action=meeting_revise，继续 wait（目标=approve）` | 同上；**不是**「不允许多次整理评审」 |

**恢复**：

1. 停止带 `--action` 的 wait
2. 用标准命令重新阻塞：`collab_prd_sync.py wait --req-id <id> --timeout 3600`
3. 若队列有遗留 intent：`recover-intent --req-id <id>` 查看，再在同一回合处理

详见 `guardrails/pipeline-redlines.md` R2.2、`runtime/recovery.md`。

## 降级（仅当无法长轮询时）

用户在本 Cursor 对话发出与企微相同的确认原话：

```bash
python3 skills/req-to-dev/sub_skills/collab-tech-design-sync/scripts/collab_tech_design_sync.py \
  approve-design --req-id <id> --chat-confirm "确认 design-patch-001 ae9b8e approver 齐迪"
```

## Agent API 路由约定

见 `knowledge/collab-intent-routing.md`。`push-state` 会携带 `phase`、`reviseCommand`、`expectedReviseIntent`。
