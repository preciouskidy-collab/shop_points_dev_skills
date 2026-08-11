---
name: kecoin-upload-e2e-matrix
description: "线下活动贝壳币上传 E2E 完整矩阵 + 反模式复盘（账期对齐、城市对齐、申诉期正负向）"
version: "1.0.0"
category: playbooks
tags:
  - e2e
  - keCoin
  - upload
  - appeal
  - anti-patterns
commands: []
---

# 贝壳币上传 E2E 完整矩阵（含反模式）

> **Single Source of Truth（用例 ID）**：`skills/req-to-dev/scripts/lib/local_e2e_manifest.py` → `KECOIN_OFFLINE_FULL_MATRIX`  
> **门禁**：`local_e2e_checklist.py gate` 须 **全部 PASS** 方可 `advance`。  
> **关联**：`playbooks/e2e-upload-collab.md`、`playbooks/apollo-mock-time.md`、`playbooks/local-e2e-browser-test.md`

## 三条铁律（Agent 必读）

### 铁律 1 · 账期对齐（H5）

**上传账期 = 验收账期。** 记录 PC 弹窗里的 `月度账期`（如 `2026M9`），H5 **必须**在同一账期下断言，**禁止**用页面默认账期（常为当前自然月 M10）代替。

| 页面 | 动作 | 断言 |
|------|------|------|
| `beikebi/index`（卡片/预估） | 点击账期选择器 → 选 **上传账期**（如 2026年9月）→ 确定 | 含「线下活动配置」卡片 + 金额与上传一致（如 400 币） |
| `beikebi/history`（明细） | 展开 **上传账期** 汇总行 | 含对应账期汇总 + 线下活动明细行 |

**反模式（已发生过，禁止再犯）**

- ❌ 默认停在 `2026年10月` 看卡片页，发现无线下活动仍标 PASS  
- ❌ 用 `store-pointsV2/index` 活动列表里的「线下活动配置」代替 `beikebi/index` **同账期**验收  
- ❌ history 看了 M9，卡片页却未切 M9（两半验收账期不一致）

### 铁律 2 · 城市/活动对齐（PC）

**活动规则城市 = Excel 门店所属城市。** 默认：天津市活动 **253** + 门店 `TJDY0101`。

| 检查项 | 要求 |
|--------|------|
| 列表筛选 | 按活动 ID / 规则城市筛到正确活动（如 ID=253、天津市） |
| 弹窗只读字段 | `规则城市` 与 Excel 门店城市一致 |
| 失败特征 | `门店XXX不属于YYY市` → 城市/活动选错 |

**反模式**

- ❌ 点列表第一行「上传贝壳币」（可能是合肥市等活动）  
- ❌ 不筛活动 ID，凭按钮位置上传

### 铁律 3 · 管理端正负向（申诉期）

**happy path 不够**，须同时验证申诉期规则：

| 用例 | 场景 | 期望 |
|------|------|------|
| `E2E-PC-01c` | **申诉期内**（或业务允许的补录窗口内）上传 | 列表终态 **已生效 / 102** |
| `E2E-PC-02` | **申诉期外** 尝试同活动上传 | 接口/弹窗 **`hasSaveError=true`** 或明确拦截文案，**不得**产生新的已生效记录 |

申诉期与 mock 时间见 `playbooks/apollo-mock-time.md`（每月 1–5 日、`month5thDay` 等）。负向用例须先 **调 `mockCurrentTime` 到申诉期外** 再点确定。

**反模式**

- ❌ 只跑成功上传，不跑申诉期外拦截  
- ❌ 负向用例在申诉期内执行，得不到 `hasSaveError`

---

## 完整用例矩阵

| ID | 端 | 内容 | 依赖 |
|----|-----|------|------|
| API-01 | 栈 | shop-points health 200 | — |
| API-02 | 栈 | `keCoin/period` 200 | — |
| E2E-PC-01a | PC | 登录 + **正确活动/城市** + 弹窗字段（含上传账期） | — |
| E2E-PC-01b | PC | notify → 用户选 Excel → wait `upload_confirm` | 01a |
| E2E-PC-01c | PC | 申诉期内点确定 → 列表 **已生效(102)** | 01b |
| **E2E-PC-02** | PC | **申诉期外**提交 → `hasSaveError=true` | Apollo mock |
| APOLLO-MOCK-01 | Apollo | `mockCurrentTime` 调至发币日/申诉期后 + **业务开关**发布 | 01c |
| E2E-H5-01 | H5 | `beikebi/index` **切换至上传账期** → 线下活动卡片 | 01c, APOLLO |
| E2E-H5-02 | H5 | `beikebi/history` **上传账期**明细 | APOLLO |

### 记录模板（写入 `e2e_checklist.json` note）

每轮 E2E 在 checklist note 中**必填**：

```text
upload_period=2026M9 activity_id=253 city=天津市 shop=TJDY0101 upload_row_id=3484
```

H5 用例 note 须含：`h5_period=2026M9`（与 upload_period 一致）。

---

## 推荐执行顺序

```
API-01/02
  → E2E-PC-01a（确认活动253·天津·账期）
  → E2E-PC-02（mock 申诉期外 → 提交失败 hasSaveError）   # 可与 01c 前后，但须独立记 PASS
  → E2E-PC-01b → wait → E2E-PC-01c（申诉期内成功上传）
  → APOLLO-MOCK-01（发币日/申诉期后，供 H5 明细可见）
  → E2E-H5-01（beikebi/index 切 upload_period）
  → E2E-H5-02（beikebi/history 同 upload_period）
  → local_e2e_checklist.py gate
```

---

## H5 账期切换操作提示

1. 打开 `beikebi/index?shopCode=TJDY0101&shopCodeInnerTest=TJDY0101`
2. 点击「预估/可获得贝壳币」右侧 **账期下拉**（默认常为当月）
3. 滚轮选 **上传账期**（如 `2026年9月`）→ **确定**
4. 断言：汇总金额 +「线下活动配置」卡片进度文案含该月金额

---

## E2E-PC-02 申诉期外（负向）

1. Apollo `mockCurrentTime` 调到 **申诉期外**（例：当月 11 日，且业务规则不允许补录该账期）
2. Portal 确认 **已发布** 后**立即**继续 PC 提交 / H5 验收（配置**实时**热更新，**禁止** `sleep 90` 或等 1–3 分钟）
3. 打开活动 **253** 上传弹窗，选文件（可空文件或同模板，重点是提交动作）
4. 点「确定」
5. **期望**：前端提示错误或接口 `hasSaveError=true`；上传列表**无**新的「已生效」行

验证方式：Network 抓提交接口响应，或弹窗错误文案 snapshot。

---

## Agent 自检（标 PASS 前）

- [ ] `upload_period` 已写入 checklist，H5 两页均在该账期下验收  
- [ ] PC 活动城市与 Excel 门店一致（非错城活动）  
- [ ] `E2E-PC-02` 负向已执行（非仅 happy path）  
- [ ] `E2E-PC-01c` 列表行状态为已生效，id 已记录  
- [ ] Apollo 独立 key `mockCurrentTime` 已 **业务开关** 发布  
- [ ] `local_e2e_checklist.py gate` 全绿  

---

## 发现本 playbook

```bash
python3 skills_loader.py search "贝壳币上传 E2E"
python3 skills_loader.py search "kecoin upload e2e"
python3 skills_loader.py resolve --stage local-e2e-test --project shop-points
```
