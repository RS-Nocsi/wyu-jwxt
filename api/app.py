# app.py — wyu-jwxt API 站点
"""五邑大学乘方教务系统 HTTP API。

部署: gunicorn app:app -w 1 -b 127.0.0.1:8090 --timeout 60
"""

import os
import threading
import logging
from pathlib import Path

from flask import Flask, request, jsonify

from wyu_jwxt import (
    Client, LoginError, SessionExpiredError, ChengfangError, RequestError,
)

# ---------- 初始化 ----------
app = Flask(__name__)

SESSIONS_DIR = Path(__file__).parent / "wyu_sessions"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("wyu-api")

_locks: dict[str, threading.Lock] = {}
_locks_factory = threading.Lock()


def _ensure_dir_private():
    """确保 session 目录仅 owner 可读写。"""
    SESSIONS_DIR.mkdir(exist_ok=True)
    try:
        os.chmod(SESSIONS_DIR, 0o700)
    except OSError:
        pass


_ensure_dir_private()


# ---------- Session 管理 ----------
def _get_lock(student_id: str) -> threading.Lock:
    with _locks_factory:
        if student_id not in _locks:
            _locks[student_id] = threading.Lock()
        return _locks[student_id]


def _get_or_login(student_id: str, username: str = None, password: str = None) -> Client:
    """获取已登录的 Client；session 不存在时自动登录。

    Args:
        student_id: 学号（用作 session 文件名和 token）
        username: 仅首次登录时需要
        password: 仅首次登录时需要

    Returns:
        已登录的 Client 实例

    Raises:
        LoginError: 登录失败
    """
    session_file = SESSIONS_DIR / f"{student_id}.json"
    lock = _get_lock(student_id)

    with lock:
        client = None

        if session_file.exists():
            try:
                client = Client.from_session(str(session_file), verify=False)
            except Exception:
                pass

        if client is None:
            if not username or not password:
                raise LoginError("请先调用 /api/login 登录")
            client = Client(verify=False)
            client.login(username, password)
            client.save_session(str(session_file))

        return client


def _client_from_session(student_id: str) -> Client | None:
    """从 session 文件加载 Client。若文件不存在或损坏返回 None。"""
    session_file = SESSIONS_DIR / f"{student_id}.json"
    if not session_file.exists():
        return None
    try:
        return Client.from_session(str(session_file), verify=False)
    except Exception:
        return None


# ---------- 响应工具 ----------
def _build_success(data=None):
    return jsonify({"code": 0, "message": "ok", "data": data})


def _build_error(code: int, message: str, http_status: int = 200):
    return jsonify({"code": code, "message": message, "data": None}), http_status


def _serialize(obj) -> dict:
    """将 dataclass 对象转为可 JSON 序列化的 dict。"""
    if hasattr(obj, "__dataclass_fields__"):
        return {k: v for k, v in obj.__dict__.items()}
    return obj


# ---------- 请求日志 + CORS ----------
@app.before_request
def _log_request():
    logger.info(f"{request.method} {request.path} from {request.remote_addr}")


@app.after_request
def _add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


# ---------- 全局错误处理 ----------
@app.errorhandler(404)
def _handle_404(e):
    return _build_error(-1, "接口不存在", 404)


@app.errorhandler(405)
def _handle_405(e):
    return _build_error(-1, "方法不允许", 405)


@app.errorhandler(500)
def _handle_500(e):
    logger.error(f"Internal server error: {e}")
    return _build_error(-99, "内部服务器错误", 500)


# ========================
# API 端点
# ========================

# ---------- 健康检查 ----------
@app.route("/api/health")
def api_health():
    return _build_success({"status": "ok"})


# ---------- 登录 ----------
@app.route("/api/login", methods=["POST"])
def api_login():
    username = (request.form.get("username") or "").strip()
    password = (request.form.get("password") or "").strip()
    if not username or not password:
        return _build_error(-1, "缺少参数: username 或 password", 400)

    try:
        client = _get_or_login(username, username, password)
        return _build_success({"token": username})
    except LoginError as e:
        return _build_error(-2, str(e), 401)
    except RequestError as e:
        return _build_error(-5, f"教务系统无响应: {e}", 502)
    except Exception as e:
        logger.exception("api_login 未知错误")
        return _build_error(-99, f"内部错误: {e}", 500)


