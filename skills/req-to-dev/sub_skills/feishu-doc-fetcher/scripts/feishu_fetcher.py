#!/usr/bin/env python3
"""
飞书文档获取器
直连飞书开放平台 API，使用 tenant_access_token 获取文档内容并下载图片到本地。
应用凭证从本地配置文件 ~/.shop-points-dev-skills/feishu-config.json 读取，不存入代码库。
"""

import re
import json
import base64
import time
import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from urllib.parse import quote


# ── 配置 ──────────────────────────────────────────────

FEISHU_BASE = "https://open.feishu.cn"
CONFIG_PATH = Path.home() / ".shop-points-dev-skills" / "feishu-config.json"


# ── 数据类 ────────────────────────────────────────────

@dataclass
class DocumentContent:
    """文档内容容器"""
    title: str
    markdown: str
    image_count: int
    raw_json: dict = field(default_factory=dict)


# ── 凭证管理 ──────────────────────────────────────────

class CredentialManager:
    """飞书应用凭证管理器，从本地配置文件读取 app_id/app_secret"""

    @staticmethod
    def load(app_id: str = "", app_secret: str = "") -> Tuple[str, str]:
        """
        读取凭证，返回 (app_id, app_secret)。
        优先使用传入参数，其次读取配置文件。
        如果传入了凭证且配置文件不存在，自动保存到配置文件。
        """
        # 传入参数优先
        if app_id and app_secret:
            CredentialManager.save(app_id, app_secret)
            return app_id, app_secret

        # 读取配置文件
        if CONFIG_PATH.exists():
            try:
                data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
                file_id = data.get("app_id", "").strip()
                file_secret = data.get("app_secret", "").strip()
                if file_id and file_secret and not file_id.startswith("你的"):
                    return file_id, file_secret
            except json.JSONDecodeError:
                pass

        # 凭证缺失，输出引导信息
        print(json.dumps({
            "error": "feishu_config_required",
            "message": "需要飞书应用凭证才能获取文档",
            "config_path": str(CONFIG_PATH),
            "steps": [
                f"1. 在飞书开放平台 (https://open.feishu.cn) 创建应用",
                f"2. 开通权限: docx:document:readonly, wiki:wiki:readonly, im:resource",
                f"3. 将知识库授权给该应用",
                f"4. 提供应用的 App ID 和 App Secret",
            ],
            "hint": "请向用户询问 app_id 和 app_secret，然后通过 --app-id 和 --app-secret 参数传入",
        }, ensure_ascii=False, indent=2))
        sys.exit(1)

    @staticmethod
    def save(app_id: str, app_secret: str):
        """保存凭证到配置文件"""
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        config = {"app_id": app_id, "app_secret": app_secret}
        CONFIG_PATH.write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"✓ 凭证已保存到 {CONFIG_PATH}", file=sys.stderr)


# ── Token 管理 ────────────────────────────────────────

class TokenManager:
    """飞书 tenant_access_token 管理器"""

    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self._token: Optional[str] = None
        self._expire_at: float = 0

    def _request_token(self) -> Tuple[str, int]:
        """向飞书 API 请求 tenant_access_token"""
        url = f"{FEISHU_BASE}/open-apis/auth/v3/tenant_access_token/internal"
        body = json.dumps({
            "app_id": self.app_id,
            "app_secret": self.app_secret,
        }).encode("utf-8")
        req = Request(url, data=body, headers={"Content-Type": "application/json"})

        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        if data.get("code") != 0:
            raise RuntimeError(f"获取 tenant_access_token 失败: {data.get('msg')} (code={data.get('code')})")

        return data["tenant_access_token"], data.get("expire", 7200)

    def get_token(self) -> str:
        """获取有效的 tenant_access_token，自动缓存和刷新"""
        if self._token and time.time() < self._expire_at - 300:
            return self._token

        token, expire = self._request_token()
        self._token = token
        self._expire_at = time.time() + expire
        print("✓ tenant_access_token 获取成功", file=sys.stderr)
        return token


# ── 飞书 API 调用 ─────────────────────────────────────

