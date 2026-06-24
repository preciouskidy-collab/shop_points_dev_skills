# Pipeline 定义

req-to-dev 的 **18 阶段**（含 2 个人工审批点）自动流转配置。

## 阶段依赖与顺序 rationale（v0.6 协议先行 + 详设并行）

```
scope-eval
    ↓
api-contract              # 仅对外 API 协议草案（最窄腰）
    ↓
tech-design  ║  frontend-design   # 逻辑并行：后端详设 ║ 前端详设（均引用契约）
    ↓
[plan-approve] 🔒          # 审协议 + 后端方案 + 前端方案，冻结契约
    ↓
backend-coding → frontend-coding → frontend-handoff（契约对齐）
    ↓
backend-review → frontend-review → backend-test-local
    ↓
[deploy-approve] → commit-push → dayu-deploy → e2e-browser-test → release
```

**为何先 api-contract 再并行详设？**

- 协议是前后端唯一共同边界，应先于库表设计与 UI 细节定稿
- `tech-design` 专注架构/库表/类设计；`frontend-design` 专注页面/交互/E2E
- 单 Agent 仍顺序执行两阶段，但**互不依赖对方详设完成**，只依赖 `api-contract.yaml`

## 执行引擎

- **自动阶段**：`run_workflow.py advance`
- **阻塞阶段**：`plan-approve`、`deploy-approve`
- **条件跳过**：`frontend_scope`、`api_change` 等见下表
- **状态迁移**：`_sync_stages_with_config` 与 `skills.json` 对齐

## 阶段定义

| # | 阶段 | ID | 自动 | 产出物 | 重试 |
|---|------|----|------|--------|------|
| 1 | PRD 拉取 | fetch-prd | ✅ | request/prd.md | 3 |
| 2 | 需求拆解 | break-down | ✅ | spec.md + tasks.md | 0 |
| 3 | 范围评估 | scope-eval | ✅ | impact/impact.md | 0 |
| 4 | **API 协议** | api-contract | ✅ 可跳过 | handoff/api-contract.yaml | 0 |
| 5 | 后端技术方案 | tech-design | ✅ | tech-design/tech-design.md | 0 |
| 6 | 前端技术设计 | frontend-design | ✅ 可跳过 | tech-design/frontend-design.md | 0 |
| 7 | **方案审批** | plan-approve | 🔒 | — | 0 |
| 8 | 后端编码 | backend-coding | ✅ | 后端 diff | 3 |
| 9 | 前端编码 | frontend-coding | ✅ 可跳过 | 前端 diff | 3 |
| 10 | 契约对齐 | frontend-handoff | ✅ 可跳过 | frontend-handoff.md + contract-verify-report.md | 2 |
| 11–18 | 审查…release | （同 v0.5） | | | |

## plan-approve 审批包

1. `request/spec.md` + `impact/impact.md`
2. **`handoff/api-contract.yaml`**（`api_change != none`）
3. **`tech-design/tech-design.md`**
4. **`tech-design/frontend-design.md`**（`frontend_scope != none`）

## 可跳过条件

| 阶段 | 跳过条件 |
|------|----------|
| api-contract | `api_change = none` |
| frontend-design ~ frontend-review、e2e | `frontend_scope = none` |
| plan-approve / deploy-approve | 不可跳过 |

纯后端：`scope-eval` → 跳过 api-contract（若 none）→ tech-design → plan-approve → backend-coding → …

## Git / 部署

同 v0.5（见原文 Git 分支规范、dayu-deploy 顺序）。
