"""本地联调栈（方案 B：nginx 网关 + 本地后端 + webpack dev）。"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from collab_common import CONFIG_DIR, find_change_dir  # noqa: E402
from local_config import (  # noqa: E402
    DEFAULT_TEST_SHOP_CODE,
    load_test_env_fixtures,
    test_env_fixtures_summary,
)

NGINX_TEMPLATE = CONFIG_DIR / "nginx" / "local-gateway.conf.template"

DEFAULT_LOTTERY_REPO = Path("/Users/qidi/IdeaProjects/shop-points-lottery")
DEFAULT_SHOP_POINTS_REPO = Path("/Users/qidi/IdeaProjects/shop-points")
DEFAULT_H5_REPO = Path("/Users/qidi/IdeaProjects/store-integral-h5/client-integral")
DEFAULT_PC_REPO = Path("/Users/qidi/IdeaProjects/store-integral")
DEFAULT_PC_CLIENT_DIR = DEFAULT_PC_REPO / "client"

DEFAULT_H5_HOST = "integral.ttb.test.ke.com"
DEFAULT_PC_HOST = "point-pc.ttb.test.ke.com"
DEFAULT_LOTTERY_HOST_HEADER = "local.ttb.test.ke.com"
DEFAULT_SHOP_POINTS_HOST_HEADER = "shop-points.shop-points-test01.ttb.test.ke.com"
DEFAULT_SHOP_CODE = DEFAULT_TEST_SHOP_CODE
DEFAULT_INTEGRAL_PROXY_TARGET = "http://shop-points.shop-points-test01.ttb.test.ke.com"
DEFAULT_INTEGRAL_PROXY_HOST = "shop-points.shop-points-test01.ttb.test.ke.com"

LOTTERY_PORT = 8080
SHOP_POINTS_PORT = 8081
FRONTEND_PORT = 9393
PC_PORT = 3000
NGINX_PORT = 8088
PC_NGINX_PORT = 8089

H5_SERVER_TEMPLATE = """    # --- H5 gateway ---
    server {
        listen {{NGINX_PORT}};
        server_name {{H5_HOST}};

        client_max_body_size 50m;

        location /activity-proxy/ {
            proxy_pass http://lottery_local/;
            proxy_http_version 1.1;
            proxy_set_header Host {{LOTTERY_HOST_HEADER}};
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header Origin "";
            proxy_connect_timeout 60s;
            proxy_read_timeout 300s;
        }

        location /integral-proxy/ {
            proxy_pass {{H5_INTEGRAL_PROXY_PASS}};
            proxy_http_version 1.1;
            proxy_set_header Host {{H5_INTEGRAL_PROXY_HOST}};
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_ssl_server_name on;
            # 同 PC：本地 shop-points CORS 不含 integral:8088
            proxy_set_header Origin "";
        }

        location /loginUser/ {
            proxy_pass {{H5_LOGIN_USER_PASS}};
            proxy_http_version 1.1;
            proxy_set_header Host {{H5_LOGIN_USER_HOST}};
        }

        location / {
            proxy_pass http://frontend_dev;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection $connection_upgrade;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_read_timeout 86400;
            proxy_buffering off;
            proxy_request_buffering off;
            proxy_max_temp_file_size 0;
        }
    }
"""

PC_SERVER_TEMPLATE = """    # --- PC admin gateway ---
    server {
        listen {{PC_NGINX_PORT}};
        server_name {{PC_HOST}};

        client_max_body_size 50m;

        location /shop-points {
            proxy_pass {{PC_SHOP_POINTS_PASS}};
            proxy_http_version 1.1;
            proxy_set_header Host {{SHOP_POINTS_HOST_HEADER}};
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            # 浏览器带 Origin: point-pc:8089；本地 shop-points CORS 仅白名单 fcn.ke.com，需剥掉以免 403
            proxy_set_header Origin "";
        }

        location /activity-proxy/ {
            proxy_pass http://lottery_local/;
            proxy_http_version 1.1;
            proxy_set_header Host {{LOTTERY_HOST_HEADER}};
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header Origin "";
            proxy_connect_timeout 60s;
            proxy_read_timeout 300s;
        }

        location /api/ {
            proxy_pass http://agent-lego.shop-points-test01.ttb.test.ke.com/;
            proxy_http_version 1.1;
            proxy_set_header Host agent-lego.shop-points-test01.ttb.test.ke.com;
        }

        location /loginUser/info {
            proxy_pass http://agent-lego.shop-points-test01.ttb.test.ke.com;
            proxy_http_version 1.1;
            proxy_set_header Host agent-lego.shop-points-test01.ttb.test.ke.com;
        }

        location /shop-points-calc/ {
            proxy_pass http://shop-points-calc.shop-points-test01.ttb.test.ke.com/;
            proxy_http_version 1.1;
            proxy_set_header Host shop-points-calc.shop-points-test01.ttb.test.ke.com;
        }

        location / {
            proxy_pass http://pc_webpack;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection $connection_upgrade;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_read_timeout 86400;
            proxy_buffering off;
            proxy_request_buffering off;
            proxy_max_temp_file_size 0;
        }
    }
