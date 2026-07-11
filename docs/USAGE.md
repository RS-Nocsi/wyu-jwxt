# wyu-jwxt 详细用法教程

## 目录

1. [安装](#1-安装)
2. [登录](#2-登录)
3. [课表查询](#3-课表查询)
4. [成绩查询](#4-成绩查询)
5. [考试安排](#5-考试安排)
6. [学籍卡片](#6-学籍卡片)
7. [Session 持久化](#7-session-持久化)
8. [验证码处理](#8-验证码处理)
9. [错误处理](#9-错误处理)
10. [其他学校兼容](#10-其他学校兼容)
11. [完整示例](#11-完整示例)

---

## 1. 安装

```bash
pip install wyu-jwxt
```

一个命令装好所有依赖（含验证码自动识别）。

如需从源码安装：

```bash
git clone https://github.com/RS-Nocsi/wyu-jwxt.git
cd wyu-jwxt
pip install -e .
```

`[ocr]` 扩展会安装 `ddddocr` 和 `Pillow`，用于自动识别教务系统的图形验证码。

---

## 2. 登录

### 2.1 基础登录

```python
from wyu_jwxt import Client

client = Client(base_url="https://jxgl.wyu.edu.cn")
client.login("学号", "密码")
```

login 内部做了什么：
1. 访问教务首页，获取 `JSESSIONID` 会话 cookie
2. 请求验证码图片（`GET /yzm`）
3. 用 ddddocr OCR 自动识别验证码（4位字母数字）
4. AES-128-ECB 加密密码（密钥 = 验证码 × 4）
5. POST 登录接口
6. 检查返回值：`code >= 0` 成功，`code = -302` 双因素，其他失败重试

### 2.2 登录参数

```python
client = Client(
    base_url="https://jxgl.wyu.edu.cn",
    max_login_retries=5,    # 最大重试次数（默认5）
    timeout=30,             # HTTP 超时秒数（默认30）
    verify=False,           # SSL证书验证（默认False，学校系统常用自签证书）
)
```

---

## 3. 课表查询

### 3.1 基础用法

```python
courses = client.get_schedule(2025, 2)   # 2025-2026 第二学期全部课表
```

### 3.2 按周次过滤

```python
week1 = client.get_schedule(2025, 2, week=1)    # 仅第1周
```

### 3.3 返回数据

返回 `List[Course]`，每条记录是一个排课时段（同一门课不同时间/教室会返回多条）。

```python
for c in courses:
    print(c.name)           # 课程名称
    print(c.teacher)        # 任课教师
    print(c.classroom)      # 教室
    print(c.start_time)     # 上课时间
    print(c.end_time)       # 下课时间
    print(c.weekday)        # 星期几: 2 (1=周一...7=周日)
    print(c.weeks)          # 上课周次: [1,2,3,4,5,7,8,9,...]
    print(c.term_code)      # 学期代码: "202502"
    print(c.course_code)    # 课程编号: "0400012"
```

### 3.4 去重

同一门课可能有多条排课记录（不同教室/时间），去重示例：

```python
seen = set()
for c in courses:
    key = (c.name, c.teacher)
    if key not in seen:
        seen.add(key)
        print(f"{c.name} - {c.teacher}")
```

---

## 4. 成绩查询

### 4.1 指定学期

```python
grades = client.get_grades(2025, 2)   # 2025-2026 第二学期
```

### 4.2 全部学期

```python
all_grades = client.get_grades()       # 不传参数 = 全部学期
```

### 4.3 返回数据

```python
for g in grades:
    print(g.course_name)    # 课程名称
    print(g.score)          # 成绩
    print(g.credit)         # 学分
    print(g.term)           # 学期
    print(g.department)     # 开课学院
    print(g.nature)         # 课程性质
    print(g.course_code)    # 课程编号
    print(g.student_name)   # 学生姓名
```

### 4.4 实用场景

```python
# 计算 GPA
grades = client.get_grades(2025, 2)
total_points = sum(float(g.score) * g.credit for g in grades)
total_credits = sum(g.credit for g in grades)
gpa = total_points / total_credits if total_credits else 0

# 按学期分组
from collections import defaultdict
by_term = defaultdict(list)
for g in client.get_grades():
    by_term[g.term].append(g)
```

---

## 5. 考试安排

### 5.1 基础用法

```python
exams = client.get_exams(2025, 2)
```

### 5.2 返回数据

```python
for e in exams:
    print(e.course_name)    # 考试课程名称
    print(e.date)           # 考试日期
    print(e.time)           # 考试时间
    print(e.classroom)      # 考场
    print(e.exam_form)      # 考试形式
    print(e.exam_type)      # 考试类型
```

### 5.3 临近考试提醒

```python
import datetime
today = datetime.date.today()
for e in exams:
    exam_date = datetime.date.fromisoformat(e.date)
    days_left = (exam_date - today).days
    if 0 <= days_left <= 7:
        print(f"⚠ {e.course_name} 还有 {days_left} 天考试 ({e.date})")
```

---

## 6. 学籍卡片

```python
info = client.get_student_info()

print(info.student_id)       # 学号
print(info.name)             # 姓名
print(info.id_number)        # 身份证号
print(info.phone)            # 手机
print(info.email)            # 邮箱
print(info.home_address)     # 家庭地址
print(info.exam_number)      # 考生号
print(info.previous_school)  # 毕业中学
print(info.enrollment_date)  # 入学日期
print(info.pinyin_name)      # 拼音名
print(info.english_name)     # 英文名
```

---

## 7. Session 持久化

登录费时间（需要请求验证码 + OCR 识别）。登录后可以保存 cookie 到磁盘，下次直接复用。

```python
# 保存
client.save_session("cookie.cache")

# 下次直接加载，无需重新登录
client = Client.from_session("cookie.cache")
schedule = client.get_schedule(2025, 2)   # 直接可用
```

缓存文件是 JSON 格式，包含 base_url、cookies、登录状态。

---

## 8. 验证码处理

### 8.1 默认模式（OCR 自动）

```python
client = Client()
client.login("学号", "密码")
# ddddocr 自动识别验证码，首次成功率约 95%
```

### 8.2 手动输入回退

当 OCR 失败时自动回调你提供的函数：

```python
from wyu_jwxt import Client, ManualSolver

def show_and_ask(image_bytes):
    """收到验证码图片，让用户手动输入"""
    with open("captcha.jpg", "wb") as f:
        f.write(image_bytes)
    return input("请输入验证码: ").strip()

client = Client(manual_solver=ManualSolver(show_and_ask))
client.login("学号", "密码")
# OCR成功 → 直接用
# OCR失败 → 调用 show_and_ask 让用户手动输入
```

### 8.3 自定义 OCR

```python
from wyu_jwxt import CaptchaSolver

class MyBetterOcr(CaptchaSolver):
    def solve(self, image_bytes):
        # 你的自定义OCR逻辑
        return "abcd"

client = Client(captcha_solver=MyBetterOcr())
```

---

## 9. 错误处理

```python
from wyu_jwxt import Client
from wyu_jwxt.exceptions import LoginError, CaptchaError, SessionExpiredError, ChengfangError

client = Client()

try:
    client.login("学号", "错误密码")
except LoginError as e:
    print(f"登录失败: {e}")

try:
    courses = client.get_schedule(2025, 2)
except SessionExpiredError:
    print("登录态过期，请重新登录")
except ChengfangError as e:
    print(f"请求失败: {e}")
```

所有异常都继承自 `ChengfangError`，可以统一捕获：

```python
try:
    client.login(...)
    data = client.get_schedule(...)
except ChengfangError as e:
    print(f"教务操作失败: {e}")
```

---

## 10. 其他学校兼容

乘方教务是一个通用教务系统，理论上其他学校也能用。通过继承 `SchoolConfig` 配置差异点：

```python
from wyu_jwxt import Client, SchoolConfig

class MySchool(SchoolConfig):
    base_url = "https://jwxt.other.edu.cn"

    # 如果接口路径不同，覆盖这些属性
    login_path = "/new/login"
    captcha_path = "/yzm"
    schedule_data_path = "/new/student/xsgrkb/getCalendarWeekDatas"

    # 如果加密算法不同，覆盖这个属性
    @property
    def password_encryptor(self):
        from wyu_jwxt.crypto import encrypt_password
        return encrypt_password  # 或你的自定义加密函数

    # 如果学期代码格式不同，覆盖这个方法
    def term_code(self, xn, xq):
        return f"{xn}-{xq}"   # 默认是 f"{xn}{xq:02d}" 即 "202502"

client = Client(config=MySchool())
```

---

## 11. 完整示例

### 11.1 一键获取所有信息

```python
from wyu_jwxt import Client

client = Client(base_url="https://jxgl.wyu.edu.cn")
client.login("学号", "密码")

# 课表
schedule = client.get_schedule(2025, 2)
print(f"课表: {len(schedule)} 条排课记录")

# 成绩
grades = client.get_grades(2025, 2)
print(f"成绩: {len(grades)} 门课程")

# 考试
exams = client.get_exams(2025, 2)
print(f"考试: {len(exams)} 场")

# 学籍
info = client.get_student_info()
print(f"学籍: {info.name} ({info.student_id})")
```

### 11.2 课表转 iCal

```python
from wyu_jwxt import Client
import datetime

client = Client()
client.login("学号", "密码")

# 开学日期（需根据校历调整）
SEMESTER_START = datetime.date(2026, 2, 23)

for c in client.get_schedule(2025, 2):
    for week in c.weeks:
        date = SEMESTER_START + datetime.timedelta(
            weeks=week - 1,
            days=c.weekday - SEMESTER_START.weekday() - 1
        )
        start = datetime.datetime.strptime(c.start_time, "%H:%M:%S").time()
        end = datetime.datetime.strptime(c.end_time, "%H:%M:%S").time()
        # ... 生成 iCal 事件
```

### 11.3 带 Session 复用的 CLI 工具

```python
#!/usr/bin/env python
import sys, os
from wyu_jwxt import Client, ManualSolver

CACHE = os.path.expanduser("~/.wyu_jwxt_cache.json")

def get_client():
    if os.path.exists(CACHE):
        return Client.from_session(CACHE)
    client = Client()
    client.login(input("学号: "), input("密码: "))
    client.save_session(CACHE)
    return client

client = get_client()
cmd = sys.argv[1] if len(sys.argv) > 1 else "schedule"

if cmd == "schedule":
    for c in client.get_schedule(2025, 2):
        print(f"{c.name} {c.teacher} {c.classroom} 周{c.weekday}")
elif cmd == "grades":
    for g in client.get_grades(2025, 2):
        print(f"{g.course_name}: {g.score}分 {g.credit}学分")
elif cmd == "exams":
    for e in client.get_exams(2025, 2):
        print(f"{e.date} {e.course_name} {e.time} {e.classroom}")
elif cmd == "info":
    i = client.get_student_info()
    print(f"{i.name} {i.student_id} {i.enrollment_date}")
```
