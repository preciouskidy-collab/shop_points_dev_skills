---
name: skill-creator
description: "当需要创建新的 skill、验证 skill 格式或打包 skill 时触发"
version: "0.1.0"
category: common
tags:
  - meta
  - skill-creation
  - scaffold
commands: []
---

# Skill 创建器

创建和验证新 skill 的元工具，用于初始化 skill 目录结构、生成 SKILL.md 模板、验证 skill 格式。

## 适用场景

- 需要创建新的后端 skill 时
- 验证已有 skill 的格式是否正确时
- 打包 skill 以供分发时

## 使用方式

### 初始化新 Skill

```bash
python skills/common/skill-creator/scripts/init_skill.py <skill-name> --path skills/<category>/
```

初始化后的目录结构：

```
<skill-name>/
├── SKILL.md          # 自动生成的模板
├── scripts/          # 可执行脚本目录
├── references/       # 参考文档目录
├── assets/           # 资源文件目录
└── tests/            # 测试文件目录
```

### 验证 Skill

```bash
python skills/common/skill-creator/scripts/quick_validate.py skills/<category>/<skill-name>/
```

### 打包 Skill

```bash
python skills/common/skill-creator/scripts/package_skill.py skills/<category>/<skill-name>/ [output-dir]
```

## SKILL.md 模板格式

```yaml
---
name: <skill-name>
description: "触发描述，决定 AI 何时自动触发此 skill"
version: "0.1.0"
category: <backend|common|agents>
tags: []
commands: []
---
# <skill-name>
技能详细文档...
```

## 注意事项

- 创建 skill 后必须在 `skills.json` 中注册
- `description` 字段是 AI agent 自动检索的依据，需准确描述触发条件
- 类别必须是 backend、common、agents 之一