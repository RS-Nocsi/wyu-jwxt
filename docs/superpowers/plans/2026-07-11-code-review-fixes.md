# Code Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复四个并行代码审查发现的所有 Critical / High / Medium / Low 级别问题（共 ~40 项）

**Architecture:** 按模块分组，每个模块作为一个独立 Task，包含该模块的所有修复点。所有修改遵循现有代码风格和 SDK 约定。

**Tech Stack:** Python >= 3.8, requests, pycryptodome, beautifulsoup4, ddddocr

## Global Constraints

- Python >= 3.8 兼容
- 所有异常继承自 `ChengfangError`
- 保持现有 API 签名不变（向后兼容）
- 遵循 PEP 8
- 测试命令：`pytest tests/`

---

### Task 1: Fix crypto.py — key length validation

**Files:**
- Modify: `src/wyu_jwxt/crypto.py:22`

**Interfaces:**
- Produces: `encrypt_password(password: str, verifycode: str) -> str` — 新增 ValueError 抛出场景

- [ ] **Step 1: Add key length validation**

```python
# src/wyu_jwxt/crypto.py, replace line 22
    if len(verifycode) != 4:
        raise ValueError(f"验证码必须为 4 字符，得到 {len(verifycode)} 位")
    key = (verifycode * 4).encode("utf-8")  # 16 字节
```

- [ ] **Step 2: Run existing tests**

```bash
pytest tests/ -v --tb=short -k "crypto or test_encrypt"
```

---

### Task 2: Fix config.py — imports, __all__, base_url normalization, isinstance bool, bare exceptions

**Files:**
- Modify: `src/wyu_jwxt/config.py`

**Interfaces:**
- Produces: `SchoolConfig` 类新增 `__post_init__` base_url 规范化；`term_code` 抛出 `ChengfangError` 子类

- [ ] **Step 1: Read current file**

Already read. Changes needed:
- Remove unused `field` import (line 4)
- Add `__all__`
- Add `__post_init__` to rstrip base_url trailing slashes
- Fix `isinstance` bool issue in `term_code` (use `type(xn) is not int`)
- Wrap `TypeError`/`ValueError` in `ChengfangError` subclasses

- [ ] **Step 2: Apply all config.py fixes**

Replace entire `config.py`:

```python
# src/wyu_jwxt/config.py
"""学校配置 — 接口路径与 base_url 集中管理，支持其他乘方学校 override。"""

from dataclasses import dataclass
from typing import Callable

from .crypto import encrypt_password
from .exceptions import ChengfangError

__all__ = ["SchoolConfig"]


class SchoolConfigError(ChengfangError):
    """配置相关错误。"""


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

    def __post_init__(self):
        self.base_url = self.base_url.rstrip("/")

    @property
    def password_encryptor(self) -> Callable[[str, str], str]:
        """密码加密函数：(password, verifycode) -> hex 密文。子类可 override 换算法。"""
        return encrypt_password

    def term_code(self, xn: int, xq: int) -> str:
        """学年学期代码。五邑格式：2025年第2学期 → '202502'。子类可 override。"""
        if type(xn) is not int or type(xq) is not int:
            raise SchoolConfigError(
                f"xn 和 xq 必须为 int，得到 xn={type(xn).__name__}, xq={type(xq).__name__}"
            )
        if xn < 2000:
            raise SchoolConfigError(f"xn 年份不合理: {xn}")
        if xq not in (1, 2):
            raise SchoolConfigError(f"xq 必须为 1 或 2，得到 {xq}")
        return f"{xn}{xq:02d}"
```

- [ ] **Step 3: Run tests**

```bash
pytest tests/ -v --tb=short -k "config or test_config"
```

---

### Task 3: Fix models.py — _to_float, _split_ints, weekday default, typing, module-level helpers

**Files:**
- Modify: `src/wyu_jwxt/models.py`

**Interfaces:**
- Produces: `_safe_int(v: Any, default: int = 0) -> int`, `_split_ints(s: Any) -> List[int]`, `_to_float(s: Any) -> Optional[float]` 提升为模块级函数
- `Course.weekday` 改为 `Optional[int]`，`Grade.credit` 改为 `Optional[float]`
- `StudentInfo.from_welcome_and_form` 参数 `form_fields: Dict[str, str]`

- [ ] **Step 1: Replace entire models.py**

