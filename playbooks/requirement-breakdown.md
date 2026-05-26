---
name: requirement-breakdown
description: "当收到需求文档或口头需求时触发，进行结构化需求分析，产出 spec.md 和 tasks.md"
version: "0.1.0"
category: harness
tags:
  - skill
  - analysis
  - requirement
  - spec
commands: []
---

# Skill: 需求拆解

## 输入
- 用户需求原文（飞书 PRD / 口头描述 / IM 消息）。
- 相关代码路径、Wiki、历史 Change。
- 已知约束和非目标。

## 步骤
1. 用 3-5 句话复述业务目标。
2. 列出明确需求、隐含需求、待确认问题。
3. 标注非目标，避免范围膨胀。
4. 写出可验证的验收标准。
5. 判断是否需要建 Change 目录（参考 `guardrails/traceability-rules`）。
6. 确定受影响的项目（shop-points 和/或 shop-points-lottery）和模块。

## 产出
写入或更新：
- `request/spec.md` — 需求背景、明确需求、非目标、验收标准、待确认问题
- `request/tasks.md` — 任务拆分表（ID | Task | Owner | Status | Notes）

## 质量标准
- 每条验收标准都能通过 mvn test / API 响应 / 日志 / 人工确认验证。
- 不把实现方案混进需求事实；实现方案写到 tasks 或 impact。
- 验收标准必须包含影响的项目和模块。
