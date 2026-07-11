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
