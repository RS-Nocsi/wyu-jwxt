# wyu-jwxt SDK

五邑大学乘方教务系统 Python SDK。以五邑大学为参考实现，理论兼容其他乘方学校。

## 项目结构

```
src/wyu_jwxt/
  __init__.py      # 导出所有公开 API，模块 mixin 挂载到 Client
  client.py        # Client 类：登录、session、通用请求封装
  config.py        # SchoolConfig：base_url + 接口路径，子类 override 实现跨校兼容
  crypto.py        # AES-128-ECB 乘方教务密码加密
  captcha.py       # 可插拔验证码：CaptchaSolver(ABC) / OcrSolver / ManualSolver
  models.py        # 数据模型：Course / Grade / Exam / StudentInfo
  schedule.py      # 课表查询 -> List[Course]
  grades.py        # 成绩查询 -> List[Grade]
  exams.py         # 考试查询 -> List[Exam]
  student_info.py  # 学籍查询 -> StudentInfo
  exceptions.py    # ChengfangError / LoginError / CaptchaError / SessionExpiredError
docs/
  USAGE.md         # 详细用法教程（11 节）
  API.md           # 完整 API 参考（含教务原始字段映射表）
```

## 环境

- Python >= 3.8
- 虚拟环境：`.venv`（Python 3.11）
- Shell：Git Bash
- `pip install -e ".[ocr,dev]"` 即可装好所有依赖
- pytest 测试：`pytest tests/`（集成测试需 `WYU_USER` / `WYU_PASS` 环境变量）
- Git 仓库已推送到 `github.com/RS-Nocsi/wyu-jwxt`，分支 `main`

## 接口协议

全部逆向自五邑大学 `jxgl.wyu.edu.cn` 实测。四个只读功能的协议：

| 功能 | 接口 | 方法 | 返回格式 |
|------|------|------|---------|
| 登录 | POST /new/login | {account, pwd(AES密文), verifycode} | {code, data} |
| 验证码 | GET /yzm?d=<ms> | — | JPEG 140×60，4位字母数字 |
| 课表 | POST /new/student/xsgrkb/getCalendarWeekDatas | {xnxqdm, zc, d1, d2} | {code, data[]} |
| 成绩 | POST /new/student/xskccj/kccjDatas | {xnxqdm, source, page, rows, sort, order} | {total, rows[]} |
| 考试 | POST /new/student/xsksrw/paginateXsksrw | {xnxqdm} | {data, rows[]} |
| 学籍 | GET /new/student/xjkpxx/edit.page + GET /new/welcome.page | — | HTML form + data 属性 |

## 登录加密

- AES-128-ECB，Pkcs7 padding
- 密钥 = 验证码 × 4（恰好 16 字节，只接受 4 字符验证码）
- 输出 hex

## 数据模型字段映射

**Course**（课表）：`kcmc→name` `teaxms→teacher` `jxcdmc→classroom` `qssj→start_time` `jssj→end_time` `jsxq→weekday(int)` `zc→weeks(List[int])` `xnxqdm→term_code` `kcbh→course_code`

**Grade**（成绩）：`kcmc→course_name` `zcj→score` `xf→credit(float)` `xnxqmc→term` `kkbmmc→department` `xdfsmc→nature` `kcbh→course_code` `xsxm→student_name`

**Exam**（考试）：`kcmc→course_name` `ksrq→date` `kssj→time` `kscdmc→classroom` `ksxsmc→exam_form` `khxsmc→exam_type`

**StudentInfo**（学籍）：welcome 页 `data-userbh→student_id` `data-userxm→name`；edit.page 表单 `sfzh→id_number` `dh→phone` `email→email` `jtdz→home_address` `ksh→exam_number` `lyzx→previous_school` `rxrq→enrollment_date` `py→pinyin_name` `xsywxm→english_name`

## 关键设计决策

- 验证码默认 ddddocr 自动识别；OCR 失败回退到 manual_solver（用户提供的回调）
- Session 持久的——`save_session`/`from_session` 免重登录
- 响应 code 检查：仅当 `"code" in result and result["code"] < 0` 才报错（课表/成绩/考试返回格式不同）
- 请求超时 30s，`verify=False`（学校自签证书）
- `verify` 和 `timeout` 在 `Client.__init__` 可配
- 学期代码格式 `f"{xn}{xq:02d}"`，term_code 有参数校验
- 硬编码日期 d1/d2 已改为按学期动态计算（第1学期8月，第2学期2月）
- `_safe_int()` 保护所有 int 转换（防非数字字符串崩溃）
- `.gitignore` 已覆盖：`.venv/` `__pycache__/` `*.egg-info/` `build/` `dist/` `.pytest_cache/` `tests/` `.idea/` `.vscode/` `*.tmp`

## 已知限制

- 不同学期课表查询的 d1/d2 是按学期估算的（开学第4周范围），未做精确校历匹配
- 双因素认证（code=-302）未支持——直接抛 LoginError
- 未实现写操作（评教/选课/请假）——Phase 2
- 仅五邑大学测试过
- 无日志系统（logging 基础设施已就位但未使用）
- 线程不安全（requests.Session 本身不是线程安全的）
- `__init__.py` mixin 猴子补丁模式——类型检查器无法推断动态挂载的方法

## Phase 2（待做）

菜单中 48 个功能已有精确接口路径（见 `menu_dump.json`，仅本地）。待实现的写操作：

- 评教：`new/student/teapj` / `new/student/wjdc` / `new/student/xsyxteapx`
- 选课/退课：`new/student/xsxk/`
- 请假：`new/student/xsqjsq`
