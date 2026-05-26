---
name: req-to-dev
description: "从飞书 PRD 到需求分析、技术方案、编码、审查、测试、发布的端到端自动 Pipeline。Agent 自动推进 8 个阶段，仅在人工审批点暂停"
version: "0.3.0"
category: req-to-dev
tags:
  - workflow
  - orchestration
  - backend
  - feishu
  - auto-pipeline
commands: []
---

# req-to-dev — 自动化 Pipeline

从飞书 PRD 到可交付代码的 8 阶段自动 Pipeline。**Agent 连续执行，仅在人工审批点暂停。**

## 触发时机

- "帮我从这个飞书文档开发后端功能"
- "从需求到代码的完整流程"
- "按这个 PRD 开发后端"
- 提供飞书文档链接并要求端到端开发

## 输入

- **必需**：飞书文档 URL
- **必需**：需求名称（用于 change 目录命名，如 `vip-points`）
- **必需**：目标项目路径（如 `/path/to/shop-points`）
- **可选**：飞书 app-id / app-secret（首次使用时由 feishu_fetcher 引导输入）

## 执行模式

```
自动阶段                                  检查点              自动阶段
─────────────────────────────          ──────────      ──────────────────────
fetch-prd → break-down → scope-eval → tech-design → [plan-approve] → coding → review → test → release
                                                              ↑
                                                        唯一暂停点
                                                        等人工审批
                                                    ┌─ 通过 → coding
                                                    └─ 驳回 → 回退到 scope-eval 重新执行
```

- **自动阶段**：Agent 连续执行，阶段完成后立即运行 `advance` 推进，不暂停不询问
- **检查点（plan-approve）**：暂停等待人工审批后才继续
- **失败处理**：按 recovery.md 重试，超限后升级人工

## 执行流程

### Step 0：初始化 Pipeline

1. **Git 上下文检查**（强制前置）：

   在目标项目路径下检查 git 状态：

   | 当前状态 | 操作 |
   |---------|------|
   | 工作区不干净 | 提示用户 commit 或 stash，**终止流程** |
   | 已在 `feature/<name>` 分支 | 继续 |
   | 不在目标分支 | 提示创建新分支，用户确认后执行 `git checkout -b feature/<name>` |

   **绝不在非目标分支或有未提交变更的工作区上生成代码。**

2. **初始化 Pipeline 状态**：

   ```bash
   cd <shop_points_dev_skills 根目录>
   python3 skills/req-to-dev/scripts/run_workflow.py init \
     --url "<飞书URL>" \
     --name "<需求名称>" \
     --target "<目标项目路径>"
   ```

3. 确认输出包含 "Pipeline 已初始化" 后进入 Step 1

### Step 1：PRD 拉取（自动）

**阶段 ID**: `fetch-prd` | **子技能**: `feishu-doc-fetcher`

1. 调用 `feishu-doc-fetcher` 子 skill 获取飞书文档
2. 产出 `request/prd.md` + `images/`
3. 如果 feishu_fetcher 报 `feishu_config_required` 错误 → 向用户索取 app-id/app-secret 后重试
4. **记录日志**：`python3 run_workflow.py log --name <name> --message "PRD 拉取完成，<N> 个图片，文档 <M> 行"`
5. 完成后运行 `python3 run_workflow.py advance --name <name>` → 自动进入下一阶段

**不暂停，不询问用户"PRD 是否完整"。**

### Step 2：需求拆解（自动）

**阶段 ID**: `break-down` | **Playbook**: `requirement-breakdown`

1. 加载阶段资源：`python3 skills_loader.py context --stage break-down --project <project>`
2. 读取 `request/prd.md`
3. 按需求拆解手册结构化拆解，产出：
   - `request/spec.md` — 需求规格（功能点、约束、验收标准）
   - `request/tasks.md` — 任务拆分（可执行的编码任务列表）
4. **记录日志**：`python3 run_workflow.py log --name <name> --message "需求拆解完成：<N> 个功能模块，<M> 个任务项"`
5. 完成后运行 `python3 run_workflow.py advance --name <name>` → 自动进入下一阶段

**不暂停。**