"""


@dataclass
class StackConfig:
    req_id: str
    change_dir: Path
    lottery_repo: Path
    shop_points_repo: Path
    h5_repo: Path
    pc_client_dir: Path
    h5_host: str
    pc_host: str
    lottery_host_header: str
    shop_points_host_header: str
    shop_code: str
    integral_proxy_target: str
    integral_proxy_host: str
    local_shop_points: bool
    surfaces: list[str] = field(default_factory=lambda: ["h5", "pc"])
    lottery_port: int = LOTTERY_PORT
    shop_points_port: int = SHOP_POINTS_PORT
    frontend_port: int = FRONTEND_PORT
    pc_port: int = PC_PORT
    nginx_port: int = NGINX_PORT
    pc_nginx_port: int = PC_NGINX_PORT
    skip_lottery: bool = False
    skip_shop_points: bool = False
    skip_h5: bool = False
    skip_pc: bool = False

    @property
    def skip_frontend(self) -> bool:
        """向后兼容：等同 skip_h5。"""
        return self.skip_h5


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


def _nested_repo_path(repos: dict, *keys: str) -> str | None:
    node: object = repos
    for key in keys:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    if isinstance(node, dict):
        path = node.get("path")
        return str(path) if path else None
    if isinstance(node, str):
        return node
    return None


def _resolve_surfaces(impact: dict, override: str | list[str] | None) -> list[str]:
    if override is not None:
        if isinstance(override, str):
            return [s.strip() for s in override.split(",") if s.strip()]
        return list(override)
    surfaces = impact.get("surfaces")
    if isinstance(surfaces, list) and surfaces:
        return surfaces
    if isinstance(surfaces, str) and surfaces:
        return [s.strip() for s in surfaces.split(",") if s.strip()]
    return ["h5", "pc"]


def load_stack_config(req_id: str, **overrides) -> StackConfig:
    change_dir = find_change_dir(req_id)
    state_path = change_dir / "pipeline_state.json"
    repos: dict = {}
    if state_path.exists():
        repos = json.loads(state_path.read_text(encoding="utf-8")).get("repos") or {}

    impact = parse_impact_frontmatter(change_dir)
    surfaces = _resolve_surfaces(impact, overrides.get("surfaces"))

    lottery_repo = Path(
        overrides.get("lottery_repo")
        or _nested_repo_path(repos, "lottery")
        or repos.get("shop-points-lottery")
        or DEFAULT_LOTTERY_REPO
    )
    shop_points_repo = Path(
        overrides.get("shop_points_repo")
        or _nested_repo_path(repos, "backend", "shop-points")
        or DEFAULT_SHOP_POINTS_REPO
    )

    h5_root = (
        overrides.get("h5_repo")
        or _nested_repo_path(repos, "frontend", "h5")
        or str(DEFAULT_H5_REPO.parent)
    )
    h5_repo = Path(h5_root)
    if h5_repo.name != "client-integral":
        h5_repo = h5_repo / "client-integral"

    pc_root = (
        overrides.get("pc_repo")
        or _nested_repo_path(repos, "frontend", "pc")
        or str(DEFAULT_PC_REPO)
    )
    pc_repo = Path(pc_root)
    pc_client_dir = Path(overrides.get("pc_client_dir") or pc_repo / "client")

    local_shop_points = overrides.get("local_shop_points", True)
    if overrides.get("remote_shop_points") or overrides.get("skip_shop_points"):
        local_shop_points = False

    skip_h5 = bool(overrides.get("skip_h5") or overrides.get("skip_frontend"))
    skip_pc = bool(overrides.get("skip_pc"))
    if "h5" not in surfaces:
        skip_h5 = True
    if "pc" not in surfaces:
        skip_pc = True
    if impact.get("frontend_scope") == "none":
        skip_h5 = True
        skip_pc = True

    skip_lottery = bool(overrides.get("skip_lottery"))
    if "skip_lottery" not in overrides and impact.get("mall_scope") == "none":
        skip_lottery = True

    return StackConfig(
        req_id=req_id,
        change_dir=change_dir,
        lottery_repo=lottery_repo,
        shop_points_repo=shop_points_repo,
        h5_repo=h5_repo,
        pc_client_dir=pc_client_dir,
        h5_host=overrides.get("h5_host", DEFAULT_H5_HOST),
        pc_host=overrides.get("pc_host", DEFAULT_PC_HOST),
        lottery_host_header=overrides.get(
            "lottery_host_header", DEFAULT_LOTTERY_HOST_HEADER
        ),
        shop_points_host_header=overrides.get(
            "shop_points_host_header", DEFAULT_SHOP_POINTS_HOST_HEADER
        ),
        shop_code=overrides.get("shop_code", DEFAULT_SHOP_CODE),
        integral_proxy_target=overrides.get(
            "integral_proxy_target", DEFAULT_INTEGRAL_PROXY_TARGET
        ),
        integral_proxy_host=overrides.get(
            "integral_proxy_host", DEFAULT_INTEGRAL_PROXY_HOST
        ),
        local_shop_points=bool(local_shop_points),
        surfaces=surfaces,
        lottery_port=int(overrides.get("lottery_port", LOTTERY_PORT)),
        shop_points_port=int(overrides.get("shop_points_port", SHOP_POINTS_PORT)),
        frontend_port=int(overrides.get("frontend_port", FRONTEND_PORT)),
        pc_port=int(overrides.get("pc_port", PC_PORT)),
        nginx_port=int(overrides.get("nginx_port", NGINX_PORT)),
        pc_nginx_port=int(overrides.get("pc_nginx_port", PC_NGINX_PORT)),
        skip_lottery=skip_lottery,
        skip_shop_points=bool(overrides.get("skip_shop_points")),
        skip_h5=skip_h5,
        skip_pc=skip_pc,
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


KECOIN_PERIOD_PATH = "/shop-points/manage/upload/keCoin/period"


def impact_requires_kecoin_api(impact: dict, change_dir: Path | None = None) -> bool:
    """本需求若新增/扩展 shop-points 上传 API，本地栈须能路由到 keCoin period。"""
    api_change = str(impact.get("api_change", "")).strip().lower()
    if api_change not in ("new", "extend"):
        return False
    modules = impact.get("deploy_modules") or []
    if isinstance(modules, str):
        modules = [m.strip() for m in modules.split(",") if m.strip()]
    if any("shop-points" in str(m) for m in modules):
        return True
    if change_dir is not None:
        contract = change_dir / "handoff" / "api-contract.yaml"
        if contract.exists() and "keCoin" in contract.read_text(encoding="utf-8"):
            return True
    return api_change == "new"


def shop_points_kecoin_period_url(cfg: StackConfig) -> str:
    return f"http://127.0.0.1:{cfg.shop_points_port}{KECOIN_PERIOD_PATH}"


def kill_processes_on_port(port: int, label: str = "port") -> list[int]:
    result = subprocess.run(
        ["lsof", "-ti", f":{port}"],
        capture_output=True,
        text=True,
    )
    pids = [int(p) for p in result.stdout.strip().split() if p.strip().isdigit()]
    for pid in pids:
        stop_process(pid, f"{label}:{port}")
    if pids:
        time.sleep(2)
    return pids


def compile_shop_points(cfg: StackConfig, log_dir: Path) -> dict:
    log_file = log_dir / "shop-points-compile.log"
    cmd = [
        "mvn",
        "install",
        "-pl",
        "shop-points-start",
        "-am",
        "-DskipTests",
        "-Dmaven.test.skip=true",
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(cfg.shop_points_repo),
        stdout=log_file.open("w", encoding="utf-8"),
        stderr=subprocess.STDOUT,
        text=False,
    )
    if proc.returncode != 0:
        tail = log_file.read_text(encoding="utf-8", errors="replace")[-2000:]
        raise RuntimeError(f"shop-points compile 失败 exit={proc.returncode}\n{tail}")
    return {"status": "compiled", "cmd": " ".join(cmd), "log": str(log_file)}


def _java_pid_on_port(port: int) -> int | None:
    result = subprocess.run(
        ["lsof", "-ti", f":{port}"],
        capture_output=True,
        text=True,
    )
    pids = [int(p) for p in result.stdout.strip().split() if p.strip().isdigit()]
    for pid in pids:
        ps = subprocess.run(
            ["ps", "-p", str(pid), "-o", "comm="],
            capture_output=True,
            text=True,
        )
        if "java" in (ps.stdout or "").lower():
            return pid
    return pids[0] if pids else None


def _process_start_epoch(pid: int) -> float | None:
    result = subprocess.run(
        ["ps", "-p", str(pid), "-o", "lstart="],
        capture_output=True,
        text=True,
    )
    line = result.stdout.strip()
    if not line:
        return None
    try:
        dt = datetime.strptime(line, "%a %b %d %H:%M:%S %Y")
        return dt.timestamp()
    except ValueError:
        return None


def kecoin_controller_class_path(cfg: StackConfig) -> Path:
    return (
        cfg.shop_points_repo
        / "shop-points-start/target/classes/com/ke/shop/points/controller/manage/upload/KeCoinV2UploadController.class"
    )


def shop_points_binary_stale(cfg: StackConfig) -> bool:
    """target/classes 晚于 JVM 启动时间 → spring-boot:run 未加载新 Controller。"""
    controller = kecoin_controller_class_path(cfg)
    if not controller.exists():
        return True
    pid = _java_pid_on_port(cfg.shop_points_port)
    if not pid:
        return False
    started = _process_start_epoch(pid)
    if started is None:
        return False
    return controller.stat().st_mtime > started + 1.0


def shop_points_kecoin_period_status(cfg: StackConfig) -> int | None:
    """直连本地 JVM；302/401 表示路由已注册，404 表示旧进程未加载新 Controller。"""
    return http_status(shop_points_kecoin_period_url(cfg))


def http_post_status(
    url: str,
    body: bytes = b"{}",
    headers: dict[str, str] | None = None,
    timeout: float = 8.0,
) -> int | None:
    hdrs = {"Content-Type": "application/json", **(headers or {})}
    try:
        req = urllib.request.Request(url, data=body, headers=hdrs, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return None


def ensure_node_modules(client_dir: Path, label: str) -> None:
    """前端 dev server 依赖 node_modules/.bin/craco；缺失时用 npm ci 安装（不升级 lockfile）。"""
    craco = client_dir / "node_modules" / ".bin" / "craco"
    if craco.exists():
        return
    lock = client_dir / "package-lock.json"
    if not lock.exists():
        raise RuntimeError(
            f"{label}: 缺少 node_modules 且无 package-lock.json（{client_dir}）。"
            "请在该目录执行 npm ci 或联系仓库维护者。"
        )
    print(f"… {label} 安装依赖 (npm ci，严格按 lockfile) …")
    proc = subprocess.run(
        ["npm", "ci"],
        cwd=str(client_dir),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip()[-800:]
        raise RuntimeError(f"{label} npm ci 失败:\n{tail}")
    if not craco.exists():
        raise RuntimeError(
            f"{label}: npm ci 完成但仍无 node_modules/.bin/craco，请检查 package.json scripts"
        )


def surfaces_skip_warnings(cfg: StackConfig, impact: dict, cli_surfaces: str | None) -> list[str]:
    """impact.md 裁剪 surfaces 时给出显式告警，避免「以为全栈已起、实际 PC/H5 被跳过」。"""
    if cli_surfaces is not None:
        return []
    raw = impact.get("surfaces")
    if not raw:
        return []
    impact_surfaces = (
        [s.strip() for s in raw.split(",") if s.strip()]
        if isinstance(raw, str)
        else list(raw)
    )
    warnings: list[str] = []
    if cfg.skip_pc and "pc" not in impact_surfaces:
        warnings.append(
            "impact.md surfaces 未含 pc → PC webpack (:3000) 已跳过。"
            "若需验收积分/商城管理端，请加 --surfaces h5,pc"
        )
    if cfg.skip_h5 and "h5" not in impact_surfaces:
        warnings.append(
            "impact.md surfaces 未含 h5 → H5 webpack (:9393) 已跳过。"
            "若需验收服务基金商城 H5，请加 --surfaces h5,pc"
        )
    return warnings


def collect_stack_health(cfg: StackConfig) -> dict:
    """启动后健康检查（供 local_stack_up / local_stack_check 共用）。"""
    health: dict = {}
    if not cfg.skip_h5:
        health["h5_nginx_entry"] = http_status(
            gateway_url(cfg, cfg.h5_host, cfg.nginx_port, "/")
        )
        health["h5_entry_deep"] = http_status(h5_entry_url(cfg))
        health["h5_webpack_direct"] = http_status(
            f"http://127.0.0.1:{cfg.frontend_port}/"
        )
        health["h5_preview_cors"] = http_post_status(
            gateway_url(
                cfg,
                cfg.h5_host,
                cfg.nginx_port,
                "/activity-proxy/api/mall/order/preview",
            ),
            body=json.dumps(
                {
                    "productId": 153,
                    "subjectId": cfg.shop_code,
                    "price": 100,
                    "quantity": 1,
                    "attach": {},
                }
            ).encode(),
            headers={"Origin": f"http://{cfg.h5_host}:{cfg.nginx_port}"},
        )
    if not cfg.skip_pc:
        health["pc_nginx_entry"] = http_status(
            gateway_url(cfg, cfg.pc_host, cfg.pc_nginx_port, "/")
        )
        health["pc_entry_deep"] = http_status(pc_entry_url(cfg))
        health["pc_webpack_direct"] = http_status(f"http://127.0.0.1:{cfg.pc_port}/")
        health["pc_login_user_info"] = http_status(
            gateway_url(cfg, cfg.pc_host, cfg.pc_nginx_port, "/loginUser/info")
        )
        health["pc_shop_points_cors"] = http_post_status(
            gateway_url(
                cfg,
                cfg.pc_host,
                cfg.pc_nginx_port,
                "/shop-points/manage/common/permission/projects",
            ),
            headers={"Origin": f"http://{cfg.pc_host}:{cfg.pc_nginx_port}"},
        )
    if cfg.local_shop_points:
        health["shop_points_health"] = http_status(
            f"http://127.0.0.1:{cfg.shop_points_port}/actuator/health"
        )
        impact = parse_impact_frontmatter(cfg.change_dir)
        if impact_requires_kecoin_api(impact, cfg.change_dir):
            health["kecoin_period_api"] = shop_points_kecoin_period_status(cfg)
    if not cfg.skip_lottery:
        health["lottery_health"] = http_status(
            f"http://127.0.0.1:{cfg.lottery_port}/actuator/health"
        )
    health["h5_nginx_port_open"] = is_port_open(cfg.nginx_port)
    health["pc_nginx_port_open"] = is_port_open(cfg.pc_nginx_port)
    return health


def _gateway_unhealthy(status: int | None) -> bool:
    """webpack 已起时，网关 502/503/连接失败才算未就绪；404 多为 SPA 编译瞬态。"""
    return status in (None, 502, 503, 504)


def validate_stack_health(cfg: StackConfig, health: dict) -> list[str]:
    """将健康检查结果转为可行动错误列表；非空时 local_stack_up 应 exit 1。"""
    errors: list[str] = []

    if not cfg.skip_h5:
        if health.get("h5_webpack_direct") != 200:
            errors.append(
                f"H5 webpack :{cfg.frontend_port} 不可达 → "
                f"nginx :{cfg.nginx_port} 页面会 502"
            )
        elif _gateway_unhealthy(health.get("h5_nginx_entry")):
            errors.append(
                f"H5 网关不可达: HTTP {health.get('h5_nginx_entry')}"
            )
        if health.get("h5_preview_cors") == 403:
            errors.append(
                "H5 order/preview CORS 403 → 检查 nginx /activity-proxy/ 是否剥 Origin"
            )

    if not cfg.skip_pc:
        if health.get("pc_webpack_direct") != 200:
            errors.append(
                f"PC webpack :{cfg.pc_port} 不可达 → "
                f"nginx :{cfg.pc_nginx_port} 页面会 502"
            )
        elif _gateway_unhealthy(health.get("pc_nginx_entry")):
            errors.append(
                f"PC 网关不可达: HTTP {health.get('pc_nginx_entry')}"
            )
        login_status = health.get("pc_login_user_info")
        if login_status not in (200, 302, 401):
            errors.append(
                f"PC /loginUser/info 异常 HTTP {login_status} → "
                "确认代理到 agent-lego **test01**（非 dev01）且 VPN 可达"
            )
        if health.get("pc_shop_points_cors") == 403:
            errors.append(
                "PC /shop-points POST CORS 403 → 检查 nginx /shop-points 是否剥 Origin"
            )

    if cfg.local_shop_points and health.get("shop_points_health") != 200:
        errors.append(
            f"shop-points :{cfg.shop_points_port} health 非 200"
        )
    kecoin_status = health.get("kecoin_period_api")
    if kecoin_status == 404:
        errors.append(
            f"keCoin period API 404 → 本地 shop-points 进程过旧（compile 后未重启）。"
            f"执行: kill $(lsof -ti :{cfg.shop_points_port}) 后重新 local_stack_up，"
            "或 mvn compile -pl shop-points-start -am && spring-boot:run"
        )
    impact = parse_impact_frontmatter(cfg.change_dir)
    if cfg.local_shop_points and impact_requires_kecoin_api(impact, cfg.change_dir):
        if shop_points_binary_stale(cfg):
            errors.append(
                f"shop-points :{cfg.shop_points_port} 二进制落后于 target/classes "
                f"（{KECOIN_PERIOD_PATH} 登录后 404）。"
                "请重新 local_stack_up（会自动 compile+重启）或手动重启 shop-points"
            )
    if not cfg.skip_lottery and health.get("lottery_health") != 200:
        errors.append(f"lottery :{cfg.lottery_port} health 非 200")

    return errors


def find_nginx_bin() -> str | None:
    for name in ("nginx", "/opt/homebrew/bin/nginx", "/usr/local/bin/nginx"):
        path = shutil.which(name) if not name.startswith("/") else name
        if path and Path(path).exists():
            return path
    return None


def _shop_points_proxy_pass(cfg: StackConfig, path_suffix: str = "/") -> str:
    if cfg.local_shop_points:
        return f"http://shop_points_local{path_suffix}"
    target = cfg.integral_proxy_target.rstrip("/")
    return f"{target}{path_suffix}"


def _render_server_block(template: str, replacements: dict[str, str]) -> str:
    out = template
    for key, val in replacements.items():
        out = out.replace(f"{{{{{key}}}}}", val)
    return out


def render_nginx_conf(cfg: StackConfig, prefix: Path) -> Path:
    prefix = prefix.resolve()
    if not NGINX_TEMPLATE.exists():
        raise FileNotFoundError(f"缺少 nginx 模板: {NGINX_TEMPLATE}")

    if cfg.local_shop_points:
        h5_integral_pass = "http://shop_points_local/"
        h5_integral_host = cfg.shop_points_host_header
        h5_login_pass = "http://shop_points_local/loginUser/"
        h5_login_host = cfg.shop_points_host_header
        pc_shop_points_pass = "http://shop_points_local"
    else:
        target = cfg.integral_proxy_target.rstrip("/")
        h5_integral_pass = f"{target}/"
        h5_integral_host = cfg.integral_proxy_host
        h5_login_pass = f"{target}/loginUser/"
        h5_login_host = cfg.integral_proxy_host
        pc_shop_points_pass = target  # 无 URI 后缀 → 保留完整 /shop-points/... 路径

    h5_block = ""
    if not cfg.skip_h5:
        h5_block = _render_server_block(
            H5_SERVER_TEMPLATE,
            {
                "NGINX_PORT": str(cfg.nginx_port),
                "H5_HOST": cfg.h5_host,
                "LOTTERY_HOST_HEADER": cfg.lottery_host_header,
                "H5_INTEGRAL_PROXY_PASS": h5_integral_pass,
                "H5_INTEGRAL_PROXY_HOST": h5_integral_host,
                "H5_LOGIN_USER_PASS": h5_login_pass,
                "H5_LOGIN_USER_HOST": h5_login_host,
            },
        )

    pc_block = ""
    if not cfg.skip_pc:
        pc_block = _render_server_block(
            PC_SERVER_TEMPLATE,
            {
                "PC_NGINX_PORT": str(cfg.pc_nginx_port),
                "PC_HOST": cfg.pc_host,
                "LOTTERY_HOST_HEADER": cfg.lottery_host_header,
                "SHOP_POINTS_HOST_HEADER": cfg.shop_points_host_header,
                "PC_SHOP_POINTS_PASS": pc_shop_points_pass,
            },
        )

    template = NGINX_TEMPLATE.read_text(encoding="utf-8")
    rendered = (
        template.replace("{{NGINX_PREFIX}}", str(prefix))
        .replace("{{FRONTEND_PORT}}", str(cfg.frontend_port))
        .replace("{{PC_PORT}}", str(cfg.pc_port))
        .replace("{{LOTTERY_PORT}}", str(cfg.lottery_port))
        .replace("{{SHOP_POINTS_PORT}}", str(cfg.shop_points_port))
        .replace("{{H5_SERVER_BLOCK}}", h5_block)
        .replace("{{PC_SERVER_BLOCK}}", pc_block)
    )
    prefix.mkdir(parents=True, exist_ok=True)
    (prefix / "logs").mkdir(exist_ok=True)
    (prefix / "proxy_temp").mkdir(exist_ok=True)
    (prefix / "client_body_temp").mkdir(exist_ok=True)
    conf_path = prefix / "local-gateway.conf"
    conf_path.write_text(rendered, encoding="utf-8")
    return conf_path


def gateway_url(cfg: StackConfig, host: str, port: int, path: str) -> str:
    base = f"http://{host}"
    if port != 80:
        base = f"{base}:{port}"
    return f"{base}{path}"


def h5_entry_url(cfg: StackConfig) -> str:
    q = f"shopCode={cfg.shop_code}&shopCodeInnerTest={cfg.shop_code}"
    return gateway_url(cfg, cfg.h5_host, cfg.nginx_port, f"/fuwujin-mall/index?{q}")


def pc_entry_url(cfg: StackConfig) -> str:
    return gateway_url(
        cfg, cfg.pc_host, cfg.pc_nginx_port, "/integral2/activity-config/city"
    )


def _wait_for_port(
    proc: subprocess.Popen,
    port: int,
    log_file: Path,
    name: str,
    timeout: int,
) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            tail = log_file.read_text(encoding="utf-8", errors="replace")[-2000:]
            raise RuntimeError(f"{name} 启动失败 exit={proc.returncode}\n{tail}")
        if is_port_open(port):
            return {
                "status": "started",
                "pid": proc.pid,
                "port": port,
                "log": str(log_file),
            }
        time.sleep(2)
    proc.terminate()
    raise RuntimeError(f"{name} 启动超时（{timeout}s），请查看 {log_file.name}")


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
    result = _wait_for_port(proc, cfg.lottery_port, log_file, "lottery", 180)
    result.update({"cmd": " ".join(cmd), "cwd": str(cfg.lottery_repo)})
    return result


def start_shop_points(cfg: StackConfig, log_dir: Path) -> dict:
    if not cfg.local_shop_points:
        return {"status": "skipped", "reason": "remote_shop_points"}
    impact = parse_impact_frontmatter(cfg.change_dir)
    need_kecoin = impact_requires_kecoin_api(impact, cfg.change_dir)
    if is_port_open(cfg.shop_points_port):
        if need_kecoin and shop_points_binary_stale(cfg):
            print(
                f"⚠ shop-points :{cfg.shop_points_port} 进程早于 keCoin Controller 编译时间，"
                "将 compile 并重启"
            )
            kill_processes_on_port(cfg.shop_points_port, "shop-points")
            compile_shop_points(cfg, log_dir)
        else:
            return {
                "status": "already_running",
                "port": cfg.shop_points_port,
                "url": f"http://127.0.0.1:{cfg.shop_points_port}",
            }
    elif need_kecoin:
        compile_shop_points(cfg, log_dir)
    log_file = log_dir / "shop-points.log"
    env = os.environ.copy()
    env["PORT"] = str(cfg.shop_points_port)
    env["KAFKA_CONSUME_ENABLED"] = "false"
    env["SCHEDULE_ENABLED"] = "false"
    cmd = [
        "mvn",
        "spring-boot:run",
        "-pl",
        "shop-points-start",
        f"-Dspring-boot.run.profiles=test",
        f"-Dspring-boot.run.jvmArguments=-Dserver.port={cfg.shop_points_port}",
    ]
    proc = subprocess.Popen(
        cmd,
        cwd=str(cfg.shop_points_repo),
        stdout=log_file.open("w", encoding="utf-8"),
        stderr=subprocess.STDOUT,
        env=env,
        start_new_session=True,
    )
    result = _wait_for_port(
        proc, cfg.shop_points_port, log_file, "shop-points", 240
    )
    result.update({"cmd": " ".join(cmd), "cwd": str(cfg.shop_points_repo)})
    return result


def start_frontend(cfg: StackConfig, log_dir: Path) -> dict:
    if is_port_open(cfg.frontend_port):
        return {
            "status": "already_running",
            "port": cfg.frontend_port,
            "url": f"http://127.0.0.1:{cfg.frontend_port}",
        }
    log_file = log_dir / "frontend-h5.log"
    env = os.environ.copy()
    env["BUILD_ENV"] = "development"
    env["PORT"] = str(cfg.frontend_port)
    cmd = ["npx", "craco", "start"]
    proc = subprocess.Popen(
        cmd,
        cwd=str(cfg.h5_repo),
        stdout=log_file.open("w", encoding="utf-8"),
        stderr=subprocess.STDOUT,
        env=env,
        start_new_session=True,
    )
    result = _wait_for_port(proc, cfg.frontend_port, log_file, "H5 frontend", 120)
    result.update(
        {
            "cmd": "BUILD_ENV=development npx craco start",
            "cwd": str(cfg.h5_repo),
        }
    )
    return result


def start_pc_frontend(cfg: StackConfig, log_dir: Path) -> dict:
    if is_port_open(cfg.pc_port):
        return {
            "status": "already_running",
            "port": cfg.pc_port,
            "url": f"http://127.0.0.1:{cfg.pc_port}",
        }
    log_file = log_dir / "frontend-pc.log"
    env = os.environ.copy()
    env["BUILD_ENV"] = "development"
    env["PORT"] = str(cfg.pc_port)
    # package.json: "start": "BUILD_ENV=development craco start"
    # 优先 npm start（依赖本地 node_modules/.bin），避免 npx 找不到 craco
    cmd = ["npm", "start"]
    proc = subprocess.Popen(
        cmd,
        cwd=str(cfg.pc_client_dir),
        stdout=log_file.open("w", encoding="utf-8"),
        stderr=subprocess.STDOUT,
        env=env,
        start_new_session=True,
    )
    result = _wait_for_port(proc, cfg.pc_port, log_file, "PC frontend", 180)
    result.update(
        {
            "cmd": "PORT=... npm start",
            "cwd": str(cfg.pc_client_dir),
        }
    )
    return result


def _nginx_listen_ports(cfg: StackConfig) -> list[int]:
    ports: list[int] = []
    if not cfg.skip_h5:
        ports.append(cfg.nginx_port)
    if not cfg.skip_pc:
        ports.append(cfg.pc_nginx_port)
    return ports


def _try_reuse_healthy_nginx(cfg: StackConfig) -> dict | None:
    """端口已被占用时：健康检查通过则复用，避免 bind() 失败阻塞 Pipeline。"""
    ports = _nginx_listen_ports(cfg)
    if not ports or not all(is_port_open(p) for p in ports):
        return None
    health = collect_stack_health(cfg)
    errors = validate_stack_health(cfg, health)
    if errors:
        return None
    print(
        f"✓ nginx 端口 {ports} 已在监听且健康检查通过，复用现有网关（跳过重复 bind）"
    )
    return {
        "status": "reused",
        "reason": "ports_healthy",
        "h5_port": cfg.nginx_port if not cfg.skip_h5 else None,
        "pc_port": cfg.pc_nginx_port if not cfg.skip_pc else None,
        "health": health,
    }


def start_nginx(cfg: StackConfig, prefix: Path, conf_path: Path) -> dict:
    reused = _try_reuse_healthy_nginx(cfg)
    if reused:
        return reused

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
        err = start.stderr or start.stdout or ""
        if "bind()" in err or "Address already in use" in err:
            reused = _try_reuse_healthy_nginx(cfg)
            if reused:
                return reused
            ports = _nginx_listen_ports(cfg)
            print(
                f"⚠ nginx bind 失败，尝试释放占用端口 {ports} 后重试…",
                file=sys.stderr,
            )
            for p in ports:
                kill_processes_on_port(p, f"nginx:{p}")
            retry = subprocess.run(
                [nginx_bin, "-p", str(prefix), "-c", str(conf_path)],
                capture_output=True,
                text=True,
            )
            if retry.returncode == 0:
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
                    "h5_port": cfg.nginx_port,
                    "pc_port": cfg.pc_nginx_port,
                    "recovered": "kill_port_and_retry",
                }
        hint = ""
        if "bind()" in err and (
            cfg.nginx_port < 1024 or cfg.pc_nginx_port < 1024
        ):
            hint = (
                f"\n提示: 监听低端口通常需要 sudo，"
                f"可改用 --nginx-port 8088 --pc-nginx-port 8089"
            )
        raise RuntimeError(f"nginx 启动失败:\n{err}{hint}")

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
        "h5_port": cfg.nginx_port,
        "pc_port": cfg.pc_nginx_port,
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

    shop_points_target = (
        f"本地 shop-points :{cfg.shop_points_port}"
        if cfg.local_shop_points
        else cfg.integral_proxy_target
    )

    lines = [
        "# Local Stack Report（方案 B · nginx 网关）",
        "",
        f"started_at: {state.get('started_at', iso_now())}",
        f"surfaces: `{', '.join(cfg.surfaces)}`",
        "",
        "## 架构",
        "",
        "```",
    ]

    if not cfg.skip_h5:
        lines.extend(
            [
                f"浏览器 → http://{cfg.h5_host}:{cfg.nginx_port}  （H5 网关）",
                f"  ├─ /activity-proxy/* → lottery :{cfg.lottery_port}",
                f"  ├─ /integral-proxy/* → {shop_points_target}",
                f"  ├─ /loginUser/*      → {shop_points_target}",
                f"  └─ 页面/HMR         → webpack :{cfg.frontend_port}",
                "",
            ]
        )
    if not cfg.skip_pc:
        lines.extend(
            [
                f"浏览器 → http://{cfg.pc_host}:{cfg.pc_nginx_port}  （PC 网关）",
                f"  ├─ /shop-points/*    → {shop_points_target}",
                f"  ├─ /activity-proxy/* → lottery :{cfg.lottery_port}",
                f"  ├─ /api/*            → agent-lego test01（远程）",
                f"  ├─ /loginUser/info   → agent-lego test01（远程）",
                f"  └─ 页面/HMR         → PC webpack :{cfg.pc_port}",
                "",
            ]
        )
    lines.append("```")
    lines.extend(["", "## 入口", ""])

    urls = state.get("urls") or {}
    if urls.get("h5_entry"):
        lines.append(f"- H5: `{urls['h5_entry']}`")
    if urls.get("pc_entry"):
        lines.append(f"- PC: `{urls['pc_entry']}`")
    fixtures = load_test_env_fixtures()
    lines.extend(
        [
            "",
            "## 测试可用数据（默认）",
            "",
            f"- {test_env_fixtures_summary()}",
            f"- H5 URL 参数：`shopCode={fixtures['shop_code']}&shopCodeInnerTest={fixtures['shop_code_inner_test']}`",
            f"- PC 筛选：规则城市选 **{fixtures['city_name']}**；上传 Excel 门店列用 `{fixtures['shop_code']}`",
            "- 详见 `knowledge/test-env-topology.md` §测试可用数据",
            "",
        ]
    )
    lines.append(
        f"- lottery 直连: `http://{cfg.lottery_host_header}:{cfg.lottery_port}`"
    )
    if cfg.local_shop_points:
        lines.append(
            f"- shop-points 直连: `http://127.0.0.1:{cfg.shop_points_port}`"
        )
    lines.extend(["", "## 进程", ""])

    for key in (
        "shop_points",
        "lottery",
        "frontend",
        "pc_frontend",
        "nginx",
    ):
        block = state.get(key) or {}
        if not block:
            continue
        lines.append(f"### {key}")
        for k, v in block.items():
            lines.append(f"- {k}: `{v}`")
        lines.append("")

    health = state.get("health") or {}
    if health:
        lines.extend(["## 健康检查", ""])
        for k, v in health.items():
            lines.append(f"- {k}: `{v}`")
        lines.append("")

    health_errors = state.get("health_errors") or []
    if health_errors:
        lines.extend(["## 健康检查失败", ""])
        for err in health_errors:
            lines.append(f"- {err}")
        lines.append("")

    lines.extend(
        [
            "## 停止",
            "",
            "```bash",
            f"python3 skills/req-to-dev/scripts/local_stack_down.py --req-id {cfg.req_id}",
            "```",
            "",
            "## 说明",
            "",
            "- **对业务代码零侵入**：仅 Harness nginx 路由，不改各仓库 craco proxy",
            "- hosts：`127.0.0.1 integral.ttb.test.ke.com local.ttb.test.ke.com point-pc.ttb.test.ke.com`",
            f"- 登录凭证：`{CONFIG_DIR / 'secrets.local.json'}` → `test_env_app`",
            "- PC `/api` 与 `/loginUser/info` 仍走远程 agent-lego",
            "- CAS 回跳：见 `playbooks/local-stack-troubleshooting.md` §四",
            "- 排障：`playbooks/local-stack-troubleshooting.md`",
            "",
        ]
    )
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report