```python
# src/wyu_jwxt/models.py
"""数据模型 — 把教务系统原始 JSON/HTML 字段映射成易用对象。"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

__all__ = ["Course", "Grade", "Exam", "StudentInfo"]


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _split_ints(s: Any) -> List[int]:
    """将逗号分隔的周次字符串/列表解析为整数列表。"""
    if not s:
        return []
    if isinstance(s, list):
        result = []
        for item in s:
            try:
                result.append(int(item))
            except (TypeError, ValueError):
                continue
        return result
    if isinstance(s, str):
        return [int(x) for x in s.split(",") if x.strip().isdigit()]
    return []


def _to_float(s: Any) -> Optional[float]:
    """安全转换为 float；失败返回 None 以区分「缺失」和「0.0」。"""
    try:
        return float(s)
    except (TypeError, ValueError):
        return None if s is not None else None


@dataclass
class Course:
    """课表中的一门课程安排。"""
    name: str
    teacher: str
    classroom: str
    start_time: str
    end_time: str
    weekday: Optional[int]
    weeks: List[int] = field(default_factory=list)
    term_code: str = ""
    course_code: str = ""

    @classmethod
    def from_raw(cls, raw: dict) -> "Course":
        weekday = _safe_int(raw.get("jsxq")) if raw.get("jsxq") is not None else None
        return cls(
            name=raw.get("kcmc", ""),
            teacher=raw.get("teaxms", ""),
            classroom=raw.get("jxcdmc", ""),
            start_time=raw.get("qssj", ""),
            end_time=raw.get("jssj", ""),
            weekday=weekday,
            weeks=_split_ints(raw.get("zc", "")),
            term_code=raw.get("xnxqdm", ""),
            course_code=raw.get("kcbh", ""),
        )


@dataclass
class Grade:
    """一门课程的成绩。"""
    course_name: str
    score: str
    credit: Optional[float]
    term: str
    department: str
    nature: str
    course_code: str
    student_name: str

    @classmethod
    def from_raw(cls, raw: dict) -> "Grade":
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
```

- [ ] **Step 2: Run tests**

```bash
pytest tests/ -v --tb=short -k "model or test_model"
```

---

### Task 4: Fix schedule.py — date calculation, type guards, import consistency, week=0

**Files:**
- Modify: `src/wyu_jwxt/schedule.py`

**Interfaces:**
- Consumes: `Course.from_raw`, `_split_ints` (via models), `ChengfangError`
- Produces: `get_schedule(self, xn: int, xq: int, week: Optional[int] = None) -> List[Course]`

- [ ] **Step 1: Apply all schedule.py fixes**

```python
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
    # 建立课表页上下文
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
```

- [ ] **Step 2: Run tests**

```bash
pytest tests/ -v --tb=short -k "schedule or test_schedule"
```

---

### Task 5: Fix grades.py — pagination, parameter validation, type guards

**Files:**
- Modify: `src/wyu_jwxt/grades.py`

**Interfaces:**
- Consumes: `Grade.from_raw`, `ChengfangError`, `term_code`
- Produces: `get_grades(self, xn: Optional[int] = None, xq: Optional[int] = None) -> List[Grade]`

- [ ] **Step 1: Apply all grades.py fixes**

```python
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

    # 建立成绩页上下文
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
```

- [ ] **Step 2: Run tests**

```bash
pytest tests/ -v --tb=short -k "grade or test_grade"
```

---

### Task 6: Fix exams.py — type guards, docstring

**Files:**
- Modify: `src/wyu_jwxt/exams.py`

**Interfaces:**
- Consumes: `Exam.from_raw`, `ChengfangError`
- Produces: `get_exams(self, xn: int, xq: int) -> List[Exam]`

- [ ] **Step 1: Apply all exams.py fixes**

```python
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
```

- [ ] **Step 2: Run tests**

```bash
pytest tests/ -v --tb=short -k "exam or test_exam"
```

---

### Task 7: Fix student_info.py — select/textarea support

**Files:**
- Modify: `src/wyu_jwxt/student_info.py`

**Interfaces:**
- Consumes: `StudentInfo.from_welcome_and_form`, `ChengfangError`
- Produces: `get_student_info(self) -> StudentInfo`

- [ ] **Step 1: Apply all student_info.py fixes**

