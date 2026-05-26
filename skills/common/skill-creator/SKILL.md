---
name: skill-creator
description: "当需要创建新的 skill、验证 skill 格式或更新 skill 注册时触发"
version: "0.2.0"
category: common
tags:
  - meta
  - skill-creation
  - scaffold
commands: []
---

# Skill 创建器

创建和验证新 skill 的元工具。确保新 skill 的目录结构、SKILL.md 格式、skills.json 注册三方面保持一致。

## 适用场景

- 需要创建新的 skill 时
- 验证已有 skill 的格式和注册是否正确时
- 更新 skill 版本或元信息时

## 类别体系

skill 类别对应 `skills.json` 中的 `category` 字段，当前有效值：

| 类别 | 用途 | 目录位置 |
|------|------|----------|
| `common` | 元工具、通用资源 | `skills/common/` |
| `req-to-dev` | Pipeline 主流程及子技能 | `skills/req-to-dev/` |
| `guardrails` | 编码守则（硬性约束） | `guardrails/` |
| `knowledge` | 系统知识（按项目组织） | `knowledge/` |
| `playbooks` | 操作手册（可复用 SOP） | `playbooks/` |
| `runtime` | Agent Runtime 配置 | `runtime/` |

## 创建新 Skill 的流程

### Step 1：确定类别和目录

根据上面的类别表，选择合适的 `category` 和对应目录。

### Step 2：创建目录结构

```
skills/<category>/<skill-name>/
├── SKILL.md          # 必需：skill 入口文档
├── scripts/          # 可选：可执行脚本
├── references/       # 可选：参考文档
├── sub_skills/       # 可选：子技能（如 feishu-doc-fetcher）
└── tests/            # 可选：测试文件
```

对于 guardrails / knowledge / playbooks / runtime 类别，通常是单个 `.md` 文件，不需要创建子目录。

### Step 3：编写 SKILL.md

#### Frontmatter 格式

```yaml
---
name: <skill-name>
description: "<一句话触发描述，决定 AI 何时自动触发此 skill>"
version: "0.1.0"
category: <common | req-to-dev | guardrails | knowledge | playbooks | runtime>
tags:
  - <tag1>
  - <tag2>
commands: []
---
```

#### 正文结构（参考模板）

```markdown
# <skill-name>

<一段话说明此 skill 做什么>

## 触发时机

- <触发场景 1>
- <触发场景 2>

## 输入

- **必需**：<必填参数>
- **可选**：<可选参数>

## 执行流程

### Step 1：<阶段名>

<具体步骤>

### Step 2：<阶段名>

<具体步骤>

## 产出

<列出此 skill 的产出物>

## 异常处理

| 场景 | 处理 |
|------|------|
| <异常情况> | <处理方式> |
```

可参考 `skills/req-to-dev/SKILL.md` 作为完整示例。

### Step 4：在 skills.json 中注册

在 `skills.json` 的 `skills` 数组中添加条目：

```json
{
  "id": "<skill-name>",
  "name": "<显示名称>",
  "description": "<与 SKILL.md description 一致的触发描述>",
  "version": "0.1.0",
  "category": "<category>",
  "tags": ["<tag1>", "<tag2>"],
  "entry": "<相对于项目根目录的路径>"
}
```

如果 skill 需要在 Pipeline 某阶段加载，还需要在 `pipeline.stages[].resources` 中添加对应的 resource ID。

### Step 5：校验

```bash
# 校验所有注册资源的文件存在性和引用完整性
python3 skills_loader.py check

# 查看新 skill 是否正确注册
python3 skills_loader.py info <skill-name>
```

## 注意事项

- `description` 字段是 AI agent 自动检索的依据，需准确描述触发条件
- `entry` 路径必须相对于项目根目录，且指向实际存在的文件
- Pipeline resource 中支持 `${project}` 模板变量，运行时由 `skills_loader.py` 替换为实际项目名
- 版本号遵循语义化版本（MAJOR.MINOR.PATCH），重大变更升 MAJOR
