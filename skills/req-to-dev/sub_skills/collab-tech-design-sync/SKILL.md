---
name: collab-tech-design-sync
description: "技术方案企微评审。plan-approve 阶段 prepare→finalize-design→push-preview→阻塞wait→approve-design"
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
  - 确认方案
---

# collab-tech-design-sync — 技术方案企微评审

与链路1 PRD 评审 **同构**：长轮询 `wait` + 意图邮箱；preview 对象为本地 `api-contract.yaml` + 详设 md。

## 触发时机

Pipeline 到达 **`plan-approve`** 阻塞阶段时执行。

## 标准流程（同一回合阻塞 wait）

```bash
cd <shop_points_dev_skills 根目录>
python3 skills/req-to-dev/sub_skills/collab-tech-design-sync/scripts/collab_tech_design_sync.py prepare --req-id <req_id>
# Agent 写 collaboration/design-patch-NNN/design_plan.json
python3 .../collab_tech_design_sync.py finalize-design --req-id <req_id> --patch design-patch-001
python3 .../collab_tech_design_sync.py push-preview --req-id <req_id> --patch design-patch-001
python3 .../collab_tech_design_sync.py wait --req-id <req_id> --timeout 3600
```

| wait 返回 | 同一回合动作 |
|-----------|--------------|
| `plan_approve` | `approve-design --pull-intent-id <id>` |
| `tech_revise` | `tech-revise` → 写 plan → `finalize-design` → `push-preview` → **再 wait** |
| `timeout` | 立即再跑 `wait` |

## 企微确认语

```
确认方案 design-patch-001 <nonce> approver <姓名>
```

修订指令：`/整理方案` 或 `/整理技术方案`

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
