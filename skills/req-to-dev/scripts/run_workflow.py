#!/usr/bin/env python3
"""
req-to-dev Pipeline 状态管理器

管理 req-to-dev 9 阶段 pipeline 的状态流转：
  init    — 初始化 pipeline，创建 changes 目录和状态文件
  status  — 查看当前 pipeline 进度
  advance — 推进到下一阶段（验证产出物）
  approve — 人工审批通过（进入编码）
  reject  — 审批驳回（回退到 scope-eval 重新执行）
  fail    — 记录失败并触发恢复策略

用法:
  python3 run_workflow.py init    --url <飞书URL> --name <名称> --target <项目路径>
  python3 run_workflow.py status  --name <名称>
  python3 run_workflow.py advance --name <名称>
  python3 run_workflow.py approve --name <名称>
  python3 run_workflow.py fail    --name <名称> --reason <原因>
  python3 run_workflow.py log     --name <名称> --message <操作描述>
  python3 run_workflow.py log     --name <名称> --show
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# ─── 常量 ───────────────────────────────────────────────

CHANGES_BASE = Path("changes")

# skills.json 路径（相对于本脚本的位置）
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent.parent.parent
SKILLS_JSON = _PROJECT_ROOT / "skills.json"


def _detect_project(target_path: str) -> str:
    """根据 target_path 检测目标项目名，返回 'shop-points' 或 'shop-points-lottery'"""
    p = target_path.lower().rstrip("/")
    if "shop-points-lottery" in p:
        return "shop-points-lottery"
    return "shop-points"


def _load_stages_from_config() -> list[dict]:
    """从 skills.json 加载 pipeline stages 定义（Single Source of Truth）"""
    if not SKILLS_JSON.exists():
        print(f"ERROR: skills.json 不存在: {SKILLS_JSON}", file=sys.stderr)
        sys.exit(1)
    with open(SKILLS_JSON, "r", encoding="utf-8") as f:
        config = json.load(f)
    pipeline = config.get("pipeline")
    if not pipeline or "stages" not in pipeline:
        print("ERROR: skills.json 中缺少 pipeline.stages", file=sys.stderr)
        sys.exit(1)
    return pipeline["stages"]


def _load_resources_registry() -> dict[str, str]:
    """从 skills.json 加载资源注册表 {resource_id: entry_path}"""
    with open(SKILLS_JSON, "r", encoding="utf-8") as f:
        config = json.load(f)
    return {s["id"]: s["entry"] for s in config.get("skills", [])}


# 模块级加载（启动时读取一次）
STAGES = _load_stages_from_config()
_RESOURCES_REGISTRY = _load_resources_registry()


def _resolve_resource_id(resource_id: str, project: str) -> str | None:
    """将 resource ID 解析为文件路径。

    支持两种模式：
    1. 直接 ID 匹配
    2. ${project} 模板替换
    """
    if resource_id in _RESOURCES_REGISTRY:
        return _RESOURCES_REGISTRY[resource_id]
    if "${project}" in resource_id:
        resolved_id = resource_id.replace("${project}", project)
        if resolved_id in _RESOURCES_REGISTRY:
            return _RESOURCES_REGISTRY[resolved_id]
    return None


def _resolve_resources(resources: list[str], project: str) -> list[str]:
    """将 resource ID 列表解析为文件路径列表"""
    result = []
    for rid in resources:
        path = _resolve_resource_id(rid, project)
        if path:
            result.append(path)
    return result


def _find_change_dir(name: str) -> Path | None:
    """根据 name 查找 changes 目录（支持 YYYYMMDD-*-name 模式）"""
    if not CHANGES_BASE.exists():
        return None
    for d in sorted(CHANGES_BASE.iterdir()):
        if d.is_dir() and d.name.endswith(f"-{name}"):
            return d
    return None


def _load_state(change_dir: Path) -> dict:
    """加载 pipeline_state.json"""
    state_file = change_dir / "pipeline_state.json"
    if not state_file.exists():
        print(f"ERROR: pipeline_state.json 不存在: {state_file}", file=sys.stderr)
        sys.exit(1)
    with open(state_file, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_state(change_dir: Path, state: dict):
    """保存 pipeline_state.json"""
    state_file = change_dir / "pipeline_state.json"
    state["updated_at"] = datetime.now().isoformat()
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def _check_artifacts(change_dir: Path, stage: dict) -> tuple[bool, list[str]]:
    """检查阶段产出物是否存在，返回 (全部存在, 缺失列表)"""
    if not stage["artifacts"]:
        return True, []
    missing = [a for a in stage["artifacts"] if not (change_dir / a).exists()]
    return len(missing) == 0, missing


def _log(change_dir: Path, message: str):
    """追加日志到 pipeline.log"""
    log_file = change_dir / "pipeline.log"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")


def _duration(iso_start: str, iso_end: str) -> str:
    """计算两个 ISO 时间字符串之间的时长"""
    try:
        start = datetime.fromisoformat(iso_start)
        end = datetime.fromisoformat(iso_end)
        delta = end - start
        minutes = int(delta.total_seconds() // 60)
        seconds = int(delta.total_seconds() % 60)
        if minutes > 0:
            return f"{minutes}m{seconds}s"
        return f"{seconds}s"
    except (ValueError, TypeError):
        return "?"


def _print_stage_header(stage: dict, index: int):
    """打印阶段头信息"""
    print(f"{'='*60}")
    print(f"阶段 {index + 1}/{len(STAGES)}: {stage['name']} ({stage['id']})")
    print(f"{'='*60}")


# ─── 子命令 ─────────────────────────────────────────────


def cmd_init(args):
    """初始化 pipeline"""
    name = args.name
    today = datetime.now().strftime("%Y%m%d")
    change_name = f"{today}-req-{name}"
    change_dir = CHANGES_BASE / change_name

    if change_dir.exists():
        print(f"Change 目录已存在: {change_dir}")
        state = _load_state(change_dir)
        print(f"当前阶段: {state['stages'][state['current_stage']]['id']}")
        return

    # 创建目录结构
    for subdir in ["request", "impact", "tech-design", "review", "tests", "deploy", "coding"]:
        (change_dir / subdir).mkdir(parents=True, exist_ok=True)

    # 初始化状态
    state = {
        "name": name,
        "change_dir": str(change_dir),
        "trigger": {"type": "manual", "url": args.url},
        "target_path": args.target,
        "project": _detect_project(args.target),
        "current_stage": 0,
        "stages": [
            {
                "id": s["id"],
                "name": s["name"],
                "status": "pending",
                "blocking": s["blocking"],
                "started_at": None,
                "completed_at": None,
                "retry_count": 0,
                "fail_reason": None,
            }
            for s in STAGES
        ],
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    state["stages"][0]["status"] = "running"
    state["stages"][0]["started_at"] = datetime.now().isoformat()

    _save_state(change_dir, state)
    _log(change_dir, f'INIT pipeline "{name}" target={args.target} project={state["project"]}')
    _log(change_dir, f'STAGE fetch-prd → running')

    print(f"Pipeline 已初始化: {change_dir}")
    print()
    _print_stage_header(STAGES[0], 0)
    print(f"  状态: running")
    project = _detect_project(args.target)
    resolved = _resolve_resources(STAGES[0].get("resources", []), project)
    if resolved:
        print(f"  加载规范: {', '.join(resolved)}")
    print(f"  产出物: {', '.join(STAGES[0]['artifacts']) or '(无固定文件)'}")
    print()
    print(">>> AGENT: 执行阶段 fetch-prd（调用 feishu-doc-fetcher 获取 PRD）")
    print(f">>> 完成后运行: python3 {sys.argv[0]} advance --name {name}")


def cmd_status(args):
    """查看 pipeline 状态"""
    change_dir = _find_change_dir(args.name)
    if not change_dir:
        print(f"ERROR: 找不到 change 目录: *-{args.name}", file=sys.stderr)
        sys.exit(1)

    state = _load_state(change_dir)
    print(f"Pipeline: {state['name']}")
    print(f"目录: {change_dir}")
    print()

    for i, stage in enumerate(state["stages"]):
        status_icons = {
            "pending": "⬜",
            "running": "▶️ ",
            "completed": "✅",
            "blocked": "🚫",
            "retrying": "🔄",
            "escalated": "⚠️ ",
            "failed": "❌",
        }
        icon = status_icons.get(stage["status"], "❓")
        marker = " ← 当前" if i == state["current_stage"] else ""
        blocking = " [阻塞]" if stage["blocking"] else ""
        print(f"  {icon} {stage['id']:<15} {stage['status']:<12}{blocking}{marker}")

    print()

    # 当前阶段详情
    current = state["stages"][state["current_stage"]]
    stage_def = STAGES[state["current_stage"]]
    print(f"当前阶段: {current['name']} ({current['id']})")
    print(f"  状态: {current['status']}")
    if stage_def.get("resources"):
        project = state.get("project", "shop-points")
        resolved = _resolve_resources(stage_def["resources"], project)
        print(f"  需加载: {', '.join(resolved)}")
    if stage_def["artifacts"]:
        print(f"  产出物: {', '.join(stage_def['artifacts'])}")

    # 产出物检查
    ok, missing = _check_artifacts(change_dir, stage_def)
    if stage_def["artifacts"]:
        if ok:
            print(f"  产出物状态: ✅ 全部就绪")
        else:
            print(f"  产出物状态: ❌ 缺失 {', '.join(missing)}")


def cmd_advance(args):
    """推进到下一阶段"""
    change_dir = _find_change_dir(args.name)
    if not change_dir:
        print(f"ERROR: 找不到 change 目录: *-{args.name}", file=sys.stderr)
        sys.exit(1)

    state = _load_state(change_dir)
    idx = state["current_stage"]
    current = state["stages"][idx]
    stage_def = STAGES[idx]

    # 0. 如果当前阶段已完成（如 approve 后），直接推进到下一阶段
    if current["status"] == "completed":
        return _advance_to_next(change_dir, state, idx, args.name)

    # 1. 如果当前阶段是阻塞的且未完成，拒绝 advance
    if current["blocking"]:
        print(f"BLOCKING: 当前阶段 {current['id']} 需要人工审批")
        print(f">>> 请用户审批后运行: python3 {sys.argv[0]} approve --name {args.name}")
        sys.exit(0)

    # 2. 检查当前阶段状态
    if current["status"] not in ("running", "retrying"):
        print(f"ERROR: 当前阶段状态为 {current['status']}，无法推进", file=sys.stderr)
        sys.exit(1)

    # 3. 检查产出物（如果有）
    ok, missing = _check_artifacts(change_dir, stage_def)
    if not ok:
        print(f"ERROR: 产出物未就绪，缺失: {', '.join(missing)}", file=sys.stderr)
        print(">>> 请先完成当前阶段的产出物，再运行 advance")
        sys.exit(1)

    # 4. 标记当前阶段完成
    current["status"] = "completed"
    current["completed_at"] = datetime.now().isoformat()
    artifacts_str = ", ".join(stage_def["artifacts"]) if stage_def["artifacts"] else "代码 diff"
    dur = _duration(current.get("started_at", ""), current["completed_at"])
    _log(change_dir, f'STAGE {current["id"]} → completed ({dur}, artifacts: {artifacts_str})')
    print(f"✅ 阶段 {current['id']} 完成")

    return _advance_to_next(change_dir, state, idx, args.name)


def _advance_to_next(change_dir: Path, state: dict, idx: int, name: str):
    """从已完成的阶段推进到下一阶段"""
    project = state.get("project", "shop-points")

    # 已是最后一个阶段？
    if idx >= len(STAGES) - 1:
        _save_state(change_dir, state)
        created = state.get("created_at", "")
        total_dur = _duration(created, datetime.now().isoformat())
        _log(change_dir, f"PIPELINE COMPLETED (总耗时 {total_dur})")
        print(f"✅ Pipeline 全部完成！")
        print(f"Change 目录: {change_dir}")
        # 更新 summary.md
        summary_file = change_dir / "summary.md"
        with open(summary_file, "w", encoding="utf-8") as f:
            f.write(f"# Change 摘要: {state['name']}\n\n")
            f.write(f"状态: ✅ 已完成\n\n")
            f.write("## 阶段记录\n\n")
            for s in state["stages"]:
                status_mark = "✅" if s["status"] == "completed" else s["status"]
                f.write(f"- {status_mark} {s['id']}")
                if s.get("completed_at"):
                    f.write(f" (完成于 {s['completed_at']})")
                f.write("\n")
        return

    # 推进到下一阶段
    next_idx = idx + 1
    next_stage = state["stages"][next_idx]
    next_def = STAGES[next_idx]

    # 跳过已有产出物的阶段
    if next_def["artifacts"] and not next_stage["blocking"]:
        skip_ok, _ = _check_artifacts(change_dir, next_def)
        if skip_ok:
            next_stage["status"] = "completed"
            next_stage["completed_at"] = datetime.now().isoformat()
            state["current_stage"] = next_idx
            _save_state(change_dir, state)
            _log(change_dir, f'SKIP {next_stage["id"]} (产出物已存在)')
            print(f"⏭  跳过阶段 {next_stage['id']}（产出物已存在）")
            # 递归推进
            return _advance_to_next(change_dir, state, next_idx, name)

    next_stage["status"] = "running"
    next_stage["started_at"] = datetime.now().isoformat()
    state["current_stage"] = next_idx
    _save_state(change_dir, state)

    # 日志
    if next_stage["blocking"]:
        _log(change_dir, f'BLOCKING {next_stage["id"]} — 等待人工审批')
    else:
        resolved = _resolve_resources(next_def.get("resources", []), project)
        loaded = f" (loaded: {', '.join(resolved)})" if resolved else ""
        _log(change_dir, f'STAGE {next_stage["id"]} → running{loaded}')

    print()
    _print_stage_header(next_def, next_idx)

    if next_stage["blocking"]:
        print(f"  状态: 🔒 阻塞 — 等待人工审批")
        print()
        print("BLOCKING: 需要人工审批")
        print()
        print(">>> 请向用户展示以下内容并请求审批：")
        print("    - request/spec.md        需求规格")
        print("    - impact/impact.md       影响范围（含 Won't Do）")
        print("    - tech-design/tech-design.md  技术方案")
        print(f">>> 审批通过: python3 {sys.argv[0]} approve --name {name}")
        print(f">>> 审批驳回: python3 {sys.argv[0]} reject --name {name} --reason \"<修改意见>\"")
    else:
        print(f"  状态: running")
        if next_def.get("resources"):
            resolved = _resolve_resources(next_def["resources"], project)
            print(f"  加载规范: {', '.join(resolved)}")
        print(f"  产出物: {', '.join(next_def['artifacts']) or '(无固定文件)'}")
        print()
        print(f">>> AGENT: 执行阶段 {next_stage['id']}")
        print(f">>> 资源加载: python3 {_PROJECT_ROOT}/skills_loader.py context --stage {next_stage['id']} --project {project}")
        print(f">>> 完成后运行: python3 {sys.argv[0]} advance --name {name}")


def cmd_approve(args):
    """人工审批通过"""
    change_dir = _find_change_dir(args.name)
    if not change_dir:
        print(f"ERROR: 找不到 change 目录: *-{args.name}", file=sys.stderr)
        sys.exit(1)

    state = _load_state(change_dir)
    idx = state["current_stage"]
    current = state["stages"][idx]

    if not current["blocking"]:
        print(f"ERROR: 当前阶段 {current['id']} 不是阻塞阶段，无需审批", file=sys.stderr)
        sys.exit(1)

    # 标记完成
    current["status"] = "completed"
    current["completed_at"] = datetime.now().isoformat()
    _save_state(change_dir, state)
    _log(change_dir, f'APPROVED {current["id"]}')
    print(f"✅ 审批通过: {current['id']}")

    # 推进到下一阶段
    print()
    _advance_to_next(change_dir, state, idx, args.name)


def cmd_reject(args):
    """审批不通过，回退到 scope-eval 重新执行"""
    change_dir = _find_change_dir(args.name)
    if not change_dir:
        print(f"ERROR: 找不到 change 目录: *-{args.name}", file=sys.stderr)
        sys.exit(1)

    state = _load_state(change_dir)
    idx = state["current_stage"]
    current = state["stages"][idx]

    if not current["blocking"]:
        print(f"ERROR: 当前阶段 {current['id']} 不是阻塞阶段，无法驳回", file=sys.stderr)
        sys.exit(1)

    # 找到 scope-eval 阶段的索引
    scope_eval_idx = None
    for i, s in enumerate(state["stages"]):
        if s["id"] == "scope-eval":
            scope_eval_idx = i
            break

    if scope_eval_idx is None:
        print("ERROR: 找不到 scope-eval 阶段", file=sys.stderr)
        sys.exit(1)

    # 重置 scope-eval 和 tech-design 为 pending
    feedback_stages = []
    for i in range(scope_eval_idx, idx + 1):
        stage = state["stages"][i]
        stage["status"] = "pending"
        stage["started_at"] = None
        stage["completed_at"] = None
        stage["retry_count"] = 0
        stage["fail_reason"] = None
        feedback_stages.append(stage["id"])

    # 从 scope-eval 重新开始
    state["stages"][scope_eval_idx]["status"] = "running"
    state["stages"][scope_eval_idx]["started_at"] = datetime.now().isoformat()
    state["current_stage"] = scope_eval_idx

    _save_state(change_dir, state)
    _log(change_dir, f'REJECTED plan-approve: {args.reason} → 回退到 scope-eval 重新执行')

    print(f"🔄 审批驳回: {args.reason}")
    print(f"   回退阶段: {' → '.join(feedback_stages)}")
    print()
    print(">>> AGENT: 根据 feedback 重新执行 scope-eval → tech-design")
    print(f">>> 完成后运行: python3 {sys.argv[0]} advance --name {args.name}")


def cmd_log(args):
    """记录 Agent 操作日志或查看日志"""
    change_dir = _find_change_dir(args.name)
    if not change_dir:
        print(f"ERROR: 找不到 change 目录: *-{args.name}", file=sys.stderr)
        sys.exit(1)

    if args.show:
        log_file = change_dir / "pipeline.log"
        if not log_file.exists():
            print("(无日志)")
            return
        with open(log_file, "r", encoding="utf-8") as f:
            print(f.read(), end="")
        return

    if args.message:
        _log(change_dir, f'AGENT: {args.message}')
        return

    print("ERROR: 需要 --message 或 --show", file=sys.stderr)
    sys.exit(1)


def cmd_fail(args):
    """记录失败并触发恢复策略"""
    change_dir = _find_change_dir(args.name)
    if not change_dir:
        print(f"ERROR: 找不到 change 目录: *-{args.name}", file=sys.stderr)
        sys.exit(1)

    state = _load_state(change_dir)
    idx = state["current_stage"]
    current = state["stages"][idx]
    stage_def = STAGES[idx]

    current["retry_count"] += 1
    current["fail_reason"] = args.reason

    retry_limit = stage_def["max_retries"]

    if current["retry_count"] <= retry_limit:
        current["status"] = "running"
        _save_state(change_dir, state)
        _log(change_dir, f'FAIL {current["id"]}: {args.reason} (retry {current["retry_count"]}/{retry_limit})')
        print(f"RETRY: 阶段 {current['id']} 失败（第 {current['retry_count']}/{retry_limit} 次重试）")
        print(f"  原因: {args.reason}")
        print()
        print(f">>> AGENT: 重新执行阶段 {current['id']}")
        print(f">>> 完成后运行: python3 {sys.argv[0]} advance --name {args.name}")
    else:
        current["status"] = "escalated"
        _save_state(change_dir, state)
        _log(change_dir, f'ESCALATED {current["id"]}: {args.reason} (retries exhausted: {current["retry_count"]})')
        print(f"ESCALATED: 阶段 {current['id']} 超过最大重试次数 ({retry_limit})")
        print(f"  原因: {args.reason}")
        print(f"  重试: {current['retry_count']} 次")
        print()
        print(">>> 需要人工介入。修复后运行:")
        print(f"    python3 {sys.argv[0]} advance --name {args.name}")

        # 写入 summary
        summary_file = change_dir / "summary.md"
        with open(summary_file, "a", encoding="utf-8") as f:
            f.write(f"\n## ⚠️ Pipeline 阻塞\n\n")
            f.write(f"阶段 `{current['id']}` 失败并升级人工介入。\n")
            f.write(f"- 原因: {args.reason}\n")
            f.write(f"- 重试: {current['retry_count']} 次\n")


# ─── CLI ────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="req-to-dev Pipeline 状态管理器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # init
    p_init = subparsers.add_parser("init", help="初始化 pipeline")
    p_init.add_argument("--url", required=True, help="飞书文档 URL")
    p_init.add_argument("--name", required=True, help="需求名称")
    p_init.add_argument("--target", required=True, help="目标项目路径")

    # status
    p_status = subparsers.add_parser("status", help="查看 pipeline 状态")
    p_status.add_argument("--name", required=True, help="需求名称")

    # advance
    p_advance = subparsers.add_parser("advance", help="推进到下一阶段")
    p_advance.add_argument("--name", required=True, help="需求名称")

    # approve
    p_approve = subparsers.add_parser("approve", help="人工审批通过")
    p_approve.add_argument("--name", required=True, help="需求名称")

    # reject
    p_reject = subparsers.add_parser("reject", help="审批驳回，回退到 scope-eval 重新执行")
    p_reject.add_argument("--name", required=True, help="需求名称")
    p_reject.add_argument("--reason", required=True, help="驳回原因/修改意见")

    # fail
    p_fail = subparsers.add_parser("fail", help="记录失败")
    p_fail.add_argument("--name", required=True, help="需求名称")
    p_fail.add_argument("--reason", required=True, help="失败原因")

    # log
    p_log = subparsers.add_parser("log", help="记录操作日志或查看日志")
    p_log.add_argument("--name", required=True, help="需求名称")
    p_log.add_argument("--message", help="Agent 操作描述")
    p_log.add_argument("--show", action="store_true", help="显示完整日志")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "init": cmd_init,
        "status": cmd_status,
        "advance": cmd_advance,
        "approve": cmd_approve,
        "reject": cmd_reject,
        "fail": cmd_fail,
        "log": cmd_log,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