```python
# src/wyu_jwxt/student_info.py
"""学籍卡片查询。"""
import re

from .models import StudentInfo
from .exceptions import ChengfangError

__all__ = ["get_student_info"]


def get_student_info(self) -> StudentInfo:
    """获取学籍卡片信息。

    学号/姓名从 welcome 页面的 data-userbh/data-userxm 属性获取，
    其他字段从 edit.page 表单的 input/select/textarea name/value 获取。
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
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    fields = {}
    for tag in soup.find_all(["input", "select", "textarea"]):
        name = tag.get("name")
        if name:
            value = tag.get("value", "")
            if value == "" and tag.name == "select":
                selected = tag.find("option", selected=True)
                if selected:
                    value = selected.get("value", "")
            fields[name] = value

    return StudentInfo.from_welcome_and_form(user_id, user_name, fields)
```

- [ ] **Step 2: Run tests**

```bash
pytest tests/ -v --tb=short -k "student_info or test_student"
```

---

### Task 8: Fix captcha.py — None check, remove unused public property

**Files:**
- Modify: `src/wyu_jwxt/captcha.py`

**Interfaces:**
- Produces: `OcrSolver.solve` 增加 `None` 保护

- [ ] **Step 1: Apply all captcha.py fixes**

Replace `OcrSolver` class in `captcha.py`:

```python
class OcrSolver(CaptchaSolver):
    """ddddocr 自动识别验证码。"""

    def __init__(self):
        self._engine = None  # 懒加载

    def _get_engine(self):
        if self._engine is None:
            try:
                import ddddocr
            except ImportError as e:
                raise CaptchaError(
                    "未安装 ddddocr，请 pip install wyu-jwxt[ocr] "
                    "或传入 manual_solver 手动处理验证码"
                ) from e
            self._engine = ddddocr.DdddOcr(show_ad=False)
        return self._engine

    def solve(self, image_bytes: bytes) -> str:
        engine = self._get_engine()
        raw = engine.classification(image_bytes)
        if raw is None:
            raise CaptchaError("验证码识别返回空结果")
        return "".join(c for c in raw if c.isalnum())
```

Remove the public `engine` property (lines 54-56 in original).

- [ ] **Step 2: Run tests**

```bash
pytest tests/ -v --tb=short -k "captcha or test_captcha"
```

---

### Task 9: Fix exceptions.py — network error wrapping

**Files:**
- Modify: `src/wyu_jwxt/exceptions.py`

**Interfaces:**
- Produces: 新增 `RequestError(ChengfangError)` 异常类

- [ ] **Step 1: Add RequestError**

```python
# src/wyu_jwxt/exceptions.py
"""wyu-jwxt 自定义异常体系。"""


class ChengfangError(Exception):
    """乘方教务 SDK 所有异常的基类。"""


class LoginError(ChengfangError):
    """登录失败（密码错/验证码错/双因素触发等）。"""


class CaptchaError(ChengfangError):
    """验证码获取或识别失败。"""


class SessionExpiredError(ChengfangError):
    """登录态过期，需重新登录。"""


class RequestError(ChengfangError):
    """网络请求失败（超时、连接错误等）。"""
```

- [ ] **Step 2: Update __init__.py to export RequestError**

Already in Task 11.

- [ ] **Step 3: Wrap network exceptions in client.py _post and _get**

In `_post`: wrap `resp.raise_for_status()` and `resp.json()` in try/except:
```python
from .exceptions import RequestError
# ...
def _post(self, ...):
    try:
        resp = self._session.post(...)
        resp.raise_for_status()
        ...
    except requests.RequestException as e:
        raise RequestError(f"POST {path} 请求失败: {e}") from e
# Same pattern for _get
```

Full client.py rewrite in Task 10.

---

### Task 10: Fix client.py — SSL, warnings, backoff, session persistence, permissions, network wrapping

**Files:**
- Modify: `src/wyu_jwxt/client.py`

**Interfaces:**
- Consumes: `SchoolConfig`, `CaptchaSolver`, `OcrSolver`, exceptions, `encrypt_password`
- Produces: `Client` with improved security defaults

- [ ] **Step 1: Replace entire client.py**

