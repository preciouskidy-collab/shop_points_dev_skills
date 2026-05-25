---
name: release-validation
description: "部署前验证时触发，确认构建、配置、接口兼容性和回滚方案"
version: "0.1.0"
category: harness
tags:
  - skill
  - deploy
  - verify
  - release
commands: []
---

# Skill: 发布验证

## 适用范围

部署前检查、环境参数确认、灰度/回滚记录。

## 步骤

1. **确认目标环境**：dev / test / preview / prod。
2. **构建验证**：`mvn clean package -DskipTests` 构建成功。
3. **Apollo 配置检查**：新增的配置 key 是否已在目标环境的 Apollo 中同步。
4. **Dubbo 接口兼容性**：
   - 新增参数是否有默认值？
   - 是否需要通知消费者升级？
   - 消费者端编译是否通过？
5. **Kafka 变更确认**：
   - topic / group 是否需要变更？
   - 是否需要 MQ 团队审批？
   - Consumer 是否支持幂等消费？
6. **数据库迁移**：
   - 新增表/列是否有 SQL migration 脚本？
   - 是否需要 DBA 审批？
   - 分片表是否配置了分片策略？
7. **记录回滚方案**：如何回滚？是否有数据回滚需求？

## 产出
- `deploy/verify.md`

模板结构：
```markdown
# Deploy Verify
## Environment
## Build Status
## Apollo Config Changes
## Dubbo Interface Changes
## Kafka Changes
## Database Migration
## Rollback Plan
```

## 质量标准
- 不推测部署参数；缺参数时等待用户确认。
- 不把编译通过等同于业务链路验证通过。
- 回滚方案必须具体可执行，不能只写"回滚代码"。
