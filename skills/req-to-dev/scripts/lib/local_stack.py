"""本地联调栈（方案 B：nginx 网关 + 本地 lottery + webpack dev）。"""

from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from collab_common import CONFIG_DIR, append_log, find_change_dir, project_root  # noqa: E402

NGINX_TEMPLATE = CONFIG_DIR / "nginx" / "integral-local.conf.template"

DEFAULT_LOTTERY_REPO = Path("/Users/qidi/IdeaProjects/shop-points-lottery")
DEFAULT_H5_REPO = Path("/Users/qidi/IdeaProjects/store-integral-h5/client-integral")

DEFAULT_H5_HOST = "integral.ttb.test.ke.com"
DEFAULT_LOTTERY_HOST_HEADER = "local.ttb.test.ke.com"
DEFAULT_SHOP_CODE = "TJDY0101"
DEFAULT_INTEGRAL_PROXY_TARGET = "http://shop-points.shop-points-test01.ttb.test.ke.com"
DEFAULT_INTEGRAL_PROXY_HOST = "shop-points.shop-points-test01.ttb.test.ke.com"

LOTTERY_PORT = 8080
FRONTEND_PORT = 9393
NGINX_PORT = 80


@dataclass
class StackConfig:
    req_id: str
    change_dir: Path
    lottery_repo: Path
    h5_repo: Path
    h5_host: str
    lottery_host_header: str
    shop_code: str
    integral_proxy_target: str
    integral_proxy_host: str
    lottery_port: int
    frontend_port: int
    nginx_port: int
    skip_lottery: bool
    skip_frontend: bool


def iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_impact_frontmatter(change_dir: Path) -> dict:
    impact_file = change_dir / "impact" / "impact.md"
    if not impact_file.exists():
        return {}
    text = impact_file.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    end = text.find("---", 3)
    if end == -1:
        return {}
    meta: dict = {}
    for line in text[3:end].strip().splitlines():
        stripped = line.strip()
        if not stripped or ":" not in stripped:
            continue
        key, _, val = stripped.partition(":")
        key, val = key.strip(), val.strip().strip("\"'")
        if val.startswith("[") and val.endswith("]"):
            meta[key] = [v.strip() for v in val[1:-1].split(",") if v.strip()]
        elif val:
            meta[key] = val
    return meta


def load_stack_config(req_id: str, **overrides) -> StackConfig:
    change_dir = find_change_dir(req_id)
    state_path = change_dir / "pipeline_state.json"
    repos: dict = {}
    if state_path.exists():
        repos = json.loads(state_path.read_text(encoding="utf-8")).get("repos") or {}

    impact = parse_impact_frontmatter(change_dir)
    lottery_repo = Path(
        overrides.get("lottery_repo")
        or repos.get("shop-points-lottery")
        or DEFAULT_LOTTERY_REPO
    )
    h5_repo = Path(
        overrides.get("h5_repo")
        or repos.get("store-integral-h5")
        or DEFAULT_H5_REPO
    )
    return StackConfig(
        req_id=req_id,
        change_dir=change_dir,
        lottery_repo=lottery_repo,
        h5_repo=h5_repo,
        h5_host=overrides.get("h5_host", DEFAULT_H5_HOST),
        lottery_host_header=overrides.get(
            "lottery_host_header", DEFAULT_LOTTERY_HOST_HEADER
        ),
        shop_code=overrides.get("shop_code", DEFAULT_SHOP_CODE),
        integral_proxy_target=overrides.get(
            "integral_proxy_target", DEFAULT_INTEGRAL_PROXY_TARGET
        ),
        integral_proxy_host=overrides.get(
            "integral_proxy_host", DEFAULT_INTEGRAL_PROXY_HOST
        ),
        lottery_port=int(overrides.get("lottery_port", LOTTERY_PORT)),
        frontend_port=int(overrides.get("frontend_port", FRONTEND_PORT)),
        nginx_port=int(overrides.get("nginx_port", NGINX_PORT)),
        skip_lottery=bool(overrides.get("skip_lottery")),
        skip_frontend=bool(overrides.get("skip_frontend")),
    )


def stack_state_path(change_dir: Path) -> Path:
    return change_dir / "tests" / "local_stack_state.json"


