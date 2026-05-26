# Pipeline 定义

req-to-dev 的 9 阶段（含 1 个人工审批点）自动流转配置。

## 执行引擎

Pipeline 由 `run_workflow.py` 状态管理器驱动，Agent 按 SKILL.md 指令连续执行。

- **自动阶段**：完成后运行 `run_workflow.py advance` 推进，不暂停
- **阻塞阶段**：advance 返回 `BLOCKING`，等待人工运行 `run_workflow.py approve`
- **失败处理**：运行 `run_workflow.py fail --reason "..."`，按恢复策略重试或升级

## 阶段定义

| # | 阶段 | ID | 自动流转 | 产出物（相对 changes/） | 最大重试 |
|---|------|----|----------|------------------------|----------|
| 1 | PRD 拉取 | fetch-prd | ✅ 自动 | request/prd.md | 3 |
| 2 | 需求拆解 | break-down | ✅ 自动 | request/spec.md + request/tasks.md | 0 |
| 3 | 范围评估 | scope-eval | ✅ 自动 | impact/impact.md | 0 |
| 4 | 技术方案 | tech-design | ✅ 自动 | tech-design/tech-design.md | 0 |
| 5 | **人工审批** | plan-approve | 🔒 阻塞等人 | — | 0 |
| 6 | 编码 | coding | ✅ 自动 | 代码 diff（目标项目） | 3 |
| 7 | 审查 | review | ✅ 自动 | review/code_review_v1.md | 2 |
| 8 | 测试验证 | test | ✅ 自动 | tests/test_report.md | 3 |
| 9 | 发布验证 | release | ✅ 自动 | deploy/verify.md | 0 |

## 阶段依赖

```
fetch-prd → break-down → scope-eval → tech-design → [plan-approve] → coding → review → test → release
                                                 ↑              ↑
                                           自动生成方案    唯一人工审批点
                                                          ┌─ 通过 → coding
                                                          └─ 驳回 → 回退 scope-eval 重新执行
```

## 审批内容

plan-approve 阶段向用户展示三件套：

```
📋 审批内容：
  1. request/spec.md              — 需求摘要
  2. impact/impact.md             — 影响范围 + Won't Do 列表
  3. tech-design/tech-design.md   — 技术方案

❓ 是否批准进入编码阶段？
```

- 用户批准 → `approve` → 自动推进到 coding
- 用户修改意见 → `reject --reason "..."` → 回退到 scope-eval 重新执行 scope-eval → tech-design
- 用户拒绝 → 终止 Pipeline

## 可跳过条件

advance 时自动检测产出物，已存在则跳过：

| 阶段 | 跳过条件 |
|------|----------|
| fetch-prd | request/prd.md 已存在 |
| break-down | request/spec.md + request/tasks.md 已存在 |
| scope-eval | impact/impact.md 已存在 |
| tech-design | tech-design/tech-design.md 已存在 |
| plan-approve | **不可跳过** |

## 阶段加载的规范

阶段资源映射由 `skills.json`（pipeline.stages）统一定义，通过 `skills_loader.py` 解析和加载：

```bash
# 查看某阶段的资源文件路径
python3 skills_loader.py resolve --stage <stage_id> --project <project>

# 一步输出某阶段全部资源内容
python3 skills_loader.py context --stage <stage_id> --project <project>
```

各阶段加载的资源：

| 阶段 | 加载的资源 |
|------|-----------|
| break-down | knowledge-project-atlas |
| scope-eval | knowledge-component-graph-${project}, knowledge-data-layer-${project} |
| tech-design | knowledge-project-atlas, knowledge-component-graph-${project}, knowledge-data-layer-${project}, knowledge-message-bus-${project}, knowledge-rpc-contracts-${project}, knowledge-service-topology |
| coding | guardrail-layering-contracts, guardrail-ai-coding-spec, playbook-spring-boot-coding |
| review | guardrail-layering-contracts, guardrail-build-standards, guardrail-traceability-rules, guardrail-ai-coding-spec, playbook-review-checklist |
| test | guardrail-build-standards, playbook-test-authoring |
| release | playbook-release-validation |

修改资源映射只需编辑 `skills.json`，无需同步多个文件。
