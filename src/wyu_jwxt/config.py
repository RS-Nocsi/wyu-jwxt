# src/wyu_jwxt/config.py
"""学校配置 — 接口路径与 base_url 集中管理，支持其他乘方学校 override。"""

from dataclasses import dataclass, field
from typing import Callable

from .crypto import encrypt_password


@dataclass
class SchoolConfig:
    """乘方教务系统配置。其他学校可继承此类 override 差异点。"""

    base_url: str = "https://jxgl.wyu.edu.cn"
    # 登录相关
    login_path: str = "/new/login"
    captcha_path: str = "/yzm"
    home_path: str = "/"
    # 只读接口路径
    schedule_page_path: str = "/new/student/xsgrkb/main.page"
    schedule_data_path: str = "/new/student/xsgrkb/getCalendarWeekDatas"
    grades_page_path: str = "/new/student/xskccj/main.page"
    grades_list_path: str = "/new/student/xskccj/kccjList.page"
    grades_data_path: str = "/new/student/xskccj/kccjDatas"
    exams_page_path: str = "/new/student/xsksrw/list.page"
    exams_data_path: str = "/new/student/xsksrw/paginateXsksrw"
    student_info_path: str = "/new/student/xjkpxx/edit.page"
    welcome_path: str = "/new/welcome.page"

    @property
    def password_encryptor(self) -> Callable[[str, str], str]:
        """密码加密函数：(password, verifycode) -> hex 密文。子类可 override 换算法。"""
        return encrypt_password

    def term_code(self, xn: int, xq: int) -> str:
        """学年学期代码。五邑格式：2025年第2学期 → '202502'。子类可 override。"""
        if not isinstance(xn, int) or not isinstance(xq, int):
            raise TypeError(f"xn 和 xq 必须为 int，得到 xn={type(xn).__name__}, xq={type(xq).__name__}")
        if xn < 2000:
            raise ValueError(f"xn 年份不合理: {xn}")
        if xq not in (1, 2):
            raise ValueError(f"xq 必须为 1 或 2，得到 {xq}")
        return f"{xn}{xq:02d}"
