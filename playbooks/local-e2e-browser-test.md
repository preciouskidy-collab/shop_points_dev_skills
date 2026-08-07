---
name: local-e2e-browser-test
description: "使用 Cursor 内置浏览器 MCP 在本地前后端执行 E2E 验收"
version: "0.3.0"
category: playbooks
tags:
  - e2e
  - local
  - cursor-browser
commands: []
---

# Skill: 本地 E2E（Cursor 内置浏览器）

## 适用时机

`local-stack-up`（方案 B nginx）**且启动验收通过**后。

**跳过条件**：`frontend_scope: none`。

> **踩坑排障（必读）**：[`local-stack-troubleshooting.md`](local-stack-troubleshooting.md)

## 前置条件

- `tests/local_stack_report.md` 记录栈已启动
- 排障文档 §二 检查清单已通过（尤其 bundle 完整、preview 非 403）
- `handoff/frontend-handoff.md` §6 用例已就绪
- `secrets.local.json` → `test_env_app` 可登录
- CAS 反代（本机 80）已起（若需浏览器 CAS 登录）

## 测试入口（方案 B · 推荐）

**服务基金积分商城**（本 Pipeline 本地 E2E 入口）：

```
http://integral.ttb.test.ke.com:8088/fuwujin-mall/index?shopCode=TJDY0101&shopCodeInnerTest=TJDY0101
```

| 不要用的入口 | 原因 |
|--------------|------|
| `localhost:9393` | 绕过 nginx，与真实链路不一致 |
| `integral.ttb.test.ke.com` 无端口 | hosts 指向本机 80，是 CAS/lottery 不是 H5 |
| `/store-points/index` | 门店积分首页，非服务基金商城 |

## 浏览器工具

| 操作 | MCP 工具 |
|------|----------|
| 打开页面 | `browser_navigate` |
| 读页面结构 | `browser_snapshot` |
| 点击 / 输入 | `browser_click` / `browser_type` |
| 截图验证 | `browser_take_screenshot` |

## 登录

1. 打开 H5 入口（**:8088**）→ 若跳 CAS：
   - 员工 → 账号登录 → `test_env_app` 工号密码
2. 或：`ab_h5_bypass_http.py`（将 `H5_URL` 改为带 `:8088` 的 fuwujin-mall 入口）
3. CAS 回跳依赖本机 80 CAS 反代（见排障文档 §四）

## 步骤

1. 加载 `frontend-handoff.md` §6 用例
2. navigate → 等待 bundle 加载完成（非永久 loading）
3. snapshot → 交互 → 断言（黄字提示 / 子选项显隐）
4. 点「去兑换」前确认 Network 中 `order/preview` 为 **200**（非 403）
5. 产出 `tests/local_e2e_report.md`

## 常见失败与对照

| 现象 | 见排障文档 |
|------|------------|
| 502 | §坑 2（9393 未起） |
| 永久 loading | §坑 3（bundle 截断） |
| serverError 403 | §坑 4（CORS） |
| 登录后白屏 | §坑 5（CAS 80） |
| 无支付方式区块 | §坑 8（preview 失败或测试数据） |

## 质量标准

- P0 用例通过，或在报告中记录阻塞原因（数据/登录/环境）
- 报告含 snapshot 或截图摘要
- 阻塞时引用排障文档章节，勿重复踩坑