class FeishuAPIClient:
    """飞书开放平台 API 客户端"""

    def __init__(self, token_manager: TokenManager):
        self.token_manager = token_manager

    def _get(self, path: str, params: str = "") -> dict:
        """GET 请求飞书 API"""
        url = f"{FEISHU_BASE}{path}"
        if params:
            url += f"?{params}"
        token = self.token_manager.get_token()
        req = Request(url, headers={"Authorization": f"Bearer {token}"})

        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _get_with_retry(self, path: str, params: str = "", max_retries: int = 3) -> dict:
        """带重试的 GET 请求"""
        for attempt in range(max_retries):
            try:
                return self._get(path, params)
            except HTTPError as e:
                if e.code == 401 and attempt == 0:
                    # token 过期，强制刷新
                    self.token_manager._token = None
                    continue
                if e.code >= 500 and attempt < max_retries - 1:
                    wait = min(2 ** attempt, 10)
                    print(f"⚠️  服务端 {e.code} 错误，{wait}s 后重试", file=sys.stderr)
                    time.sleep(wait)
                    continue
                raise
            except URLError as e:
                if attempt < max_retries - 1:
                    time.sleep(min(2 ** attempt, 10))
                    continue
                raise

    def get_docx_content(self, doc_token: str) -> dict:
        """获取 docx 文档 raw_content"""
        data = self._get_with_retry(
            f"/open-apis/docx/v1/documents/{doc_token}/raw_content"
        )
        if data.get("code") != 0:
            raise RuntimeError(f"读取文档失败: {data.get('msg')} (code={data.get('code')})")
        return data.get("data", {})

    def get_wiki_node(self, wiki_token: str) -> dict:
        """获取 wiki 节点信息（含实际文档 token 和类型）"""
        data = self._get_with_retry(
            f"/open-apis/wiki/v2/spaces/get_node",
            f"token={wiki_token}"
        )
        if data.get("code") != 0:
            raise RuntimeError(f"获取 wiki 节点失败: {data.get('msg')} (code={data.get('code')})")
        return data.get("data", {}).get("node", {})

    def get_wiki_content(self, wiki_token: str) -> dict:
        """获取 wiki 文档内容：先查节点信息，再按实际类型读取"""
        node = self.get_wiki_node(wiki_token)
        obj_token = node.get("obj_token", wiki_token)
        obj_type = node.get("obj_type", "docx")

        if obj_type == "docx":
            content_data = self.get_docx_content(obj_token)
        else:
            # 其他类型降级处理
            raise RuntimeError(f"不支持的 wiki 文档类型: {obj_type}，目前仅支持 docx")

        # 用 wiki 标题补充
        title = node.get("title", "")
        return {"content": content_data.get("content", ""), "title": title, "obj_token": obj_token}

    def get_document_blocks(self, doc_token: str) -> dict:
        """获取文档块结构（用于提取图片 block_id）"""
        data = self._get_with_retry(
            f"/open-apis/docx/v1/documents/{doc_token}/blocks",
            "page_size=500"
        )
        if data.get("code") != 0:
            print(f"⚠️  获取文档块结构失败: {data.get('msg')}", file=sys.stderr)
            return {}
        return data.get("data", {})

    def download_image(self, image_token: str) -> Tuple[bytes, str]:
        """下载飞书图片，返回 (二进制数据, content_type)"""
        token = self.token_manager.get_token()
        # 文档内嵌图片使用 drive 接口下载
        url = f"{FEISHU_BASE}/open-apis/drive/v1/medias/{image_token}/download"
        req = Request(url, headers={"Authorization": f"Bearer {token}"})

        with urlopen(req, timeout=30) as resp:
            content_type = resp.headers.get("Content-Type", "image/png")
            data = resp.read()
        return data, content_type

    def probe_drive_readonly(self) -> dict:
        """探针：GET /open-apis/drive/v1/files?limit=1 → 验证 drive:drive:readonly"""
        return self._get_with_retry("/open-apis/drive/v1/files", "limit=1")

    def probe_im_resource(self) -> dict:
        """探针：GET /open-apis/im/v1/files/{fake_key} → 验证 im:resource

        im/v1/files 无 list 端点；用 fake key 触发业务错误（如 code 234008），
        由调用方根据错误码区分「权限不足」与「业务错误」。
        """
        return self._get_with_retry("/open-apis/im/v1/files/_check_config_probe")


# ── 文档拉取 ──────────────────────────────────────────

