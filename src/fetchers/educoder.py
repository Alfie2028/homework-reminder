"""头歌(educoder.net)抓取器。

头歌按「课堂(classroom)」组织作业，每个课堂下的作业又分多个类别(type)：
  1=图文作业, 3=分组作业, 4=实训作业(课堂实验)。
没有全站作业一览接口，因此沿用两级流程：课程列表 → 逐课作业。

鉴权要点(逆向自前端 umi 包)：
  - 登录后拿到 Cookie: autologin_trustie(长期) + _educoder_session(会话)
  - 每个请求都要带 X-EDU-Signature 签名，否则返回 -102
  - 签名算法: md5(btoa("method=" + METHOD + "&ak=" + AK + "&sk=" + SK + "&time=" + ts))
  - AK/SK 为前端硬编码密钥(getKey 双重 base64 解码后的结果)
"""
from __future__ import annotations

import base64
import hashlib
import re
import time

import requests

from .base import BaseFetcher, Course, Homework

EDUCODER_BASE = "https://www.educoder.net"
DATA_BASE = "https://data.educoder.net"

COURSES_API = DATA_BASE + "/api/users/{username}/courses.json"
HOMEWORKS_API = DATA_BASE + "/api/courses/{identifier}/homework_commons.json"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

# 签名密钥(前端 umi 包 module 57101 硬编码，getKey=atob(atob(x)) 解码得到)
_SIGN_AK = "e9dd5b4322f9f7d83d009de9bfa100c3"
_SIGN_SK = "2e3da06ae26ba9f76a5d8d355746f2fe"

# 作业类别: type 参数 → 类别名。逐类抓取后合并成该课的完整作业列表。
HOMEWORK_TYPES = {1: "图文作业", 2: "测验", 3: "分组作业", 4: "实训作业"}

# 平台原文状态 → 标准化状态(未写/已提交/已批改)
STATUS_MAP = {
    "未开始": "未写",
    "未提交": "未写",
    "未完成": "未写",
    "已提交": "已提交",
    "已完成": "已提交",
    "已批改": "已批改",
    "已评分": "已批改",
    "已通过": "已批改",
}


def _sign(method: str, ts: str) -> str:
    """按前端算法计算 X-EDU-Signature。"""
    n = f"method={method.upper()}&ak={_SIGN_AK}&sk={_SIGN_SK}&time={ts}"
    b64 = base64.b64encode(n.encode("utf-8")).decode("ascii")
    return hashlib.md5(b64.encode("utf-8")).hexdigest()


def normalize_status(raw: str) -> str:
    return STATUS_MAP.get(raw.strip(), raw.strip())


def _parse_cookie(cookie_str: str) -> dict:
    pairs = {}
    for part in cookie_str.split(";"):
        if "=" in part:
            k, _, v = part.strip().partition("=")
            pairs[k] = v
    return pairs


def extract_course_identifier(url: str) -> str | None:
    """从课程 URL 里提取课堂短标识，如 /classrooms/ZSPU7VCV/... → ZSPU7VCV。"""
    m = re.search(r"/classrooms/([^/]+)", url or "")
    return m.group(1) if m else None


def _derive_status(hw: dict) -> str:
    """从作业对象推导提交状态原文(实训 vs 图文两类字段不同)。"""
    if hw.get("is_shixun"):
        # 实训: shixun_finished_status 0=未完成 1=已完成
        return "已完成" if hw.get("shixun_finished_status") else "未完成"
    # 图文/分组作业: un_commit_work 标记是否未提交
    return "未提交" if hw.get("un_commit_work") else "已提交"


def _derive_url(hw: dict) -> str:
    """实训作业 task_operation[1] 是相对路径，拼成完整链接。"""
    op = hw.get("task_operation")
    if isinstance(op, list) and len(op) >= 2 and isinstance(op[1], str) and op[1].startswith("/"):
        return EDUCODER_BASE + op[1]
    return ""


