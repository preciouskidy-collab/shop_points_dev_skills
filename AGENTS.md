# shop_points_dev_skills — Agent 指引

## collab-prd-sync 触发词（必读）

**任何「修改/更新飞书 PRD 文档」的诉求都走 collab-prd-sync**（不是端到端开发）。先做**链路判定**，再 dry-run → **人工对话确认** → 才 approve 写飞书。

| 用户说法（满足任一即命中） | 链路 | Agent 动作 |
|----------------------------|------|------------|
| PRD + 会议纪要 / 更新飞书 PRD / PRD 定稿 | 链路1 | bootstrap → binding-check → meeting → push-preview → **阻塞 wait** |
| **技术方案评审** / plan-approve 企微评审 | 技术方案 | `collab-tech-design-sync prepare` → finalize-design → push-preview → **阻塞 wait** |
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
| `action=meeting_revise` | meeting-revise 全流程 → push-preview → **再 wait** |
| `action=plan_approve` | approve-design --pull-intent-id → 解锁 plan-approve |
| `action=tech_revise` | tech-revise → finalize-design → push-preview → **再 wait** |
| `status=timeout` | 立即再跑 wait |

**禁止**：`block_until_ms=0` 后台 watch；回合结束后再等企微唤起。

**降级**：`--chat-confirm`；`push-preview --headless-listen`（仅自动 approve）。