class FeishuFetcher:
    """飞书文档获取器"""

    URL_PATTERN = re.compile(r"/(docx|docs|wiki)/([A-Za-z0-9]+)")

    def __init__(self, app_id: str = "", app_secret: str = ""):
        app_id, app_secret = CredentialManager.load(app_id, app_secret)
        self.token_manager = TokenManager(app_id, app_secret)
        self.api = FeishuAPIClient(self.token_manager)

    @staticmethod
    def parse_url(url: str) -> Tuple[str, str]:
        """解析飞书 URL，返回 (token, doc_type)"""
        match = FeishuFetcher.URL_PATTERN.search(url)
        if not match:
            raise ValueError(f"无法从 URL 解析飞书文档 token: {url}")
        doc_type = "wiki" if match.group(1) == "wiki" else "docx"
        return match.group(2), doc_type

    def fetch_document(self, url: str) -> DocumentContent:
        """
        获取飞书文档内容。

        Args:
            url: 飞书文档 URL

        Returns:
            DocumentContent 对象
        """
        print(f"📄 正在获取飞书文档: {url}")

        # 解析 URL
        token, doc_type = self.parse_url(url)
        print(f"   类型: {doc_type}, Token: {token}")

        try:
            # 获取文档内容
            if doc_type == "wiki":
                result = self.api.get_wiki_content(token)
            else:
                data = self.api.get_docx_content(token)
                result = {"content": data.get("content", ""), "title": "", "obj_token": token}

            content = (result.get("content") or "").strip()
            title = result.get("title") or result.get("obj_token") or "未命名文档"

            # 获取图片
            images = self._fetch_images(token, doc_type)

            print(f"✓ 文档获取成功: {title}")
            print(f"✓ 发现 {len(images)} 张图片")

            return DocumentContent(
                title=title,
                markdown=content,
                image_count=len(images),
                raw_json={"content": content, "images": images, "title": title},
            )

        except Exception as e:
            print(f"❌ 文档拉取失败: {e}", file=sys.stderr)
            return DocumentContent(title="待获取", markdown="", image_count=0)

    def _fetch_images(self, doc_token: str, doc_type: str) -> List[dict]:
        """从文档块结构中提取并下载图片"""
        # wiki 需要先获取实际 obj_token
        actual_token = doc_token
        if doc_type == "wiki":
            try:
                node = self.api.get_wiki_node(doc_token)
                actual_token = node.get("obj_token", doc_token)
            except Exception:
                pass

        # 获取文档块结构
        try:
            blocks_data = self.api.get_document_blocks(actual_token)
        except Exception:
            return []

        items = blocks_data.get("items", [])
        image_blocks = []

        for block in items:
            block_type = block.get("block_type")
            # 飞书 API 中图片 block_type 为 27
            if block_type == 27 or block_type == "image":
                image_block = block.get("image", {})
                image_token = image_block.get("token", "")
                if image_token:
                    image_blocks.append(image_token)

        # 下载图片并转 base64（兼容下游 save_images 逻辑）
        images = []
        for idx, img_token in enumerate(image_blocks):
            try:
                raw, content_type = self.api.download_image(img_token)
                b64 = base64.b64encode(raw).decode("ascii")
                images.append({
                    "index": idx,
                    "token": img_token,
                    "base64": b64,
                    "content_type": content_type,
                })
            except Exception as e:
                print(f"  ⚠️  图片 {img_token} 下载失败: {e}", file=sys.stderr)

        return images


# ── 图片处理 ──────────────────────────────────────────

EXT_MAP = {
    "image/png": ".png", "image/jpeg": ".jpg", "image/jpg": ".jpg",
    "image/gif": ".gif", "image/webp": ".webp", "image/bmp": ".bmp",
    "image/svg+xml": ".svg",
}


def _sniff_ext(data: bytes) -> Optional[str]:
    """根据 magic bytes 推断图片类型"""
    if not data or len(data) < 4:
        return None
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return ".gif"
    if data.startswith(b"RIFF") and len(data) >= 12 and data[8:12] == b"WEBP":
        return ".webp"
    if data.startswith(b"BM"):
        return ".bmp"
    if data.lstrip()[:5].lower() == b"<?xml" or data.lstrip()[:4].lower() == b"<svg":
        return ".svg"
    return None


def _ext_for(mime: Optional[str], data: Optional[bytes] = None) -> str:
    """确定文件扩展名"""
    if mime:
        ext = EXT_MAP.get(mime.lower())
        if ext:
            return ext
    if data is not None:
        sniffed = _sniff_ext(data)
        if sniffed:
            return sniffed
    return ".bin"


