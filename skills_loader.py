#!/usr/bin/env python3
"""
Skills Loader - Shop Points 后端 Skill 工具集
加载和管理 skills，支持 list / info / search / exec 命令。
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional


class Skill:
    """Skill 类"""

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


class SkillsLoader:
    """Skills 加载器"""

    def __init__(self, config_path: str = 'skills.json'):
        self.config_path = Path(config_path)
        self.base_path = self.config_path.parent / 'skills'
        self.skills: Dict[str, Skill] = {}
        self.metadata = {}

    def load_all(self) -> Dict[str, Skill]:
        """加载所有 skills"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        self.metadata = config.get('metadata', {})

        for skill_config in config['skills']:
            skill = Skill(skill_config, self.base_path)
            self.skills[skill.id] = skill

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


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("使用方法:")
        print("  python skills_loader.py list                    - 列出所有 skills")
        print("  python skills_loader.py info <skill_id>         - 显示 skill 详情")
        print("  python skills_loader.py search <query>          - 搜索 skills")
        print("  python skills_loader.py exec <skill_id> <cmd> [args...] - 执行命令")
        sys.exit(1)

    action = sys.argv[1]

    config_path = Path('skills.json')
    if not config_path.exists():
        config_path = Path(__file__).parent / 'skills.json'

    loader = SkillsLoader(str(config_path))
    loader.load_all()

    if action == 'list':
        loader.print_summary()

    elif action == 'info':
        if len(sys.argv) < 3:
            print("错误: 请指定 skill ID")
            sys.exit(1)

        skill_id = sys.argv[2]
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

    elif action == 'search':
        if len(sys.argv) < 3:
            print("错误: 请指定搜索关键词")
            sys.exit(1)

        query = sys.argv[2]
        results = loader.search_skills(query=query)

        print(f"\n找到 {len(results)} 个结果:\n")
        for skill in results:
            print(f"  {skill.name} ({skill.id})")
            print(f"   {skill.description}\n")

    elif action == 'exec':
        if len(sys.argv) < 4:
            print("错误: 请指定 skill ID 和命令")
            print("用法: python skills_loader.py exec <skill_id> <command> [args...]")
            sys.exit(1)

        skill_id = sys.argv[2]
        command = sys.argv[3]
        args = sys.argv[4:]

        skill = loader.get_skill(skill_id)
        if not skill:
            print(f"错误: Skill '{skill_id}' 不存在")
            sys.exit(1)

        try:
            result = skill.execute(command, *args)
            print(result)
        except Exception as e:
            print(f"错误: {e}")
            sys.exit(1)

    else:
        print(f"错误: 未知操作 '{action}'")
        sys.exit(1)


if __name__ == '__main__':
    main()
