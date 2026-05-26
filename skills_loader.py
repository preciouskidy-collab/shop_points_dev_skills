#!/usr/bin/env python3
"""
Skills Loader - Shop Points 后端 Skill 工具集
加载和管理 skills，支持 list / info / search / resolve / context / check 命令。

核心职责：
  - skills.json 是资源注册 + pipeline stage 映射的 Single Source of Truth
  - resolve  解析某阶段需要加载的资源文件路径（按项目替换）
  - context  一步输出某阶段全部资源内容（减少 Claude Code 的 Read 调用）
  - check    校验所有注册资源的文件存在性
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional


class Skill:
    """Skill / Resource 条目"""

    def __init__(self, config: Dict[str, Any], base_path: Path):
        self.id = config['id']
        self.name = config['name']
        self.description = config['description']
        self.version = config['version']
        self.category = config['category']
        self.tags = config.get('tags', [])
        self.entry = base_path / config['entry']
        self.commands = config.get('commands', [])
        self.references = [base_path / ref for ref in config.get('references', [])]
        self.config = config.get('config', {})

    def list_commands(self) -> List[str]:
        return [cmd['name'] for cmd in self.commands]

    def get_command(self, name: str) -> Optional[Dict[str, Any]]:
        for cmd in self.commands:
            if cmd['name'] == name:
                return cmd
        return None

    def execute(self, command_name: str, *args) -> str:
        """执行 skill 命令"""
        cmd = self.get_command(command_name)
        if not cmd:
            raise ValueError(f"Command '{command_name}' not found in skill '{self.id}'")

        script_path = self.entry / cmd['script']
        if not script_path.exists():
            raise FileNotFoundError(f"Script not found: {script_path}")

        import subprocess as sp
        _cmd = [sys.executable, str(script_path)] + list(args)
        proc = sp.run(_cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            return f"<Skill {self.id}: {self.name}>"
        return proc.stdout


class PipelineConfig:
    """Pipeline 阶段配置"""

    def __init__(self, pipeline_data: Dict[str, Any], base_path: Path):
        self.stages = pipeline_data.get('stages', [])
        self.base_path = base_path

    def get_stage(self, stage_id: str) -> Optional[Dict[str, Any]]:
        for s in self.stages:
            if s['id'] == stage_id:
                return s
        return None

    def list_stage_ids(self) -> List[str]:
        return [s['id'] for s in self.stages]


class SkillsLoader:
    """Skills 加载器"""

    def __init__(self, config_path: str = 'skills.json'):
        self.config_path = Path(config_path)
        self.base_path = self.config_path.parent
        self.skills: Dict[str, Skill] = {}
        self.pipeline: Optional[PipelineConfig] = None
        self.metadata = {}

    def load_all(self) -> Dict[str, Skill]:
        """加载所有 skills 和 pipeline 配置"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        self.metadata = config.get('metadata', {})

        for skill_config in config.get('skills', []):
            skill = Skill(skill_config, self.base_path)
            self.skills[skill.id] = skill

        pipeline_data = config.get('pipeline')
        if pipeline_data:
            self.pipeline = PipelineConfig(pipeline_data, self.base_path)

        return self.skills

    def get_skill(self, skill_id: str) -> Optional[Skill]:
        """获取指定 skill"""
        return self.skills.get(skill_id)

    def list_skills(self) -> List[str]:
        """列出所有 skill IDs"""
        return list(self.skills.keys())

    def search_skills(self, query: str = None, category: str = None, tag: str = None) -> List[Skill]:
        """搜索 skills"""
        results = []
        for skill in self.skills.values():
            if query and query.lower() not in skill.name.lower() and query.lower() not in skill.description.lower():
                continue
            if category and skill.category != category:
                continue
            if tag and tag not in skill.tags:
                continue
            results.append(skill)
        return results

    def resolve_resource_id(self, resource_id: str, project: str = None) -> Optional[Path]:
        """将 resource ID 解析为文件路径。

        支持两种模式：
        1. 直接 ID 匹配：resource_id 与 skills.json 中的 id 完全一致
        2. 模板替换：resource_id 包含 ${project}，替换为项目名后匹配
        """
        # 尝试直接匹配
        skill = self.skills.get(resource_id)
        if skill:
            return skill.entry

        # 尝试 ${project} 模板替换
        if project and '${project}' in resource_id:
            resolved_id = resource_id.replace('${project}', project)
            skill = self.skills.get(resolved_id)
            if skill:
                return skill.entry

        return None

    def resolve_stage_resources(self, stage_id: str, project: str = 'shop-points') -> List[Path]:
        """解析某阶段全部资源文件路径"""
        if not self.pipeline:
            return []
        stage = self.pipeline.get_stage(stage_id)
        if not stage:
            return []
        paths = []
        for rid in stage.get('resources', []):
            path = self.resolve_resource_id(rid, project)
            if path:
                paths.append(path)
        return paths

    def get_stage_config(self, stage_id: str) -> Optional[Dict[str, Any]]:
        """获取某阶段的完整配置"""
        if not self.pipeline:
            return None
        return self.pipeline.get_stage(stage_id)

    def print_summary(self):
        """打印 skills 摘要"""
        print("\n" + "=" * 60)
        print(f"Shop Points 后端 Skill 工具集 - v{self.metadata.get('version', 'unknown')}")
        print("=" * 60 + "\n")

        print(f"Total Skills: {len(self.skills)}\n")

        for skill in self.skills.values():
            print(f"  {skill.name} ({skill.id})")
            print(f"   {skill.description}")
            print(f"   Category: {skill.category}")
            print(f"   Version: {skill.version}")
            print(f"   Commands: {', '.join(skill.list_commands())}")
            print()

        if self.pipeline:
            print(f"Pipeline Stages: {len(self.pipeline.stages)}")
            for s in self.pipeline.stages:
                res_count = len(s.get('resources', []))
                print(f"  {s['id']:<15} resources={res_count}  blocking={s.get('blocking', False)}")
            print()


