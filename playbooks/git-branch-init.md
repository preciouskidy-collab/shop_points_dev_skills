---
name: git-branch-init
description: "Pipeline 启动时为各目标仓库初始化 feature 分支：fetch → checkout master → pull → 新建分支"
version: "0.1.0"
category: playbooks
tags:
  - git
  - branch
  - workflow
commands: []
---

# Skill: Git 分支初始化

## 适用时机

- **Pipeline Step 0**：编码开始前，为所有参与仓库创建统一 feature 分支
- **commit-push 阶段**：push 前确认各仓在正确分支且已同步 master

## 原则

1. **每个参与仓库**独立执行，分支名统一为 `feature/<需求名称>`
2. **必须先同步最新 master**，再创建或切换 feature 分支
3. 工作区必须干净；有未提交变更则终止
4. **禁止**在 `master` / `release` 上直接编码

## 标准命令（每个仓库执行一遍）

```bash
REPO_PATH="<仓库绝对路径>"
BRANCH="feature/<需求名称>"

cd "$REPO_PATH"

# 1. 工作区检查
git status --porcelain
# 若有输出 → 终止，提示用户 commit 或 stash

# 2. 同步 master
git fetch origin
git checkout master
git pull origin master

# 3. 创建或切换 feature 分支
if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
  git checkout "$BRANCH"
  git merge origin/master --no-edit   # 可选：将 feature 分支追上最新 master
else
  git checkout -b "$BRANCH"
fi
```

## 参与仓库清单

根据 `pipeline_state.json` 的 `repos` 字段和 `impact/impact.md` 的 `deploy_modules` 决定涉及哪些仓库：

| 仓库路径 | 何时参与 |
|----------|----------|
| `/Users/qidi/IdeaProjects/shop-points` | 后端门店积分有改动 |
| `/Users/qidi/IdeaProjects/shop-points-lottery` | `mall_scope != none` |
| `/Users/qidi/IdeaProjects/store-integral` | PC 前端有改动 |
| `/Users/qidi/IdeaProjects/store-integral-h5` | H5 前端有改动 |

## 状态判定

| 当前状态 | 操作 |
|----------|------|
| 工作区不干净 | **终止 Pipeline** |
| 已在 `feature/<name>` 且基于最新 master | 继续 |
| 在 master 且工作区干净 | 执行标准命令创建分支 |
| 在其他分支 | 提示用户确认后执行标准命令 |

## 产出

- 无独立文件；在 `pipeline.log` 记录每个仓库的分支初始化结果
- `pipeline_state.json` 的 `repos.*.branch` 字段更新为 `feature/<name>`

## 质量标准

- 不跳过 `git pull origin master`
- 四个仓库分支名必须一致
- 不向用户询问是否 pull master——这是硬性步骤
