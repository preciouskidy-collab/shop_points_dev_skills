# 企微协作 Intent 路由（Agent API 约定）

Pipeline 通过 `collab_push_state.py` 同步 `phase` 到 Agent。群消息解析须 **按 phase 分轨**，避免技术方案阶段 `/整理评审` 误入 PRD 修订。

## Pipeline stage ↔ 企微 phase（同义）

| Pipeline `stages[].id` | `collaboration.phase` | 何时进入 |
|------------------------|----------------------|----------|
| **`plan-approve`** | **`tech_design_review`** | `collab-tech-design-sync prepare` / `finalize-design` 即 `push-state`；**`push-preview` 发群时已是技术方案评审** |

群消息标题：**技术方案评审** · design-patch-NNN（非「预览」）。

## push-state 字段

| 字段 | 说明 |
|------|------|
| `phase` | `prd_review` \| `tech_design_review` \| `idle` \| … |
| `activePreviewType` | `prd` \| `tech_design` |
| `reviseCommand` | 当前阶段应使用的修订口令 |
| `expectedReviseIntent` | 修订口令应对应的 `action` |
| `revisionCursor` | PRD 修订轮游标 |
| `techDesignRevisionCursor` | 技术方案修订轮游标 |
| `stateJson` | 完整 `collaboration` 快照 |

## 群消息 → intent 规则

| 用户消息（企微） | phase 条件 | intentType | action |
|------------------|------------|------------|--------|
| `/整理评审`、整理评审反馈 | `prd_review` 且 PRD 评审未结束 | `command_intent` | `meeting_revise` |
| `/整理方案`、整理技术方案、整理方案评审 | `tech_design_review` | `command_intent` | `tech_revise` |
| `确认 patch-NNN <nonce> approver <姓名>` | `prd_review`，nonce/patch 匹配 active preview | `approval_intent` | `approve` |
| `确认 design-patch-NNN <nonce> approver <姓名>` | `tech_design_review`，匹配 design preview | `approval_intent` | `plan_approve` |

## 错误路由防护

- `phase=tech_design_review` 时：`/整理评审` **不应** 产生 `meeting_revise`；应提示用户发 `/整理方案`。
- `phase=prd_review` 时：`/整理方案` 可拒绝或提示使用 `/整理评审`。

## Cursor Agent 侧

收到 intent 后须在 **同一对话回合** 处理；`push-preview` 后必须 `wait --timeout 3600`，禁止结束回合。

### wait 禁止 action 过滤

PRD / 技术方案评审的 wait **不得**使用 `--action` 只等 `approve`。须同时处理：

| action | 触发 | 同一回合动作 |
|--------|------|--------------|
| `meeting_revise` | `/整理评审` | 修订循环 → 再 wait |
| `tech_revise` | `/整理方案` | 修订循环 → 再 wait |
| `approve` | PRD 确认语 | `approve --pull-intent-id` |
| `plan_approve` | 技术方案确认语 | `approve-design --pull-intent-id` |

**允许多次** `/整理评审` / `/整理方案`；每次返回修订 intent 即进入新一轮 patch。

仅 `collab_e2e_upload.py wait` 可过滤为 `upload_confirm`（E2E 人工上传，与评审 wait 分离）。

详见 `playbooks/wecom-collab-review.md`、`guardrails/pipeline-redlines.md` R2/R2.1/R2.2。
