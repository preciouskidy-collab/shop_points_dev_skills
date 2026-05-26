# 失败恢复策略

定义每个阶段失败时的自动恢复规则。

## 恢复规则

| 阶段 | 失败场景 | 恢复策略 | 最大重试 |
|------|----------|----------|----------|
| fetch-prd | 飞书 API 超时 | 重试拉取 | 3 |
| fetch-prd | 飞书配置缺失（`feishu_config_required`） | 向用户索取 app-id/app-secret 后重试 | — |
| break-down | 需求不明确 | 标记阻塞，通知人工补充 PRD 信息 | 0 |
| scope-eval | 影响面超出预期 | 标记风险，仍产出 impact.md 进入下一阶段 | 0 |
| tech-design | 方案无法覆盖全部需求 | 标记待确认项，仍产出 tech-design.md 进入审批 | 0 |
| coding | `mvn compile` 失败 | Agent 自修编译错误，重跑 compile | 3 |
| coding | Guardrails 违规（分层/幂等/分片键） | Agent 自动修正，重跑 compile | 3（共享 coding 重试上限） |
| review | MUST FIX 问题 | Agent 按审查意见修复，重跑审查 | 2 |
| test | 测试失败 | Agent 修复测试，重跑 | 3 |
| test | 接口测试需要入参 | 暂停询问用户提供 Cookie + 请求参数 | — |
| release | Apollo 配置缺失 | 标记阻塞，等待人工同步 | 0 |

## 升级规则

超过最大重试次数后：
1. 运行 `run_workflow.py log --name <name> --message "升级人工：<阶段> 超过重试上限"`
2. 停止 Pipeline，向用户报告失败阶段和原因
3. 用户可选择：
   - 人工修复后从失败阶段继续（已完成阶段自动跳过）
   - 终止 Pipeline，运行 `run_workflow.py status` 记录进度

## 人工审批点

Pipeline 中只有 **plan-approve** 一个阻塞点：

| 节点 | 触发条件 | 审批内容 | 操作 |
|------|----------|----------|------|
| plan-approve | 必经（advance 返回 `BLOCKING`） | spec.md + impact.md + tech-design.md | 通过 → coding / 驳回 → 回退 scope-eval / 拒绝 → 终止 |

驳回时运行 `run_workflow.py reject --reason "<修改意见>"`，Pipeline 回退到 scope-eval 重新执行 scope-eval → tech-design → plan-approve。

## 状态流转

```
pending → running → completed → (下一阶段 running)
                  → blocked（plan-approve 等人）
                  → failed → retrying → running
                           → escalated（超重试上限，人工介入）

驳回路径:
plan-approve(blocked) → reject → scope-eval(running) → tech-design(running) → plan-approve(blocked)
```

## 异常场景速查

| 场景 | 命令 | 说明 |
|------|------|------|
| 查看当前进度 | `run_workflow.py status --name <name>` | 查看当前阶段和状态 |
| 记录日志 | `run_workflow.py log --name <name> --message "..."` | 记录关键事件 |
| 标记失败 | `run_workflow.py fail --name <name> --reason "..."` | 触发重试或升级 |
| 审批通过 | `run_workflow.py approve --name <name>` | 推进到 coding |
| 审批驳回 | `run_workflow.py reject --name <name> --reason "..."` | 回退到 scope-eval |