### Step 3：范围评估（自动）

**阶段 ID**: `scope-eval` | **Playbook**: `scope-evaluation`

1. 加载阶段资源：`python3 skills_loader.py context --stage scope-eval --project <project>`
2. 读取 `request/spec.md`
3. 按范围评估手册追踪影响面，产出：
   - `impact/impact.md` — 影响分析（含 **Won't Do 列表**）
4. **记录日志**：`python3 run_workflow.py log --name <name> --message "范围评估完成：涉及 <模块列表>，Won't Do: <列表>"`
5. 完成后运行 `python3 run_workflow.py advance --name <name>`

**不暂停。**

### Step 4：技术方案（自动）

**阶段 ID**: `tech-design`

1. 加载阶段资源：`python3 skills_loader.py context --stage tech-design --project <project>`
2. 读取 PRD + spec + impact
3. 生成结构化技术设计文档 → `tech-design/tech-design.md`
4. **记录日志**：`python3 run_workflow.py log --name <name> --message "技术方案生成完成：<N> 个接口变更，<M> 个数据库变更"`
5. 完成后运行 `python3 run_workflow.py advance --name <name>`

**advance 会返回 `BLOCKING` → 进入检查点。**

### Step 5：检查点 — 人工审批（暂停）

**阶段 ID**: `plan-approve` | **阻塞等人**

暂停并向用户展示：

```
📋 审批内容：
  1. request/spec.md              — 需求摘要
  2. impact/impact.md             — 影响范围 + Won't Do 列表
  3. tech-design/tech-design.md   — 技术方案

❓ 是否批准进入编码阶段？
```

- 用户批准 → 运行 `python3 run_workflow.py approve --name <name>` → 自动推进到 Step 6
- 用户给出修改意见 → 运行 `python3 run_workflow.py reject --name <name> --reason "<修改意见>"` → 回退到 Step 3 重新执行 scope-eval → tech-design
- 用户拒绝 → 终止 Pipeline

### Step 6：编码（自动）

**阶段 ID**: `coding` | **Playbook**: `spring-boot-coding`

1. 加载阶段资源：`python3 skills_loader.py context --stage coding --project <project>`
2. 读取 `tech-design/tech-design.md`
3. 按 KeBoot 四模块结构生成/修改 Java 代码到目标项目
4. **记录日志**：`python3 run_workflow.py log --name <name> --message "编码完成：生成 <N> 个文件，修改 <M> 个文件"`
5. 运行 `mvn compile` 验证编译
   - 编译成功 → 完成后运行 `python3 run_workflow.py advance --name <name>`
   - 编译失败 → 运行 `python3 run_workflow.py fail --name <name> --reason "mvn compile failed: ..."`
     - 返回 `RETRY` → Agent 自修编译错误，重新验证
     - 返回 `ESCALATED` → 暂停，通知用户

**不暂停（除非编译反复失败被升级）。**

### Step 7：审查（自动）

**阶段 ID**: `review` | **Playbook**: `review-checklist`

1. 加载阶段资源：`python3 skills_loader.py context --stage review --project <project>`
2. 审查 Step 6 产出的代码变更
3. 按 MUST FIX / SHOULD FIX / INFO 三级输出审查报告 → `review/code_review_v1.md`
4. **记录日志**：`python3 run_workflow.py log --name <name> --message "审查完成：<N> MUST FIX, <M> SHOULD FIX, <K> INFO"`
5. 如有 MUST FIX：
   - Agent 按审查意见自动修复
   - 修复后重新运行审查
   - 最多重试 2 次
6. 完成后运行 `python3 run_workflow.py advance --name <name>`

**不暂停。**

### Step 8：测试验证

**阶段 ID**: `test` | **Playbook**: `test-authoring`

1. 加载阶段资源：`python3 skills_loader.py context --stage test --project <project>`
2. **判断测试类型**：
   - 如果改动涉及 Web 接口（Controller 层）→ 执行接口测试流程
   - 否则 → 执行单元测试流程