def save_images(doc: DocumentContent, output_dir: Path) -> Tuple[Dict[str, Path], List[str]]:
    """
    解码图片并保存到本地。

    Args:
        doc: 文档内容
        output_dir: 输出目录（prd 目录）

    Returns:
        (成功映射 {key: Path}, 失败列表)
    """
    images = doc.raw_json.get("images") or []
    if not images:
        return {}, []

    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    print(f"🖼️  开始解码 {len(images)} 张图片")

    success_map: Dict[str, Path] = {}
    failed: List[str] = []

    for seq, img in enumerate(images):
        b64 = img.get("base64")
        if not b64:
            failed.append(f"img-{seq}")
            continue

        try:
            raw = base64.b64decode(b64)
            content_type = img.get("content_type") or img.get("mime_type")
            ext = _ext_for(content_type, raw)
            idx = img.get("index", seq)
            token = img.get("token", "")
            filename = f"img-{idx}{ext}"
            filepath = images_dir / filename

            filepath.write_bytes(raw)

            success_map[token or str(idx)] = filepath
            print(f"  ✓ {filename}")
        except Exception as e:
            failed.append(f"img-{seq}")
            print(f"  ✗ img-{seq}: {e}")

    print(f"✓ 图片解码完成: {len(success_map)}/{len(images)}")
    return success_map, failed


def replace_placeholders(markdown: str, success_map: Dict[str, Path], raw_json: dict) -> str:
    """将正文中的图片占位符替换为本地图片引用

    支持三种占位符格式：
    1. 独立一行的图片文件名（如 "xxx.png"）— 按顺序匹配
    2. <block:BLOCK_ID> — 块引用格式
    3. <image token="KEY"> — 飞书原生 HTML 标签格式
    """
    result = markdown

    # 按文件名排序的有序路径列表
    ordered_paths = sorted(success_map.values(), key=lambda p: p.stem)

    # 策略0: 正文中独占一行的图片文件名
    img_name_pattern = re.compile(r"^([^\n]+\.(?:png|jpg|jpeg|gif|webp|bmp|svg))\s*$", re.MULTILINE)
    path_idx = 0
    while path_idx < len(ordered_paths):
        match = img_name_pattern.search(result)
        if not match:
            break
        filepath = ordered_paths[path_idx]
        ref = f"![img-{filepath.stem.replace('img-', '')}](images/{filepath.name})"
        result = result[:match.start()] + ref + result[match.end():]
        path_idx += 1

    # 策略1: 替换 <block:KEY> 格式
    for key, filepath in success_map.items():
        ref = f"![img-{filepath.stem.replace('img-', '')}](images/{filepath.name})"
        placeholder = f"<block:{key}>"
        if key and placeholder in result:
            result = result.replace(placeholder, ref, 1)
            continue

        # 策略3: 替换 <image token="KEY"> 格式
        image_tag = f'<image token="{key}"'
        if image_tag in result:
            result = re.sub(
                rf'<image\s+token="{re.escape(key)}"[^/]*/?>',
                ref, result, count=1,
            )

    return result


# ── 主流程 ────────────────────────────────────────────

# ── lark-cli 路径（默认） ─────────────────────────────

def _fetch_via_lark_cli(url: str, output_dir: Path, project_name: str) -> Path:
    lib_dir = Path(__file__).resolve().parents[3] / "scripts" / "lib"
    if str(lib_dir) not in sys.path:
        sys.path.insert(0, str(lib_dir))
    from lark_cli import check_available, fetch as lark_fetch  # noqa: WPS433

    ok, msg = check_available()
    if not ok:
        raise RuntimeError(msg)

    output_dir.mkdir(parents=True, exist_ok=True)
    prd_path = output_dir / "prd.md"
    lark_fetch(url, prd_path)

    text = prd_path.read_text(encoding="utf-8").strip()
    if not text.startswith("#"):
        text = f"# {project_name}\n\n{text}\n"
        prd_path.write_text(text, encoding="utf-8")

    print(f"✓ lark-cli 文档已保存: {prd_path} ({len(text)} chars)")
    return prd_path


