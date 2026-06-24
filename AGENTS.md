# shop_points_dev_skills — Agent 指引

## collab-prd-sync 触发词（必读）

**「整理联调消息写回 PRD」** = 企微群消息 → 摘要 → 对照 PRD 找出入拟修正 → dry-run 预览 → **人工对话确认** → 才 approve 写飞书。

| 用户说法 | Agent 动作 |
|----------|------------|
| **整理联调消息写回 PRD** / 企微消息整理 / 联调共识写回 PRD | `digest` → 说明摘要与 PRD 差异 → **等确认** → `approve` |
| 根据会议纪要更新 PRD | `meeting` → **等确认** → `approve` |
| 确认 patch-NNN … approver … | `approve --chat-confirm` → **自动 resync** |
| prd resync | `resync` |

**禁止** digest/meeting 后未经用户对话确认就 approve。

Skill 路径：`skills/req-to-dev/sub_skills/collab-prd-sync/SKILL.md`

## 审批：默认 Agent 聊天交互

所有 PRD 写回 approve 在**对话中确认**，不需另开终端。

1. `meeting` / `digest` → 展示 human_summary（含验证码）
2. 用户回复：`确认 patch-001 abc123 approver 周美琪`
3. Agent 跑 approve（`patch`/`approver` 从确认语解析）→ **链路 2 自动 prd resync**

```bash
python3 skills/req-to-dev/sub_skills/collab-prd-sync/scripts/collab_prd_sync.py approve \
  --req-id "<req_id>" \
  --chat-confirm "确认 patch-001 abc123 approver 周美琪"
```

## 会议纪要 → PRD（init 前 · 无 req_id）

```bash
python3 .../collab_prd_sync.py meeting --meeting-url "..." --prd-url "..."
```

## 联调 → PRD（init 后 · 有 req_id）

```bash
python3 .../collab_prd_sync.py digest --req-id <id>
python3 .../collab_prd_sync.py approve --req-id <id> --chat-confirm "确认 patch-002 ... approver 齐迪"
# approve 成功后自动 resync，一般无需再跑 resync
```
