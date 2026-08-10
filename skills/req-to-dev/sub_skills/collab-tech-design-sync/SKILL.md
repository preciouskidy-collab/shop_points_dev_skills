---
name: collab-tech-design-sync
description: "技术方案企微评审。plan-approve（phase=tech_design_review）prepare→finalize-design→push-preview→阻塞wait→approve-design"
version: "0.1.0"
category: req-to-dev
tags:
  - collab
  - tech-design
  - plan-approve
  - wechat
commands:
  - prepare
  - finalize-design
  - push-preview
  - wait
  - tech-revise
  - approve-design
trigger_phrases:
  - 技术方案评审
  - 方案评审
  - 整理技术方案
  - 整理方案
  - 确认方案
---

# collab-tech-design-sync — 技术方案企微评审

与链路1 PRD 评审 **同构**：长轮询 `wait` + 意图邮箱；preview 对象为本地 `api-contract.yaml` + 详设 md。

## 触发时机

Pipeline 到达 **`plan-approve`**（企微 **`tech_design_review`**）阻塞阶段时执行。

> **`push-preview` 发到企微时即处于技术方案评审阶段**（`prepare` / `finalize-design` 已 `push-state phase=tech_design_review`）。

## 标准流程（同一回合阻塞 wait）

```bash
cd <shop_points_dev_skills 根目录>
python3 skills/req-to-dev/sub_skills/collab-tech-design-sync/scripts/collab_tech_design_sync.py prepare --req-id <req_id>
# Agent 写 collaboration/design-patch-NNN/design_plan.json（仅修订 changes/ 内方案文档）
python3 .../collab_tech_design_sync.py finalize-design --req-id <req_id> --patch design-patch-001
python3 .../collab_tech_design_sync.py push-preview --req-id <req_id> --patch design-patch-001
# 【红线】同一回合阻塞 wait，禁止结束回合等用户在 Cursor 输入
python3 skills/req-to-dev/sub_skills/collab-prd-sync/scripts/collab_prd_sync.py wait \
  --req-id <req_id> --timeout 3600
```

| wait 返回 | 同一回合动作 |
|-----------|--------------|
| `plan_approve` | `approve-design --pull-intent-id <id>` → 自动解锁 backend-coding |
| `tech_revise` | `tech-revise` → 写 plan → `finalize-design` → `push-preview` → **再 wait** |
| `timeout` | 立即再跑 `wait`（仍在本回合） |

## 企微交互（修订 vs 确认）

| 意图 | 企微操作 | 说明 |
|------|----------|------|
| **确认通过** | `确认 design-patch-NNN <nonce> approver <姓名>` | 产生 `plan_approve` intent |
| **需要修订** | 先文字说明修改点 → 发 **`/整理方案`** | 产生 `tech_revise` intent，**勿用 `/整理评审`** |

修订轮：`tech-revise` 会拉群消息写入 `revise_prompt.md`，Agent 改 `design_plan.json` 后重新 preview。

完整 SOP：`playbooks/wecom-collab-review.md`

## 硬规则（红线）

- **prepare/finalize/push 之前**：禁止检出 feature 分支、禁止改 shop-points/store-integral 业务代码
- **push-preview 之后**：必须阻塞 `wait`；禁止 `block_until_ms=0` 后台 watch
- **禁止**直接 `run_workflow.py approve` 跳过本流程（脚本已门禁）
- 详见 `guardrails/pipeline-redlines.md`

## 企微确认语

```
确认 design-patch-001 <nonce> approver <姓名>
```

修订指令（技术方案专用）：**`/整理方案`**（可在群里先写修改意见再发口令）

**禁止**在技术方案阶段使用 `/整理评审`（会误触发 PRD `meeting_revise`）。

## design_plan.json 格式

```json
{
  "version": 1,
  "source": "tech_design_review",
  "plan_source": "agent",
  "design_diff_summary": "修订说明…",
  "changes": [{"summary": "统一分页参数"}],
  "updates": [
    {
      "target": "handoff/api-contract.yaml",
      "command": "str_replace",
      "pattern": "pageNo:",
      "content": "pageNum:"
    }
  ]
}
```

`target` 允许：`handoff/api-contract.yaml`、`tech-design/tech-design.md`、`tech-design/frontend-design.md`

## 与 plan-approve 的关系

`approve-design` 会：应用 `updates` → `push-state phase=idle` → 自动 `run_workflow approve` 解锁编码阶段。
