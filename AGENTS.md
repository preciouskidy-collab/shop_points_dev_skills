# shop_points_dev_skills — Agent 指引

## 审批：默认 Agent 聊天交互

所有 PRD 写回 approve 在**对话中确认**，不需另开终端。

1. `meeting` / `digest` → 展示 human_summary（含验证码）
2. 用户回复：`确认 patch-001 abc123 approver 周美琪`
3. Agent 跑 approve，`--chat-confirm` 填用户**原话**

```bash
python3 skills/req-to-dev/sub_skills/collab-prd-sync/scripts/collab_prd_sync.py approve \
  --prd-url "<PRD URL>" --patch patch-001 --approver 周美琪 \
  --chat-confirm "确认 patch-001 abc123 approver 周美琪"
```

## 会议纪要 → PRD（init 前 · 无 req_id）

```bash
python3 .../collab_prd_sync.py meeting --meeting-url "..." --prd-url "..."
```

## 联调 → PRD（init 后 · 有 req_id）

```bash
python3 .../collab_prd_sync.py digest --req-id <id>
python3 .../collab_prd_sync.py approve --req-id <id> --patch ... --chat-confirm "..."
python3 .../collab_prd_sync.py resync --req-id <id>
```
