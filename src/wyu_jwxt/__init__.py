__version__ = "0.1.2"

from .client import Client
from .config import SchoolConfig
from .exceptions import (
    ChengfangError, LoginError, CaptchaError, SessionExpiredError, RequestError,
)
from .models import Course, Grade, Exam, StudentInfo
from .captcha import CaptchaSolver, OcrSolver, ManualSolver
from . import schedule
from . import grades
from . import exams
from . import student_info

# 把功能方法挂到 Client（mixin 风格，避免多继承）
Client.get_schedule = schedule.get_schedule
Client.get_grades = grades.get_grades
Client.get_exams = exams.get_exams
Client.get_student_info = student_info.get_student_info

__all__ = [
    "__version__",
    "Client", "SchoolConfig",
    "ChengfangError", "LoginError", "CaptchaError", "SessionExpiredError",
    "RequestError",
    "Course", "Grade", "Exam", "StudentInfo",
    "CaptchaSolver", "OcrSolver", "ManualSolver",
]