def _enrich_images(
    url: str,
    prd_path: Path,
    output_dir: Path,
    app_id: str,
    app_secret: str,
) -> None:
    """在 lark-cli 拉取的 Markdown 上补充本地下载图片（legacy API）。"""
    fetcher = FeishuFetcher(app_id, app_secret)
    doc = fetcher.fetch_document(url)
    if not doc.markdown and not doc.raw_json.get("images"):
        print("⚠️  图片补充跳过：legacy API 未返回内容")
        return

    success_map, failed = save_images(doc, output_dir)
    if not success_map:
        return

    text = prd_path.read_text(encoding="utf-8")
    body = text
    title = project_title_from_md(text) or doc.title or "未命名文档"
    if body.startswith("#"):
        parts = body.split("\n", 1)
        body = parts[1].lstrip("\n") if len(parts) > 1 else ""

    source_md = doc.markdown or body
    enriched = replace_placeholders(source_md, success_map, doc.raw_json)
    prd_path.write_text(f"# {title}\n\n{enriched.lstrip()}\n", encoding="utf-8")

    images_dir = output_dir / "images"
    image_files = {f.name for f in images_dir.iterdir() if f.is_file()} if images_dir.exists() else set()
    print(f"✓ 图片目录: {images_dir} ({len(image_files)} 文件)")
    if failed:
        print(f"⚠️  图片解码失败: {len(failed)}")


def project_title_from_md(text: str) -> str:
    first = text.lstrip().split("\n", 1)[0]
    if first.startswith("#"):
        return first.lstrip("#").strip()
    return ""


def _fetch_via_legacy_api(
    url: str, output_dir: Path, project_name: str, app_id: str, app_secret: str
) -> str:
    """完整 legacy API 路径（含图片）。"""
    output_dir.mkdir(parents=True, exist_ok=True)

    fetcher = FeishuFetcher(app_id, app_secret)
    doc = fetcher.fetch_document(url)

    if not doc.markdown:
        prd_path = output_dir / "prd.md"
        prd_path.write_text(
            f"# {project_name}\n\n⚠️ 飞书文档获取失败，请手动补充内容。\n", encoding="utf-8"
        )
        return str(prd_path)

    success_map, failed = save_images(doc, output_dir)
    markdown = replace_placeholders(doc.markdown, success_map, doc.raw_json)
    final = f"# {doc.title}\n\n{markdown}"
    prd_path = output_dir / "prd.md"
    prd_path.write_text(final, encoding="utf-8")

    images_dir = output_dir / "images"
    image_files = set()
    if images_dir.exists():
        image_files = {f.name for f in images_dir.iterdir() if f.is_file()}

    print()
    print(f"✓ 文档已保存: {prd_path}")
    print(f"✓ 图片目录: {images_dir}")
    print(f"✓ 图片文件数: {len(image_files)}")
    if failed:
        print(f"⚠️  图片解码失败: {len(failed)}")

    return str(prd_path)


def fetch_and_save(
    url: str,
    output_dir: Path,
    project_name: str,
    app_id: str = "",
    app_secret: str = "",
    *,
    with_images: bool = False,
    legacy_api: bool = False,
) -> str:
    """获取 + 保存：默认 lark-cli；--legacy-api 或 --with-images 可走 legacy API。"""
    if legacy_api:
        return _fetch_via_legacy_api(url, output_dir, project_name, app_id, app_secret)

    try:
        prd_path = _fetch_via_lark_cli(url, output_dir, project_name)
    except RuntimeError as e:
        print(f"⚠️  lark-cli 不可用，降级 legacy API: {e}", file=sys.stderr)
        return _fetch_via_legacy_api(url, output_dir, project_name, app_id, app_secret)

    if with_images:
        _enrich_images(url, prd_path, output_dir, app_id, app_secret)

    return str(prd_path)


def main():
    parser = argparse.ArgumentParser(description="飞书文档获取器")
    parser.add_argument("doc_url", help="飞书文档 URL")
    parser.add_argument("--output-dir", required=True, help="输出目录 (如 changes/<req-id>/request)")
    parser.add_argument("--project-name", default="未命名项目", help="项目名称")
    parser.add_argument("--app-id", default="", help="飞书应用 App ID（legacy API / 图片补充时使用）")
    parser.add_argument("--app-secret", default="", help="飞书应用 App Secret")
    parser.add_argument(
        "--with-images",
        action="store_true",
        help="lark-cli 拉取后，用 legacy API 补充下载图片到 images/",
    )
    parser.add_argument(
        "--legacy-api",
        action="store_true",
        help="强制使用直连飞书 Open API（不经过 lark-cli）",
    )
    args = parser.parse_args()

    fetch_and_save(
        args.doc_url,
        Path(args.output_dir),
        args.project_name,
        args.app_id,
        args.app_secret,
        with_images=args.with_images,
        legacy_api=args.legacy_api,
    )


if __name__ == "__main__":
    main()