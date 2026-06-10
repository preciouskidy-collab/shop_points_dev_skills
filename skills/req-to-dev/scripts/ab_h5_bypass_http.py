#!/usr/bin/env python3
"""agent-browser H5：手机模式 + CAS 登录（员工→账号登录）+ HTTP 不安全连接绕过。

流程：
  1. close → Chrome 带 DEFAULT_ARGS 启动 → set device iPhone → open H5
  2. CAS：点「员工」→ 点「账号登录」（手机端选员工后通常已在账号表单）
  3. 填表登录；若仍出现 chrome-error / 不安全连接，用启动参数 + 关多余 Tab 处理

用法：
  python3 ab_h5_bypass_http.py           # 完整流程
  python3 ab_h5_bypass_http.py proceed-only  # 仅处理当前拦截页
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

CLI = os.environ.get(
    "AGENT_BROWSER_CLI",
    "/opt/anaconda3/lib/python3.12/site-packages/agent_browser/bin/agent-browser-darwin-arm64",
)
DEFAULT_ARGS = (
    "--unsafely-treat-insecure-origin-as-secure=http://integral.ttb.test.ke.com,"
    "http://shop-points-lottery.shop-points-test01.ttb.test.ke.com,"
    "http://shop-points-lottery.shop-points-test01.ttb.test.ke.com:80,"
    "http://shop-points.shop-points-test01.ttb.test.ke.com,"
    "http://shop-points.shop-points-test01.ttb.test.ke.com:80,"
    "--disable-features=HttpsFirstMode,HttpsUpgrades,HttpsFirstBalancedMode,"
    "--disable-web-security,--allow-running-insecure-content,"
    "--ignore-certificate-errors,--test-type,--remote-allow-origins=*"
)
SECRETS = Path(__file__).resolve().parents[1] / "config" / "secrets.local.json"
H5_URL = (
    "http://integral.ttb.test.ke.com/fuwujin-mall/index"
    "?shopCode=TJDY0101&shopCodeInnerTest=TJDY0101"
)
H5_DEVICE = os.environ.get("AGENT_BROWSER_H5_DEVICE", "iPhone 12")


def _truthy(raw: str) -> bool:
    return raw.strip().strip('"').lower() in ("true", "1", "yes")


def _ok(out: str) -> bool:
    return "✓" in out or out.lower().endswith("done")


def ab(session: str, *args: str, extra_env: dict | None = None) -> str:
    env = os.environ.copy()
    env.setdefault(
        "AGENT_BROWSER_EXECUTABLE_PATH",
        os.path.expanduser(
            "~/.agent-browser/browsers/chrome-149.0.7827.55/"
            "Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"
        ),
    )
    env.setdefault("AGENT_BROWSER_HEADED", "1")
    env.setdefault("AGENT_BROWSER_ARGS", DEFAULT_ARGS)
    env["AGENT_BROWSER_SESSION_NAME"] = session
    if extra_env:
        env.update(extra_env)
    r = subprocess.run(
        [CLI, "--session", session, *args],
        capture_output=True,
        text=True,
        env=env,
    )
    out = (r.stdout or r.stderr or "").strip()
    return out


def eval_text(session: str, js: str) -> str:
    raw = ab(session, "eval", js)
    if raw.startswith('"'):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
    return raw.strip().strip('"')


def is_on_h5(url: str) -> bool:
    return url.startswith("http://integral.ttb.test.ke.com") and "chrome-error" not in url


def is_select_account_page(session: str) -> bool:
    """仅看页面文案；#/select-as 在选完员工后仍留在 URL 上，不能作为判断依据。"""
    body = eval_text(session, "document.body.innerText.slice(0,100)")
    if has_login_form(session) or "返回账号选择" in body or "找回密码" in body:
        return False
    return "选择账号类型" in body


def has_login_form(session: str) -> bool:
    return _truthy(
        ab(
            session,
            "eval",
            "!!document.querySelector('input[placeholder*=\"密码\"], input[type=\"password\"]')",
        )
    )


