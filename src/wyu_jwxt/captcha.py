# src/wyu_jwxt/captcha.py
"""验证码处理 — 可插拔设计。

默认用 ddddocr 自动识别（需装 [ocr] extras），识别失败/未安装时
回退到用户传入的 ManualSolver 手动输入。
"""
from abc import ABC, abstractmethod
from typing import Callable, Optional

from .exceptions import CaptchaError

__all__ = ["CaptchaSolver", "OcrSolver", "ManualSolver"]


class CaptchaSolver(ABC):
    """验证码识别器接口。"""

    @abstractmethod
    def solve(self, image_bytes: bytes) -> str:
        """识别验证码图片，返回 4 位字母数字字符串。"""


class ManualSolver(CaptchaSolver):
    """手动输入验证码 — 调用用户提供的回调函数。"""

    def __init__(self, callback: Callable[[bytes], Optional[str]]):
        self._callback = callback

    def solve(self, image_bytes: bytes) -> str:
        result = self._callback(image_bytes)
        if not result:
            raise CaptchaError("手动验证码回调未返回结果")
        return "".join(c for c in result if c.isalnum())


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

    @property
    def engine(self):
        return self._get_engine()

    def solve(self, image_bytes: bytes) -> str:
        engine = self._get_engine()
        raw = engine.classification(image_bytes)
        return "".join(c for c in raw if c.isalnum())
