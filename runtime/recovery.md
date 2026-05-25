# 失败恢复策略

定义每个阶段失败时的自动恢复规则。

## 恢复规则

| 阶段 | 失败场景 | 恢复策略 | 最大重试 |
|------|----------|----------|----------|
| fetch-prd | 飞书 API 超时 | 重试 | 3 |
| break-down | 需求不明确 | 标记阻塞，通知人工补充 | 0 |
| scope-eval | 影响面超出预期 | 标记风险，仍进入 plan-approve | 0 |
| coding | `mvn compile` 失败 | Agent 自修编译错误 | 3 |
| coding | Guardrails 违规 | Agent 自动修正分层违规 | 2 |
| review | MUST FIX 问题 | Agent 按审查意见修复 | 2 |
| test | 测试失败 | Agent 修复测试 | 3 |
| test | 测试无法运行 | 记录阻塞原因，跳过测试阶段 | 0 |
| release | Apollo 配置缺失 | 标记阻塞，等待人工同步 | 0 |

## 升级规则

超过最大重试次数后：
1. 写入 `changes/<change>/summary.md` 标记失败阶段和原因
2. 停止 Pipeline，通知人工介入
3. 人工修复后可从失败阶段重启（跳过已完成阶段）

## 人工审批点

| 节点 | 触发条件 | 审批内容 |
|------|----------|----------|
| plan-approve | 必经 | 范围评估结果、影响面、Won't Do 列表 |
| scope-expand | scope-eval 发现跨服务变更 | 跨服务变更方案确认 |
| guardrail-violation | coding 阶段 2 次修复仍违反 Guardrails | 是否放宽约束 |

## 状态流转

```
pending → running → blocked → approved → running → completed
                  → failed → retrying → running
                           → escalated（人工介入）
```