class EducoderFetcher(BaseFetcher):
    platform = "educoder"

    def __init__(self, cookie: str = "", username: str = "", password: str = ""):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": UA})
        self.username = username
        self.password = password
        self._cookie = _parse_cookie(cookie)
        self._session_token = self._cookie.get("_educoder_session", "")
        if cookie:
            self.session.headers["Cookie"] = cookie

    # ---- 两级抓取 ----

    def fetch_courses(self) -> list[Course]:
        if not self.username:
            raise PermissionError("缺少头歌用户名(EDUCODER_USERNAME)")
        data = self._get(COURSES_API.format(username=self.username), {
            "category": "", "status": "", "page": 1, "per_page": 100,
            "sort_by": "updated_at", "sort_direction": "desc",
            "username": self.username, "zzud": self.username,
        })
        return self._parse_courses(data)

    def fetch_course_homeworks(self, course: Course) -> list[Homework]:
        out: list[Homework] = []
        for typ in HOMEWORK_TYPES:
            data = self._get(HOMEWORKS_API.format(identifier=course.id), {
                "limit": 100, "status": 0, "id": course.id,
                "type": typ, "order": 0, "zzud": self.username,
            })
            out.extend(self._parse_homeworks(data, course, typ))
        return out

    # ---- 解析 ----

    def _parse_courses(self, data) -> list[Course]:
        if not isinstance(data, dict):
            return []
        courses: list[Course] = []
        for c in data.get("courses") or []:
            url = c.get("first_category_url") or ""
            identifier = extract_course_identifier(url) or str(c.get("id", ""))
            courses.append(Course(
                id=identifier,
                name=c.get("name", ""),
                course_type=(c.get("first_category") or {}).get("module_type", ""),
                url=EDUCODER_BASE + url if url else "",
            ))
        return courses

    def _parse_homeworks(self, data, course: Course, typ: int) -> list[Homework]:
        if not isinstance(data, dict):
            return []
        category = HOMEWORK_TYPES.get(typ, "")
        out: list[Homework] = []
        for hw in data.get("homeworks") or []:
            raw_status = _derive_status(hw)
            out.append(Homework(
                platform=self.platform,
                key=f"educoder:{hw.get('homework_id')}",
                title=hw.get("name", ""),
                status=normalize_status(raw_status),
                score="",
                deadline=hw.get("end_time") or hw.get("end_time_s") or "",
                url=_derive_url(hw),
                course=course.name,
                course_type=category or course.course_type,
                extra={"raw_status": raw_status, "is_shixun": hw.get("is_shixun", False)},
            ))
        return out

    # ---- 请求 ----

    def _get(self, url: str, params: dict | None = None, retries: int = 3):
        last_exc: Exception | None = None
        for attempt in range(retries):
            try:
                return self._get_once(url, params)
            except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError) as e:
                last_exc = e
                if attempt < retries - 1:
                    time.sleep(1.5 * (attempt + 1))
        raise last_exc  # type: ignore[misc]

    def _get_once(self, url: str, params: dict | None = None):
        ts = str(int(time.time() * 1000))
        self.session.headers.update({
            "X-EDU-Type": "pc",
            "X-EDU-Timestamp": ts,
            "X-EDU-Signature": _sign("GET", ts),
            "Pc-Authorization": self._session_token,
            "X-Original-Protocol": "https:",
            "X-Original-Host": "www.educoder.net",
            "X-Original-Origin": "https://www.educoder.net",
            "Referer": "https://www.educoder.net/",
        })
        resp = self.session.get(url, params=params, timeout=30)
        if resp.status_code in (401, 403):
            print(f"[诊断] HTTP {resp.status_code} <- {url}")
            print(f"[诊断] body: {resp.text[:400]}")
            raise PermissionError(f"401/403 Cookie 失效: {url}")
        resp.raise_for_status()
        try:
            return resp.json()
        except Exception:
            return resp.text
