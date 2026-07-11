# src/wyu_jwxt/grades.py
"""课程成绩查询。"""
from typing import List, Optional

from .models import Grade
from .exceptions import ChengfangError

__all__ = ["get_grades"]


def get_grades(self, xn: Optional[int] = None, xq: Optional[int] = None) -> List[Grade]:
    """获取课程成绩。自动拉取所有分页。

    Args:
        xn: 学年起始年；None 表示全部学期
        xq: 学期；None 表示全部学期

    Returns:
        Grade 列表

    Raises:
        ValueError: 仅传入 xn 或 xq 其中一个时
    """
    if (xn is None) != (xq is None):
        raise ValueError("xn 和 xq 必须同时提供或同时为 None")
    xnxqdm = self.config.term_code(xn, xq) if (xn is not None and xq is not None) else ""

    self._get(self.config.grades_page_path)
    self._post(self.config.grades_list_path,
               data={"xnxqdm": xnxqdm}, json_response=False)

    referer = self.config.base_url + self.config.grades_page_path
    PAGE_SIZE = 200
    page = 1
    all_grades: List[Grade] = []

    while True:
        result = self._post(
            self.config.grades_data_path,
            data={
                "xnxqdm": xnxqdm,
                "source": "kccjlist",
                "page": str(page),
                "rows": str(PAGE_SIZE),
                "sort": "cjdm",
                "order": "desc",
            },
            referer=referer,
        )
        if "code" in result and result["code"] < 0:
            raise ChengfangError(result.get("message", "成绩查询失败"))

        rows = result.get("rows") or []
        for r in rows:
            if isinstance(r, dict):
                try:
                    all_grades.append(Grade.from_raw(r))
                except Exception:
                    continue

        total = result.get("total", 0)
        if page * PAGE_SIZE >= total:
            break
        page += 1

    return all_grades
