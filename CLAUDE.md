# CLAUDE.md

本文件为 Claude Code 在此仓库中编码时提供架构说明、脚本命令和开发规范。

> 📋 **完整 Skills 目录** → 见 [README.md](README.md)

---

## 项目概述

Shop Points 后端 Skill 工具集，为 Shop Points 研发团队提供 AI 辅助编码能力。核心入口是 **req-to-dev** — 一条命令完成飞书 PRD 拉取到编码验证的全流程。Guardrails（约束）、Knowledge（知识）、Playbooks（操作手册）为流程中各阶段提供工程规范支撑。

## 目录结构

```
shop_points_dev_skills/
├── CLAUDE.md                  # 本文件
├── README.md                  # 项目说明
├── skills.json                # 资源注册 + Pipeline stage 映射（Single Source of Truth）
├── skills_loader.py           # 资源解析器（resolve / context / check）
├── .claude/skills/             # Claude Code 原生 skill 目录
│   └── req-to-dev/
│       └── SKILL.md           #   主入口（Claude Code 自动发现）
├── skills/                    # Skill 执行资源
│   ├── config.js              #   类别定义
│   ├── req-to-dev/            #   主流程：飞书 PRD → 需求 → 编码 → 验证
│   │   ├── SKILL.md           #     详细执行指令
│   │   ├── scripts/           #     run_workflow.py + feishu_fetcher.py
│   │   ├── references/        #     tech-design-template / coding-standards
│   │   └── sub_skills/
│   │       └── feishu-doc-fetcher/
│   └── common/                #   元工具
│       └── skill-creator/
├── guardrails/                # 编码守则（硬性约束，Pipeline 加载的资源）
│   ├── layering-contracts.md
│   ├── build-standards.md
│   ├── traceability-rules.md
│   └── ai-coding-spec.md
├── knowledge/                 # 系统知识（按项目组织）
│   ├── shop-points/           #   shop-points 专属
│   ├── shop-points-lottery/   #   shop-points-lottery 专属
│   ├── project-atlas.md       #   两个项目全景概览
│   └── service-topology.md    #   跨服务交互（Dubbo + Kafka）
├── playbooks/                 # 操作手册（可复用 SOP）
│   ├── requirement-breakdown.md
│   ├── scope-evaluation.md
│   ├── spring-boot-coding.md
│   ├── review-checklist.md
│   ├── test-authoring.md
│   ├── checkpoints.md
│   └── release-validation.md
├── runtime/                   # Agent Runtime（自动流转配置）
│   ├── pipeline.md
│   ├── triggers.md
│   ├── recovery.md
│   └── metrics.md
├── changes/                   # Pipeline 运行时产出（.gitignore）
└── docs/
    └── demo-sop.md            # Demo 使用 SOP
```

---

## 核心入口：req-to-dev

req-to-dev 是唯一的主流程入口（已作为 Claude Code 原生 Skill 注册），触发方式：
- 提供飞书文档链接 + 要求端到端开发

一条命令跑通从 PRD 到代码验证的全流程：

```
飞书 PRD → 需求拆解 → 范围评估 → 技术方案 → [审批] → 编码 → 审查 → 测试 → 发布验证
                                               ↑ 驳回时回退到范围评估重新执行
```

各阶段的资源加载由 `skills.json` 统一定义，通过 `skills_loader.py` 解析：

```bash
python3 skills_loader.py resolve --stage coding --project shop-points  # 查看资源路径
python3 skills_loader.py context --stage coding --project shop-points  # 输出资源内容
python3 skills_loader.py check                                         # 校验完整性
```

---

## 编码守则速查（Guardrails）

| 守则 | 一句话 | 路径 |
|------|--------|------|
| 分层契约 | Controller→Service→DAO→Mapper，禁止反向依赖 | `guardrails/layering-contracts.md` |
| 构建标准 | `mvn compile` 必须通过，Mapper XML 必须匹配 | `guardrails/build-standards.md` |
| 变更追溯 | 跨 2+ 模块或改 Kafka/Dubbo 必须建 Change | `guardrails/traceability-rules.md` |
| AI 编码规范 | 积分操作幂等，分片查询带 subject_id | `guardrails/ai-coding-spec.md` |

## 系统知识入口（Knowledge）

Knowledge 按目标项目组织，Pipeline 根据 `--target` 自动加载对应项目目录：

| 主题 | 路径 | 范围 |
|------|------|------|
| 项目全景 | `knowledge/project-atlas.md` | 两个项目概览 |
| 服务拓扑 | `knowledge/service-topology.md` | 跨服务交互 |
| 组件图谱 | `knowledge/shop-points/component-graph.md` | shop-points 专属 |
| 数据层 | `knowledge/shop-points/data-layer.md` | shop-points 专属 |
| 消息总线 | `knowledge/shop-points/message-bus.md` | shop-points 专属 |
| RPC 契约 | `knowledge/shop-points/rpc-contracts.md` | shop-points 专属 |
| 组件图谱 | `knowledge/shop-points-lottery/component-graph.md` | lottery 专属 |
| 数据层 | `knowledge/shop-points-lottery/data-layer.md` | lottery 专属 |
| 消息总线 | `knowledge/shop-points-lottery/message-bus.md` | lottery 专属 |
| RPC 契约 | `knowledge/shop-points-lottery/rpc-contracts.md` | lottery 专属 |

---

## Agent Runtime

Playbooks 解决了"能力封装"——Agent 知道每一步怎么做。Agent Runtime 解决"任务自动流转"——自动触发、推进、恢复。

配置文件位于 `runtime/`：

| 文件 | 职责 |
|------|------|
| `pipeline.md` | 8 阶段定义、依赖、可跳过条件、每阶段加载的规范资源 |
| `triggers.md` | 触发规则：手动 / Issue 触发 / PRD 就绪触发 |
| `recovery.md` | 失败恢复策略、重试上限、升级规则、状态流转 |
| `metrics.md` | 效率/质量/规范层的可量化指标 |

---

## 原则

- Guardrails 是硬性约束，Playbooks 是推荐方法
- 旧版本只追加不覆盖（v1→v2→v3）
- "不会做什么"和"会做什么"一样重要
- AI 自检不能作为唯一验收依据
- Playbooks 是能力层，Agent Runtime 是规模化执行层
