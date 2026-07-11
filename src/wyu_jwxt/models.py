# src/wyu_jwxt/models.py
"""数据模型 — 把教务系统原始 JSON/HTML 字段映射成易用对象。"""
from dataclasses import dataclass
from typing import List

__all__ = ["Course", "Grade", "Exam", "StudentInfo"]


@dataclass
class Course:
    """课表中的一门课程安排。"""
    name: str
    teacher: str
    classroom: str
    start_time: str
    end_time: str
    weekday: int
    weeks: List[int]
    term_code: str
    course_code: str

    @classmethod
    def from_raw(cls, raw: dict) -> "Course":
        def _split_ints(s: str) -> List[int]:
            return [int(x) for x in str(s).split(",") if x.strip().isdigit()] if s else []

        def _safe_int(v, default=0) -> int:
            try:
                return int(v)
            except (TypeError, ValueError):
                return default

        return cls(
            name=raw.get("kcmc", ""),
            teacher=raw.get("teaxms", ""),
            classroom=raw.get("jxcdmc", ""),
            start_time=raw.get("qssj", ""),
            end_time=raw.get("jssj", ""),
            weekday=_safe_int(raw.get("jsxq") or 0),
            weeks=_split_ints(raw.get("zc", "")),
            term_code=raw.get("xnxqdm", ""),
            course_code=raw.get("kcbh", ""),
        )


@dataclass
class Grade:
    """一门课程的成绩。"""
    course_name: str
    score: str
    credit: float
    term: str
    department: str
    nature: str
    course_code: str
    student_name: str

    @classmethod
    def from_raw(cls, raw: dict) -> "Grade":
        def _to_float(s) -> float:
            try:
                return float(s)
            except (TypeError, ValueError):
                return 0.0
        return cls(
            course_name=raw.get("kcmc", ""),
            score=raw.get("zcj", ""),
            credit=_to_float(raw.get("xf")),
            term=raw.get("xnxqmc", ""),
            department=raw.get("kkbmmc", ""),
            nature=raw.get("xdfsmc", ""),
            course_code=raw.get("kcbh", ""),
            student_name=raw.get("xsxm", ""),
        )


@dataclass
class Exam:
    """一门考试安排。"""
    course_name: str
    date: str
    time: str
    classroom: str
    exam_form: str
    exam_type: str

    @classmethod
    def from_raw(cls, raw: dict) -> "Exam":
        return cls(
            course_name=raw.get("kcmc", ""),
            date=raw.get("ksrq", ""),
            time=raw.get("kssj", ""),
            classroom=raw.get("kscdmc", ""),
            exam_form=raw.get("ksxsmc", ""),
            exam_type=raw.get("khxsmc", ""),
        )


@dataclass
class StudentInfo:
    """学籍卡片信息。"""
    student_id: str
    name: str
    id_number: str
    phone: str
    email: str
    home_address: str
    exam_number: str
    previous_school: str
    enrollment_date: str
    pinyin_name: str
    english_name: str

    @classmethod
    def from_welcome_and_form(cls, user_id: str, user_name: str, form_fields: dict) -> "StudentInfo":
        """从 welcome 页面（学号/姓名）+ edit.page 表单（其他字段）组合构建。"""
        return cls(
            student_id=user_id,
            name=user_name,
            id_number=form_fields.get("sfzh", ""),
            phone=form_fields.get("dh", ""),
            email=form_fields.get("email", ""),
            home_address=form_fields.get("jtdz", ""),
            exam_number=form_fields.get("ksh", ""),
            previous_school=form_fields.get("lyzx", ""),
            enrollment_date=form_fields.get("rxrq", ""),
            pinyin_name=form_fields.get("py", ""),
            english_name=form_fields.get("xsywxm", ""),
        )
