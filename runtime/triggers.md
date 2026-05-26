# 触发规则

定义何时自动启动 req-to-dev Pipeline。

## 触发方式

| 方式 | 条件 | 动作 |
|------|------|------|
| **Skill 触发** | 用户在 Claude Code 中调用 `/req-to-dev` 或描述端到端开发需求 | 立即启动 |

触发关键词：
- "帮我从这个飞书文档开发后端功能"
- "从需求到代码的完整流程"
- "按这个 PRD 开发后端"
- 提供飞书文档链接并要求端到端开发

## 必需输入

| 参数 | 说明 | 示例 |
|------|------|------|
| 飞书文档 URL | PRD 来源 | `https://bytedance.larkoffice.com/docx/xxx` |
| 需求名称 | change 目录命名 | `vip-points` |
| 目标项目路径 | 源码仓库本地路径 | `/Users/qidi/IdeaProjects/shop-points` |

可选输入：
- 飞书 app-id / app-secret（首次使用时由 feishu-doc-fetcher 引导输入）

## 触发后动作

### Step 0：前置检查

1. **Git 上下文检查**（在目标项目路径下）:
   - 工作区不干净 → 提示 commit 或 stash，**终止**
   - 不在目标分支 → 提示创建 `feature/<name>` 分支

2. **初始化 Pipeline**:
   ```bash
   cd <shop_points_dev_skills 根目录>
   python3 skills/req-to-dev/scripts/run_workflow.py init \
     --url "<飞书URL>" \
     --name "<需求名称>" \
     --target "<目标项目路径>"
   ```

3. 确认输出包含 "Pipeline 已初始化" 后进入 fetch-prd

### 产出目录

```
changes/YYYYMMDD-req-<name>/
├── pipeline_state.json          # Pipeline 状态（自动维护）
├── summary.md                   # 变更摘要（完成时生成）
├── request/                     # ← fetch-prd + break-down 产出
├── impact/                      # ← scope-eval 产出
├── tech-design/                 # ← tech-design 产出
├── review/                      # ← review 产出
├── tests/                       # ← test 产出
└── deploy/                      # ← release 产出
```
