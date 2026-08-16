"""一键刷新头歌 + 中国大学MOOC 的登录 Cookie，自动更新 config.json。

用法:
    python refresh_cookies.py           # 检测过期，只在失效时重新登录(适合定时自动跑)
    python refresh_cookies.py --force   # 强制重新登录刷新

依赖: pip install playwright (使用系统 Edge 浏览器，无需下载 Chromium)
账密读取 config.json 里的 educoder_phone / educoder_password / mooc_phone / mooc_password。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

# pythonw 无控制台时 sys.stdout 为 None，print 会崩；兜底到 devnull
if sys.stdout is None:
    sys.stdout = sys.stderr = open(os.devnull, "w", encoding="utf-8")

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
CONFIG = ROOT / "config.json"

MOOC_COOKIE_NAMES = ["NTESSTUDYSI", "STUDY_SESS", "STUDY_PERSIST", "STUDY_INFO", "NTES_YD_SESS", "NTES_YD_PASSPORT"]
EDUCODER_COOKIE_NAMES = ["autologin_trustie", "_educoder_session"]


def load_cfg() -> dict:
    with open(CONFIG, "r", encoding="utf-8") as f:
        return json.load(f)


def save_cfg(cfg: dict) -> None:
    with open(CONFIG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def cookies_to_str(cookies, names) -> str:
    return "; ".join(f"{c['name']}={c['value']}" for c in cookies if c["name"] in names)


def cookies_valid(cfg: dict) -> tuple[bool, bool]:
    """检测两个平台 Cookie 是否仍有效，返回 (头歌有效, MOOC有效)。"""
    from src.fetchers.educoder import EducoderFetcher
    from src.fetchers.mooc import MoocFetcher

    ev = mv = False
    try:
        f = EducoderFetcher(cfg.get("educoder_cookie", ""), username=cfg.get("educoder_username", ""))
        ev = len(f.fetch_courses()) > 0
    except Exception:
        ev = False
    try:
        f = MoocFetcher(cfg.get("mooc_cookie", ""))
        mv = len(f.fetch_courses()) > 0
    except Exception:
        mv = False
    return ev, mv


def refresh_educoder(ctx, phone: str, password: str) -> str:
    page = ctx.new_page()
    page.goto("https://www.educoder.net/", wait_until="domcontentloaded")
    page.wait_for_timeout(2000)
    # 已登录（导航栏有 /messages/ 链接）则跳过登录表单
    if page.locator('a[href*="/messages/"]').count() == 0:
        page.get_by_text("登录 / 注册").first.click(force=True)
        page.get_by_placeholder("请输入有效的手机号/邮箱号/账号").fill(phone)
        page.get_by_placeholder("密码").fill(password)
        page.wait_for_timeout(800)
        page.get_by_role("button", name="登录").click(force=True)
        page.wait_for_timeout(3000)
    cookie = cookies_to_str(ctx.cookies(), EDUCODER_COOKIE_NAMES)
    page.close()
    if "_educoder_session" not in cookie:
        raise RuntimeError("头歌登录失败，Cookie 里没有 _educoder_session")
    return cookie


def refresh_mooc(ctx, phone: str, password: str) -> str:
    page = ctx.new_page()
    page.goto("https://www.icourse163.org/", wait_until="domcontentloaded")
    page.get_by_text("登录 | 注册").first.click()
    page.wait_for_timeout(4000)
    filled = False
    for frame in page.frames:
        try:
            phone_input = frame.get_by_placeholder("请输入手机号")
            pwd_input = frame.get_by_placeholder("请输入密码")
            if phone_input.count() > 0 and pwd_input.count() > 0:
                phone_input.first.fill(phone)
                pwd_input.first.fill(password)
                pwd_input.first.press("Enter")
                filled = True
                break
        except Exception:
            continue
    if not filled:
        raise RuntimeError("MOOC 登录表单未找到")
    page.wait_for_timeout(6000)
    cookie = cookies_to_str(ctx.cookies(), MOOC_COOKIE_NAMES)
    page.close()
    if "NTESSTUDYSI" not in cookie:
        raise RuntimeError("MOOC 登录失败，Cookie 里没有 NTESSTUDYSI")
    return cookie


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="强制重新登录")
    args = parser.parse_args()

    cfg = load_cfg()
    edu_phone = cfg.get("educoder_phone", "")
    edu_password = cfg.get("educoder_password", "")
    mooc_phone = cfg.get("mooc_phone", "")
    mooc_password = cfg.get("mooc_password", "")

    # 检测哪些需要刷新
    if args.force:
        need_edu = need_mooc = True
    else:
        ev, mv = cookies_valid(cfg)
        need_edu = not ev
        need_mooc = not mv
        if ev:
            print("头歌 Cookie 仍有效，跳过")
        if mv:
            print("MOOC Cookie 仍有效，跳过")

    # 平台开关：关闭的平台不刷新
    if not cfg.get("educoder_enabled", True):
        need_edu = False
        print("头歌已禁用，跳过")
    if not cfg.get("mooc_enabled", True):
        need_mooc = False
        print("MOOC 已禁用，跳过")

    if not need_edu and not need_mooc:
        print("无需刷新")
        return 0

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=False, args=["--window-position=-32000,-32000"])
        ctx = browser.new_context()

        if need_edu:
            if not edu_phone or not edu_password:
                print("✗ 头歌缺少账号密码，跳过（请在 config.json 填 educoder_phone / educoder_password）")
            else:
                try:
                    cfg["educoder_cookie"] = refresh_educoder(ctx, edu_phone, edu_password)
                    print("✓ 头歌 Cookie 已刷新")
                except Exception as e:
                    print(f"✗ 头歌刷新失败: {e}")

        if need_mooc:
            if not mooc_phone or not mooc_password:
                print("✗ MOOC 缺少账号密码，跳过（请在 config.json 填 mooc_phone / mooc_password）")
            else:
                try:
                    cfg["mooc_cookie"] = refresh_mooc(ctx, mooc_phone, mooc_password)
                    print("✓ MOOC Cookie 已刷新")
                except Exception as e:
                    print(f"✗ MOOC 刷新失败: {e}")

        browser.close()

    save_cfg(cfg)
    print("config.json 已保存")
    return 0


if __name__ == "__main__":
    sys.exit(main())
