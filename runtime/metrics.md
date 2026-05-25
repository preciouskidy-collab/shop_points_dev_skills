# 观测度量

定义 Agentic Coding 的可量化指标，从"体感快了"到"数据可度量"。

## 核心指标

### 效率指标

| 指标 | 定义 | 采集方式 | 目标 |
|------|------|----------|------|
| Issue 关闭时长 | 从 Issue 创建到 Pipeline completed 的时间 | changes/summary.md 的时间戳 | P50 < 4h |
| 编码阶段耗时 | coding 阶段的实际执行时间 | Agent 日志 | P50 < 30min |
| Token 效率 | 有效代码行数 / 消耗 token 数 | Claude Code 用量统计 | 持续优化 |

### 质量指标

| 指标 | 定义 | 采集方式 | 目标 |
|------|------|----------|------|
| 首次 Review 通过率 | 一次 review 无 MUST FIX 的比例 | review 报告 | > 70% |
| 编译一次通过率 | coding 后 mvn compile 一次通过的比例 | checkpoints 执行结果 | > 90% |
| Agent 自愈率 | 失败后 Agent 自行修复成功的比例 | recovery 日志 | > 50% |

### 规范层指标

| 指标 | 定义 | 采集方式 | 目标 |
|------|------|----------|------|
| Playbook 复用率 | 各 Playbook 被加载的频次 | skills_loader 调用日志 | 识别高频场景 |
| Domain Spec 命中率 | Knowledge/Guardrails 被引用的比例 | Agent 上下文记录 | > 80% |
| Changes 完整率 | 必填 5 产物齐全的 Change 比例 | changes/ 目录扫描 | 100% |

## 采集方式

当前阶段以手动记录为主：
- Pipeline 每阶段完成后更新 `changes/<change>/summary.md` 的状态时间戳
- review/test 结果记录到对应产物文件
- 后续可通过 Agent Runtime 自动采集
