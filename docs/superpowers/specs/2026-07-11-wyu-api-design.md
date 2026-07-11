# wyu-jwxt API 站点设计文档

> 2026-07-11 | 方案 A：Flask API + Session 文件池

## 1. 目标

为五邑大学乘方教务 Python SDK（`wyu-jwxt`）封装 HTTP API，部署在 `wyu.rsnocsi.cn`，供个人调用。

## 2. 使用场景

- **对象：** 单用户自用（传自己的学号密码）
- **方式：** HTTP API 调用，无前端页面
- **验证码：** `ddddocr` 全自动识别，调用者无需参与

## 3. 架构

```
wyu.rsnocsi.cn (Nginx SSL)
        │
        ▼  proxy_pass http://127.0.0.1:8090
  Gunicorn (1 worker)
        │
        ▼
  Flask app (app.py)
        │
   ┌────┴────┐
   ▼         ▼
 wyu-jwxt   Session 文件池
   SDK      /www/wwwroot/wyu.rsnocsi.cn/wyu_sessions/
            ├── {学号}.json
            └── ...
```

### 3.1 技术栈

| 组件 | 选型 | 原因 |
|------|------|------|
| Web 框架 | Flask | 轻量，单文件即可 |
| WSGI 服务器 | Gunicorn（1 worker） | 个人用单进程足够，避免跨进程 session 同步 |
| SDK | wyu-jwxt v0.1.0 | 已有，`pip install` 安装 |
| Session 持久化 | 文件系统 JSON | 利用 SDK 自带 `save_session`/`from_session` |
| 验证码 | ddddocr | SDK 已集成 |

### 3.2 服务器环境

- OS：Linux（宝塔面板 BT Panel）
- Python：>= 3.11
- 网站根目录：`/www/wwwroot/wyu.rsnocsi.cn/`
- FTP：纯 FTP，端口 21，用户 `wyu_jxgl`
- 域名：`wyu.rsnocsi.cn`，已配置 SSL（Let's Encrypt）

## 4. API 设计

### 4.1 通用响应格式

```json
{"code": 0, "message": "ok", "data": ...}
```

- `code >= 0`：成功
- `code < 0`：失败，`message` 包含错误原因

### 4.2 端点一览

| # | 方法 | 路径 | 必需参数 | 可选参数 | data 类型 |
|---|------|------|----------|----------|-----------|
| 1 | POST | `/api/login` | `username`, `password` | — | `{"token": str}` |
| 2 | GET | `/api/schedule` | `token`, `xn`, `xq` | `week` | `Course[]` |
| 3 | GET | `/api/grades` | `token` | `xn`, `xq` | `Grade[]` |
| 4 | GET | `/api/exams` | `token`, `xn`, `xq` | — | `Exam[]` |
| 5 | GET | `/api/student-info` | `token` | — | `StudentInfo` |

### 4.3 端点详细说明

#### POST /api/login

登录教务系统并缓存 session。后续其他端点直接使用 `token`。

- **参数：** `username=学号&password=密码`（application/x-www-form-urlencoded）
- **成功：** `{"code": 0, "data": {"token": "3125001122"}}`
- **验证码：** 自动获取并 OCR 识别，对调用者透明

#### GET /api/schedule

- **参数：** `token`, `xn`（学年起始年）, `xq`（1 或 2）, `week?`（周次或空=整学期）
- **成功 data：** `[{name, teacher, classroom, start_time, end_time, weekday, weeks, term_code, course_code}, ...]`

#### GET /api/grades

- **参数：** `token`, `xn?`, `xq?`（都不传=全部学期）
- **成功 data：** `[{course_name, score, credit, term, department, nature, course_code, student_name}, ...]`
- **分页：** 服务端自动拉取所有分页，一次性返回

#### GET /api/exams

- **参数：** `token`, `xn`, `xq`
- **成功 data：** `[{course_name, date, time, classroom, exam_form, exam_type}, ...]`

#### GET /api/student-info

- **参数：** `token`
- **成功 data：** `{student_id, name, id_number, phone, email, home_address, exam_number, previous_school, enrollment_date, pinyin_name, english_name}`

## 5. Session 管理

### 5.1 文件池

- 路径：`/www/wwwroot/wyu.rsnocsi.cn/wyu_sessions/{学号}.json`
- 内容：SDK `save_session` 输出的 JSON（cookie + base_url + logged_in 标志）

### 5.2 生命周期

```
首次请求 → Client.from_session(学号.json)
              │
   ┌──────────┴──────────┐
   ▼ 文件存在且有效       ▼ 文件不存在或过期
  直接使用 Client       创建 Client → login() → save_session()
                              │
                              ▼
                         后续请求直接复用

请求失败(SessionExpiredError) → 自动 login() 重新执行 → save_session()
```

### 5.3 并发安全

- Gunicorn 单 worker（1 进程），仅多线程
- 按学号粒度 `threading.Lock`，防止同用户并发登录
- 文件读写前加锁，写完后解锁

## 6. 错误处理

| 场景 | HTTP | code | message |
|------|------|------|---------|
| 缺少必填参数 | 400 | -1 | "缺少参数: username" |
| token 参数缺失 | 400 | -1 | "缺少参数: token" |
| 自动登录失败（密码错等） | 401 | -2 | "登录失败: 密码错误 (code=-1)" |
| OCR 验证码连续失败 | 401 | -2 | "登录失败: 验证码识别多次失败" |
| Session 过期且自动重登失败 | 401 | -3 | "登录态过期且重登失败" |
| 教务查询返回错误 | 500 | -4 | "课表查询失败" |
| 教务系统不可达 | 502 | -5 | "教务系统无响应: timeout" |
| 内部未知异常 | 500 | -99 | "内部错误: ..." |

## 7. 部署

### 7.1 文件清单

```
/www/wwwroot/wyu.rsnocsi.cn/
├── app.py                 # Flask 应用（全部路由 + session 管理）
├── requirements.txt       # 依赖
│   wyu-jwxt==0.1.0
│   flask>=2.3
│   gunicorn>=21.2
└── wyu_sessions/          # 运行时自动创建
```

### 7.2 宝塔面板配置

1. 网站 → wyu.rsnocsi.cn → 设置 → 项目类型：**Python**
2. Python 版本：3.11（或服务器已有版本）
3. 运行目录：`/www/wwwroot/wyu.rsnocsi.cn`
4. 启动命令：`gunicorn app:app -w 1 -b 127.0.0.1:8090 --timeout 60`
5. 反向代理：`/` → `http://127.0.0.1:8090`（宝塔自动生成 nginx 配置）

### 7.3 依赖安装

SSH 到服务器执行：

```bash
cd /www/wwwroot/wyu.rsnocsi.cn
pip install -r requirements.txt
```

### 7.4 启动

在宝塔面板 Python 项目管理器中启动项目，或手动：

```bash
cd /www/wwwroot/wyu.rsnocsi.cn
gunicorn app:app -w 1 -b 127.0.0.1:8090 --timeout 60 --daemon
```

## 8. 安全考虑

- Nginx SSL 终止（宝塔已配 Let's Encrypt）
- API 无独立认证层（依赖教务账号密码本身做认证）
- Session 文件 `wyu_sessions/` 应对 Web 用户不可读（`chmod 700`）
- `app.py` 不包含任何硬编码凭据
- 所有参数做空值/类型校验

## 9. 已知限制

- 单 worker 模式，并发能力有限（个人自用足够）
- 未实现 token 刷新机制（session 过期自动重登）
- 未做频率限制
- 未实现 logout 端点（session 会自然过期或手动删文件）
- 暂不支持多学期参数组合查询
