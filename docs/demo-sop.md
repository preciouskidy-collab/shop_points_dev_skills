# req-to-dev Demo 使用 SOP

从打开 Claude Code 到 Pipeline 完成，完整的使用流程。

---

## 前置准备（一次性）

1. **飞书凭证** — 首次使用 feishu-doc-fetcher 时会提示输入 app-id/app-secret，自动保存到 `~/.shop-points-dev-skills/feishu-config.json`
2. **确认目标项目路径**：
   - shop-points: `/Users/qidi/IdeaProjects/shop-points`
   - shop-points-lottery: `/Users/qidi/IdeaProjects/shop-points-lottery`

---

## 使用步骤

### Step 1：在 skills 仓库打开 Claude Code

```bash
cd /Users/qidi/Desktop/日常小记/Harness/shop_points_dev_skills
claude
```

### Step 2：发送需求

在 Claude Code 中输入：

```
从这个飞书文档开发后端功能
飞书 URL: https://feishu.cn/doc/xxx
需求名称: add-points-expiry
目标项目: /Users/qidi/IdeaProjects/shop-points
```

或更简洁：

```
req-to-dev https://feishu.cn/doc/xxx add-points-expiry /Users/qidi/IdeaProjects/shop-points
```

### Step 3：Agent 自动执行

Agent 读到触发词后，按 SKILL.md 自动执行：

```
┌─────────────────────────────────────────────────────────────────┐
│ 自动阶段                        检查点        自动阶段           │
│ ────────────────────────       ─────────     ──────────────────│
│ fetch-prd → break-down → scope-eval → [审批] → tech-design →   │
│ coding → review → test → release                                │
└─────────────────────────────────────────────────────────────────┘
```

**全程你只需要做一件事：在 plan-approve 检查点审批。**

### Step 4：审批点交互

Agent 会暂停并向你展示：

```
📋 审批内容：

1. 需求摘要（spec.md）：
   - 功能 A：积分过期提醒
   - 功能 B：过期积分自动扣减
   - 功能 C：过期记录查询

2. 影响范围（impact.md）：
   - 涉及模块：shop-points-service（points 子包）、shop-points-dao
   - 新增接口：2 个
   - 数据库变更：新增 1 张表

3. Won't Do：
   - 不涉及 shop-points-lottery
   - 不修改 Dubbo 接口
   - 不添加 Kafka 消息

❓ 是否批准？
```

你回答 **"批准"** 即可。如需调整，告诉 Agent 修改哪部分。

### Step 5：等待完成

Agent 自动完成后续所有阶段。完成后你会看到：

```
✅ Pipeline 全部完成！
Change 目录: changes/20260525-req-add-points-expiry
```

---

## 查看执行日志

Pipeline 的每一步操作都记录在 `pipeline.log` 中：

```bash
# 查看完整日志
python3 skills/req-to-dev/scripts/run_workflow.py log --name add-points-expiry --show

# 查看当前状态
python3 skills/req-to-dev/scripts/run_workflow.py status --name add-points-expiry
```

### 预期日志输出

