---
name: req-to-dev
description: "从飞书 PRD 到全栈开发、大禹部署、AgentBrowser E2E 自测的端到端 Pipeline。两个人工审批点：plan-approve、deploy-approve"
version: "0.4.0"
category: req-to-dev
tags:
  - workflow
  - orchestration
  - backend
  - frontend
  - fullstack
  - feishu
  - e2e
  - auto-pipeline
commands: []
---

# req-to-dev — 全栈自动化 Pipeline

从飞书 PRD 到可交付代码 + 测试环境部署 + 页面 E2E 验证。**Agent 连续执行，仅在两个人工审批点暂停。**

## 触发时机

- 提供飞书文档链接并要求端到端开发（含前端）
- "按这个 PRD 全栈开发"
- "飞书 PRD → 后端 → 前端 → 部署测试环境 → 页面自测"

## 输入

- **必需**：飞书文档 URL
- **必需**：需求名称（如 `vip-points`，用于 `feature/<name>` 分支和 change 目录）
- **必需**：后端目标路径（如 `/Users/qidi/IdeaProjects/shop-points`）
- **可选**：`--frontend-pc`（默认 `/Users/qidi/IdeaProjects/store-integral`）
- **可选**：`--frontend-h5`（默认 `/Users/qidi/IdeaProjects/store-integral-h5`）
- **可选**：`--surfaces h5,pc`
- **可选**：飞书 app-id / app-secret
- **必需（部署/E2E 前）**：复制 `skills/req-to-dev/config/secrets.local.json.example` 为 `secrets.local.json` 并填写凭证

## 执行模式

```
fetch-prd → break-down → scope-eval → tech-design
    → [plan-approve] 🔒
    → backend-coding
    → frontend-handoff (FDH) → frontend-coding   ← 前端依赖 FDH
    → backend-review → frontend-review → backend-test-local
    → [deploy-approve] 🔒
    → commit-push → dayu-deploy → e2e-browser-test → release
```

**编码链依赖**：后端落地 → 基于后端 diff 出 FDH → 前端按 FDH 开发 → 统一审查与本地测。

- **两个人工审批点**：`plan-approve`（进入编码）、`deploy-approve`（进入 push + 部署，**必须人工**）
- **条件跳过**：`impact.md` 中 `frontend_scope: none` 时跳过前端交接/编码/审查/E2E
- **浏览器工具**：本地 `agent-browser` CLI（非 Cursor Browser MCP）

## 执行流程

### Step 0：初始化 Pipeline + Git 分支

#### 0.1 多仓 Git 分支初始化（强制）

对 **所有参与仓库** 执行（Playbook: `git-branch-init`）：

```bash
git fetch origin
git checkout master
git pull origin master
git checkout -b feature/<name>   # 已存在则 checkout 已有分支
```

| 仓库 | 默认路径 | 何时参与 |
|------|----------|----------|
| shop-points | `/Users/qidi/IdeaProjects/shop-points` | 后端门店积分改动 |
| shop-points-lottery | `/Users/qidi/IdeaProjects/shop-points-lottery` | `mall_scope != none` |
| store-integral | `/Users/qidi/IdeaProjects/store-integral` | PC 前端改动 |
| store-integral-h5 | `/Users/qidi/IdeaProjects/store-integral-h5` | H5 前端改动 |

| 当前状态 | 操作 |
|----------|------|
| 工作区不干净 | **终止流程** |
| 已在 `feature/<name>` | 继续（建议仍 pull master） |
| 其他 | 执行上述标准命令 |

**绝不在 master/release 或有未提交变更时编码。**

#### 0.2 初始化 Pipeline 状态

```bash
cd <shop_points_dev_skills 根目录>
python3 skills/req-to-dev/scripts/run_workflow.py init \
  --url "<飞书URL>" \
  --name "<需求名称>" \
  --target "/Users/qidi/IdeaProjects/shop-points" \
  --frontend-pc "/Users/qidi/IdeaProjects/store-integral" \
  --frontend-h5 "/Users/qidi/IdeaProjects/store-integral-h5" \
  --surfaces "h5,pc"
```

### Step 1–4：分析阶段（自动）

`fetch-prd`（加载 **feishu-doc-fetcher** Skill，lark-cli 拉 PRD）→ `break-down` → `scope-eval` → `tech-design`

**scope-eval 额外要求**：`impact/impact.md` 必须含 YAML frontmatter（`frontend_scope`、`mall_scope`、`surfaces`、`deploy_modules`），见 `playbooks/scope-evaluation.md`。

### 侧车：collab-prd-sync