def load_stack_state(change_dir: Path) -> dict | None:
    path = stack_state_path(change_dir)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_stack_state(change_dir: Path, state: dict) -> None:
    path = stack_state_path(change_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def nginx_prefix(change_dir: Path) -> Path:
    return (change_dir / "tests" / "local-stack" / "nginx").resolve()


def is_port_open(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        return sock.connect_ex((host, port)) == 0


def http_status(url: str, timeout: float = 5.0) -> int | None:
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return None


def find_nginx_bin() -> str | None:
    for name in ("nginx", "/opt/homebrew/bin/nginx", "/usr/local/bin/nginx"):
        path = shutil.which(name) if not name.startswith("/") else name
        if path and Path(path).exists():
            return path
    return None


def render_nginx_conf(cfg: StackConfig, prefix: Path) -> Path:
    prefix = prefix.resolve()
    if not NGINX_TEMPLATE.exists():
        raise FileNotFoundError(f"缺少 nginx 模板: {NGINX_TEMPLATE}")
    template = NGINX_TEMPLATE.read_text(encoding="utf-8")
    rendered = (
        template.replace("{{NGINX_PREFIX}}", str(prefix))
        .replace("{{FRONTEND_PORT}}", str(cfg.frontend_port))
        .replace("{{LOTTERY_PORT}}", str(cfg.lottery_port))
        .replace("{{NGINX_PORT}}", str(cfg.nginx_port))
        .replace("{{H5_HOST}}", cfg.h5_host)
        .replace("{{LOTTERY_HOST_HEADER}}", cfg.lottery_host_header)
        .replace("{{INTEGRAL_PROXY_TARGET}}", cfg.integral_proxy_target.rstrip("/"))
        .replace("{{INTEGRAL_PROXY_HOST}}", cfg.integral_proxy_host)
    )
    prefix.mkdir(parents=True, exist_ok=True)
    (prefix / "logs").mkdir(exist_ok=True)
    (prefix / "proxy_temp").mkdir(exist_ok=True)
    (prefix / "client_body_temp").mkdir(exist_ok=True)
    conf_path = prefix / "integral-local.conf"
    conf_path.write_text(rendered, encoding="utf-8")
    return conf_path


def h5_entry_url(cfg: StackConfig) -> str:
    q = f"shopCode={cfg.shop_code}&shopCodeInnerTest={cfg.shop_code}"
    return f"http://{cfg.h5_host}/fuwujin-mall/index?{q}"


def start_lottery(cfg: StackConfig, log_dir: Path) -> dict:
    if is_port_open(cfg.lottery_port):
        return {
            "status": "already_running",
            "port": cfg.lottery_port,
            "url": f"http://{cfg.lottery_host_header}:{cfg.lottery_port}",
        }
    log_file = log_dir / "lottery.log"
    cmd = [
        "mvn",
        "spring-boot:run",
        "-pl",
        "shop-points-lottery-start",
        "-Dspring-boot.run.profiles=test",
    ]
    proc = subprocess.Popen(
        cmd,
        cwd=str(cfg.lottery_repo),
        stdout=log_file.open("w", encoding="utf-8"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    deadline = time.time() + 180
    while time.time() < deadline:
        if proc.poll() is not None:
            tail = log_file.read_text(encoding="utf-8", errors="replace")[-2000:]
            raise RuntimeError(f"lottery 启动失败 exit={proc.returncode}\n{tail}")
        if is_port_open(cfg.lottery_port):
            return {
                "status": "started",
                "pid": proc.pid,
                "port": cfg.lottery_port,
                "log": str(log_file),
                "cmd": " ".join(cmd),
                "cwd": str(cfg.lottery_repo),
            }
        time.sleep(2)
    proc.terminate()
    raise RuntimeError("lottery 启动超时（180s），请查看 lottery.log")


def start_frontend(cfg: StackConfig, log_dir: Path) -> dict:
    if is_port_open(cfg.frontend_port):
        return {
            "status": "already_running",
            "port": cfg.frontend_port,
            "url": f"http://127.0.0.1:{cfg.frontend_port}",
        }
    log_file = log_dir / "frontend.log"
    env = os.environ.copy()
    env["BUILD_ENV"] = "development"
    cmd = ["npx", "craco", "start"]
    proc = subprocess.Popen(
        cmd,
        cwd=str(cfg.h5_repo),
        stdout=log_file.open("w", encoding="utf-8"),
        stderr=subprocess.STDOUT,
        env=env,
        start_new_session=True,
    )
    deadline = time.time() + 120
    while time.time() < deadline:
        if proc.poll() is not None:
            tail = log_file.read_text(encoding="utf-8", errors="replace")[-2000:]
            raise RuntimeError(f"frontend 启动失败 exit={proc.returncode}\n{tail}")
        if is_port_open(cfg.frontend_port):
            return {
                "status": "started",
                "pid": proc.pid,
                "port": cfg.frontend_port,
                "log": str(log_file),
                "cmd": "BUILD_ENV=development npx craco start",
                "cwd": str(cfg.h5_repo),
            }
        time.sleep(2)
    raise RuntimeError("frontend 启动超时（120s），请查看 frontend.log")


def start_nginx(cfg: StackConfig, prefix: Path, conf_path: Path) -> dict:
    nginx_bin = find_nginx_bin()
    if not nginx_bin:
        raise RuntimeError("未找到 nginx，请安装: brew install nginx")

    test = subprocess.run(
        [nginx_bin, "-t", "-p", str(prefix), "-c", str(conf_path)],
        capture_output=True,
        text=True,
    )
    if test.returncode != 0:
        raise RuntimeError(f"nginx -t 失败:\n{test.stderr or test.stdout}")

    pid_file = prefix / "nginx.pid"
    if pid_file.exists():
        subprocess.run(
            [nginx_bin, "-s", "stop", "-p", str(prefix), "-c", str(conf_path)],
            capture_output=True,
        )
        time.sleep(1)

    start = subprocess.run(
        [nginx_bin, "-p", str(prefix), "-c", str(conf_path)],
        capture_output=True,
        text=True,
    )
    if start.returncode != 0:
        hint = ""
        if "bind()" in (start.stderr or "") and cfg.nginx_port < 1024:
            hint = (
                f"\n提示: 监听 {cfg.nginx_port} 端口通常需要 sudo，"
                f"可改用 --nginx-port 8088 并访问 http://{cfg.h5_host}:8088/..."
            )
        raise RuntimeError(f"nginx 启动失败:\n{start.stderr or start.stdout}{hint}")

    time.sleep(0.5)
    pid = None
    if pid_file.exists():
        pid = int(pid_file.read_text(encoding="utf-8").strip())
    return {
        "status": "started",
        "pid": pid,
        "bin": nginx_bin,
        "prefix": str(prefix),
        "conf": str(conf_path),
        "port": cfg.nginx_port,
    }


def stop_process(pid: int | None, name: str) -> None:
    if not pid:
        return
    try:
        os.kill(pid, 15)
    except ProcessLookupError:
        return
    except PermissionError as e:
        raise RuntimeError(f"无法停止 {name} pid={pid}: {e}") from e


def write_stack_report(cfg: StackConfig, state: dict) -> Path:
    report = cfg.change_dir / "tests" / "local_stack_report.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Local Stack Report（方案 B · nginx 网关）",
        "",
        f"started_at: {state.get('started_at', iso_now())}",
        "",
        "## 架构",
        "",
        "```",
        f"浏览器 → http://{cfg.h5_host} (nginx:{cfg.nginx_port})",
        f"  ├─ /activity-proxy/* → 本地 lottery :{cfg.lottery_port}",
        f"  ├─ /integral-proxy/* → {cfg.integral_proxy_target}",
        f"  └─ 其余 → webpack dev :{cfg.frontend_port}",
        "```",
        "",
        "## 入口",
        "",
        f"- H5: `{state['urls']['h5_entry']}`",
        f"- 本地 lottery 直连: `http://{cfg.lottery_host_header}:{cfg.lottery_port}`",
        "",
        "## 进程",
        "",
    ]
    for key in ("lottery", "frontend", "nginx"):
        block = state.get(key) or {}
        lines.append(f"### {key}")
        for k, v in block.items():
            lines.append(f"- {k}: `{v}`")
        lines.append("")

    lines.extend(
        [
            "## 停止",
            "",
            f"```bash",
            f"python3 skills/req-to-dev/scripts/local_stack_down.py --req-id {cfg.req_id}",
            f"```",
            "",
            "## 说明",
            "",
            "- **对前端业务代码零侵入**：未修改 `store-integral-h5/src`，仅本机 nginx 路由",
            "- hosts 需包含：`127.0.0.1 integral.ttb.test.ke.com local.ttb.test.ke.com`（**本地联调访问须带 nginx 端口，默认 :8088**）",
            f"- 登录凭证：`{CONFIG_DIR / 'secrets.local.json'}` → `test_env_app`（与 `ab_h5_bypass_http.py` 同源）",
            "- CAS 回跳：另需 sudo 起 `config/nginx/cas-local.conf.template`（见 `playbooks/local-stack-troubleshooting.md` §四）",
            "- 排障手册：`playbooks/local-stack-troubleshooting.md`（bundle 截断、CORS 403、502 等）",
            "",
            "## 启动验收",
            "",
            "```bash",
            "# bundle 约 7MB；preview POST 非 403",
            f"curl -sS -o /dev/null -w 'h5:%{{http_code}} bundle:%{{size_download}}\\n' '{state['urls']['h5_entry']}'",
            f"curl -sS -o /dev/null -w '%{{size_download}}\\n' 'http://{cfg.h5_host}:{cfg.nginx_port}/static/js/bundle.js' 2>/dev/null || true",
            "```",
        ]
    )
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report