```python
# src/wyu_jwxt/client.py
"""Client — SDK 主入口，管理 session、登录、通用请求封装。"""
import json
import os
import stat
import time
import logging
from pathlib import Path
from typing import Optional

import requests

from .config import SchoolConfig
from .captcha import CaptchaSolver, OcrSolver
from .exceptions import (
    LoginError, SessionExpiredError, ChengfangError, RequestError,
)

__all__ = ["Client"]

_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
_DEFAULT_TIMEOUT = 30

logger = logging.getLogger(__name__)


class Client:
    """乘方教务系统客户端。"""

    def __init__(
        self,
        base_url: Optional[str] = None,
        *,
        config: Optional[SchoolConfig] = None,
        captcha_solver: Optional[CaptchaSolver] = None,
        manual_solver: Optional[CaptchaSolver] = None,
        max_login_retries: int = 5,
        timeout: float = _DEFAULT_TIMEOUT,
        verify: bool = True,
    ):
        self.config = config or (SchoolConfig(base_url=base_url) if base_url else SchoolConfig())
        self._captcha_solver = captcha_solver
        self._manual_solver = manual_solver
        self._max_retries = max_login_retries
        self._timeout = timeout
        self._session = requests.Session()
        self._session.verify = verify
        self._rebuild_headers()
        self._logged_in = False

    # ---------- 属性 ----------
    @property
    def logged_in(self) -> bool:
        return self._logged_in

    @property
    def session(self):
        return self._session

    def _rebuild_headers(self):
        self._session.headers.update({
            "User-Agent": _DEFAULT_UA,
            "Referer": self.config.base_url + "/",
        })

    # ---------- 验证码 ----------
    def _solve_captcha(self, image_bytes: bytes) -> str:
        """OCR 自动；失败回退手动"""
        if self._captcha_solver:
            try:
                return self._captcha_solver.solve(image_bytes)
            except Exception:
                pass
        if self._manual_solver:
            return self._manual_solver.solve(image_bytes)
        # 默认 OCR
        try:
            return OcrSolver().solve(image_bytes)
        except Exception:
            raise LoginError("验证码识别失败且无手动回退，请配置 manual_solver")

    # ---------- 登录 ----------
    def login(self, username: str, password: str) -> None:
        """完整登录流程。失败抛 LoginError。"""
        self._session.get(
            self.config.base_url + self.config.home_path,
            timeout=self._timeout,
        )
        encryptor = self.config.password_encryptor
        captcha_len_failures = 0

        for attempt in range(1, self._max_retries + 1):
            ts = str(int(time.time() * 1000))
            cap_resp = self._session.get(
                self.config.base_url + self.config.captcha_path,
                params={"d": ts},
                timeout=self._timeout,
            )
            if cap_resp.status_code != 200 or "image" not in cap_resp.headers.get("Content-Type", ""):
                raise LoginError(f"验证码获取失败: HTTP {cap_resp.status_code}")

            verifycode = self._solve_captcha(cap_resp.content)
            if len(verifycode) != 4:
                captcha_len_failures += 1
                if captcha_len_failures >= 3:
                    raise LoginError(
                        f"验证码识别连续 {captcha_len_failures} 次返回错误长度 "
                        f"({len(verifycode)} 位)，请检查验证码图片或手动输入"
                    )
                continue  # OCR 位数不对，重取
            captcha_len_failures = 0

            pwd_enc = encryptor(password, verifycode)
            resp = self._session.post(
                self.config.base_url + self.config.login_path,
                data={"account": username, "pwd": pwd_enc, "verifycode": verifycode},
                timeout=self._timeout,
            )
            try:
                result = resp.json()
            except ValueError:
                raise LoginError(f"登录响应非 JSON: {resp.text[:200]}")

            code = result.get("code")
            if code is not None and code >= 0:
                self._logged_in = True
                return
            if code == -302:
                raise LoginError("触发双因素认证，当前 SDK 暂不支持扫码")
            # 密码错误等不可恢复错误，不重试
            if code is not None and code < 0:
                raise LoginError(
                    f"登录失败: {result.get('message', '未知错误')} (code={code})"
                )

        raise LoginError(f"登录失败，已重试 {self._max_retries} 次")

    # ---------- session 持久化 ----------
    def save_session(self, path: str) -> None:
        """保存当前 cookie 到磁盘。"""
        cookies = []
        for c in self._session.cookies:
            cookie_dict = {
                "name": c.name, "value": c.value,
                "domain": c.domain, "path": c.path,
            }
            if c.expires:
                cookie_dict["expires"] = c.expires
            if c.secure:
                cookie_dict["secure"] = True
            cookies.append(cookie_dict)
        Path(path).write_text(
            json.dumps({"cookies": cookies, "logged_in": self._logged_in,
                        "base_url": self.config.base_url}, ensure_ascii=False),
            encoding="utf-8",
        )
        # 设置文件仅 owner 可读写
        try:
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass

    @classmethod
    def from_session(cls, path: str, *, config: Optional[SchoolConfig] = None) -> "Client":
        """从磁盘加载 cookie 复用登录态。"""
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            raise ChengfangError(f"会话文件不存在或损坏: {path}")
        saved_base_url = data.get("base_url") or "https://jxgl.wyu.edu.cn"
        if config is not None and config.base_url != saved_base_url:
            import warnings
            warnings.warn(
                f"config.base_url ({config.base_url}) 与会话文件的 base_url "
                f"({saved_base_url}) 不一致，cookie 可能无效"
            )
        client = cls(config=config or SchoolConfig(base_url=saved_base_url))
        for c in data.get("cookies", []):
            client._session.cookies.set(
                c["name"], c["value"],
                domain=c.get("domain"), path=c.get("path"),
            )
        client._logged_in = data.get("logged_in", False)
        return client

    # ---------- 通用请求 ----------
    def _ensure_logged_in(self):
        if not self._logged_in:
            raise SessionExpiredError("未登录，请先调用 login()")

    def _post(self, path: str, data: dict, *, json_response: bool = True,
              referer: Optional[str] = None):
        self._ensure_logged_in()
        headers = {}
        if referer:
            headers["Referer"] = referer
            headers["X-Requested-With"] = "XMLHttpRequest"
        try:
            resp = self._session.post(
                self.config.base_url + path, data=data, headers=headers,
                timeout=self._timeout,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            raise RequestError(f"POST {path} 请求失败: {e}") from e
        if json_response:
            try:
                return resp.json()
            except ValueError:
                raise ChengfangError(f"服务器返回非 JSON 响应: {resp.text[:200]}")
        return resp.text

    def _get(self, path: str, params: Optional[dict] = None, *,
             referer: Optional[str] = None):
        self._ensure_logged_in()
        headers = {}
        if referer:
            headers["Referer"] = referer
        try:
            resp = self._session.get(
                self.config.base_url + path, params=params, headers=headers,
                timeout=self._timeout,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            raise RequestError(f"GET {path} 请求失败: {e}") from e
        return resp.text
```

