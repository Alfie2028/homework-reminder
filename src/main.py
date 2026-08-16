"""主流程编排：抓取 → 比对 → 分级推送。

用法:
    python -m src.main [--force-summary]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# pythonw 无控制台时 sys.stdout 为 None，print 会崩；兜底到 devnull
if sys.stdout is None:
    sys.stdout = sys.stderr = open(os.devnull, "w", encoding="utf-8")

from .config import DATA_DIR, load_config
from .fetchers.educoder import EducoderFetcher, Homework
from .fetchers.mooc import MoocFetcher
from .pusher import ServerChanPusher, WecomPusher
from .store import StateStore

DB_PATH = DATA_DIR / "state.sqlite3"


def _now() -> datetime:
    return datetime.now()


def _parse_deadline(raw: str) -> datetime | None:
    """解析截止时间字符串，多种格式容错。"""
    if not raw:
        return None
    raw = raw.strip()
    formats = [
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00").split("+")[0])
    except ValueError:
        return None


def _deadline_label(raw: str | datetime | None) -> str:
    """接受原始字符串或 datetime，返回人类可读的剩余时间。"""
    deadline = raw if isinstance(raw, datetime) else _parse_deadline(raw or "")
    if deadline is None:
        return "无截止"
    remain = deadline - _now()
    if remain.total_seconds() < 0:
        return f"已过期{abs(remain).days}天"
    hours = int(remain.total_seconds() // 3600)
    if hours < 24:
        return f"{hours}小时"
    return f"{remain.days}天"


# 分级提醒档位：截止前 8 小时、4 小时各催一次（rank 越大越紧迫）
URGENT_LEVELS = {"8小时": 1, "4小时": 2}


def urgent_level(hw: Homework, now: datetime) -> str | None:
    """当前剩余的紧迫档位：8小时 / 4小时 / None（还没到催的窗口）。"""
    dl = _parse_deadline(hw.deadline)
    if dl is None:
        return None
    hours = (dl - now).total_seconds() / 3600
    if hours < 0:
        return None  # 已过期由汇总推送提示
    if hours <= 4:
        return "4小时"
    if hours <= 8:
        return "8小时"
    return None


def detect_new_urgent(homeworks: list[Homework], reminded: dict, now: datetime | None = None) -> list[Homework]:
    """只返回「新跨入 8/4 小时档」的作业，每档只催一次，不再反复催。"""
    now = now or _now()
    out = []
    for hw in homeworks:
        if hw.status in ("已提交", "已批改"):
            continue
        level = urgent_level(hw, now)
        if level is None:
            continue
        if URGENT_LEVELS[level] > reminded.get(hw.key, 0):
            out.append(hw)
            reminded[hw.key] = URGENT_LEVELS[level]
    out.sort(key=lambda h: _parse_deadline(h.deadline) or datetime.max)
    return out


def detect_changes(old: dict, new: dict) -> dict:
    """比对上次与本次状态，返回有变化/新增的作业。"""
    changes = {"new": [], "status_changed": [], "score_changed": []}
    for key, hw in new.items():
        old_hw = old.get(key)
        if old_hw is None:
            changes["new"].append(hw)
        else:
            if old_hw.get("status") != hw.get("status"):
                changes["status_changed"].append(hw)
            elif (
                hw.get("score")
                and old_hw.get("score") != hw.get("score")
            ):
                changes["score_changed"].append(hw)
    return changes


def filter_pending(homeworks: list[Homework], now: datetime | None = None) -> list[Homework]:
    """只保留「未提交」且「有截止时间且未过期」的作业。"""
    now = now or _now()
    pending = []
    for hw in homeworks:
        if hw.status != "未写":
            continue
        dl = _parse_deadline(hw.deadline)
        if dl is None:
            continue  # 无截止时间，跳过
        if dl < now:
            continue  # 已过期，跳过
        pending.append(hw)
    return pending


def _hw_line(hw: Homework) -> str:
    """作业行: 课程名(可点击跳平台首页) + 标题。"""
    home = PLATFORM_HOME.get(hw.platform, "")
    if hw.course:
        name = f"[{hw.course}]({home})" if home else f"[{hw.course}]"
        return f"{name} {hw.title}"
    return hw.title


PLATFORM_NAMES = {"educoder": "🎓 头歌", "mooc": "📚 中国大学MOOC"}

# 平台主域名：点击分组标题跳平台首页（不深链到课程/登录/个人信息页）
PLATFORM_HOME = {
    "educoder": "https://www.educoder.net",
    "mooc": "https://www.icourse163.org",
}

# 未提交条数 → 调侃文案（1 / 3 / 5+ / 8+ 各一条；2、4 条不调侃）
_BANTER = {
    1: "🎯 就剩这 1 条了，随手清掉，今天就能安心卷别的。",
    3: "⛰️ 三座大山压顶，先挑最急的那座啃。",
}
_BANTER_MANY = "🧹 作业都排到山海关了，别摆烂，一条条清，先交先安。"
_BANTER_OVER = "你他娘的看看多少作业没写！再不交作业找人弄你"


def _banter(count: int) -> str:
    if count in _BANTER:
        return _BANTER[count]
    if count > 7:
        return _BANTER_OVER
    if count >= 5:
        return _BANTER_MANY
    return ""


def build_summary_message(homeworks: list[Homework], new_keys: set[str] | None = None) -> str:
    new_keys = new_keys or set()
    todo = [h for h in homeworks if h.status == "未写"]
    # 按截止时间升序(最近截止在前)
    todo.sort(key=lambda h: _parse_deadline(h.deadline) or datetime.max)

    if not todo:
        return "## 🎉 无未提交作业"

    # 按平台分组
    groups: dict[str, list[Homework]] = {}
    for hw in todo:
        groups.setdefault(hw.platform, []).append(hw)

    lines = []
    for platform in ("educoder", "mooc"):
        items = groups.get(platform, [])
        if not items:
            continue
        name = PLATFORM_NAMES.get(platform, platform)
        home = PLATFORM_HOME.get(platform, "")
        label = f"[{name}（{len(items)}）]({home})" if home else f"{name}（{len(items)}）"
        lines.append(f"**{label}**")
        for hw in items[:15]:
            mark = " [新]" if hw.key in new_keys else ""
            lines.append(f"- {_deadline_label(hw.deadline)} · {_hw_line(hw)}{mark}")
        if len(items) > 15:
            lines.append(f"  …还有{len(items) - 15}条")
        lines.append("")

    header = f"📋 作业提醒 · {len(todo)} 条未提交"
    banter = _banter(len(todo))
    if banter:
        return f"## {header}\n\n{banter}\n" + "\n".join(lines).rstrip()
    return f"## {header}\n" + "\n".join(lines).rstrip()


def run(force_summary: bool = False, inspect: bool = False):
    cfg = load_config()
    if cfg["serverchan_key"]:
        pusher = ServerChanPusher(cfg["serverchan_key"])
    elif cfg["wecom_webhook"]:
        pusher = WecomPusher(cfg["wecom_webhook"])
    else:
        raise SystemExit("缺少推送渠道，请在 config.json 配置 serverchan_key 或 wecom_webhook")
    if not cfg["educoder_cookie"]:
        print("警告: 未配置 EDUCODER_COOKIE，本轮跳过头歌检测")
    store = StateStore(DB_PATH)

    homeworks: list[Homework] = []

    # ---- 头歌 ----
    if cfg["educoder_cookie"] and cfg.get("educoder_enabled", True):
        try:
            fetcher = EducoderFetcher(cfg["educoder_cookie"], username=cfg["educoder_username"])
            homeworks.extend(fetcher.fetch_all())
        except NotImplementedError as e:
            print(f"头歌抓取器未完成: {e}")
            return 2
        except Exception as e:
            _handle_fetch_error(pusher, "头歌", e)

    # ---- MOOC ----
    if cfg["mooc_cookie"] and cfg.get("mooc_enabled", True):
        try:
            fetcher = MoocFetcher(cfg["mooc_cookie"])
            homeworks.extend(fetcher.fetch_all())
        except Exception as e:
            _handle_fetch_error(pusher, "MOOC", e)

    # ---- 筛选：只保留未提交且未过期的作业 ----
    homeworks = filter_pending(homeworks)

    # ---- 状态索引 + 变化检测 + 紧急 ----
    new_state = {hw.key: hw.__dict__ for hw in homeworks}
    old_state = store.get("homeworks") or {}
    changes = detect_changes(old_state, new_state)
    new_keys = {hw["key"] for hw in changes["new"]}
    reminded = store.get("reminded") or {}
    urgent = detect_new_urgent(homeworks, reminded)

    # ---- 组装并推送 ----
    if inspect:
        # 巡检模式: 无论有无待办作业都推送当前状态
        body = build_summary_message(homeworks, new_keys)
        pusher.send_markdown("作业提醒 · 巡检", body)
        print(f"巡检完成, 共{len(homeworks)}条未提交作业")
    elif not homeworks:
        print("本轮未获取到任何作业，跳过推送")
    elif force_summary:
        # 每日汇总: 固定推送完整未提交清单
        body = build_summary_message(homeworks, new_keys)
        pusher.send_markdown("作业提醒", body)
        print(f"已推送汇总, 共{len(homeworks)}条作业")
    elif changes["new"] or urgent:
        # 每3h运行: 有新作业或新跨入 8/4 小时档才推完整清单
        body = build_summary_message(homeworks, new_keys)
        pusher.send_markdown("作业提醒", body)
        print(f"已推送, 共{len(homeworks)}条作业")
    else:
        print("无变化、无紧急，跳过推送")

    store.set("homeworks", new_state)
    store.set("reminded", reminded)
    return 0


def _handle_fetch_error(pusher, platform: str, exc: Exception):
    msg = str(exc)
    if "401" in msg or "403" in msg or "login" in msg.lower():
        pusher.send_text(f"⚠️ {platform} Cookie 失效，请重新复制登录后的 Cookie 并更新。")
    else:
        print(f"{platform} 抓取失败: {exc}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force-summary", action="store_true", help="强制推送汇总")
    parser.add_argument("--inspect", action="store_true", help="巡检模式：无论有无待办作业都推送当前状态到手机")
    args = parser.parse_args()
    sys.exit(run(force_summary=args.force_summary, inspect=args.inspect))


if __name__ == "__main__":
    main()