# ─── 子命令 ─────────────────────────────────────────────


def cmd_list(loader: SkillsLoader, args):
    """列出所有 skills"""
    loader.print_summary()


def cmd_info(loader: SkillsLoader, args):
    """显示 skill 详情"""
    skill_id = args.skill_id
    skill = loader.get_skill(skill_id)
    if not skill:
        print(f"错误: Skill '{skill_id}' 不存在")
        sys.exit(1)

    print(f"\n{skill.name}")
    print("=" * 60)
    print(f"ID: {skill.id}")
    print(f"描述: {skill.description}")
    print(f"版本: {skill.version}")
    print(f"分类: {skill.category}")
    print(f"标签: {', '.join(skill.tags)}")
    print(f"\n可用命令:")
    for cmd in skill.commands:
        print(f"\n  {cmd['name']}")
        print(f"    {cmd['description']}")
        print(f"    用法: {cmd['usage']}")
        if 'examples' in cmd:
            print(f"    示例:")
            for example in cmd['examples']:
                print(f"      {example}")


def cmd_search(loader: SkillsLoader, args):
    """搜索 skills"""
    query = args.query
    results = loader.search_skills(query=query)
    print(f"\n找到 {len(results)} 个结果:\n")
    for skill in results:
        print(f"  {skill.name} ({skill.id})")
        print(f"   {skill.description}\n")


def cmd_resolve(loader: SkillsLoader, args):
    """解析某阶段需要加载的资源文件路径"""
    stage_id = args.stage
    project = args.project

    stage = loader.get_stage_config(stage_id)
    if not stage:
        print(f"错误: 未找到阶段 '{stage_id}'", file=sys.stderr)
        print(f"可用阶段: {', '.join(loader.pipeline.list_stage_ids())}", file=sys.stderr)
        sys.exit(1)

    paths = loader.resolve_stage_resources(stage_id, project)
    if not paths:
        print(f"(阶段 {stage_id} 无需加载资源)")
        return

    for p in paths:
        print(p)


