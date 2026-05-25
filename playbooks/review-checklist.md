---
name: review-checklist
description: "审查 Java 代码变更时触发，按优先级检查行为、分层、事务、Mapper、异常处理"
version: "0.1.0"
category: harness
tags:
  - skill
  - review
  - code-quality
  - java
commands: []
---

# Skill: 审查清单

## 审查顺序

1. **行为是否满足 spec**：变更后的行为是否与 spec 描述一致。
2. **是否破坏分层边界**：Controller 是否直接访问 DAO/RPC；Service 是否被 RPC 反向依赖。
3. **事务是否正确**：@Transactional 是否在 Service 层；事务范围是否过大或过小。
4. **Mapper 是否匹配**：XML namespace 是否与 Interface 全限定名一致；resultType 是否指向存在的类。
5. **异常处理是否完整**：是否处理了空值、缺失字段、超时、重试边界。
6. **分片查询是否安全**：分库分表查询是否包含分片键。
7. **是否需要测试**：新增/修改的业务逻辑是否有对应测试。
8. **是否需要更新 Wiki/Change**：系统事实是否因本次变更而改变。

## 输出格式

按严重程度输出：

- **MUST FIX**：功能错误、线上风险、数据不一致、验证失效。
- **SHOULD FIX**：质量问题、可维护性风险、缺少降级。
- **INFO**：建议或后续优化。

每条问题必须包含：
- 文件路径（精确到行号）
- 问题描述
- 建议修复方式
- 验证方式

## 质量标准
- 评审者不替实现者辩护。
- 没有发现问题时，也要说明剩余测试缺口。
