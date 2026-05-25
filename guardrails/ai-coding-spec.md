---
name: ai-coding-spec
description: "AI 生成 Java/Spring Boot 代码时必须遵守的运行约束和业务红线"
version: "0.1.0"
category: harness
tags:
  - rule
  - ai-agent
  - java
  - spring-boot
  - business-constraints
commands: []
---

# Guardrail: AI 编码规范

## 适用范围

适用于 AI Agent 生成的所有 Java/Spring Boot 代码，包括 Controller、Service、DAO、Mapper、RPC Proxy、Kafka Consumer、定时任务。

## 编码约束

- AI 生成的代码必须遵循 `layering-contracts` 的分层约束。
- Controller 只调 Service；Service 编排 DAO/RPC/Kafka。
- 不生成绕过 Service 层直接访问 DAO 的代码。
- MyBatis Mapper 改动必须同时更新 Mapper Interface 和 Mapper XML。
- `@Transactional` 注解用于 Service 方法，不用于 Controller。
- Apollo 配置 key 的修改必须说明默认值和降级方案。

## 业务红线

### 积分操作
- 积分消耗/退还操作必须是**幂等**的。
- 分库分表查询必须包含 `subject_id` 分片键。
- 积分余额不能为负；扣减前必须校验余额充足。

### Kafka 消费
- Kafka Consumer 必须正确处理重复消息（幂等消费）。
- 消息体中必须包含 `subject_id` 用于分库分表路由。

### Dubbo RPC
- Dubbo 调用必须设置超时时间。
- 关键路径必须有 fallback 或降级处理。
- 接口新增参数必须有默认值。

### 数据安全
- 不得在日志中打印用户敏感信息（手机号、身份证）。
- 分库分表的分片键不得暴露给前端。

## 修改后最低验证

- `mvn compile` 通过。
- 受影响的类 import 正确、无循环依赖。
- 如果添加了新的 Mapper 方法，XML 同步更新。
- 如果修改了 Dubbo 接口，消费者端仍能编译。

## 禁止事项

- 未读现有代码就直接改。
- 跳过编译验证直接宣称完成。
- 把一次性决策写成永久规则。
- 为了让测试通过而删除业务约束。
- 在非目标分支上生成代码。
