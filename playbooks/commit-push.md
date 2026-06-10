---
name: commit-push
description: "多仓库统一 commit message 规范，按依赖顺序 push feature 分支到远程"
version: "0.1.0"
category: playbooks
tags:
  - git
  - commit
  - push
commands: []
---

# Skill: 多仓 Commit & Push

## 适用时机

`deploy-approve` 人工审批通过后，**部署前**执行。

## 前置条件

- `deploy-approve` 已通过
- 各仓库代码已审查完成，工作区有未提交变更

## Commit Message 规范

```
feat(<scope>): <简短描述>

Change: <change-id>
Refs: request/spec.md

- <变更点1>
- <变更点2>
```

`<scope>` 取值：`shop-points` | `shop-points-lottery` | `store-integral-pc` | `store-integral-h5`

### 前端项目 commit 前缀（H5 / PC）

前端仓库（`store-integral` / `store-integral-h5`）commit 必须以 **`[紧急]`** 开头，否则会被 GL-HOOK 拒推（`没有关联对应的KeOnes ID`）。

格式示例：

```
[紧急] feat(store-integral-h5): 混合支付服务基金余额为0时红字提示+过滤

Change: 20260609-req-lottery-wiki-ckfd
Refs: request/spec.md

- ...
```

> 历史可见两种合法前缀：
> - **`[紧急]`** — 通用（推荐用于需求/缺陷修复）
> - **`[需求][<数字ID>]`** — 已绑定 KeOnes 工单时使用（例：`[需求][50540338]M5W2...`）

## 步骤（每个有改动的仓库）

```bash
cd <repo_path>
git status
git add <changed_files>    # 不要 git add -A 盲目全加
git commit -m "$(cat <<'EOF'
feat(shop-points): xxx

Change: 20250609-req-vip-points
Refs: request/spec.md

- 新增 xxx 接口
EOF
)"
git push -u origin feature/<name>
```

## Push 顺序

与部署顺序一致（后端先于前端）：

1. `shop-points`
2. `shop-points-lottery`（如有）
3. `store-integral`（PC）
4. `store-integral-h5`（H5）

## ⚠️ 不要合并到 master

测试环境（test01）由 Dayu **直接使用推送的 `feature/<name>` 分支**部署（见 `knowledge/dayu-platform.md`）。

- **不要**在 commit-push 阶段 merge 到 master
- **不要**创建 MR 后再 deploy
- **不要**在 dayu-deploy 之前等 MR 合入

只有当需求需要发布到**生产环境**时，才走「合 master → 切 release → 部署 prod」流程（与 test env 完全独立）。

## 产出

`deploy/git_push_report.md`：

```markdown
# Git Push Report

> ⚠️ 测试环境部署使用以下 feature 分支，**不合并 master**。Dayu 部署时直接选择该分支。

| 仓库 | 分支 | Commit | Push 状态 | Dayu 部署分支 |
|------|------|--------|-----------|---------------|
| shop-points-lottery | feature/lottery-wiki-ckfd | e2b23dce | ✅ | feature/lottery-wiki-ckfd |
| store-integral-h5 | feature/lottery-wiki-ckfd | f310d1ce | ✅ | feature/lottery-wiki-ckfd |
```

## 质量标准

- 不 push 到 master / release
- 四个仓库分支名一致
- push 失败时不继续 dayu-deploy，先解决冲突
