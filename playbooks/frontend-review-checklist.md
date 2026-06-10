---
name: frontend-review-checklist
description: "审查 React 前端变更：API 调用、路由、空态异常态、与 FDH 一致性"
version: "0.1.0"
category: playbooks
tags:
  - frontend
  - review
commands: []
---

# Skill: 前端审查清单

## 审查输入

- `handoff/frontend-handoff.md`
- 前端代码 diff

## 检查项

### MUST FIX

- [ ] API 路径/方法与 FDH、后端代码不一致
- [ ] 遗漏 FDH P0 改造点
- [ ] 未处理接口错误（网络失败、业务 code != 0）
- [ ] 新增页面未注册路由
- [ ] 硬编码测试环境 URL 或密钥

### SHOULD FIX

- [ ] 缺少 loading / 空态
- [ ] 未复用现有组件，重复造轮子
- [ ] ESLint 可修复项

### INFO

- [ ] 命名风格与周边不一致
- [ ] 可优化的性能点

## 产出

`review/frontend_review_v1.md`（MUST FIX / SHOULD FIX / INFO 三级）

## 质量标准

- 有 MUST FIX 时 Agent 自动修复后重审，最多 2 次
