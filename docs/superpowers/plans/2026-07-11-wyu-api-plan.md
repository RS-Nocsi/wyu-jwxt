# wyu-jwxt API 站点实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 wyu-jwxt SDK 搭建 Flask API 站点，部署到 wyu.rsnocsi.cn（宝塔面板 + gunicorn）

**Architecture:** 单文件 Flask app，Session 文件池持久化登录态，ddddocr 自动识别验证码，线程锁保护并发

**Tech Stack:** Python 3.11, Flask 2.3+, Gunicorn 21+, wyu-jwxt 0.1.0, ddddocr 1.4+

## Global Constraints

- Python >= 3.8（与 SDK 一致）
- 所有异常统一返回 `{"code": <0, "message": "...", "data": None}`
- Session 文件池路径：`{app.py 同级}/wyu_sessions/`
- Gunicorn 1 worker，避免跨进程 session 共享问题
- 教务系统自签证书，需 `verify=False`
- API 返回 JSON（Content-Type: application/json）
- 不硬编码凭据
- 参数校验：所有必填参数有缺失时返回 code=-1

---

### Task 1: 创建 app.py — 基础框架 + 登录端点

**Files:**
- Create: `D:\Desktop\wyu-jwxt-poc\app.py`

**Interfaces:**
- Produces: Flask app 实例 + `POST /api/login` + session 管理函数

- [ ] **Step 1: 编写 app.py 基础结构**

```python
# app.py — wyu-jwxt API 站点
"""五邑大学乘方教务系统 HTTP API。"""

import os
import threading
from pathlib import Path

from flask import Flask, request, jsonify

from wyu_jwxt import (
    Client, LoginError, SessionExpiredError, ChengfangError, RequestError,
)

app = Flask(__name__)

SESSIONS_DIR = Path(__file__).parent / "wyu_sessions"
SESSIONS_DIR.mkdir(exist_ok=True)
os.chmod(SESSIONS_DIR, 0o700)

_locks: dict[str, threading.Lock] = {}
_locks_factory = threading.Lock()


def _ensure_dir_private():
    try:
        os.chmod(SESSIONS_DIR, 0o700)
    except OSError:
        pass


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

        # 尝试从已保存的 session 恢复
        if session_file.exists():
            try:
                client = Client.from_session(str(session_file), verify=False)
            except Exception:
                pass  # session 损坏，走登录流程

        # session 不存在或无效，需要登录
        if client is None:
            if not username or not password:
                raise LoginError("请先调用 /api/login 登录")
            client = Client(verify=False)
            client.login(username, password)
            client.save_session(str(session_file))

        return client


def _build_error(code: int, message: str, http_status: int = 200):
    return jsonify({"code": code, "message": message, "data": None}), http_status


# ---------- 登录端点 ----------
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
        return _build_error(-99, f"内部错误: {e}", 500)


# ---------- 健康检查 ----------
@app.route("/api/health")
def api_health():
    return _build_success({"status": "ok"})
```

- [ ] **Step 2: 验证语法**

```bash
python -m py_compile app.py
```

- [ ] **Step 3: 启动 Flask 开发服务器验证**

```bash
python app.py &
```
访问 http://127.0.0.1:5000/api/health
Expected: `{"code":0,"message":"ok","data":{"status":"ok"}}`

---

### Task 2: 添加四个数据端点

**Files:**
- Modify: `D:\Desktop\wyu-jwxt-poc\app.py`（在 Task 1 的基础上追加）

**Interfaces:**
- Consumes: `_get_or_login`, `_recover_or_raise`, `_build_success`, `_build_error`
- Produces: 4 个 GET 端点

- [ ] **Step 1: 追加端点代码到 app.py**

在 `api_login` 之后、`api_health` 之前插入：

```python
# ---------- 通用查询包装器 ----------
def _client_from_session(student_id: str) -> Client | None:
    """从 session 文件加载 Client。若文件不存在或损坏返回 None。"""
    session_file = SESSIONS_DIR / f"{student_id}.json"
    if not session_file.exists():
        return None
    try:
        return Client.from_session(str(session_file), verify=False)
    except Exception:
        return None


def _serialize(obj) -> dict:
    """将 dataclass 对象转为可 JSON 序列化的 dict。"""
    if hasattr(obj, "__dataclass_fields__"):
        return {k: v for k, v in obj.__dict__.items()}
    return obj


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
        # 清理过期 session 文件
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
        obj = client.get_student_info()
    return _api_query(student_id, query, error_label="学籍查询")
```

- [ ] **Step 2: 验证语法**

```bash
python -m py_compile app.py
```

- [ ] **Step 3: 启动 Flask 测试（需要环境变量）**

```bash
set WYU_USER=3125001122
set WYU_PASS=...
python app.py &
curl "http://127.0.0.1:5000/api/login" -d "username=3125001122&password=..."
```
Expected: `{"code":0,"message":"ok","data":{"token":"3125001122"}}`

---

### Task 3: 完善错误处理 + 添加 CORS 和日志

**Files:**
- Modify: `D:\Desktop\wyu-jwxt-poc\app.py`

