"""Playwright CAS 登录（员工 → 账号登录 → 填表），与 ab_h5_bypass_http 流程对齐。"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import Page


def _is_select_account_page(page: "Page") -> bool:
    body = page.inner_text("body", timeout=5000)
    return "选择账号类型" in body


def _has_login_form(page: "Page") -> bool:
    for sel in ('input[name="username"]', 'input[type="password"]', '#username'):
        try:
            if page.locator(sel).first.is_visible(timeout=1000):
                return True
        except Exception:
            pass
    return False


def _wait_cas_ready(page: "Page", *, timeout_sec: int = 30) -> str:
    """等待 CAS SPA 就绪，返回 select|form|done。"""
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        url = page.url
        if "test-login" not in url:
            return "done"
        body = ""
        try:
            body = page.inner_text("body", timeout=3000)
        except Exception:
            pass
        if "加载中" in body and "选择账号类型" not in body:
            time.sleep(1)
            continue
        if "选择账号类型" in body:
            return "select"
        if _has_login_form(page) or "返回账号选择" in body:
            return "form"
        time.sleep(1)
    return "select" if _is_select_account_page(page) else "done"


def click_employee(page: "Page", *, retries: int = 5) -> bool:
    state = _wait_cas_ready(page)
    if state == "done":
        return True
    if state == "form":
        return True
    for attempt in range(retries):
        if not _is_select_account_page(page):
            return True
        # PC 模式：.p-account-name 员工卡片（playbooks/e2e-browser-test.md）
        try:
            card = page.locator(".p-account-name").filter(has_text="员工").first
            if card.is_visible(timeout=3000):
                card.click()
                time.sleep(2)
                if not _is_select_account_page(page):
                    return True
                card.locator("xpath=ancestor::*[contains(@class,'account') or contains(@class,'item')][1]").click(
                    timeout=2000
                )
        except Exception:
            pass
        page.evaluate(
            """() => {
  const p = Array.from(document.querySelectorAll('.p-account-name, span, div'))
    .find(el => el.textContent.trim() === '员工');
  if (p?.parentElement) { p.parentElement.click(); return 'ok'; }
  return 'no';
}"""
        )
        time.sleep(2)
        try:
            page.get_by_text("员工", exact=True).first.click(timeout=3000)
        except Exception:
            pass
        time.sleep(2)
        _wait_cas_ready(page, timeout_sec=10)
        if not _is_select_account_page(page):
            return True
    return not _is_select_account_page(page)


def click_account_login_tab(page: "Page", *, retries: int = 3) -> bool:
    for attempt in range(retries):
        if _has_login_form(page):
            return True
        page.evaluate(
            """() => {
  const a = Array.from(document.querySelectorAll('a, span, div'))
    .find(el => el.textContent.trim() === '账号登录');
  if (a) { a.click(); return 'ok'; }
  return 'no';
}"""
        )
        try:
            page.get_by_text("账号登录", exact=True).first.click(timeout=3000)
        except Exception:
            pass
        time.sleep(1.5)
        if _has_login_form(page):
            return True
    return _has_login_form(page)


def fill_and_submit(page: "Page", username: str, password: str) -> None:
    for sel in ('input[name="username"]', '#username', 'input[placeholder*="账号"]', 'input[type="text"]'):
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=2000):
                loc.fill(username)
                break
        except Exception:
            pass
    for sel in ('input[name="password"]', '#password', 'input[type="password"]'):
        try:
            page.locator(sel).first.fill(password, timeout=5000)
            break
        except Exception:
            pass
    for sel in ('button[type="submit"]', 'text=登 录'):
        try:
            page.locator(sel).first.click(timeout=5000)
            return
        except Exception:
            pass
    try:
        page.get_by_role("button", name="登录").click(timeout=5000)
    except Exception:
        page.get_by_role("button", name="登 录").click(timeout=5000)


def cas_login(page: "Page", username: str, password: str, *, wait_sec: int = 8) -> bool:
    """在 CAS 页完成登录；若已在业务页则直接返回 True。"""
    if "test-login" not in page.url and not _is_select_account_page(page):
        return True
    if not click_employee(page):
        return False
    if not click_account_login_tab(page):
        return False
    fill_and_submit(page, username, password)
    try:
        page.wait_for_load_state("networkidle", timeout=90000)
    except Exception:
        pass
    time.sleep(wait_sec)
    return "test-login" not in page.url


def ensure_logged_in(
    page: "Page",
    username: str,
    password: str,
    target_url: str,
    *,
    timeout_ms: int = 90000,
) -> None:
    page.goto(target_url, wait_until="domcontentloaded", timeout=timeout_ms)
    time.sleep(3)
    if "test-login" in page.url:
        _wait_cas_ready(page, timeout_sec=30)
    if "test-login" in page.url or _is_select_account_page(page):
        if not cas_login(page, username, password):
            raise RuntimeError(f"CAS 登录失败: {page.url}")
        page.goto(target_url, wait_until="networkidle", timeout=timeout_ms)
        time.sleep(3)
    if "test-login" in page.url:
        raise RuntimeError(f"CAS 登录未完成: {page.url}")
