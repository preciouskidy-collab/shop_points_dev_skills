# Shop Points 后端 Skill 工具集

Shop Points 研发团队后端 AI 辅助技能工具集，为 Java/Spring Boot 后端开发提供代码生成、审查、重构、质量检测等能力。

## 安装与接入

### 第一步：克隆仓库

```bash
git clone https://git.lianjia.com/maochaochao001/shop_points_dev_skills.git
# 记住你克隆到的路径，例如：/Users/yourname/mcc/shop_points_dev_skills
```

无第三方依赖，所有 Python 脚本仅使用标准库，克隆即可用。

### 第二步：安装 Skills 到 Claude Code

Claude Code 的 `Skill` 工具只识别特定目录下的 SKILL.md：

| 位置 | 路径 | 作用域 |
|------|------|--------|
| 个人级 | `~/.claude/skills/<skill-name>/SKILL.md` | 你所有项目通用 |
| 项目级 | `<项目>/.claude/skills/<skill-name>/SKILL.md` | 仅当前项目 |

需要将本仓库的 skill 目录**复制或符号链接**到上述位置，Claude Code 才能通过 `/skill-name` 或自动匹配触发。

#### 方式 A：个人级安装（推荐）

所有项目都能使用，一条命令安装全部：

```bash
SKILLS_SRC="/Users/yourname/mcc/shop_points_dev_skills/skills"
SKILLS_DST="$HOME/.claude/skills"

# 创建目录（首次）
mkdir -p "$SKILLS_DST"

# 符号链接 skill
ln -sf "$SKILLS_SRC/req-to-dev" "$SKILLS_DST/req-to-dev"
ln -sf "$SKILLS_SRC/req-to-dev/sub_skills/feishu-doc-fetcher" "$SKILLS_DST/feishu-doc-fetcher"
ln -sf "$SKILLS_SRC/common/skill-creator" "$SKILLS_DST/skill-creator"
```

> **注意**：将 `SKILLS_SRC` 替换为你实际的克隆路径。

安装后**重启 Claude Code**（首次创建 `~/.claude/skills/` 需重启才能生效）。

#### 方式 B：项目级安装

仅在特定项目中使用，将 skill 链接到项目的 `.claude/skills/` 下：

```bash
cd /path/to/your-project
mkdir -p .claude/skills
ln -sf "/Users/yourname/mcc/shop_points_dev_skills/skills/req-to-dev" .claude/skills/req-to-dev
# ... 按需链接其他 skill
```

#### 方式 C：用 --add-dir 引入

启动 Claude Code 时指定额外目录，该目录下的 `.claude/skills/` 会被自动加载：

```bash
cd /path/to/your-project
claude --add-dir /Users/yourname/mcc/shop_points_dev_skills
```

此方式需本仓库内有 `.claude/skills/` 结构，当前暂不支持。

### 第三步：验证安装

在任意目录启动 Claude Code，输入：

```
/feishu-doc-fetcher
```

如果能看到技能内容加载，说明安装成功。也可用自然语言触发：

```
帮我获取这个飞书文档 https://beike.feishu.cn/wiki/xxx
```

Claude 匹配到 SKILL.md 的 `description` 字段后会自动执行对应技能。

### 飞书功能前置条件

使用飞书文档获取功能（feishu-doc-fetcher / req-to-dev），需完成以下配置：

