# src/wyu_jwxt/exams.py
"""考试安排查询。"""
from typing import List

from .models import Exam
from .exceptions import ChengfangError

__all__ = ["get_exams"]


def get_exams(self, xn: int, xq: int) -> List[Exam]:
    """获取考试安排。"""
    xnxqdm = self.config.term_code(xn, xq)
    self._get(self.config.exams_page_path)
    result = self._post(
        self.config.exams_data_path,
        data={"xnxqdm": xnxqdm},
        referer=self.config.base_url + self.config.exams_page_path,
    )
    if "code" in result and result["code"] < 0:
        raise ChengfangError(result.get("message", "考试查询失败"))
    rows = result.get("rows", []) or []
    return [Exam.from_raw(r) for r in rows]
