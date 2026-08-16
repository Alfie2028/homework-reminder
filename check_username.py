"""检查并修正头歌用户名(educoder_username)。

头歌 API 用的是内部用户名(如 pn3kvxzay)，不是手机号。本工具自动登录头歌，
从账号里探测出正确用户名，和 config.json 里的对比，不对就自动改。

用法:
    python check_username.py           # 自动检测并修正
    python check_username.py --set xxx # 手动指定用户名

依赖: pip install playwright (使用系统 Edge)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "config.json"


def load_cfg() -> dict:
    with open(CONFIG, "r", encoding="utf-8") as f:
        return json.load(f)


def save_cfg(cfg: dict) -> None:
    with open(CONFIG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def detect_username(phone: str, password: str) -> str:
    """登录头歌，从消息链接 /messages/{用户名}/ 里提取用户名。"""
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=False, args=["--window-position=-32000,-32000"])
        page = browser.new_context().new_page()
        page.goto("https://www.educoder.net/", wait_until="domcontentloaded")
        page.get_by_text("登录 / 注册").first.click()
        page.get_by_placeholder("请输入有效的手机号/邮箱号/账号").fill(phone)
        page.get_by_placeholder("密码").fill(password)
        page.wait_for_timeout(800)
        page.get_by_role("button", name="登录").click(force=True)
        page.wait_for_timeout(3000)

        # 从 /messages/{用户名}/ 链接里提取
        for href in page.eval_on_selector_all(
            'a[href*="/messages/"]', "els => els.map(e => e.getAttribute('href'))"
        ):
            m = re.search(r"/messages/([^/]+)", href)
            if m:
                browser.close()
                return m.group(1)
        browser.close()
    return ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--set", dest="manual", help="手动指定用户名")
    args = parser.parse_args()

    cfg = load_cfg()
    current = cfg.get("educoder_username", "")

    if args.manual:
        cfg["educoder_username"] = args.manual
        save_cfg(cfg)
        print(f"已手动设置 educoder_username = {args.manual}")
        return 0

    phone = cfg.get("educoder_phone", "")
    password = cfg.get("educoder_password", "")
    if not phone or not password:
        print("缺少 educoder_phone / educoder_password，请先填 config.json")
        return 1

    print(f"当前 educoder_username = {current!r}")
    print("正在登录头歌探测正确用户名...")
    detected = detect_username(phone, password)
    if not detected:
        print("✗ 探测失败，未找到用户名")
        return 1

    print(f"探测到的用户名 = {detected!r}")
    if detected == current:
        print("✓ 用户名正确，无需修改")
        return 0

    cfg["educoder_username"] = detected
    save_cfg(cfg)
    print(f"✓ 已自动修正：{current!r} → {detected!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
