---
name: dayu-deploy
description: "通过 agent-browser CLI 在大禹平台构建部署测试环境，按 deploy_modules 顺序执行"
version: "0.1.0"
category: playbooks
tags:
  - deploy
  - dayu
  - agent-browser
commands: []
---

# Skill: 大禹测试环境部署

## 适用时机

`commit-push` 完成后，在 `e2e-browser-test` 之前。

## 前置条件

- 各目标仓库已 push `feature/<name>` 到远程
- `handoff/frontend-handoff.md` 或 `impact/impact.md` 中 `deploy_modules` 已明确
- `skills/req-to-dev/config/secrets.local.json` 已配置大禹凭证

## AgentBrowser 初始化

```bash
export AGENT_BROWSER_EXECUTABLE_PATH="$HOME/.agent-browser/browsers/chrome-149.0.7827.55/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"
export AGENT_BROWSER_HEADED=1
export AGENT_BROWSER_SESSION_NAME="req-to-dev-<change-name>"
```

## 部署顺序

读取 `deploy_modules`，严格按 `knowledge/dayu-platform.md` 顺序：

1. `shop-points`
2. `shop-points-lottery`（仅 `mall_scope != none`）
3. `store-integral-cdn`
4. `store-integral-h5-cdn`

## 部署耗时与轮询

- **后端（Java/Spring Boot）**: ~1-3 分钟（mvn package + 启动 JVM）
- **前端 CDN（PC/H5）**: ~5-15 分钟（npm build + 上传静态资源到 CDN，体积大）
- **轮询节奏**: 每 **5 分钟**刷新一次，状态由 `更新中` → `运行中` 即完成
- 单次轮询用 `agent-browser reload && agent-browser wait --load networkidle && agent-browser eval "Array.from(...).map(...)"`，避免在 JS 里 `sleep` 占住 daemon

## 单模块操作流程

```bash
# 1. 打开大禹环境页
agent-browser open "https://dayu.ke.com/env/module?name=shop-points-test01" \
  && agent-browser wait --load networkidle \
  && agent-browser snapshot -i

# 2. 若需登录 → fill 工号/密码 → click 登录按钮 → wait networkidle

# 3. 找到目标模块 → 点击「构建部署」
# 4. 选择分支 feature/<name>
# 5. 点击「构建并部署」

## ⚠️ 分支正确性校验（必须！放在点构建之前）

模块在 DOM 里的索引顺序可能因布局变化而漂移，**点错模块**+**setter 没生效**会构建出错误模块/旧分支的镜像。**点完「构建并部署」后**、**等 modal 关闭前**必须做一次硬校验：

```bash
# 校验当前 modal 的 GIT 输入框指向的仓库是不是预期仓库
agent-browser eval "JSON.stringify({git: document.querySelector('.ant-modal input[disabled]')?.value, modalTitle: document.querySelector('.ant-modal-title')?.textContent})"

# 校验分支输入框里的值（用 React 兼容方式 set 后立刻 verify）
agent-browser eval "(() => { const i = document.querySelector('input#branch'); return i ? i.value : 'no branch input'; })()"
```

**期望值（必须 match）**：

| 模块 | GIT 仓库后缀 | 分支前缀 |
|------|--------------|----------|
| shop-points | `shop-points.git` | `feature/<name>` |
| shop-points-lottery | `shop-points-lottery.git` | `feature/<name>` |
| store-integral-cdn | `store-integral.git` | `feature/<name>` |
| store-integral-h5-cdn | `store-integral-h5.git` | `feature/<name>` |

**只有 git 后缀和分支前缀都 match 才允许点「构建并部署」**。否则先 cancel modal，重新定位模块卡片上的 `构建部署` 链接（不要按固定 index 假设顺序）。

定位方法：用 `snapshot -i` 找 `heading "运行中 <module>"` 那个 ref，再沿 DOM tree 找其卡片内的 `构建部署` 链接 ref（不要依赖 `Array.from(...)[N]` 这种位置索引）。

## 6. 等待完成 → snapshot 确认「运行中」标签
```

## 轮询脚本（核心）

部署后启动轮询，单次 eval 拿所有模块状态：

```bash
poll_dayu() {
  while true; do
    STATUS=$(agent-browser eval "JSON.stringify(Array.from(document.querySelectorAll('h4')).map(h => h.textContent.trim()))" 2>/dev/null)
    echo "[$(date +%H:%M:%S)] $STATUS"
    if echo "$STATUS" | grep -q "更新中"; then
      echo "still updating, sleep 5 min..."
      sleep 300
      agent-browser reload >/dev/null 2>&1
      agent-browser wait --load networkidle >/dev/null 2>&1
    else
      echo "all modules running"
      break
    fi
  done
}
```

**为何不在 eval 里 sleep**: `agent-browser` 是单 daemon 串行通信，JS 里 `await new Promise(r => setTimeout(r, 300000))` 会让 daemon 长时间挂起、其他命令全部 timeout。用 shell `sleep 300` 释放 daemon。

## 7. 刷新验证

```bash
agent-browser reload \
  && agent-browser wait --load networkidle \
  && agent-browser snapshot -i \
  && agent-browser screenshot "deploy/<module>-running.png"
```

优先使用 `snapshot -i` 返回的 `@eN` ref 进行 `click` / `fill`；也可用：

```bash
agent-browser find role button click --name "构建并部署"
```

## 成功判定

每个模块必须：

1. 显示 **「运行中」** 标签
2. **刷新页面后**标签仍存在

否则记为失败，查后端日志：

- 终端 → `cd /data0/www/applogs/<项目名>`

## 失败处理

1. 截图 + 摘录日志写入 `deploy/dayu_deploy_report.md`
2. 运行 `run_workflow.py fail --reason "dayu deploy failed: <module>"`
3. 修复后重新 `commit-push` → 重跑 `dayu-deploy`

## 产出

`deploy/dayu_deploy_report.md`：

```markdown
# Dayu Deploy Report

## Environment
shop-points-test01

## Deploy Results

| 模块 | 分支 | 状态 | 刷新后仍运行中 | 耗时 | 备注 |
|------|------|------|----------------|------|------|
| shop-points | feature/xxx | ✅ | ✅ | 3m | |

## Screenshots
- deploy/shop-points-running.png

## Logs（失败时）
...
```

## 质量标准

- 不跳过刷新验证步骤
- 不按错误顺序部署（后端必须在前端之前）
- 凭证从 secrets 读取，不出现在报告和日志中