def cmd_context(loader: SkillsLoader, args):
    """一步输出某阶段全部资源内容"""
    stage_id = args.stage
    project = args.project

    stage = loader.get_stage_config(stage_id)
    if not stage:
        print(f"错误: 未找到阶段 '{stage_id}'", file=sys.stderr)
        print(f"可用阶段: {', '.join(loader.pipeline.list_stage_ids())}", file=sys.stderr)
        sys.exit(1)

    paths = loader.resolve_stage_resources(stage_id, project)
    if not paths:
        print(f"(阶段 {stage_id} 无需加载资源)")
        return

    for p in paths:
        if not p.exists():
            print(f"WARNING: 文件不存在: {p}", file=sys.stderr)
            continue
        print(f"# {'=' * 60}")
        print(f"# Resource: {p}")
        print(f"# {'=' * 60}")
        print()
        with open(p, 'r', encoding='utf-8') as f:
            print(f.read())
        print()


def cmd_check(loader: SkillsLoader, args):
    """校验所有注册资源的文件存在性"""
    errors = []
    warnings = []

    # 检查所有 skill/resource 的 entry 文件
    for skill in loader.skills.values():
        if not skill.entry.exists():
            errors.append(f"MISSING: {skill.id} → {skill.entry}")

    # 检查 pipeline 中引用的 resource ID 是否都能解析
    if loader.pipeline:
        projects = ['shop-points', 'shop-points-lottery']
        for stage in loader.pipeline.stages:
            for rid in stage.get('resources', []):
                for proj in projects:
                    path = loader.resolve_resource_id(rid, proj)
                    if path is None:
                        errors.append(f"UNRESOLVED: stage={stage['id']} resource={rid} project={proj}")
                    elif not path.exists():
                        warnings.append(f"MISSING FILE: stage={stage['id']} resource={rid} → {path}")

    print(f"资源总数: {len(loader.skills)}")
    if loader.pipeline:
        print(f"Pipeline 阶段: {len(loader.pipeline.stages)}")

    if errors:
        print(f"\n❌ 错误 ({len(errors)}):")
        for e in errors:
            print(f"  {e}")
    if warnings:
        print(f"\n⚠️  警告 ({len(warnings)}):")
        for w in warnings:
            print(f"  {w}")
    if not errors and not warnings:
        print("\n✅ 所有资源检查通过")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="Skills Loader - Shop Points 后端 Skill 工具集",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # list
    subparsers.add_parser("list", help="列出所有 skills")

    # info
    p_info = subparsers.add_parser("info", help="显示 skill 详情")
    p_info.add_argument("skill_id", help="Skill ID")

    # search
    p_search = subparsers.add_parser("search", help="搜索 skills")
    p_search.add_argument("query", help="搜索关键词")

    # resolve
    p_resolve = subparsers.add_parser("resolve", help="解析某阶段的资源文件路径")
    p_resolve.add_argument("--stage", required=True, help="阶段 ID")
    p_resolve.add_argument("--project", default="shop-points", help="目标项目 (shop-points / shop-points-lottery)")

    # context
    p_context = subparsers.add_parser("context", help="输出某阶段全部资源内容")
    p_context.add_argument("--stage", required=True, help="阶段 ID")
    p_context.add_argument("--project", default="shop-points", help="目标项目 (shop-points / shop-points-lottery)")

    # check
    subparsers.add_parser("check", help="校验所有注册资源的文件存在性")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    config_path = Path('skills.json')
    if not config_path.exists():
        config_path = Path(__file__).parent / 'skills.json'

    loader = SkillsLoader(str(config_path))
    loader.load_all()

    commands = {
        "list": cmd_list,
        "info": cmd_info,
        "search": cmd_search,
        "resolve": cmd_resolve,
        "context": cmd_context,
        "check": cmd_check,
    }
    commands[args.command](loader, args)


if __name__ == '__main__':
    main()
