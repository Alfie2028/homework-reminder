"""中国大学MOOC(icourse163.org)抓取器。

MOOC 按「课程(term)」组织，每门课程下按「章节(chapter)」分测验(quiz)/作业(homework)。
接口是 RPC 风格: POST /web/j/{Bean}.{method}.rpc?csrfKey={csrf}

鉴权要点:
  - csrfKey = Cookie 里的 NTESSTUDYSI 值
  - 必须带上 HttpOnly Cookie(STUDY_SESS / STUDY_PERSIST 等)，否则课程详情接口返回 null
    document.cookie 看不到这些 HttpOnly 值，需从浏览器 DevTools 的 Cookie 面板复制

作业时间线(尤其同伴互评):
  - deadline           提交截止
  - evaluateStart      互评开启
  - evaluateEnd        互评截止
  - evaluateScoreReleaseTime  互评成绩发布
"""
from __future__ import annotations

from datetime import datetime

import requests

from .base import BaseFetcher, Course, Homework

MOOC_BASE = "https://www.icourse163.org"
COURSES_API = MOOC_BASE + "/web/j/learnerCourseRpcBean.getMyLearnedCoursePanelList.rpc"
TERM_API = MOOC_BASE + "/web/j/courseBean.getLastLearnedMocTermDto.rpc"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

STATUS_MAP = {
    "未开始": "未写",
    "未提交": "未写",
    "进行中": "未写",
    "已提交": "已提交",
    "已完成": "已提交",
    "已批改": "已批改",
    "已评分": "已批改",
}

# 课程 channel 值 → 类型名
CHANNEL_MAP = {"1": "MOOC", "3": "SPOC"}


def _fmt_ms(ms) -> str:
    """epoch 毫秒 → 本地时间字符串。"""
    if not ms:
        return ""
    try:
        return datetime.fromtimestamp(int(ms) // 1000).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, OSError):
        return ""


def _extract_csrf(cookie: str) -> str:
    for part in cookie.split(";"):
        if "NTESSTUDYSI" in part:
            return part.split("=", 1)[1].strip()
    return ""


class MoocFetcher(BaseFetcher):
    platform = "mooc"

    def __init__(self, cookie: str = "", username: str = ""):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": UA,
            "Origin": MOOC_BASE,
            "Content-Type": "application/x-www-form-urlencoded",
        })
        self.username = username
        self.csrf = _extract_csrf(cookie)
        if cookie:
            self.session.headers["Cookie"] = cookie

    # ---- 两级抓取 ----

    def fetch_courses(self) -> list[Course]:
        d = self._rpc(COURSES_API, {"type": "30", "p": "1", "psize": "8", "courseType": "1"})
        result = d.get("result") or {}
        courses: list[Course] = []
        for c in result.get("result") or []:
            tp = c.get("termPanel") or {}
            term_id = str(tp.get("id") or c.get("id", ""))
            short = c.get("shortName", "")
            courses.append(Course(
                id=term_id,
                name=c.get("name", ""),
                course_type=CHANNEL_MAP.get(str(c.get("channel")), "MOOC"),
                url=f"{MOOC_BASE}/learn/{short}-{c.get('id')}",
            ))
        return courses

    def fetch_course_homeworks(self, course: Course) -> list[Homework]:
        d = self._rpc(TERM_API, {"termId": course.id})
        term = (d.get("result") or {}).get("mocTermDto") or {}
        out: list[Homework] = []
        for ch in term.get("chapters") or []:
            for q in ch.get("quizs") or []:
                out.append(self._to_homework(q, course, "单元测验"))
            for hw in ch.get("homeworks") or []:
                out.append(self._to_homework(hw, course, "单元作业"))
        return out

    # ---- 解析 ----

    def _to_homework(self, item: dict, course: Course, category: str) -> Homework:
        test = item.get("test") or {}
        user_score = test.get("userScore")
        raw_status = "已提交" if user_score is not None else "未提交"
        score = ""
        if user_score is not None:
            total = test.get("totalScore")
            score = f"{user_score}/{total}" if total is not None else str(user_score)
        return Homework(
            platform=self.platform,
            key=f"mooc:{item.get('id')}",
            title=item.get("name", ""),
            status=STATUS_MAP.get(raw_status, raw_status),
            score=score,
            deadline=_fmt_ms(test.get("deadline")),
            url=course.url or "",
            course=course.name,
            course_type=category,
            extra={
                "evaluate": bool(test.get("enableEvaluation")),
                "evaluateStart": _fmt_ms(test.get("evaluateStart")),
                "evaluateEnd": _fmt_ms(test.get("evaluateEnd")),
            },
        )

    # ---- 请求 ----

    def _rpc(self, url: str, data: dict):
        resp = self.session.post(f"{url}?csrfKey={self.csrf}", data=data, timeout=20)
        if resp.status_code in (401, 403):
            raise PermissionError(f"401/403 Cookie 失效: {url}")
        resp.raise_for_status()
        return resp.json()