# ---------- 通用查询包装器 ----------
def _api_query(student_id: str, query_fn, *args, error_label: str = "查询", **kwargs):
    """通用查询：从 session 加载 Client → 执行查询 → 返回 JSON。

    session 不存在返回 -3 要求先登录；session 过期返回 -3。
    """
    client = _client_from_session(student_id)
    if client is None:
        return _build_error(-3, "未登录或 session 已失效，请先调用 /api/login", 401)

    try:
        result = query_fn(client, *args, **kwargs)
    except SessionExpiredError:
        try:
            (SESSIONS_DIR / f"{student_id}.json").unlink()
        except OSError:
            pass
        return _build_error(-3, "登录态过期，请重新调用 /api/login", 401)
    except ChengfangError as e:
        return _build_error(-4, f"{error_label}失败: {e}", 500)
    except RequestError as e:
        return _build_error(-5, f"教务系统无响应: {e}", 502)
    except Exception as e:
        logger.exception(f"{error_label} 未知错误")
        return _build_error(-99, f"内部错误: {e}", 500)

    if isinstance(result, list):
        data = [_serialize(obj) for obj in result]
    else:
        data = _serialize(result)
    return _build_success(data)


# ---------- 课表 ----------
@app.route("/api/schedule")
def api_schedule():
    student_id = request.args.get("token", "").strip()
    xn_s = request.args.get("xn", "").strip()
    xq_s = request.args.get("xq", "").strip()
    week_s = request.args.get("week", "").strip()

    if not student_id:
        return _build_error(-1, "缺少参数: token", 400)
    if not xn_s or not xq_s:
        return _build_error(-1, "缺少参数: xn 或 xq", 400)

    try:
        xn = int(xn_s)
        xq = int(xq_s)
    except ValueError:
        return _build_error(-1, "xn 和 xq 必须为整数", 400)

    week = int(week_s) if week_s else None

    def query(client, xn, xq, week):
        return client.get_schedule(xn, xq, week)

    return _api_query(student_id, query, xn, xq, week, error_label="课表查询")


# ---------- 成绩 ----------
@app.route("/api/grades")
def api_grades():
    student_id = request.args.get("token", "").strip()
    xn_s = request.args.get("xn", "").strip()
    xq_s = request.args.get("xq", "").strip()

    if not student_id:
        return _build_error(-1, "缺少参数: token", 400)

    xn = None
    xq = None
    if xn_s or xq_s:
        if not xn_s or not xq_s:
            return _build_error(-1, "xn 和 xq 必须同时提供或同时省略", 400)
        try:
            xn = int(xn_s)
            xq = int(xq_s)
        except ValueError:
            return _build_error(-1, "xn 和 xq 必须为整数", 400)

    def query(client, xn, xq):
        return client.get_grades(xn, xq)

    return _api_query(student_id, query, xn, xq, error_label="成绩查询")


# ---------- 考试 ----------
@app.route("/api/exams")
def api_exams():
    student_id = request.args.get("token", "").strip()
    xn_s = request.args.get("xn", "").strip()
    xq_s = request.args.get("xq", "").strip()

    if not student_id:
        return _build_error(-1, "缺少参数: token", 400)
    if not xn_s or not xq_s:
        return _build_error(-1, "缺少参数: xn 或 xq", 400)

    try:
        xn = int(xn_s)
        xq = int(xq_s)
    except ValueError:
        return _build_error(-1, "xn 和 xq 必须为整数", 400)

    def query(client, xn, xq):
        return client.get_exams(xn, xq)

    return _api_query(student_id, query, xn, xq, error_label="考试查询")


# ---------- 学籍 ----------
@app.route("/api/student-info")
def api_student_info():
    student_id = request.args.get("token", "").strip()

    if not student_id:
        return _build_error(-1, "缺少参数: token", 400)

    def query(client):
        return client.get_student_info()

    return _api_query(student_id, query, error_label="学籍查询")


# ========================
# 启动入口
# ========================
if __name__ == "__main__":
    _ensure_dir_private()
    logger.info("Starting wyu-jwxt API server on 0.0.0.0:5000 ...")
    app.run(host="0.0.0.0", port=5000, debug=False)