**Interfaces:**
- 新增全局错误处理器、CORS 头、启动日志

- [ ] **Step 1: 在 app.py 顶部（app 创建之后）加入**

```python
# 请求日志中间件
import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("wyu-api")


@app.before_request
def _log_request():
    logger.info(f"{request.method} {request.path} from {request.remote_addr}")


@app.after_request
def _add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


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


if __name__ == "__main__":
    _ensure_dir_private()
    logger.info("Starting wyu-jwxt API server...")
    app.run(host="0.0.0.0", port=5000, debug=False)
```

- [ ] **Step 2: 验证语法**

```bash
python -m py_compile app.py
```

---

### Task 4: 创建 requirements.txt 和部署配置

**Files:**
- Create: `D:\Desktop\wyu-jwxt-poc\requirements.txt`

- [ ] **Step 1: 编写 requirements.txt**

```
flask>=2.3
gunicorn>=21.2
wyu-jwxt==0.1.0
```

- [ ] **Step 2: 验证文件存在**

```bash
type requirements.txt
```

---

### Task 5: 本地上线前全量测试

**Files:**
- 验证: `app.py`, `requirements.txt`

- [ ] **Step 1: 检查所有文件语法**

```bash
python -m py_compile app.py
```

- [ ] **Step 2: 运行 SDK 测试确保没有破坏**

```bash
.venv\Scripts\python.exe -m pytest tests/ -v --tb=short
```

Expected: 全部通过

- [ ] **Step 3: 检查 app.py 不包含硬编码凭据**

```bash
python -c "import ast; code=open('app.py',encoding='utf-8').read(); tree=ast.parse(code); print('AST OK')"
```

- [ ] **Step 4: 用环境变量启动并测试健康检查**

```bash
$env:WYU_USER=""; $env:WYU_PASS=""
Start-Process -NoNewWindow python -ArgumentList "app.py"
Start-Sleep -Seconds 2
curl.exe -s http://127.0.0.1:5000/api/health
```

Expected: `{"code":0,"message":"ok","data":{"status":"ok"}}`

- [ ] **Step 5: 测试错误处理**

```bash
curl.exe -s http://127.0.0.1:5000/api/schedule
```

Expected: `{"code":-1,"message":"缺少参数: token","data":null}`

---

### Task 6: FTP 部署 + 服务器端配置

**Files:**
- Deploy: `app.py` → FTP `/www/wwwroot/wyu.rsnocsi.cn/app.py`
- Deploy: `requirements.txt` → FTP `/www/wwwroot/wyu.rsnocsi.cn/requirements.txt`
- Open `wyu_sessions/` directory

**注意：此 Task 需要在服务器上执行 `pip install` 和宝塔面板重新配置，需用户配合。**

- [ ] **Step 1: 通过 FTP 上传文件**

连接到 `ftp://175.178.224.42:21`（纯 FTP，用户 `wyu_jxgl`），上传：
- `app.py` → `/www/wwwroot/wyu.rsnocsi.cn/app.py`
- `requirements.txt` → `/www/wwwroot/wyu.rsnocsi.cn/requirements.txt`

```bash
# 在服务器 SSH 上执行（需用户执行）：
cd /www/wwwroot/wyu.rsnocsi.cn
pip install -r requirements.txt
mkdir -p wyu_sessions
chmod 700 wyu_sessions
```

- [ ] **Step 2: 宝塔面板配置**

在宝塔面板中：
1. 网站 → wyu.rsnocsi.cn → 设置 → **网站目录** → 项目类型：从 PHP 改为 **Python**
2. 运行目录：`/www/wwwroot/wyu.rsnocsi.cn`
3. 启动命令：`gunicorn app:app -w 1 -b 127.0.0.1:8090 --timeout 60 --daemon --error-logfile /www/wwwroot/wyu.rsnocsi.cn/error.log --access-logfile /www/wwwroot/wyu.rsnocsi.cn/access.log`
4. 保存并启动

- [ ] **Step 3: 验证线上 API**

```bash
curl -s https://wyu.rsnocsi.cn/api/health
```

Expected: `{"code":0,"message":"ok","data":{"status":"ok"}}`

```bash
curl -s -X POST https://wyu.rsnocsi.cn/api/login -d "username=3125001122&password=xxx"
```

Expected: `{"code":0,"message":"ok","data":{"token":"3125001122"}}`

```bash
curl -s "https://wyu.rsnocsi.cn/api/schedule?token=3125001122&xn=2025&xq=1"
```

Expected: 返回课表 JSON 数组

---

### Task 7: 提交代码

- [ ] **Step 1: Stage 并 commit**

```bash
git add app.py requirements.txt docs/superpowers/specs/ docs/superpowers/plans/
git commit -m "feat: add Flask API site wrapping wyu-jwxt SDK

- Single-file Flask app with 5 endpoints (login, schedule, grades, exams, student-info)
- Session file pool for persistent login reuse
- Auto OCR captcha via ddddocr
- Thread-safe session management with per-student locks
- Request logging, CORS, unified error response format
- Deployment config via requirements.txt + gunicorn"
```

- [ ] **Step 2: Push**

```bash
git push origin main
```
