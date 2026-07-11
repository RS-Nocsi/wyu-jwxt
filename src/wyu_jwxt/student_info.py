# src/wyu_jwxt/student_info.py
"""学籍卡片查询。"""
import re

from bs4 import BeautifulSoup

from .models import StudentInfo
from .exceptions import ChengfangError

__all__ = ["get_student_info"]


def get_student_info(self) -> StudentInfo:
    """获取学籍卡片信息。

    学号/姓名从 welcome 页面的 data-userbh/data-userxm 属性获取，
    其他字段从 edit.page 表单的 input name/value 获取。
    """
    # 1. 从 welcome 页面获取学号和姓名
    welcome_html = self._get(self.config.welcome_path)
    user_id_match = re.search(r'''data-userbh=["']([^"']+)["']''', welcome_html)
    user_name_match = re.search(r'''data-userxm=["']([^"']+)["']''', welcome_html)
    if not user_id_match or not user_name_match:
        raise ChengfangError(
            "无法从 welcome 页面提取学号/姓名，页面格式可能已变更。"
            f"请确认 {self.config.welcome_path} 中存在 data-userbh / data-userxm 属性。"
        )
    user_id = user_id_match.group(1)
    user_name = user_name_match.group(1)

    # 2. 从 edit.page 表单获取其他字段
    html = self._get(self.config.student_info_path)
    soup = BeautifulSoup(html, "html.parser")
    fields = {}
    for inp in soup.find_all("input"):
        name = inp.get("name")
        if name:
            fields[name] = inp.get("value", "")

    return StudentInfo.from_welcome_and_form(user_id, user_name, fields)
