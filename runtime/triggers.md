# 触发规则

定义何时自动启动 req-to-dev Pipeline。

## 触发方式

| 方式 | 条件 | 动作 |
|------|------|------|
| **手动触发** | 用户在 Claude Code 中执行 req-to-dev | 立即启动 |
| **Issue 触发** | GitLab Issue 标记为 `ai-coding` label | 自动启动，Issue 描述作为输入 |
| **PRD 就绪触发** | 飞书文档状态变为"已评审" | 自动启动，文档 URL 作为输入 |

## Issue 触发模板

```markdown
## 需求来源
<!-- 飞书文档 URL 或需求描述 -->

## 目标项目
- [ ] shop-points
- [ ] shop-points-lottery

## 优先级
- P0 / P1 / P2

## 期望产出
- [ ] 技术方案
- [ ] 代码实现
- [ ] 测试用例
```

## 触发后动作

1. 在 `changes/` 下创建 Change 目录（按 `YYYYMMDD-<type>-<name>` 命名）
2. 写入 `request/spec.md`
3. 启动 Pipeline 阶段1
