# Pipeline 定义

req-to-dev 的 **19 阶段**（含 **1 个人工审批点**：技术方案企微评审）自动流转配置。

## 阶段依赖与顺序 rationale（v0.6 协议先行 + 详设并行）

```
scope-eval
    ↓
api-contract              # 仅对外 API 协议草案（最窄腰）
    ↓
tech-design  ║  frontend-design   # 逻辑并行：后端详设 ║ 前端详设（均引用契约）
    ↓
[plan-approve] 🔒          # 技术方案评审（企微 phase=tech_design_review）
    ↓
backend-coding → frontend-coding → frontend-handoff（契约对齐）
    ↓
backend-review → frontend-review → backend-test-local
    ↓
local-stack-up → local-e2e-test          # 默认 integration_mode=local，Cursor 内置浏览器
    ↓
commit-push → dayu-deploy → e2e-browser-test → release
                                          # dayu/e2e 在 local 模式下跳过
```

**为何先 api-contract 再并行详设？**

- 协议是前后端唯一共同边界，应先于库表设计与 UI 细节定稿
- `tech-design` 专注架构/库表/类设计；`frontend-design` 专注页面/交互/E2E
- 单 Agent 仍顺序执行两阶段，但**互不依赖对方详设完成**，只依赖 `api-contract.yaml`

## Pipeline stage 与企微 phase 对照（必读）

| Pipeline `stages[].id` | `collaboration.phase` | 企微群消息标题 | 说明 |
|------------------------|----------------------|----------------|------|
| `plan-approve` | **`tech_design_review`** | **技术方案评审** · design-patch-NNN | `prepare` / `finalize-design` 后即 `push-state phase=tech_design_review`；**`push-preview` 发群时已是评审阶段**（不是发完才进入） |
| （PRD 定稿，链路1） | `prd_review` | PRD 修订预览 · patch-NNN | `collab-prd-sync`，非本 Pipeline 主路径 |

> **命名约定**：文档与脚本中的 `plan-approve` = 业务上的「技术方案评审」；与企微 `tech_design_review` **同义**，勿与「部署前审批」混淆（已取消）。

## 执行引擎

- **自动阶段**：`run_workflow.py advance`
- **唯一阻塞阶段**：`plan-approve`（技术方案企微评审）
- **条件跳过**：`frontend_scope`、`api_change` 等见下表
- **状态迁移**：`_sync_stages_with_config` 与 `skills.json` 对齐（已移除 `deploy-approve` 的旧 state 自动迁移至 `commit-push`）

## 阶段定义

| # | 阶段 | ID | 自动 | 产出物 | 重试 |
|---|------|----|------|--------|------|
| 1 | PRD 拉取 | fetch-prd | ✅ | request/prd.md | 3 |
| 2 | 需求拆解 | break-down | ✅ | spec.md + tasks.md | 0 |
| 3 | 范围评估 | scope-eval | ✅ | impact/impact.md | 0 |
| 4 | **API 协议** | api-contract | ✅ 可跳过 | handoff/api-contract.yaml | 0 |
| 5 | 后端技术方案 | tech-design | ✅ | tech-design/tech-design.md | 0 |
| 6 | 前端技术设计 | frontend-design | ✅ 可跳过 | tech-design/frontend-design.md | 0 |
| 7 | **技术方案评审** | plan-approve | 🔒 | — | 0 |
| 8–18 | 编码…release | （同 v0.6） | | | |

## plan-approve（技术方案评审）审批包

1. `request/spec.md` + `impact/impact.md`
2. **`handoff/api-contract.yaml`**（`api_change != none`）
3. **`tech-design/tech-design.md`**
4. **`tech-design/frontend-design.md`**（`frontend_scope != none`）

## 企微交互（必读）

1. `collab-tech-design-sync prepare` → `finalize-design` → **`push-preview`**（此时 `phase=tech_design_review`，群消息为 **技术方案评审**）
2. **同一 Cursor 回合内阻塞 `wait --timeout 3600`**
3. 确认：`确认 design-patch-NNN <nonce> approver <姓名>` → `plan_approve` → `approve-design`
4. 修订：文字说明 → 企微 **`/整理方案`** → `tech_revise` → `tech-revise` → 再 preview → 再 wait

**禁止**技术方案阶段使用 `/整理评审`。详见 `playbooks/wecom-collab-review.md`。

**wait 红线（R2.2）**：阻塞 wait **禁止** `--action` 过滤；`/整理评审`、`/整理方案` **允许多次**，每次修订 intent 须在同一回合走完整修订循环。

## 可跳过条件

| 阶段 | 跳过条件 |
|------|----------|
| api-contract | `api_change = none` |
| frontend-design ~ frontend-review、e2e | `frontend_scope = none` |
| plan-approve | 不可跳过 |
| dayu-deploy / e2e-browser-test | `integration_mode = local` |

纯后端：`scope-eval` → 跳过 api-contract（若 none）→ tech-design → plan-approve → backend-coding → …

## Git / 部署

- **无部署前人工审批**：`local-e2e-test` 通过后 `advance` 直接进入 `commit-push`
- 大禹部署仅当 `integration_mode=dayu` 且用户明确要求