- [ ] **Step 2: Run tests**

```bash
pytest tests/ -v --tb=short
```

---

### Task 11: Fix __init__.py — __version__, RequestError export, import consolidation

**Files:**
- Modify: `src/wyu_jwxt/__init__.py`

- [ ] **Step 1: Replace entire __init__.py**

```python
__version__ = "0.1.0"

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
```

- [ ] **Step 2: Verify import works**

```bash
python -c "import sys; sys.path.insert(0, 'src'); import wyu_jwxt; print(wyu_jwxt.__version__)"
```

Expected: `0.1.0`

---

### Task 12: Fix .gitignore and pyproject.toml

**Files:**
- Modify: `D:\Desktop\wyu-jwxt-poc\.gitignore`
- Modify: `D:\Desktop\wyu-jwxt-poc\pyproject.toml`

- [ ] **Step 1: Add missing entries to .gitignore**

Append to `.gitignore`:

```
# 凭据与敏感文件
.env
*.log
credentials.*
secrets.*
*.pem
*.key

# 系统文件
Thumbs.db
.DS_Store
```

Also remove the duplicate `*.egg-info/` line (line 27 in original).

- [ ] **Step 2: Add [all] extras to pyproject.toml**

In `pyproject.toml`, under `[project.optional-dependencies]`, add:

```toml
all = ["wyu-jwxt[ocr,dev]"]
```

- [ ] **Step 3: Verify package config**

```bash
pip install -e ".[all]" --dry-run
```

---

### Task 13: Final integration verification

- [ ] **Step 1: Install with all extras**

```bash
pip install -e ".[all]"
```

- [ ] **Step 2: Run full test suite**

```bash
pytest tests/ -v --tb=short
```

- [ ] **Step 3: Check import and version**

```bash
python -c "from wyu_jwxt import Client, __version__; print(f'wyu-jwxt v{__version__} OK')"
```

- [ ] **Step 4: Lint check**

```bash
python -m py_compile src/wyu_jwxt/*.py
```