```
[2026-05-25 14:30:00] INIT pipeline "add-points-expiry" target=/Users/qidi/IdeaProjects/shop-points project=shop-points
[2026-05-25 14:30:00] STAGE fetch-prd → running
[2026-05-25 14:30:15] AGENT: PRD 拉取完成，3 个图片，文档 150 行
[2026-05-25 14:30:15] STAGE fetch-prd → completed (15s, artifacts: request/prd.md)
[2026-05-25 14:30:16] STAGE break-down → running (loaded: knowledge/project-atlas)
[2026-05-25 14:30:45] AGENT: 需求拆解完成：3 个功能模块，8 个任务项
[2026-05-25 14:30:45] STAGE break-down → completed (29s, artifacts: request/spec.md, request/tasks.md)
[2026-05-25 14:30:46] STAGE scope-eval → running (loaded: knowledge/shop-points/component-graph, knowledge/shop-points/data-layer)
[2026-05-25 14:31:15] AGENT: 范围评估完成：涉及 points/equity 模块，Won't Do: 跨服务变更
[2026-05-25 14:31:15] STAGE scope-eval → completed (29s, artifacts: impact/impact.md)
[2026-05-25 14:31:15] BLOCKING plan-approve — 等待人工审批
[2026-05-25 14:32:00] APPROVED plan-approve
[2026-05-25 14:32:01] STAGE tech-design → running (loaded: knowledge/project-atlas, knowledge/shop-points/component-graph, ...)
[2026-05-25 14:33:00] AGENT: 技术方案生成完成：3 个接口变更，1 个数据库变更
[2026-05-25 14:33:00] STAGE tech-design → completed (59s, artifacts: tech-design/tech-design.md)
[2026-05-25 14:33:01] STAGE coding → running (loaded: guardrails/layering-contracts, guardrails/ai-coding-spec, playbooks/spring-boot-coding)
[2026-05-25 14:35:00] AGENT: 编码完成：生成 5 个文件，修改 3 个文件
[2026-05-25 14:35:00] STAGE coding → completed (2m0s, artifacts: 代码 diff)
[2026-05-25 14:35:01] STAGE review → running (loaded: guardrails/layering-contracts, ...)
[2026-05-25 14:36:00] AGENT: 审查完成：0 MUST FIX, 2 SHOULD FIX, 3 INFO
[2026-05-25 14:36:00] STAGE review → completed (59s, artifacts: review/code_review_v1.md)
[2026-05-25 14:36:01] STAGE test → running (loaded: checkpoints, playbooks/test-authoring)
[2026-05-25 14:37:00] AGENT: 测试编写完成：6 个测试用例
[2026-05-25 14:37:00] STAGE test → completed (59s, artifacts: tests/test_report.md)
[2026-05-25 14:37:01] STAGE release → running (loaded: playbooks/release-validation)
[2026-05-25 14:37:30] AGENT: 发布验证完成：Apollo OK，Dubbo OK，Kafka OK
[2026-05-25 14:37:30] STAGE release → completed (29s, artifacts: deploy/verify.md)
[2026-05-25 14:37:30] PIPELINE COMPLETED (总耗时 7m30s)
```

---

## 产出物目录

Pipeline 完成后，所有产出物在 `changes/YYYYMMDD-req-<name>/` 下：

```
changes/20260525-req-add-points-expiry/
├── pipeline.log              # 完整执行日志
├── pipeline_state.json       # Pipeline 状态（含每阶段时间戳）
├── summary.md                # 变更摘要
├── request/
│   ├── prd.md                # PRD 原文
│   ├── spec.md               # 需求规格
│   └── tasks.md              # 任务拆分
├── impact/
│   └── impact.md             # 影响分析 + Won't Do
├── tech-design/
│   └── tech-design.md        # 技术方案
├── review/
│   └── code_review_v1.md     # 审查报告
├── tests/
│   └── test_report.md        # 测试报告
└── deploy/
    └── verify.md             # 发布验证
```

目标项目路径下是 Agent 生成的 Java 代码。

---

## 中断恢复

如果 Pipeline 中途 Claude Code 会话断开：

```bash
# 1. 重新打开 Claude Code
cd /Users/qidi/Desktop/日常小记/Harness/shop_points_dev_skills
claude

# 2. 告诉 Agent 恢复
"继续 req-to-dev pipeline，名称 add-points-expiry"

# 3. Agent 会自动检查状态
python3 skills/req-to-dev/scripts/run_workflow.py status --name add-points-expiry
python3 skills/req-to-dev/scripts/run_workflow.py log --name add-points-expiry --show

# 已完成的阶段会被跳过（产出物已存在）
```

---

## 两个项目的区别

| 参数 | shop-points                            | shop-points-lottery |
|------|----------------------------------------|---------------------|
| `--target` | `/Users/qidi/IdeaProjects/shop-points` | `/Users/qidi/IdeaProjects/shop-points-lottery` |
| 自动加载 knowledge | `knowledge/shop-points/*`              | `knowledge/shop-points-lottery/*` |
| 模块数 | 8                                      | 5 |
| 数据库 | 双库 + 部分表ShardingSphere 100 分片          | 双库（lottery + mall） |
