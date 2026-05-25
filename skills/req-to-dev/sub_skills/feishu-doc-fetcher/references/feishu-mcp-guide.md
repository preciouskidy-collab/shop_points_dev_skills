# 飞书文档获取 API 调用指南

## 架构

```
feishu-doc-fetcher
       │ 直连 HTTPS
       ▼
飞书开放平台 (https://open.feishu.cn)
  /auth/v3/tenant_access_token/internal   → 获取应用级 token
  /docx/v1/documents/{token}/raw_content  → 获取文档内容
  /docx/v1/documents/{token}/blocks       → 获取文档块结构
  /wiki/v2/spaces/get_node                → 获取 wiki 节点信息
  /im/v1/images/{image_token}             → 下载图片
```

**无中间代理**：脚本直连飞书 API，使用应用自己的 tenant_access_token。

## 凭证管理

### 凭证位置

`~/.shop-points-dev-skills/feishu-config.json`（不入代码库）

```json
{
  "app_id": "cli_xxxxxxxxxxxx",
  "app_secret": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
}
```

### 首次使用

脚本检测到配置文件不存在时，自动生成模板并提示用户填写。

### 应用权限要求

在飞书开放平台为应用开通以下权限：
- `docx:document:readonly` — 读取文档内容
- `wiki:wiki:readonly` — 读取知识库文档
- `drive:drive:readonly` — 读取云文档
- `im:resource` — 下载图片资源

知识库文档还需将知识库授权给应用。

## Token 机制

### tenant_access_token（应用级）

- **获取方式**：app_id + app_secret 直接换取，无需用户交互
- **有效期**：2 小时
- **缓存**：内存缓存，提前 5 分钟自动刷新
- **适用场景**：读取应用有权限的文档

### 与旧方案的区别

| 对比项 | 旧方案 (newh-spec-kit) | 新方案 (直连飞书 API) |
|--------|----------------------|---------------------|
| 中间层 | newh-spec-kit 代理 | 无，直连飞书 |
| Token 类型 | user_access_token | tenant_access_token |
| 授权方式 | 浏览器 OAuth | app_id+app_secret 直接换 |
| 凭证存储 | 服务端 Redis | 本地 ~/.shop-points-dev-skills/ |
| 应用归属 | 新房应用 | 用户自己的应用 |

## API 调用流程

### 1. 获取 tenant_access_token

```
POST https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal
Content-Type: application/json

{
  "app_id": "cli_xxx",
  "app_secret": "xxx"
}
```

返回：`{"tenant_access_token": "t-xxx", "expire": 7200}`

### 2. 获取文档内容（docx）

```
GET https://open.feishu.cn/open-apis/docx/v1/documents/{doc_token}/raw_content
Authorization: Bearer {tenant_access_token}
```

返回：`{"data": {"content": "Markdown 内容"}}`

### 3. 获取 wiki 文档

先获取节点信息：
```
GET https://open.feishu.cn/open-apis/wiki/v2/spaces/get_node?token={wiki_token}
Authorization: Bearer {tenant_access_token}
```

返回节点中的 `obj_token`（实际文档 token）和 `obj_type`（文档类型），再按类型调用对应 API。

### 4. 获取文档块结构（图片提取）

```
GET https://open.feishu.cn/open-apis/docx/v1/documents/{doc_token}/blocks?page_size=500
Authorization: Bearer {tenant_access_token}
```

遍历 items，提取 `block_type == "image"` 的 `image.token`。

### 5. 下载图片

```
GET https://open.feishu.cn/open-apis/im/v1/images/{image_token}
Authorization: Bearer {tenant_access_token}
```

返回图片二进制数据，Content-Type 标明格式。

## URL 解析规则

| URL 格式 | 文档类型 |
|----------|---------|
| `https://beike.feishu.cn/docx/TOKEN` | docx |
| `https://beike.feishu.cn/docs/TOKEN` | docx |
| `https://beike.feishu.cn/wiki/TOKEN` | wiki |

## 注意事项

1. **凭证安全**：app_id/app_secret 仅存在用户本地，不提交到代码库
2. **应用权限**：文档所在知识库必须授权给应用，否则 403
3. **画板/思维导图不支持**：API 仅识别 docx 内嵌图
4. **图片数量限制**：blocks API 单次最多 500 个块
5. **图片占位符**：正文中的占位符需替换为本地图片路径