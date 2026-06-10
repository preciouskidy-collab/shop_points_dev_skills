# Pipeline 定义

req-to-dev 的 16 阶段（含 2 个人工审批点）自动流转配置。

## 阶段依赖与顺序 rationale

编码阶段遵循 **「后端 → FDH → 前端 → 审查 → 本地测」** 依赖链：

```
backend-coding          # 后端先落地，产出真实 API diff
    ↓
frontend-handoff (FDH)  # 基于后端代码 diff 生成交接文档（前端开发的唯一输入）
    ↓
frontend-coding         # 严格按 FDH 改前端
    ↓
backend-review          # 审查全部代码（后端 + 前端解耦后各自审查）
frontend-review
    ↓
backend-test-local      # 本地编译/接口快验（部署前兜底）
    ↓
[deploy-approve] → commit-push → dayu-deploy → e2e-browser-test → release
```

**为何 FDH 紧接后端编码、在审查之前？**

- FDH 内容来自**后端实际代码**（Controller/DTO），不是技术方案复印件
- 前端编码**依赖 FDH**，不应等后端审查/本地测完成才开始
- 审查与本地测在**前后端代码均完成后**统一执行，避免重复审查

## 执行引擎

Pipeline 由 `run_workflow.py` 状态管理器驱动，Agent 按 SKILL.md 指令连续执行。

- **自动阶段**：完成后运行 `run_workflow.py advance` 推进，不暂停
- **阻塞阶段**：advance 返回 `BLOCKING`，等待人工运行 `run_workflow.py approve`
- **条件跳过**：读取 `impact/impact.md` frontmatter（如 `frontend_scope: none`）
- **状态迁移**：`run_workflow.py` 加载 state 时自动与 `skills.json` 阶段顺序对齐

## 阶段定义

| # | 阶段 | ID | 自动流转 | 产出物（相对 changes/） | 最大重试 |
|---|------|----|----------|------------------------|----------|
| 1 | PRD 拉取 | fetch-prd | ✅ | request/prd.md | 3 |
| 2 | 需求拆解 | break-down | ✅ | request/spec.md + request/tasks.md | 0 |
| 3 | 范围评估 | scope-eval | ✅ | impact/impact.md | 0 |
| 4 | 技术方案 | tech-design | ✅ | tech-design/tech-design.md | 0 |
| 5 | **方案审批** | plan-approve | 🔒 | — | 0 |
| 6 | 后端编码 | backend-coding | ✅ | 后端代码 diff | 3 |
| 7 | **前端交接 FDH** | frontend-handoff | ✅ 可跳过 | handoff/frontend-handoff.md + handoff/api-contract.yaml | 2 |
| 8 | 前端编码 | frontend-coding | ✅ 可跳过 | 前端代码 diff | 3 |
| 9 | 后端审查 | backend-review | ✅ | review/backend_review_v1.md | 2 |
| 10 | 前端审查 | frontend-review | ✅ 可跳过 | review/frontend_review_v1.md | 2 |
| 11 | 本地验证 | backend-test-local | ✅ | tests/backend_test_report.md | 3 |
| 12 | **部署前审批** | deploy-approve | 🔒 必须人工 | — | 0 |
| 13 | 提交推送 | commit-push | ✅ | deploy/git_push_report.md | 2 |
| 14 | 大禹部署 | dayu-deploy | ✅ | deploy/dayu_deploy_report.md | 3 |
| 15 | E2E 浏览器自测 | e2e-browser-test | ✅ 可跳过 | tests/e2e_test_report.md | 3 |
| 16 | 发布验证 | release | ✅ | deploy/verify.md | 0 |

## 审批内容

### plan-approve

- request/spec.md + impact/impact.md + tech-design/tech-design.md

### deploy-approve（必须人工）

- 各仓库 git diff + handoff/frontend-handoff.md + deploy_modules + 审查报告

## 可跳过条件

| 阶段 | 跳过条件 |
|------|----------|
| frontend-handoff ~ frontend-review | `impact.frontend_scope = none` |
| e2e-browser-test | `impact.frontend_scope = none` |
| plan-approve / deploy-approve | **不可跳过** |

纯后端需求路径：`backend-coding` → 跳过 7/8/10/15 → `backend-review` → `backend-test-local` → …

## Git 分支规范（Step 0）

每个参与仓库：`git fetch origin && git checkout master && git pull origin master && git checkout -b feature/<name>`

## 部署顺序（dayu-deploy）

1. `shop-points`（如有）
2. `shop-points-lottery`（仅 `mall_scope != none`）
3. `store-integral-cdn` / `store-integral-h5-cdn`（按 surfaces）