3. **接口测试流程**（Web 接口类改动）：

   a. **启动本地应用**：
   ```bash
   cd <目标项目路径>
   mvn spring-boot:run -pl <start模块> -Dspring-boot.run.profiles=test
   ```
   等待应用启动完成（日志出现 `Started` 字样）。

   本地应用地址统一使用 `http://local.ttb.test.ke.com`（不要用 localhost）。

   b. **收集测试数据**：向用户一次性索取完整的测试信息：
   ```
   📋 接口测试需要以下信息，请一次性提供：
     1. Cookie（登录凭证）
     2. 完整的请求参数（JSON 格式）
   
   示例：
     Cookie: SESSION=xxx; ...
     请求参数: {"subjectId":"123","productId":456,"quantity":1,"price":100}
   
   ❓ 请提供 Cookie 和请求参数
   ```

   用户可以直接粘贴 Cookie + JSON，也可以说"帮我构造，productId 用 xxx"由 Agent 补全。

   c. **调用接口验证**：使用 curl 携带 Cookie 调用相关接口，验证响应符合预期。

   d. **关闭应用**：测试完成后停止本地应用。

4. **单元测试流程**（非接口类改动）：
   - 为 Step 6 的代码变更编写单元测试
   - 运行 `mvn test`

5. **产出** `tests/test_report.md`，记录测试结果
6. 完成后运行 `python3 run_workflow.py advance --name <name>`

**如果需要入参，暂停询问用户；测试失败可重试，最多 3 次。**

### Step 9：发布验证（自动）

**阶段 ID**: `release` | **Playbook**: `release-validation`

1. 加载阶段资源：`python3 skills_loader.py context --stage release --project <project>`
2. 检查 Apollo 配置、Dubbo 接口兼容性、Kafka 消息格式、数据库变更
3. 产出 `deploy/verify.md`
4. **记录日志**：`python3 run_workflow.py log --name <name> --message "发布验证完成：Apollo <状态>，Dubbo <状态>，Kafka <状态>"`
5. 完成后运行 `python3 run_workflow.py advance --name <name>`

**Pipeline 全部完成，输出最终摘要。**

## 异常处理

| 场景 | 处理 |
|------|------|
| 飞书 API 超时 | Agent 重试，最多 3 次 |
| `mvn compile` 失败 | Agent 自修，最多 3 次 |
| 审查 MUST FIX | Agent 按意见修复，最多 2 次 |
| 测试失败 | Agent 修复，最多 3 次 |
| 超过重试上限 | 升级人工，暂停 Pipeline |
| 用户终止 | 运行 `python3 run_workflow.py status --name <name>` 记录进度 |

## 产出目录结构

```
changes/YYYYMMDD-req-<name>/
├── pipeline_state.json          # Pipeline 状态（自动维护）
├── summary.md                   # 变更摘要（完成时自动生成）
├── request/
│   ├── prd.md                   # PRD 原文
│   ├── spec.md                  # 需求规格
│   └── tasks.md                 # 任务拆分
├── impact/
│   └── impact.md                # 影响分析 + Won't Do
├── tech-design/
│   └── tech-design.md           # 技术方案
├── review/
│   └── code_review_v1.md        # 审查报告
├── tests/
│   └── test_report.md           # 测试报告
└── deploy/
    └── verify.md                # 发布验证
```

## 资源加载

阶段资源映射由 `skills.json` 统一定义（Single Source of Truth），通过 `skills_loader.py` 解析：

```bash
# 查看某阶段需要加载的资源文件路径
python3 skills_loader.py resolve --stage <stage_id> --project <project>

# 一步输出某阶段全部资源内容
python3 skills_loader.py context --stage <stage_id> --project <project>

# 校验所有注册资源文件存在性
python3 skills_loader.py check
```

`<project>` 取值：`shop-points`（默认）或 `shop-points-lottery`，由 `run_workflow.py init --target` 自动检测。

## 恢复中断的 Pipeline

如果 Pipeline 中途中断（如 Claude Code 会话结束），恢复步骤：

1. `python3 run_workflow.py status --name <name>` — 查看当前阶段
2. 从当前阶段继续执行（状态文件记录了进度）
3. 已完成的阶段会被自动跳过（产出物已存在）
