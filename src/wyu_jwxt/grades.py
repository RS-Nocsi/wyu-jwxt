# src/wyu_jwxt/grades.py
"""课程成绩查询。"""
from typing import List, Optional

from .models import Grade
from .exceptions import ChengfangError

__all__ = ["get_grades"]


def get_grades(self, xn: Optional[int] = None, xq: Optional[int] = None) -> List[Grade]:
    """获取课程成绩。

    Args:
        xn: 学年起始年；None 表示全部学期
        xq: 学期；None 表示全部

    Returns:
        Grade 列表
    """
    xnxqdm = self.config.term_code(xn, xq) if (xn is not None and xq is not None) else ""
    # 建立成绩页上下文
    self._get(self.config.grades_page_path)
    self._post(self.config.grades_list_path,
               data={"xnxqdm": xnxqdm}, json_response=False)
    # 真实数据请求（easyui datagrid 风格）
    result = self._post(
        self.config.grades_data_path,
        data={
            "xnxqdm": xnxqdm,
            "source": "kccjlist",
            "page": "1",
            "rows": "200",
            "sort": "cjdm",
            "order": "desc",
        },
        referer=self.config.base_url + self.config.grades_page_path,
    )
    if "code" in result and result["code"] < 0:
        raise ChengfangError(result.get("message", "成绩查询失败"))
    rows = result.get("rows", []) or []
    return [Grade.from_raw(r) for r in rows]
