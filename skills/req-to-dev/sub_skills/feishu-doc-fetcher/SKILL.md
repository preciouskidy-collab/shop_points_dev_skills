---
name: feishu-doc-fetcher
description: "当用户提供飞书文档链接并需要获取文档内容时触发，直连飞书开放平台 API 获取文档，转换为 Markdown 并下载图片到本地"
version: "0.3.0"
category: req-to-dev
tags:
  - feishu
  - document
  - api
  - markdown
  - prd
commands: []
---

# 飞书文档获取器

直连飞书开放平台 API，使用 tenant_access_token 获取文档内容，转换为 Markdown 并下载图片到本地。无需中间代理服务。

## 触发时机

- 用户提供飞书文档链接并需要获取文档内容时
- "帮我获取这个飞书文档"
- "读取这个飞书链接的内容"
- 需要将飞书 PRD 文档转为本地 Markdown 时

## 前置条件

### 飞书应用权限要求（需在飞书开放平台为应用开通）

- `docx:document:readonly` — 读取文档内容
- `wiki:wiki:readonly` — 读取知识库文档
- `drive:drive:readonly` — 读取云文档
- `im:resource` — 下载图片资源

**知识库授权**：如果文档在知识库中，还需在飞书开放平台将知识库授权给该应用。

## 执行流程

### Step 0 — 运行脚本获取文档

**直接运行脚本，不要预先检查配置文件。** 脚本会自行处理凭证检查。

```bash
python3 scripts/feishu_fetcher.py "<飞书URL>" --output-dir <输出目录> --project-name <项目名>
```

#### 如果脚本输出 `feishu_config_required` 错误

说明凭证未配置。此时必须：

1. **直接向用户询问**："请提供飞书应用的 App ID 和 App Secret"
2. 用户提供后，**通过命令行参数传入**重新运行：

```bash
python3 scripts/feishu_fetcher.py "<飞书URL>" --output-dir <输出目录> --project-name <项目名> \
  --app-id "<用户提供的 App ID>" --app-secret "<用户提供的 App Secret>"
```

3. 凭证会自动保存到 `~/.shop-points-dev-skills/feishu-config.json`，后续无需再传

**重要**：不要让用户自己去编辑配置文件，直接询问凭证然后通过参数传入。

#### 如果用户没有飞书应用

引导用户：
1. 到 https://open.feishu.cn 创建自建应用
2. 开通上述权限
3. 将知识库授权给应用
4. 提供 App ID 和 App Secret

### Step 1 — 解析飞书 URL

从 URL 中提取 token 和文档类型：
- `https://beike.feishu.cn/docx/TOKEN` → docx 类型
- `https://beike.feishu.cn/wiki/TOKEN` → wiki 类型
- `https://beike.feishu.cn/docs/TOKEN` → docx 类型

### Step 2 — 获取 tenant_access_token

用 app_id + app_secret 直接换取 tenant_access_token，无需用户浏览器授权：
- 缓存在内存中，提前 5 分钟自动刷新
- 无 OAuth 流程，零交互

### Step 3 — 拉取文档内容

- **docx 文档**：调用 `/docx/v1/documents/{token}/raw_content`
- **wiki 文档**：先查 `/wiki/v2/spaces/get_node` 获取实际文档 token 和类型，再按类型读取

### Step 4 — 获取并下载图片

1. 调用 `/docx/v1/documents/{token}/blocks` 获取文档块结构
2. 提取 block_type=image 的图片 token
3. 逐一下载图片（`/im/v1/images/{image_token}`）
4. base64 编码后保存到 `images/` 目录

### Step 5 — 输出

- 输出 Markdown 到 `docs/req-to-dev/<project-name>/prd/prd.md`
- 图片目录 `docs/req-to-dev/<project-name>/prd/images/`
- 替换正文中的图片占位符为本地引用

### Step 6 — 校验

- 对比图片引用与实际文件，确保零缺失
- 统计：文档标题、图片下载数/失败数、输出路径

## 降级方案

当凭证缺失或 API 调用失败时：
1. 提示用户："飞书文档获取失败，请手动粘贴文档内容或导出为 PDF/Word"
2. 将用户粘贴的内容保存到 `docs/req-to-dev/<project-name>/prd/prd.md`
3. 继续后续流程

## 注意事项

1. **凭证安全**：app_id/app_secret 存在用户本地 `~/.shop-points-dev-skills/` 下，不提交到代码库
2. **画板/思维导图不支持**：API 仅识别 docx 内嵌图，画板等需用户手动导出
3. **图片数量限制**：blocks API 单次最多 500 个块，超大文档可能遗漏图片
4. **应用权限**：应用必须有文档对应知识库的访问权限，否则返回 403