**自然语言触发**：`整理联调消息写回 PRD` = 群消息→摘要→对照 PRD 找出入→dry-run→**人工确认后**才写 PRD（见 `sub_skills/collab-prd-sync/SKILL.md`）。

| 阶段 | 链路 | 命令 | req_id |
|------|------|------|--------|
| PRD 定稿（init 前） | 会议纪要 → PRD | `meeting` → `approve --prd-url` | ❌ |
| 开发立项 | — | `run_workflow init` | ✅ 产生 |
| 编码联调 | 企微群 → PRD | `digest` → `approve --req-id` → `resync` | ✅ |

详见 `skills/req-to-dev/sub_skills/collab-prd-sync/SKILL.md`。

### Step 5：plan-approve 🔒

展示 `spec.md` + `impact.md` + `tech-design.md`，等待人工批准。

- 批准 → `approve`
- 驳回 → `reject --reason "..."` → 回退 scope-eval

### Step 6：backend-coding（自动）

Playbook: `spring-boot-coding`。产出后端代码 diff，`mvn compile` 通过。

### Step 7：frontend-handoff / FDH（自动，可跳过）

**紧接后端编码**，不等待审查/本地测。

1. 加载 `playbook-frontend-handoff` + `knowledge-frontend-atlas`
2. 扫描后端 **实际代码 diff**（Controller/DTO），生成：
   - `handoff/frontend-handoff.md`
   - `handoff/api-contract.yaml`
3. 模板：`skills/req-to-dev/references/fdh-template.md`

### Step 8：frontend-coding（自动，可跳过）

**必须读取 FDH**。改 `store-integral/client/` 或 `store-integral-h5/client-integral/`，`npm run build` 通过。

### Step 9–11：审查与本地测（自动）

| 阶段 ID | Playbook | 产出 |
|---------|----------|------|
| `backend-review` | review-checklist | `review/backend_review_v1.md` |
| `frontend-review` | frontend-review-checklist | `review/frontend_review_v1.md`（可跳过） |
| `backend-test-local` | test-authoring | `tests/backend_test_report.md` |

本地接口测试用 `http://local.ttb.test.ke.com` + curl；最终页面验收在 `e2e-browser-test`。

### Step 12：deploy-approve 🔒（必须人工）

展示各仓 diff 摘要 + FDH + deploy_modules + 审查报告。

```
📋 部署前审批：
  1. 各仓库变更摘要
  2. handoff/frontend-handoff.md（如有前端）
  3. impact.md → deploy_modules
  4. 审查报告

❓ 是否批准 commit-push 并部署测试环境？
```

- 批准 → `approve` → commit-push
- **不可自动跳过**

### Step 13：commit-push（自动）

Playbook: `commit-push`。多仓 commit + push `feature/<name>`，产出 `deploy/git_push_report.md`。

### Step 14：dayu-deploy（自动，AgentBrowser）

Playbook: `dayu-deploy` + `knowledge/dayu-platform`。

```bash
export AGENT_BROWSER_EXECUTABLE_PATH="$HOME/.agent-browser/browsers/chrome-149.0.7827.55/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"
export AGENT_BROWSER_HEADED=1
export AGENT_BROWSER_SESSION_NAME="req-to-dev-<name>"

agent-browser open "https://dayu.ke.com/env/module?name=shop-points-test01" \
  && agent-browser wait --load networkidle \
  && agent-browser snapshot -i
```

按 `deploy_modules` 顺序部署，刷新后「运行中」标签仍存在才算成功。产出 `deploy/dayu_deploy_report.md`。

### Step 15：e2e-browser-test（自动，可跳过）

Playbook: `e2e-browser-test` + `knowledge/test-env-topology`。

按 FDH §6 / `api-contract.yaml` 的 `e2e_cases` 在测试环境页面执行。产出 `tests/e2e_test_report.md`。

### Step 16：release（自动）

Playbook: `release-validation`。产出 `deploy/verify.md`。

## 产出目录结构

```
changes/YYYYMMDD-req-<name>/
├── pipeline_state.json
├── request/          # prd, spec, tasks
├── impact/           # impact.md（含 YAML frontmatter）
├── tech-design/
├── handoff/          # frontend-handoff.md, api-contract.yaml
├── review/           # backend_review_v1.md, frontend_review_v1.md
├── tests/            # backend_test_report.md, e2e_test_report.md
└── deploy/           # git_push_report.md, dayu_deploy_report.md, verify.md
```

## 资源加载

```bash
python3 skills_loader.py context --stage <stage_id> --project <project>
python3 skills_loader.py check
```

## 恢复中断的 Pipeline

1. `python3 run_workflow.py status --name <name>`
2. 从当前阶段继续；已完成阶段自动跳过
