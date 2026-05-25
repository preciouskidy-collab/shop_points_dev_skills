---
name: traceability-rules
description: "创建变更文档之前加载，定义何时必须创建 Change 及其必填产物"
version: "0.1.0"
category: harness
tags:
  - rule
  - documentation
  - traceability
  - change-management
commands: []
---

# Guardrail: 变更追溯

## 什么时候必须建 Change

满足任一条件时，创建 `skills/harness/changes/YYYYMMDD-<type>-<short-name>/`：

- 跨 2 个以上 Maven 模块。
- 改 Kafka Consumer/Producer、Dubbo RPC 接口、Apollo 配置。
- 改 MyBatis Mapper XML 或 ShardingSphere 分片策略。
- 跨服务变更（同时影响 shop-points 和 shop-points-lottery）。
- 改定时任务逻辑、消息广播、BPM 工作流。
- 用户明确要求可追溯。

## Change 必填产物

| 产物 | 路径 | 回答的问题 |
|------|------|-----------|
| 状态摘要 | `summary.md` | 现在什么状态？ |
| 需求规格 | `request/spec.md` | 要做什么？ |
| 任务拆分 | `request/tasks.md` | 怎么拆的？ |
| 影响分析 | `impact/impact.md` | 影响多大？ |
| 测试报告 | `tests/test_report.md` | 验证了吗？ |

按需补充：`coding/coding_report_v*.md`、`review/code_review_v*.md`、`deploy/verify.md`。

## 写作规则

- 记录事实、决策和证据，不写空泛口号。
- 旧评审版本不删除；新一轮使用 `v2`、`v3`。
- Wiki 只记录长期系统事实；单次需求细节留在 Changes。
- Rules 只记录稳定约束；临时例外写到 Change。
- 用户显式做出的策略取舍，需要写清楚，防止后续 AI Agent 误改。

## 命名规范

```
skills/harness/changes/YYYYMMDD-<type>-<short-name>/
```

类型：`feature` / `fix` / `refactor` / `docs` / `config`

示例：
- `20260525-feature-points-exchange-api/`
- `20260525-fix-lottery-chance-deduction/`
- `20260525-refactor-disbursement-processor/`
