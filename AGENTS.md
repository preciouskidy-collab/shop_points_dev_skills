# shop_points_dev_skills — Agent 指引

## collab-prd-sync 触发词（必读）

**任何「修改/更新飞书 PRD 文档」的诉求都走 collab-prd-sync**（不是端到端开发）。先做**链路判定**，再 dry-run → **人工对话确认** → 才 approve 写飞书。

| 用户说法（满足任一即命中） | 链路 | Agent 动作 |
|----------------------------|------|------------|
| PRD + 会议纪要 / 更新飞书 PRD / PRD 定稿 | 链路1 | bootstrap → binding-check → meeting → push-preview → **阻塞 wait** |
| **技术方案评审** / plan-approve 企微评审 | 技术方案（`plan-approve` = `tech_design_review`） | `collab-tech-design-sync prepare` → finalize-design → push-preview（**发群即评审阶段**）→ **阻塞 wait** |
| **整理联调消息写回 PRD**（有 req_id）| 链路2 | `digest` → 说明差异 → 等确认 → `approve`（自动 resync） |
| 确认 patch-NNN … approver … | — | **立即** `approve --chat-confirm` |
| prd resync | — | `resync` |

Skill 路径：`skills/req-to-dev/sub_skills/collab-prd-sync/SKILL.md`

## 审批：链路1 阻塞 wait（生产）

**单轮结束无法靠意图唤起** → `push-preview` 后 **同一回合**阻塞 `wait`，收到 intent JSON 后 **同一回合**处理。

```bash
python3 skills/req-to-dev/sub_skills/collab-prd-sync/scripts/collab_prd_sync.py wait \
  --req-id "<req_id>" --timeout 3600
```

| 返回 | 同一回合动作 |
|------|--------------|
| `action=approve` | `approve --pull-intent-id <id>` |
| `action=meeting_revise` | meeting-revise 全流程 → push-preview → **再 wait**（PRD；口令 `/整理评审`） |
| `action=plan_approve` | approve-design --pull-intent-id → 解锁 plan-approve |
| `action=tech_revise` | tech-revise → finalize-design → push-preview → **再 wait**（技术方案；口令 `/整理方案`） |
| `status=timeout` | 立即再跑 wait |

**禁止**：`block_until_ms=0` 后台 watch；回合结束后再等企微唤起。

**禁止 wait `--action` 过滤**（R2.2）：不得 `collab_wait.py --action approve` 只等确认；须无过滤 wait，以接收多次 `/整理评审` 产生的 `meeting_revise`。

**企微修订口令**：PRD 用 `/整理评审`；技术方案用 `/整理方案`（勿混用）。详见 `playbooks/wecom-collab-review.md`。

**降级**：`--chat-confirm`；`push-preview --headless-listen`（仅自动 approve）。

## Apollo Mock 时间（按需）

贝壳币明细缺账期、改 `mockCurrentTime`、申诉期相关 E2E → 读 `playbooks/apollo-mock-time.md`（或 `python3 skills_loader.py search "apollo mock"`）。

## E2E 人工上传（企微 + 阻塞 wait，无对话降级）

需用户选手动上传 → `playbooks/e2e-upload-collab.md`：`notify` → **同一回合** `wait` → 企微 `upload_confirm` 后再点确定。Agent API 不可用则阻塞，**禁止**在 Cursor 对话回复「已上传」代替。

## req-to-dev Pipeline 红线（必读）

完整条文：`guardrails/pipeline-redlines.md` · Cursor 规则：`.cursor/rules/req-to-dev-pipeline.mdc`

| 红线 | 要点 |
|------|------|
| R1 企微不可漏推 | finalize → **push-preview** → 确认 Webhook 成功 |
| R2 同一回合阻塞 wait | push 后 **禁止结束回合**；必须 `wait --timeout 3600` 并处理 intent |
| R2.2 禁止 action 过滤 | **禁止** `collab_wait --action approve`；须无过滤 wait，支持多次 `/整理评审` |
| R3 先方案后编码 | plan-approve（=技术方案评审）前 **禁止**改 shop-points/store-integral；须 `approve-design` 解锁 |
| R4 验收默认本地 | `integration_mode: local` + Cursor 浏览器 E2E；通过后 **直接** commit-push（无 deploy-approve） |

**禁止**直接 `run_workflow.py approve` 跳过 `approve-design`（脚本已门禁）。
