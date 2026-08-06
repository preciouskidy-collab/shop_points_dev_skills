#!/usr/bin/env python3
"""链路1 bootstrap：飞书 PRD + 会议纪要 → req_id + changes/{req_id}/。"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

_LIB = Path(__file__).resolve().parent / "lib"
_SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_LIB))
sys.path.insert(0, str(_SCRIPTS))

from agent_client import AgentClient  # noqa: E402
from collab_common import (  # noqa: E402
    CHANGES_BASE,
    append_log,
    iso_now,
    load_state,
    normalize_feishu_url,
    save_state,
)
from collab_push_state import push_state_for_change  # noqa: E402
from collab_repos import (  # noqa: E402
    apply_scope_hint,
    load_scope_hint,
    write_scope_hint_template,
)
from lark_cli import fetch  # noqa: E402
from run_workflow import STAGES  # noqa: E402
from slug_utils import (  # noqa: E402
    extract_prd_title,
    generate_req_id,
    normalize_slug,
    repair_change_dir_req_id,
    slugify,
)


def _create_change_dirs(change_dir: Path) -> None:
    for subdir in [
        "request",
        "impact",
        "tech-design",
        "review",
        "tests",
        "deploy",
        "coding",
        "handoff",
        "collaboration",
    ]:
        (change_dir / subdir).mkdir(parents=True, exist_ok=True)


def _new_pipeline_state(
    *,
    req_id: str,
    slug: str,
    prd_url: str,
    meeting_url: str,
) -> dict:
    now = datetime.now().isoformat()
    return {
        "req_id": req_id,
        "slug": slug,
        "name": req_id,
        "change_dir": str(CHANGES_BASE / req_id),
        "trigger": {
            "type": "meeting",
            "url": prd_url,
            "meeting_url": meeting_url,
        },
        "target_path": None,
        "project": None,
        "branch": f"feature/{req_id}",
        "surfaces": [],
        "collaboration": {
            "phase": "prd_review",
            "binding_status": None,
            "group_id": None,
            "last_patch_seq": 0,
            "patches": {},
            "prd_review": {
                "started_at": iso_now(),
                "ended_at": None,
                "active_patch": None,
                "revision_round": 0,
                "revision_cursor": iso_now(),
                "last_preview_at": None,
            },
            "collab": {
                "started_at": None,
                "digest_cursor": None,
            },
        },
        "prd_resync": {},
        "repos": {},
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
        "created_at": now,
        "updated_at": now,
        "bootstrap_at": iso_now(),
    }


def _bootstrap_new(args: argparse.Namespace) -> int:
    prd_url = normalize_feishu_url(args.prd_url)
    meeting_url = normalize_feishu_url(args.meeting_url)

    prd_draft = Path("changes/.bootstrap_prd.md")
    prd_draft.parent.mkdir(parents=True, exist_ok=True)
    print(f"📄 拉取 PRD: {prd_url}")
    fetch(prd_url, prd_draft)
    prd_md = prd_draft.read_text(encoding="utf-8")
    title = extract_prd_title(prd_md)
    try:
        slug = normalize_slug(args.slug) if args.slug else slugify(title)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    try:
        req_id = generate_req_id(slug)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    change_dir = CHANGES_BASE / req_id

    if change_dir.exists():
        print(f"ERROR: 目录已存在: {change_dir}", file=sys.stderr)
        return 1

    _create_change_dirs(change_dir)
    prd_path = change_dir / "request" / "prd.md"
    prd_path.write_text(prd_md, encoding="utf-8")
    prd_draft.unlink(missing_ok=True)

    state = _new_pipeline_state(
        req_id=req_id,
        slug=slug,
        prd_url=prd_url,
        meeting_url=meeting_url,
    )

    if args.project and args.target:
        hint = {
            "project": args.project,
            "target_path": args.target,
            "surfaces": [s.strip() for s in args.surfaces.split(",") if s.strip()],
            "inference_note": "CLI 手动指定",
        }
        state = apply_scope_hint(state, hint)

    save_state(change_dir, state)
    write_scope_hint_template(change_dir)
    append_log(change_dir, f"BOOTSTRAP req_id={req_id} slug={slug} meeting={meeting_url}")

    print(f"✓ req_id: {req_id}")
    print(f"✓ slug: {slug}")
    print(f"✓ PRD 标题: {title}")
    print(f"✓ 工作区: {change_dir}")
    print("\n--- 下一步（须按顺序，禁止跳步）---")
    print(f"1. 企微群发送: /init {req_id}")
    print("2. 绑群完成后回复「绑群完成」")
    print("3. （可选）填写 scope_hint.json → bootstrap --req-id ... --apply-scope-hint")
    print(
        f"4. binding-check:\n"
        f"   python3 skills/req-to-dev/sub_skills/collab-prd-sync/scripts/collab_prd_sync.py "
        f"binding-check --req-id {req_id}"
    )
    print("5. binding-check 通过后 → meeting → finalize-plan → push-preview（默认含 wait）")
    print("   未绑群时 meeting / push-preview 会报错拒绝执行")

    try:
        push_state_for_change(change_dir, state)
        print("✓ 已同步 phase=prd_review 到 Agent")
    except RuntimeError as e:
        print(f"WARN: push-state 失败（可稍后重试）: {e}")

    return 0


def _apply_scope_hint(args: argparse.Namespace) -> int:
    from collab_common import find_change_dir  # noqa: WPS433

    change_dir = find_change_dir(args.req_id)
    state = load_state(change_dir)

    if args.scope_hint_json:
        hint = json.loads(args.scope_hint_json)
        (change_dir / "scope_hint.json").write_text(
            json.dumps(hint, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    else:
        hint = load_scope_hint(change_dir)
        if not hint:
            print(
                "ERROR: 缺少 scope_hint.json 或内容未填写（需 project / target_path）",
                file=sys.stderr,
            )
            return 1

    state = apply_scope_hint(state, hint)
    save_state(change_dir, state)
    append_log(change_dir, f"SCOPE_HINT applied project={state.get('project')}")
    print(f"✓ project: {state.get('project')}")
    print(f"✓ target_path: {state.get('target_path')}")
    return 0


def _repair_req_id(args: argparse.Namespace) -> int:
    from collab_common import append_log, find_change_dir  # noqa: WPS433

    try:
        change_dir = find_change_dir(args.repair_req_id)
        new_req_id, slug = repair_change_dir_req_id(
            change_dir,
            new_slug=args.slug,
        )
        change_dir = change_dir.parent / new_req_id
    except (RuntimeError, FileNotFoundError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    append_log(change_dir, f"REPAIR_REQ_ID {args.repair_req_id} -> {new_req_id} slug={slug}")
    print(f"✓ 已修复 req_id: {args.repair_req_id} → {new_req_id}")
    print(f"✓ slug: {slug}")
    print(f"✓ 工作区: changes/{new_req_id}")
    print(f"\n请在企微群发送: /init {new_req_id}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="链路1 bootstrap（评审期立项）")
    parser.add_argument("--prd-url", default=None)
    parser.add_argument("--meeting-url", default=None)
    parser.add_argument("--slug", default=None, help="覆盖自动 slug（仅 ASCII a-z0-9-）")
    parser.add_argument("--req-id", default=None, help="续跑：应用 scope_hint")
    parser.add_argument(
        "--repair-req-id",
        default=None,
        help="修复非法 req_id（如含中文 slug），重命名 changes 目录",
    )
    parser.add_argument("--apply-scope-hint", action="store_true")
    parser.add_argument("--scope-hint-json", default=None, help="内联 scope_hint JSON")
    parser.add_argument("--project", default=None, help="手动覆盖 project")
    parser.add_argument("--target", default=None, help="手动覆盖 target_path")
    parser.add_argument("--surfaces", default="h5", help="手动覆盖 surfaces，逗号分隔")
    args = parser.parse_args()

    if args.repair_req_id:
        return _repair_req_id(args)

    if args.apply_scope_hint or args.scope_hint_json:
        if not args.req_id:
            print("ERROR: --apply-scope-hint 需要 --req-id", file=sys.stderr)
            return 1
        return _apply_scope_hint(args)

    if not args.prd_url or not args.meeting_url:
        print("ERROR: 新建 bootstrap 需要 --prd-url 与 --meeting-url", file=sys.stderr)
        return 1
    return _bootstrap_new(args)


if __name__ == "__main__":
    raise SystemExit(main())
