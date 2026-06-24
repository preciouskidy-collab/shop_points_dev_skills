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
6. 判断是否需要更新 knowledge 或 guardrails。

## 产出
- `impact/impact.md`

模板结构（**YAML frontmatter 必填**，供 `run_workflow.py` 解析阶段跳过与部署顺序）：

```markdown
---
frontend_scope: full | partial | none
api_change: none | extend | new
mall_scope: full | partial | none
surfaces: [h5, pc]
deploy_modules:
  - shop-points
  # - shop-points-lottery      # 仅 mall_scope != none 时加入
  # - store-integral-cdn       # PC 有前端改动时
  # - store-integral-h5-cdn    # H5 有前端改动时
---

# Impact Analysis
## Entry Points
## Files To Change（含完整路径）
## Files To Read Only
## Behavior Changes
## Compatibility Risks
## Cross-Service Impact（如有）
## Frontend Impact
- surfaces: h5 / pc / both / none
- 涉及页面/路由
- 涉及文件（PC: store-integral/client/...，H5: store-integral-h5/client-integral/...）
## Mall Impact（商城）
- 是否涉及积分商城（商品/订单/抽奖/兑换）
- mall_scope 判定依据
## Won't Do
## Verification Plan
```

### frontmatter 字段说明

| 字段 | 取值 | 说明 |
|------|------|------|
| `frontend_scope` | `full` / `partial` / `none` | `none` 时跳过前端编码、契约对齐、审查、E2E |
| `api_change` | `none` / `extend` / `new` | `none` 时跳过 `api-contract` 阶段 |
| `mall_scope` | `full` / `partial` / `none` | `none` 时 `deploy_modules` 不含 lottery |
| `surfaces` | `[h5]`, `[pc]`, `[h5, pc]` | 涉及的前端端 |
| `deploy_modules` | 大禹模块名列表 | 决定 dayu-deploy 部署哪些项目 |

## 质量标准
- 不只列文件名；要说明为什么受影响。
- 至少包含"不会做什么"。
- 跨服务变更必须说明对端影响。
