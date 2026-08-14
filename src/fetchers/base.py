"""抓取器基类：两级结构(课程列表 → 逐课程作业)。

头歌与慕课都按课程划分作业入口，没有全站作业一览接口，
因此统一为: fetch_all() = fetch_courses() + 逐课 fetch_course_homeworks()
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Course:
    """一门课程/班级。"""

    id: str
    name: str
    course_type: str = ""  # 如 实训/作业/测验/视频 等平台分类
    url: str = ""


@dataclass
class Homework:
    """一条作业的标准化状态。"""

    platform: str
    key: str  # 平台内唯一id
    title: str
    status: str  # 未写 / 已提交 / 已批改(标准化) 或 平台原文
    score: str = ""
    deadline: str = ""  # ISO 或原文
    url: str = ""
    course: str = ""
    course_type: str = ""
    extra: dict = field(default_factory=dict)


class BaseFetcher:
    platform = "base"

    def fetch_all(self) -> list[Homework]:
        all_hw: list[Homework] = []
        for course in self.fetch_courses():
            hws = self.fetch_course_homeworks(course)
            for hw in hws:
                if not hw.course:
                    hw.course = course.name
                if not hw.course_type:
                    hw.course_type = course.course_type
                if not hw.platform:
                    hw.platform = self.platform
            all_hw.extend(hws)
        return all_hw

    def fetch_courses(self) -> list[Course]:
        raise NotImplementedError

    def fetch_course_homeworks(self, course: Course) -> list[Homework]:
        raise NotImplementedError
