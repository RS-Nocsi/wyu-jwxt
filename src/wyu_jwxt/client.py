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
                continue
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
