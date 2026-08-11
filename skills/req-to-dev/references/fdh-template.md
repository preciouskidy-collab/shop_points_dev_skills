# Frontend Development Handoff (FDH) 模板

契约对齐阶段（`frontend-handoff`）按此模板生成瘦身版 `handoff/frontend-handoff.md`（UI + E2E；API 引用 `api-contract.yaml`）。

---

```markdown
# Frontend Development Handoff (FDH)

> Change: {change-id} | Branch: feature/{name} | Surfaces: {h5|pc|both}

## 1. 变更摘要

- **业务背景**：（1 段）
- **用户可见变化**：
  - ...
- **PRD 章节**：request/prd.md §...

## 2. 影响面矩阵

| 端 | 路由/页面 | 组件/文件路径 | 变更类型 | 优先级 |
|----|-----------|---------------|----------|--------|
| H5 | /store-pointsV2/xxx | client-integral/src/views/... | 新增字段 | P0 |
| PC | /integral2/xxx | client/src/container/... | 列表扩展 | P1 |

## 3. API 契约

### 3.1 {METHOD} {path}

- **鉴权**：Cookie / CAS
- **调用端**：H5 / PC / 双端
- **Request**：

```json
{}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|

- **Response 成功**：

```json
{ "code": 0, "message": "success", "data": {} }
```

- **错误码**：

| code | 说明 | 前端处理 |
|------|------|----------|

- **兼容性**：新增字段 / 破坏性变更说明

（每个接口重复 3.x 小节）

## 4. UI 改造点

### 4.1 [H5] 页面名称

- **改造点**：...
- **交互**：点击 xxx → 调 API 3.1
- **空态/异常态**：...
- **PRD 截图**：images/xxx.png

### 4.2 [PC] 页面名称

（同上）

## 5. 状态与数据流

- 页面 state 变更：...
- 字段映射：后端字段 → 前端展示

## 6. 验收场景（E2E）

> **贝壳币上传类需求**：§6 须覆盖 `skills/req-to-dev/references/kecoin-upload-e2e-cases.yaml` 全部 `E2E-*` ID；H5 用例**必须**写「切换至 `upload_period`」步骤，**禁止**仅用页面默认账期；须含 **E2E-PC-02 申诉期外负向**（`hasSaveError=true`）。默认测试数据见 `test_context`（天津 / 253 / TJDY0101 / 2026M9）。

| ID | 端 | 前置条件 | 操作步骤 | 期望结果 |
|----|----|----------|----------|----------|
| E2E-PC-01a | PC | 活动 **253（天津市）** | 筛选活动 → 上传贝壳币弹窗 | 记录 **upload_period**（如 2026M9） |
| E2E-PC-01b | PC | 01a 完成 | notify → 用户选 Excel → wait `upload_confirm` | 协作确认收到 |
| E2E-PC-01c | PC | 申诉期内 | 点确定 → 列表 **已生效(102)** | 账期与 upload_period 一致 |
| **E2E-PC-02** | PC | **申诉期外**（Apollo mock） | 同活动再次提交 | **hasSaveError=true**，无新 102 |
| E2E-H5-01 | H5 | PC 上传成功 + Apollo mock | beikebi/index → **切换至上传账期** | 线下活动卡片/金额正确 |
| E2E-H5-02 | H5 | Apollo mock | beikebi/history → **同 upload_period** | 明细账期与上传一致 |
| E2E-01 | H5 | 已登录 TJDY0101（天津市门店） | 进入首页 → 查看 xxx | 显示新字段，值与接口一致 |
| E2E-02 | PC | 已登录管理端；城市 **天津市** | 进入活动配置 → 编辑 | 保存成功，列表刷新 |

> 默认测试数据：城市 **天津市**（`cityCode=120000`）、活动 **253**、门店 **TJDY0101**、`upload_period` **2026M9** → `knowledge/test-env-topology.md`

## 7. 部署依赖

```yaml
deploy_modules:
  - shop-points
  # - shop-points-lottery   # 仅商城需求
  - store-integral-h5-cdn
  # - store-integral-cdn
deploy_order: 后端 → 前端
apollo_keys: []   # 如有
```

## 8. Won't Do（前端）

- ...
```

---

## api-contract.yaml 模板

```yaml
version: "1.0"
change_id: "{change-id}"
branch: "feature/{name}"
surfaces: [h5, pc]

backend:
  repo: shop-points
  modules_changed: []

apis:
  - id: API-001
    method: POST
    path: /shop-points/web/xxx
    surfaces: [h5]
    request:
      type: object
      properties: {}
    response:
      type: object
      properties: {}
    errors:
      - code: 10001
        message: "余额不足"
    sample_curl: |
      curl -b '$COOKIE' -X POST 'http://local.ttb.test.ke.com/shop-points/web/xxx' \
        -H 'Content-Type: application/json' -d '{}'

e2e_cases:
  - id: E2E-01
    surface: h5
    entry_url: "http://integral.ttb.test.ke.com/store-pointsV2/index?shopCode=TJDY0101&shopCodeInnerTest=TJDY0101"
    preconditions: ["已登录"]
    steps:
      - action: navigate
        target: entry_url
      - action: assert_visible
        selector: "text=xxx"
    expected: "首页展示新字段"

deploy_modules:
  - shop-points
  - store-integral-h5-cdn
```