def wait_until(session: str, js: str, timeout_s: float = 30, interval_s: float = 0.5) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if _truthy(ab(session, "eval", js)):
            return True
        time.sleep(interval_s)
    return False


def wait_cas_ready(session: str) -> None:
    """networkidle 后 SPA 仍可能显示「加载中...」，需等按钮可交互。"""
    wait_until(
        session,
        "!document.body.innerText.includes('加载中') && "
        "(!!document.querySelector('button') || !!document.querySelector('.p-account-name'))",
        timeout_s=25,
    )
    time.sleep(1)


def click_proceed_via_accessibility() -> str:
    script = '''
tell application "Google Chrome for Testing" to activate
delay 0.4
tell application "System Events"
  tell process "Google Chrome for Testing"
    set frontmost to true
    repeat with w in windows
      try
        click button "继续访问网站" of w
        return "clicked:继续访问网站"
      end try
      try
        click button "Continue to site" of w
        return "clicked:Continue to site"
      end try
    end repeat
  end tell
end tell
return "not_found"
'''
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return (r.stdout or r.stderr or "").strip()


def list_tab_lines(session: str) -> list[str]:
    listing = ab(session, "tab", "list")
    return [ln.strip() for ln in listing.splitlines() if ln.strip().startswith(("[", "→"))]


def find_h5_tab_index(session: str) -> int | None:
    for i, ln in enumerate(list_tab_lines(session)):
        if "integral.ttb.test.ke.com" in ln and "chrome-error" not in ln:
            return i
    return None


def switch_tab(session: str, index: int) -> None:
    ab(session, "tab", str(index))


def close_extra_tabs(session: str) -> None:
    lines = list_tab_lines(session)
    keep = find_h5_tab_index(session)
    if keep is None:
        keep = 0
    for i in range(len(lines) - 1, -1, -1):
        if i != keep:
            ab(session, "tab", "close", str(i))
    switch_tab(session, min(keep, len(lines) - 1))


def bypass_http_on_all_tabs(session: str, max_rounds: int = 5) -> bool:
    """处理所有 Tab 上的 chrome-error / 不安全连接拦截。"""
    for round_i in range(max_rounds):
        if find_h5_tab_index(session) is not None:
            switch_tab(session, find_h5_tab_index(session) or 0)
            if is_on_h5(ab(session, "get", "url")):
                return True

        lines = list_tab_lines(session)
        progressed = False
        for idx in range(len(lines)):
            switch_tab(session, idx)
            url = ab(session, "get", "url")
            if is_on_h5(url):
                close_extra_tabs(session)
                return True
            if "chrome-error" in url or "ERR_BLOCKED" in url:
                result = click_proceed_via_accessibility()
                print(f"[bypass] tab {idx} round {round_i + 1}: {result}", file=sys.stderr)
                time.sleep(2)
                progressed = True
            elif url.startswith("http://") and "test-login" not in url:
                ab(session, "reload")
                time.sleep(2)
                progressed = True

        if not progressed:
            break
        time.sleep(2)

    close_extra_tabs(session)
    return is_on_h5(ab(session, "get", "url"))


def click_employee(session: str) -> bool:
    if not is_select_account_page(session):
        return has_login_form(session) or "返回账号选择" in eval_text(
            session, "document.body.innerText.slice(0,80)"
        )

    wait_cas_ready(session)

    for attempt in range(6):
        if _truthy(ab(session, "eval", "!!document.querySelector('.p-account-name')")):
            ab(
                session,
                "eval",
                """
(() => {
  const p = Array.from(document.querySelectorAll('.p-account-name'))
    .find(el => el.textContent.trim() === '员工');
  if (p?.parentElement) { p.parentElement.click(); return 'ok'; }
  return 'no';
})()
""",
            )
        else:
            ab(session, "find", "role", "button", "click", "--name", "员工")

        time.sleep(2)
        if not is_select_account_page(session):
            return True
        print(f"[cas_login] 员工选择重试 {attempt + 1}", file=sys.stderr)

    return not is_select_account_page(session)


