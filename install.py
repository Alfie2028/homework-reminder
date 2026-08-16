"""作业提醒 · 安装向导。

双击「安装.bat」后调用本脚本，依次完成：选择平台 → 输入账密 →
输入推送密钥 → 设置检测频率与通知时间 → 自动登录 → 注册定时任务。
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "config.json"

try:
    import msvcrt
except ImportError:  # 非 Windows 环境
    msvcrt = None


# ANSI 颜色（Windows 终端高亮提示用）
RED = "\033[31m"
YELLOW = "\033[33m"
BOLD = "\033[1m"
RESET = "\033[0m"


def _enable_vt() -> None:
    """Windows 上启用 ANSI 转义序列支持（否则颜色码会显示成乱码）。"""
    if sys.platform == "win32":
        try:
            import ctypes
            k = ctypes.windll.kernel32
            h = k.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
            mode = ctypes.c_uint32()
            k.GetConsoleMode(h, ctypes.byref(mode))
            k.SetConsoleMode(h, mode.value | 0x0004)  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
        except Exception:
            pass


def load_cfg() -> dict:
    if CONFIG.exists():
        with open(CONFIG, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cfg(cfg: dict) -> None:
    with open(CONFIG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def input_password(prompt: str) -> str:
    """输入密码，回显星号。"""
    print(prompt, end="", flush=True)
    if msvcrt is None:
        return input()
    chars: list[str] = []
    while True:
        ch = msvcrt.getwch()
        if ch in ("\r", "\n"):
            print()
            break
        elif ch in ("\x08", "\x7f"):  # 退格
            if chars:
                chars.pop()
                print("\b \b", end="", flush=True)
        elif ch == "\x03":  # Ctrl+C
            raise KeyboardInterrupt
        else:
            chars.append(ch)
            print("*", end="", flush=True)
    return "".join(chars)


def select_platform() -> tuple[bool, bool]:
    print()
    print("请选择需要监控作业的学习平台：")
    print("  1 = 头歌")
    print("  2 = 中国大学MOOC")
    print("  3 = 两个平台")
    while True:
        c = input("请输入对应数字：").strip()
        if c == "1":
            return True, False
        if c == "2":
            return False, True
        if c == "3":
            return True, True
        print("输入无效，请输入 1 / 2 / 3")


def select_interval() -> int:
    print()
    print("请设置作业检测频率（本程序为定期检测，并非实时监控）：")
    print("  1 = 每 1 小时")
    print("  2 = 每 2 小时")
    print("  3 = 每 3 小时（推荐）")
    print("  4 = 每 6 小时")
    print("检测间隔越短，越能及时通知你新发布的任务。")
    c = input("直接按回车键 = 使用默认值（每 3 小时）：").strip()
    return {"1": 1, "2": 2, "3": 3, "4": 6, "": 3}.get(c, 3)


def select_time() -> str:
    print()
    t = input(
        "请设置每日汇总通知的推送时间。\n"
        "直接按回车键 = 使用默认值 12:30\n"
        "如需修改，请输入时间（格式示例：08:00）："
    ).strip()
    if not t:
        return "12:30"
    if re.fullmatch(r"\d{2}:\d{2}", t):
        h, m = int(t[:2]), int(t[3:])
        if 0 <= h <= 23 and 0 <= m <= 59:
            return t
    print("时间格式有误，使用默认值 12:30")
    return "12:30"


def input_key() -> str:
    print()
    print("请输入推送密钥（用于将通知发送至微信）：")
    print("  获取方式：访问 https://sct.ftqq.com ，使用微信扫码登录后获取。")
    while True:
        k = input("  请输入：").strip()
        if k:
            return k
        print("  密钥不能为空，请重新输入")


def login_educoder(ctx, phone: str, password: str) -> tuple[str, str]:
    """登录头歌，返回 (cookie, username)。"""
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

    cookie = "; ".join(
        f"{c['name']}={c['value']}" for c in ctx.cookies()
        if c["name"] in ("autologin_trustie", "_educoder_session")
    )
    username = ""
    for href in page.eval_on_selector_all(
        'a[href*="/messages/"]', "els => els.map(e => e.getAttribute('href'))"
    ):
        m = re.search(r"/messages/([^/]+)", href)
        if m:
            username = m.group(1)
            break
    page.close()
    return cookie, username


def auto_login(cfg: dict, edu_phone: str, edu_password: str, mooc_phone: str, mooc_password: str) -> None:
    from refresh_cookies import refresh_mooc
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=False)
        ctx = browser.new_context()

        if cfg.get("educoder_enabled"):
            print("正在登录「头歌」平台...")
            print("  系统将自动打开浏览器完成登录，请勿手动操作。")
            cookie, username = login_educoder(ctx, edu_phone, edu_password)
            if "_educoder_session" not in cookie:
                print("  ✗ 头歌登录失败，可能是账号密码有误。")
            else:
                cfg["educoder_cookie"] = cookie
                if username:
                    cfg["educoder_username"] = username
                print("  ✓ 头歌登录成功")

        if cfg.get("mooc_enabled"):
            print("正在登录「中国大学MOOC」平台...")
            print("  系统将自动打开浏览器完成登录，请勿手动操作。")
            try:
                cfg["mooc_cookie"] = refresh_mooc(ctx, mooc_phone, mooc_password)
                print("  ✓ 中国大学MOOC登录成功")
            except Exception as e:
                print(f"  ✗ 中国大学MOOC登录失败: {e}")

        browser.close()


def write_run_bat() -> None:
    (ROOT / "run.bat").write_text(
        '@echo off\r\ncd /d "%~dp0"\r\nset PYTHONIOENCODING=utf-8\r\npython -m src.main\r\n',
        encoding="ascii",
    )
    (ROOT / "run-summary.bat").write_text(
        '@echo off\r\ncd /d "%~dp0"\r\nset PYTHONIOENCODING=utf-8\r\npython -m src.main --force-summary\r\n',
        encoding="ascii",
    )
    (ROOT / "refresh.bat").write_text(
        '@echo off\r\ncd /d "%~dp0"\r\nset PYTHONIOENCODING=utf-8\r\npython refresh_cookies.py\r\n',
        encoding="ascii",
    )


def register_tasks(interval_hours: int, summary_time: str) -> None:
    print()
    subprocess.run(
        ["schtasks", "/Create", "/F", "/TN", "homework-check",
         "/TR", f'"{ROOT / "run.bat"}"', "/SC", "HOURLY", "/MO", str(interval_hours)],
        capture_output=True,
    )
    print(f"  正在配置定时检测任务（每 {interval_hours} 小时一次）... 完成")

    subprocess.run(
        ["schtasks", "/Create", "/F", "/TN", "homework-summary",
         "/TR", f'"{ROOT / "run-summary.bat"}"', "/SC", "DAILY", "/ST", summary_time],
        capture_output=True,
    )
    print(f"  正在配置每日汇总通知（每日 {summary_time}）... 完成")

    subprocess.run(
        ["schtasks", "/Create", "/F", "/TN", "homework-refresh-cookie",
         "/TR", f'"{ROOT / "refresh.bat"}"', "/SC", "DAILY", "/ST", "08:00"],
        capture_output=True,
    )
    print("  正在配置登录凭证自动刷新（每日 08:00）... 完成")


def _wait_before_browser(seconds: int = 5) -> None:
    """自动登录前给用户缓冲时间，提示浏览器即将弹出。"""
    _enable_vt()
    print()
    print("配置已完成。")
    print()
    print("接下来将自动登录所选平台：")
    print("  - 系统会自动打开浏览器并完成登录")
    print(f"  - {RED}{BOLD}请勿手动操作浏览器，登录完成后会自动关闭{RESET}")
    print("  - 整个过程约需 30 秒，请耐心等待")
    print()
    for i in range(seconds, 0, -1):
        print(f"  {i} 秒后自动开始...", flush=True)
        time.sleep(1)
    print()


def main() -> int:
    print("=" * 44)
    print("        作业提醒 · 安装向导")
    print("=" * 44)

    cfg = load_cfg()

    # 选平台
    edu_enabled, mooc_enabled = select_platform()
    cfg["educoder_enabled"] = edu_enabled
    cfg["mooc_enabled"] = mooc_enabled

    # 分平台账密
    edu_phone = edu_password = mooc_phone = mooc_password = ""
    if edu_enabled:
        print()
        print("请输入「头歌」平台的登录信息：")
        edu_phone = input("  登录账号（手机号）：").strip()
        edu_password = input_password("  登录密码：")
        cfg["educoder_phone"] = edu_phone
        cfg["educoder_password"] = edu_password

    if mooc_enabled:
        print()
        print("请输入「中国大学MOOC」平台的登录信息：")
        mooc_phone = input("  登录账号（手机号）：").strip()
        mooc_password = input_password("  登录密码：")
        cfg["mooc_phone"] = mooc_phone
        cfg["mooc_password"] = mooc_password

    # 推送密钥
    cfg["serverchan_key"] = input_key()

    # 检测频率 + 通知时间
    interval = select_interval()
    summary_time = select_time()

    # 先保存配置（避免登录失败时丢失已填信息）
    save_cfg(cfg)

    # 自动登录（弹出浏览器前给缓冲提示）
    _wait_before_browser()
    auto_login(cfg, edu_phone, edu_password, mooc_phone, mooc_password)
    save_cfg(cfg)

    # 生成运行脚本 + 注册定时任务
    write_run_bat()
    register_tasks(interval, summary_time)

    print()
    print("=" * 44)
    print("            安装完成")
    print("=" * 44)
    print()
    print("本程序已安装完毕，将按设定自动监控作业并向你发送通知。")
    print()
    print("如需停止使用本程序，请双击文件夹中的「卸载.bat」。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
