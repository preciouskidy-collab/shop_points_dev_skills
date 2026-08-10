---
name: e2e-upload-collab
description: "E2E 需人工上传文件时：企微通知 + 阻塞 wait upload_confirm；禁止结束回合"
version: "1.0.0"
category: playbooks
tags:
  - e2e
  - wecom
  - upload
  - collab
  - wait
commands: []
---

# E2E 人工上传 · 企微通知 + 阻塞 wait

> **适用**：PC Excel 上传、S3 附件等 Cursor 浏览器无法 `setFileInputFiles` 的场景。  
> **原则**：通知用户后 **同一回合阻塞 wait**，收到 `upload_confirm` 再继续点「确定」等操作。

## 禁止

| 禁止 | 原因 |
|------|------|
| 通知后结束回合，等用户在 Cursor 聊天回复 | 单轮结束无法靠企微唤起主会话 |
| `block_until_ms=0` 后台 watch | 同上 |
| 未 wait 到确认就点「确定」 | 弹窗无文件会失败 |

## 前置条件

- 联调群已 `/init <req_id>` 且 `binding-check` 通过（与 PRD 协作共用绑群）
- **Agent API 必须可达**（`skills/req-to-dev/config/agent.yaml`）；不可达则整个流程阻塞，**无 Cursor 对话降级**
- 企微 `messagePersistEnabled=true`（消息落库，wait 可轮询群消息）

## Agent 流程（同一回合）

```
1. 浏览器：打开上传弹窗，确认账期/城市已填
2. notify：企微推送「请上传」+ 确认语
3. wait：阻塞长轮询（禁止结束回合）
4. 收到 upload_confirm → snapshot → 点「确定」→ 继续验收
```

### 1. 企微通知

```bash
python3 skills/req-to-dev/scripts/collab_e2e_upload.py notify \
  --req-id <req_id> \
  --label "上传贝壳币 Excel（活动 253 · 账期 2026M9）" \
  --detail "PC 弹窗已打开；门店 TJDY0101 · 天津市"
```

stdout 含 `confirm_phrase`（带 nonce 的推荐确认语）。

### 2. 阻塞 wait（同一回合立即执行）

```bash
python3 skills/req-to-dev/scripts/collab_e2e_upload.py wait \
  --req-id <req_id> --timeout 3600
```

| 返回 | 同一回合动作 |
|------|--------------|
| `action=upload_confirm` | 继续浏览器：snapshot → 点「确定」→ 列表/H5 验收 |
| `status=timeout` | **立即再跑 wait**，勿结束对话 |

### 3. 用户侧（企微群）

推荐回复 notify 消息中的完整确认语，例如：

```text
确认 upload-a1b2c3d4 <nonce> 已上传
```

或简短：`已上传` / `文件已选好` / `上传完成`

## 确认来源

| 来源 | 说明 |
|------|------|
| `upload_confirm` intent | shop-points-agent 解析群消息后入队（推荐，与 PRD approve 同架构） |
| 群消息匹配 | Harness 轮询 `list_messages` + 确认语启发式（**当前兜底**，无需等新 intent 上线） |

Agent 后端扩展（可选）：群消息 → `intent_type=e2e_upload_intent`, `action=upload_confirm`。

## 与 PRD wait 的区别

| 项 | PRD / 方案评审 | E2E 上传 |
|----|----------------|----------|
| 脚本 | `collab_prd_sync.py wait` | `collab_e2e_upload.py wait` |
| action | `approve` / `meeting_revise` … | `upload_confirm` |
| 发布属性 | 业务变更 / 业务开关 | 无（仅 notify） |

## 无降级（强制）

| 禁止 | 说明 |
|------|------|
| Cursor 对话回复「已上传」视为确认 | 单轮结束无法靠聊天唤起；且与企微 wait 架构不一致 |
| Agent API 不可达时改走对话 | **必须先恢复 Agent API**（`agent.yaml` / VPN），再 `notify` + `wait` |
| 跳过 `wait` 直接点「确定」 | 弹窗无文件会失败 |

Agent API 连接失败时：`notify` / `wait` 脚本报错退出；Agent **不得**自行继续上传验收，应报告阻塞并等待环境恢复。

## 关联

- 上传场景说明：`playbooks/local-e2e-browser-test.md` §含文件上传的 E2E
- 流程红线：`guardrails/pipeline-redlines.md` R5
