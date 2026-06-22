#!/usr/bin/env python3
"""链路 1：飞书会议纪要 wiki → PRD（Pre-Pipeline，init 之前，无 req_id）。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parent / "lib"
sys.path.insert(0, str(_LIB))
sys.path.insert(0, str(Path(__file__).resolve().parent))  # 同目录 import

from collab_check_config import _print_report, run_check  # noqa: E402
from collab_common import normalize_feishu_url  # noqa: E402
from lark_cli import fetch  # noqa: E402
from patch_builder import build_meeting_plan, chat_confirm_phrase, finalize_pre_pipeline_patch, new_approval_nonce  # noqa: E402
from prd_sync_session import load_session, next_patch, patch_dir, session_id_for  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="会议纪要 wiki → PRD digest（pre-pipeline，无需 req_id）",
    )
    parser.add_argument("--meeting-url", required=True, help="飞书会议纪要 wiki/docx URL")
    parser.add_argument("--prd-url", required=True, help="飞书 PRD wiki/docx URL")
    parser.add_argument(
        "--skip-preflight", action="store_true",
        help="跳过凭证 / 权限预检（调试用）",
    )
    args = parser.parse_args()

    # 预检：凭证 / 权限
    if not args.skip_preflight:
        preflight = run_check(test_url=args.prd_url)
        if not preflight.ok:
            _print_report(preflight)
            return 1

    prd_url = normalize_feishu_url(args.prd_url)
    session = load_session(prd_url)
    patch_id, seq = next_patch(session)
    pdir = patch_dir(prd_url, patch_id)
    sid = session_id_for(prd_url)

    prd_snapshot = session_root_snapshot(prd_url)
    prd_snapshot.parent.mkdir(parents=True, exist_ok=True)
    meeting_path = pdir / "meeting.md"

    print(f"📄 阶段: pre-pipeline（尚无 req_id）")
    print(f"📄 session: {sid}")
    print(f"📄 拉取会议纪要: {args.meeting_url}")
    fetch(args.meeting_url, meeting_path)
    print(f"📄 拉取 PRD: {prd_url}")
    fetch(prd_url, prd_snapshot)

    meeting_md = meeting_path.read_text(encoding="utf-8")
    prd_md = prd_snapshot.read_text(encoding="utf-8")
    (pdir / "prd_snapshot.md").write_text(prd_md, encoding="utf-8")

    plan = build_meeting_plan(
        meeting_md,
        prd_md,
        prd_url=prd_url,
        patch_id=patch_id,
        meeting_url=args.meeting_url,
    )
    update_cmd = plan.get("update", {}).get("command", "append")
    print(f"✓ 生成 plan（update.command={update_cmd}，变更项 {len(plan.get('changes', []))} 条）")

    approval_nonce = new_approval_nonce()

    digest_prompt = "\n".join(
        [
            "# Digest Prompt · 会议纪要 → PRD（pre-pipeline）",
            "",
            f"session: {sid}",
            "",
            "## PRD URL",
            prd_url,
            "",
            "## 会议纪要 URL",
            args.meeting_url,
            "",
            "## 会议纪要正文",
            meeting_md,
            "",
            "## 当前 PRD 快照",
            prd_md[:8000],
            "",
            "## 说明",
            "本 patch 在 Pipeline init 之前生成。PRD 定稿后 RD 再执行 run_workflow init。",
        ]
    )

    cli = "skills/req-to-dev/sub_skills/collab-prd-sync/scripts/collab_prd_sync.py"
    finalize_pre_pipeline_patch(
        prd_url,
        session,
        pdir,
        patch_id=patch_id,
        seq=seq,
        plan=plan,
        source_label="飞书会议纪要",
        meta_extra={
            "source": "feishu_prd_sync",
            "meeting_url": args.meeting_url,
            "update_command": update_cmd,
            "approval_nonce": approval_nonce,
        },
        digest_prompt=digest_prompt,
        notify=(
            f"请 PM 在 Agent 对话中回复：\n"
            f"  `{chat_confirm_phrase(patch_id, approval_nonce)}`"
        ),
    )
    print(
        "\n--- PRD 定稿后的下一步（开发阶段）---\n"
        f'  python3 skills/req-to-dev/scripts/run_workflow.py init \\\n'
        f'    --url "{prd_url}" --slug <需求名> --target <项目路径>'
    )
    return 0


def session_root_snapshot(prd_url: str) -> Path:
    from prd_sync_session import session_root  # noqa: WPS433

    return session_root(prd_url) / "prd_snapshot.md"


if __name__ == "__main__":
    raise SystemExit(main())