1. **创建飞书应用**：在 [飞书开放平台](https://open.feishu.cn) 创建应用，获取 App ID 和 App Secret
2. **开通应用权限**：
   - `docx:document:readonly` — 读取文档内容
   - `wiki:wiki:readonly` — 读取知识库文档
   - `drive:drive:readonly` — 读取云文档
   - `im:resource` — 下载图片资源
3. **配置本地凭证**：首次运行会自动生成模板文件 `~/.shop-points-dev-skills/feishu-config.json`，填写 App ID 和 App Secret 即可
4. **知识库授权**（如需读取知识库文档）：在飞书开放平台将知识库授权给该应用

### 其他 AI IDE 接入

**Trae / Cursor**：将 Skills 仓库路径配置到 IDE 的项目指令/系统提示中，使 AI 能读取 SKILL.md 文件即可。

## Skill 目录

| 类别 | Skill | 版本 | 说明 |
|------|-------|------|------|
| **req-to-dev** | req-to-dev | 0.3.0 | 飞书 PRD → 需求拆解 → 编码 → 审查 → 测试 → 发布 端到端 Pipeline |
| **req-to-dev** | feishu-doc-fetcher | 0.3.0 | 飞书文档获取与转换 |
| **common** | skill-creator | 0.1.0 | 创建和验证新 skill 的元工具 |

## 使用方式

### 在 AI IDE 中触发 Skill

AI IDE（Claude Code、Trae、Cursor 等）通过匹配 SKILL.md 的 `description` 字段自动触发对应 skill。**你只需用自然语言描述意图，无需记忆特定命令格式。**

#### 各 Skill 触发示例

**req-to-dev（需求到开发 — 端到端 Pipeline）**

| 触发语句 | 说明 |
|---------|------|
| `帮我从这个飞书文档开发后端功能 https://beike.feishu.cn/wiki/xxx` | 完整端到端流程 |
| `从需求到代码的完整流程` | 完整端到端流程 |
| `按这个 PRD 开发后端` | 需配合飞书链接或 PRD 路径 |
| `端到端开发，项目名 xxx，目标路径 /path/to/project` | 指定项目和路径 |

需提供：飞书文档 URL、项目名称、目标项目路径（代码生成位置）。

**feishu-doc-fetcher（飞书文档获取器）**

| 触发语句 | 说明 |
|---------|------|
| `帮我获取这个飞书文档 https://beike.feishu.cn/wiki/xxx` | 单独获取飞书文档 |
| `读取这个飞书链接的内容` | 单独获取飞书文档 |
| `把飞书文档转成 Markdown` | 单独获取飞书文档 |

**skill-creator（Skill 创建器）**

| 触发语句 | 说明 |
|---------|------|
| `创建一个新的 skill` | 初始化 skill 目录结构 |
| `验证 skill 格式` | 检查 SKILL.md 合规性 |
| `打包 skill` | 打包分发 |

### req-to-dev Pipeline 详解

req-to-dev 是 9 阶段自动 Pipeline，仅在人工审批点暂停：

```
fetch-prd → break-down → scope-eval → [plan-approve] → tech-design → coding → review → test → release
```

**前置检查**：Pipeline 启动前自动检查 git 上下文（Step 0），确保：
- 不在 release/master 等受保护分支上生成代码
- 工作区干净（无未提交变更）
- 如需创建特性分支会提示用户确认

**全程只需做一件事**：在 plan-approve 检查点审批。

详细使用流程见 [docs/demo-sop.md](docs/demo-sop.md)。

### 通过命令行

```bash
# 列出所有 skills
python skills_loader.py list

# 查看 skill 详情
python skills_loader.py info <skill_id>

# 搜索 skills
python skills_loader.py search <关键词>

# 执行 skill 命令
python skills_loader.py exec <skill_id> <command> [args...]
```

## 产出目录结构

req-to-dev Pipeline 的产出放在 `changes/YYYYMMDD-req-<name>/` 下：

```
changes/YYYYMMDD-req-<name>/
├── pipeline.log              # 完整执行日志
├── pipeline_state.json       # Pipeline 状态
├── summary.md                # 变更摘要
├── request/
│   ├── prd.md                # PRD 原文
│   ├── spec.md               # 需求规格
│   └── tasks.md              # 任务拆分
├── impact/
│   └── impact.md             # 影响分析 + Won't Do
├── tech-design/
│   └── tech-design.md        # 技术方案
├── review/
│   └── code_review_v1.md     # 审查报告
├── tests/
│   └── test_report.md        # 测试报告
└── deploy/
    └── verify.md             # 发布验证
```

目标项目路径下是 Agent 生成的 Java 代码。

## 开发新 Skill

1. 在 `skills/<category>/` 下创建 skill 目录
2. 编写 `SKILL.md`（含 YAML frontmatter，`description` 字段决定 AI 何时触发此 skill）
3. 在 `skills.json` 中注册 skill 元数据
4. 按需添加 `scripts/`、`references/`、`tests/` 子目录

详见 [CLAUDE.md](CLAUDE.md) 中的开发工作流章节。

## 项目结构

```
shop_points_dev_skills/
├── CLAUDE.md                  # 架构说明和开发规范
├── README.md                  # 本文件
├── skills.json                # Skills 元数据注册表
├── skills_loader.py           # Skills 加载器
├── skills/                    # 可执行的 Skill
│   ├── config.js              # 类别定义
│   ├── req-to-dev/            # 需求到开发 Pipeline
│   │   ├── SKILL.md
│   │   ├── scripts/           # run_workflow.py + feishu_fetcher.py
│   │   ├── references/        # 模板和规范参考
│   │   └── sub_skills/
│   │       └── feishu-doc-fetcher/
│   └── common/
│       └── skill-creator/
├── guardrails/                # 编码守则（Pipeline 加载的资源）
├── knowledge/                 # 系统知识（按项目组织）
├── playbooks/                 # 操作手册（可复用 SOP）
├── runtime/                   # Agent Runtime（自动流转配置）
├── changes/                   # Pipeline 运行时产出（.gitignore）
├── checkpoints.md             # 验证命令
└── docs/
    └── demo-sop.md            # Demo 使用 SOP
```
