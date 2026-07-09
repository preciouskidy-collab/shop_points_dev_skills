# shop_points_dev_skills — Agent 指引

## collab-prd-sync 触发词（必读）

**任何「修改/更新飞书 PRD 文档」的诉求都走 collab-prd-sync**（不是端到端开发）。先做**链路判定**，再 dry-run → **人工对话确认** → 才 approve 写飞书。即使用户措辞不是精确触发词（如「帮我更新飞书 prd」并附会议纪要链接），也要命中本能力。

| 用户说法（满足任一即命中） | 链路 | Agent 动作 |
|----------------------------|------|------------|
| **更新飞书 PRD** / 帮我更新飞书 prd / 更新 PRD（附**会议纪要链接**）| 链路1 | `meeting --meeting-url --prd-url` → 说明纪要共识与 PRD 拟修正点 → **等确认** → `approve --prd-url` |
| **根据会议纪要 / 评审会更新 PRD**、PRD 定稿 | 链路1 | 同上（**无 req_id**，不 resync） |
| 同时给出 **PRD 链接 + 会议纪要链接** | 链路1 | 同上 |
| **整理联调消息写回 PRD** / 企微消息整理 / 联调共识写回 PRD（已 init / 有 req_id）| 链路2 | `digest --req-id` → 说明摘要与 PRD 差异 → **等确认** → `approve --req-id`（自动 resync） |
| 确认 patch-NNN … approver … | — | `approve --chat-confirm` |
| prd resync | — | `resync` |
| 只给 PRD 链接、信息不足 | — | 先问：会议纪要更新(meeting) 还是 联调消息更新(digest)？ |

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
