---
name: scope-evaluation
description: "在编码前分析影响面时触发，追踪 Controller/Service/DAO/Mapper/Dubbo/Kafka 调用链"
version: "0.1.0"
category: harness
tags:
  - skill
  - analysis
  - impact
  - trace
commands: []
---

# Skill: 范围评估

## 关注面

- **入口**：HTTP Controller、Kafka Consumer、Dubbo Provider、Scheduled Task。
- **业务**：Service 层、策略模式、模板方法、责任链。
- **数据**：Mapper Interface、Mapper XML、分片策略、Domain 实体。
- **RPC**：Dubbo 接口、Proxy 类。
- **配置**：Apollo key、application.yml。
- **跨服务**：对 shop-points-lottery（或反之 shop-points）的影响。

## 步骤
1. 从入口开始画出调用链（Controller → Service → DAO → Mapper XML）。
2. 标注本次会修改和只读的文件。
3. 找出行为变化点和兼容性风险。
4. 为每个风险绑定验证方法（编译/测试/API验证/人工确认）。
5. 明确列出"不会做什么"，防止自行扩大范围。
6. 判断是否需要更新 Wiki 或 Rules。

## 产出
- `impact/impact.md`

模板结构：
```markdown
# Impact Analysis
## Entry Points
## Files To Change（含完整路径）
## Files To Read Only
## Behavior Changes
## Compatibility Risks
## Cross-Service Impact（如有）
## Won't Do
## Verification Plan
```

## 质量标准
- 不只列文件名；要说明为什么受影响。
- 至少包含"不会做什么"。
- 跨服务变更必须说明对端影响。
