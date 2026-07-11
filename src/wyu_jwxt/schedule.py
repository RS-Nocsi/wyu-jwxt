# src/wyu_jwxt/schedule.py
"""课表查询。"""
from typing import List, Optional

from .models import Course

__all__ = ["get_schedule"]


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
    # 建立课表页上下文
    self._get(self.config.schedule_page_path, params={"xnxqdm": xnxqdm})
    # 根据学期计算日期范围（第1学期8月，第2学期2月）
    year = xn + 1 if xq == 1 else xn  # 第1学期跨年到 xn+1
    month = "08" if xq == 1 else "02"
    data = {
        "xnxqdm": xnxqdm,
        "zc": str(week) if week else "",
        "d1": f"{year}-{month}-23 00:00:00",
        "d2": f"{year}-{month}-28 23:59:59",
    }
    result = self._post(
        self.config.schedule_data_path, data,
        referer=self.config.base_url + self.config.schedule_page_path,
    )
    if "code" in result and result["code"] < 0:
        from .exceptions import ChengfangError
        raise ChengfangError(result.get("message", "课表查询失败"))
    rows = result.get("data", []) or []
    courses = [Course.from_raw(r) for r in rows]
    return courses
