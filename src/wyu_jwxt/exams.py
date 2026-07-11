# src/wyu_jwxt/exams.py
"""考试安排查询。"""
from typing import List

from .models import Exam
from .exceptions import ChengfangError

__all__ = ["get_exams"]


def get_exams(self, xn: int, xq: int) -> List[Exam]:
    """获取考试安排。

    Args:
        xn: 学年起始年，如 2025
        xq: 学期，1 或 2

    Returns:
        Exam 列表
    """
    xnxqdm = self.config.term_code(xn, xq)
    self._get(self.config.exams_page_path)
    result = self._post(
        self.config.exams_data_path,
        data={"xnxqdm": xnxqdm},
        referer=self.config.base_url + self.config.exams_page_path,
    )
    if "code" in result and result["code"] < 0:
        raise ChengfangError(result.get("message", "考试查询失败"))
    exams = []
    for r in result.get("rows") or []:
        if isinstance(r, dict):
            try:
                exams.append(Exam.from_raw(r))
            except Exception:
                continue
    return exams