def click_account_login_tab(session: str) -> bool:
    if has_login_form(session):
        return True

    for attempt in range(4):
        ab(session, "find", "text", "账号登录", "click")
        ab(
            session,
            "eval",
            """
(() => {
  const a = document.querySelector('a[href="/login/username-password"]')
    || Array.from(document.querySelectorAll('a')).find(el => el.textContent.trim() === '账号登录');
  if (a) { a.click(); return 'ok'; }
  return 'no';
})()
""",
        )
        time.sleep(1.5)
        if has_login_form(session):
            return True
        print(f"[cas_login] 账号登录 Tab 重试 {attempt + 1}", file=sys.stderr)

    return has_login_form(session)


def cas_login(session: str, username: str, password: str) -> bool:
    print("[cas_login] 1/3 选择员工", file=sys.stderr)
    if not click_employee(session):
        print("[cas_login] 失败：未能选择员工", file=sys.stderr)
        return False

    print("[cas_login] 2/3 切换账号登录", file=sys.stderr)
    if not click_account_login_tab(session):
        print("[cas_login] 失败：未能进入账号登录表单", file=sys.stderr)
        return False

    print("[cas_login] 3/3 填写并提交", file=sys.stderr)
    ab(
        session,
        "fill",
        "input[placeholder*='手机'], input[placeholder*='账号']",
        username,
    )
    ab(
        session,
        "fill",
        "input[placeholder*='密码'], input[type='password']",
        password,
    )
    if not _ok(ab(session, "find", "role", "button", "click", "--name", "登录")):
        ab(session, "find", "role", "button", "click", "--name", "登 录")

    # 等待跳回 H5 或出现中间 Tab
    for _ in range(30):
        time.sleep(1)
        if find_h5_tab_index(session) is not None:
            switch_tab(session, find_h5_tab_index(session) or 0)
            if is_on_h5(ab(session, "get", "url")):
                return True
        if bypass_http_on_all_tabs(session):
            return True

    return bypass_http_on_all_tabs(session)


def ensure_mobile_mode(session: str) -> None:
    ab(session, "set", "device", H5_DEVICE)


def ensure_h5_browser(session: str) -> None:
    ab(session, "close")
    time.sleep(1)
    ab(
        session,
        "--args",
        DEFAULT_ARGS,
        "open",
        "about:blank",
        extra_env={"AGENT_BROWSER_ARGS": DEFAULT_ARGS},
    )
    ensure_mobile_mode(session)
    ab(session, "open", H5_URL)
    ab(session, "wait", "--load", "networkidle")
    wait_cas_ready(session)


def main() -> int:
    session = os.environ.get("AGENT_BROWSER_SESSION_NAME", "req-to-dev-h5-auto")
    secrets = json.loads(SECRETS.read_text())
    creds = secrets["test_env_app"]

    if len(sys.argv) > 1 and sys.argv[1] == "proceed-only":
        ok = bypass_http_on_all_tabs(session)
        print("OK" if ok else "FAIL", ab(session, "get", "url"))
        return 0 if ok else 1

    ensure_h5_browser(session)
    url = ab(session, "get", "url")
    body = eval_text(session, "document.body.innerText.slice(0,80)")

    if "test-login" in url or is_select_account_page(session) or "选择账号类型" in body:
        if not cas_login(session, creds["username"], creds["password"]):
            print(f"final_url={url}", file=sys.stderr)
            return 1

    bypass_http_on_all_tabs(session)
    ensure_mobile_mode(session)

    if not is_on_h5(ab(session, "get", "url")):
        ab(session, "open", H5_URL)
        ab(session, "wait", "--load", "networkidle")
        bypass_http_on_all_tabs(session)

    close_extra_tabs(session)
    final = ab(session, "get", "url")
    text = eval_text(session, "document.body.innerText.slice(0,120)")
    tabs = list_tab_lines(session)
    print(f"final_url={final}")
    print(f"tabs={len(tabs)}")
    print(f"text={text}")
    return 0 if is_on_h5(final) and "积分商城" in text else 1


if __name__ == "__main__":
    raise SystemExit(main())
