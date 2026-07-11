# src/wyu_jwxt/schedule.py
"""课表查询。"""
from typing import List, Optional

from .models import Course
from .exceptions import ChengfangError

__all__ = ["get_schedule"]


def _build_date_range(xn: int, xq: int) -> "tuple[str, str]":
    """根据学年学期计算课表查询的日期范围。

    第1学期（秋季）始于 xn 年 8 月，第2学期（春季）始于 xn+1 年 2 月。
    取开学第4周的 7 天范围，可覆盖大部分学期边界。
    """
    if xq == 1:
        year = xn
        month = 8
    else:
        year = xn + 1
        month = 2
    return (
        f"{year}-{month:02d}-22 00:00:00",
        f"{year}-{month:02d}-28 23:59:59",
    )


def get_schedule(self, xn: int, xq: int, week: Optional[int] = None) -> List[Course]:
    """获取课表。

    Args:
        xn: 学年起始年，如 2025
        xq: 学期，1 或 2
        week: 指定周次；None 返回整学期

    Returns:
        Course 列表
    """
    xnxqdm = self.config.term_code(xn, xq)
    self._get(self.config.schedule_page_path, params={"xnxqdm": xnxqdm})

    week_str = str(week) if week is not None else ""
    d1, d2 = _build_date_range(xn, xq)
    data = {
        "xnxqdm": xnxqdm,
        "zc": week_str,
        "d1": d1,
        "d2": d2,
    }
    result = self._post(
        self.config.schedule_data_path, data,
        referer=self.config.base_url + self.config.schedule_page_path,
    )
    if "code" in result and result["code"] < 0:
        raise ChengfangError(result.get("message", "课表查询失败"))
    courses = []
    for r in result.get("data") or []:
        if isinstance(r, dict):
            try:
                courses.append(Course.from_raw(r))
            except Exception:
                continue
    return courses
