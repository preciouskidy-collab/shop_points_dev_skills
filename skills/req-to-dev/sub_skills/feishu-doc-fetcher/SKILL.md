---
name: feishu-doc-fetcher
description: "当用户提供飞书文档链接并需要获取 PRD 内容时触发，默认通过 lark-cli 拉取 Markdown，可选 --with-images 补充图片"
version: "0.5.0"
category: req-to-dev
tags:
  - feishu
  - document
  - lark-cli
  - markdown
  - prd
commands: []
---

# 飞书文档获取器

通过 **lark-cli** 拉取飞书 PRD 为本地 Markdown。实现层统一走 `lib/lark_cli.py`；需要内嵌图片时可加 `--with-images`（legacy API 补充下载）。

## 触发时机

- 用户提供飞书文档链接并需要获取文档内容
- req-to-dev Pipeline 的 **fetch-prd** 阶段（`skills.json` 已绑定本 Skill）
- 需要将飞书 PRD 转为本地 `request/prd.md`

## 前置条件

### lark-cli（默认路径）

```bash
bash skills/req-to-dev/scripts/setup_lark_cli.sh
```

凭证与 `~/.shop-points-dev-skills/feishu-config.json` 共用。

### 飞书应用权限

| 操作 | Scope |
|------|-------|
| fetch | `docx:document:readonly` + `wiki:wiki:readonly` |
| `--with-images` | 同上 + `im:resource`（下载图片） |

## 执行流程

### Step 0 — 运行 Skill 入口脚本

**直接运行，不要预先检查配置文件。**

```bash
cd <shop_points_dev_skills 根目录>
python3 skills/req-to-dev/sub_skills/feishu-doc-fetcher/scripts/feishu_fetcher.py "<飞书URL>" \
  --output-dir changes/<req-id>/request \
  --project-name <需求名称>
```

### Step 1 — 默认：lark-cli fetch

- 调用 `lark-cli docs +fetch --doc-format markdown`
- 写入 `changes/<req-id>/request/prd.md`
- lark-cli 不可用时 **自动降级** legacy Open API

### Step 2 — 可选：补充图片

PRD 含大量内嵌图时：

```bash
python3 .../feishu_fetcher.py "<URL>" \
  --output-dir changes/<req-id>/request \
  --project-name <name> \
  --with-images
```

### Step 3 — 强制 legacy API

```bash
python3 .../feishu_fetcher.py "<URL>" ... --legacy-api
```

## 产出

```
changes/<req-id>/request/
├── prd.md
└── images/          ← 仅 --with-images / --legacy-api
    └── img-0.png
```

## 降级方案

| 场景 | 处理 |
|------|------|
| lark-cli 未安装 | 自动降级 legacy API |
| 凭证缺失 | 询问 App ID/Secret，通过 `--app-id` `--app-secret` 传入 |
| 全部失败 | 提示用户手动粘贴 PRD 到 `prd.md` |

## 架构说明

```
Pipeline fetch-prd
    → feishu-doc-fetcher (Skill)
        → feishu_fetcher.py (CLI 入口)
            → lib/lark_cli.py (统一适配器)
                → lark-cli npm
```

Skill 是对 Agent 的契约；CLI 是实现细节。Pipeline 通过 `skills.json` 加载本 Skill，不直接暴露裸脚本路径。

## 注意事项

1. **凭证安全**：存在 `~/.shop-points-dev-skills/`，不提交代码库
2. **画板/思维导图**：API 不支持，需用户手动导出
3. **默认不含图片**：纯文本 PRD 用默认路径即可；图文并茂 PRD 加 `--with-images`
