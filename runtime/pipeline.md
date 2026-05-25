# Pipeline 定义

req-to-dev 的 9 阶段（含 1 个人工审批点）自动流转配置。

## 执行引擎

Pipeline 由 `run_workflow.py` 状态管理器驱动，Agent 按 SKILL.md 指令连续执行。

- **自动阶段**：完成后运行 `run_workflow.py advance` 推进，不暂停
- **阻塞阶段**：advance 返回 `BLOCKING`，等待人工运行 `run_workflow.py approve`
- **失败处理**：运行 `run_workflow.py fail --reason "..."`，按恢复策略重试或升级

## 阶段定义

| 阶段 | ID | Playbook | 输入 | 产出物（相对 changes/） | 自动流转 | 最大重试 |
|------|-----|----------|------|------------------------|----------|----------|
| PRD 拉取 | fetch-prd | feishu-doc-fetcher | 飞书 URL | request/prd.md | ✅ 自动 | 3 |
| 需求拆解 | break-down | requirement-breakdown | prd.md | request/spec.md + request/tasks.md | ✅ 自动 | 0 |
| 范围评估 | scope-eval | scope-evaluation | spec.md | impact/impact.md | ✅ 自动 | 0 |
| **人工审批** | plan-approve | — | spec + impact | — | 🔒 阻塞等人 | 0 |
| 技术方案 | tech-design | tech-design-generator | PRD + impact | tech-design/tech-design.md | ✅ 自动 | 0 |
| 编码 | coding | spring-boot-coding | tech-design.md | 代码 diff（目标项目） | ✅ 自动 | 3 |
| 审查 | review | review-checklist | 代码 diff | review/code_review_v1.md | ✅ 自动 | 2 |
| 测试验证 | test | test-authoring + checkpoints | 代码 diff | tests/test_report.md | ✅ 自动 | 3 |
| 发布验证 | release | release-validation | 全部产物 | deploy/verify.md | ✅ 自动 | 0 |

## 阶段依赖

```
fetch-prd → break-down → scope-eval → plan-approve → tech-design → coding → review → test → release
                                                              ↑
                                                        唯一人工审批点
```

## 可跳过条件

advance 时自动检测产出物，已存在则跳过：

| 阶段 | 跳过条件 |
|------|----------|
| fetch-prd | request/prd.md 已存在 |
| break-down | request/spec.md + request/tasks.md 已存在 |
| scope-eval | impact/impact.md 已存在 |
| plan-approve | **不可跳过** |
| tech-design | tech-design/tech-design.md 已存在 |

## 阶段加载的规范

每个阶段进入时，Agent 自动加载对应的规范资源。Knowledge 按目标项目加载：

| 阶段 | 加载 |
|------|------|
| break-down | knowledge/project-atlas |
| scope-eval | knowledge/{project}/component-graph, knowledge/{project}/data-layer |
| tech-design | knowledge/project-atlas, knowledge/{project}/*, knowledge/service-topology |
| coding | guardrails/layering-contracts, guardrails/ai-coding-spec, playbooks/spring-boot-coding |
| review | guardrails/*（全部 4 个）, playbooks/review-checklist |
| test | checkpoints, playbooks/test-authoring |
| release | playbooks/release-validation |

`{project}` 由 `run_workflow.py init --target` 自动检测：
- 路径含 `shop-points-lottery` → 加载 `knowledge/shop-points-lottery/*`
- 其他 → 加载 `knowledge/shop-points/*`
