# wyu-jwxt

[![Python](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

五邑大学乘方教务系统 Python SDK。**以五邑大学为参考实现**，base_url 可配，理论兼容其他乘方教务学校。

> 登录加密算法、接口协议全部逆向自 `jxgl.wyu.edu.cn` 实测，理论兼容其它乘方教务系统。

📖 **[详细用法教程](docs/USAGE.md)** · **[API 参考](docs/API.md)**

## 安装

```bash
git clone https://github.com/RS-Nocsi/wyu-jwxt.git
cd wyu-jwxt
pip install -e .             # 基础安装
pip install -e ".[ocr]"      # 含验证码自动识别（推荐）
```

## 快速开始

```python
from wyu_jwxt import Client

client = Client(base_url="https://jxgl.wyu.edu.cn")
client.login("学号", "密码")                       # 自动处理验证码 + AES 加密
schedule = client.get_schedule(2025, 2)             # 课表
grades = client.get_grades(2025, 2)                 # 成绩
exams = client.get_exams(2025, 2)                   # 考试
info = client.get_student_info()                    # 学籍
```

## 功能

| 方法 | 说明 | 返回类型 |
|------|------|---------|
| `client.login(username, password)` | 登录 | `None` |
| `client.get_schedule(xn, xq, week=None)` | 课表查询 | `List[Course]` |
| `client.get_grades(xn=None, xq=None)` | 成绩查询 | `List[Grade]` |
| `client.get_exams(xn, xq)` | 考试安排 | `List[Exam]` |
| `client.get_student_info()` | 学籍卡片 | `StudentInfo` |
| `client.save_session(path)` | 保存登录态 | `None` |
| `Client.from_session(path)` | 加载登录态 | `Client` |

## 数据模型

> 所有 SDK 属性均映射自教务系统原始 JSON/HTML 字段。详见 [docs/API.md](docs/API.md)。

### Course（课表）

| 属性 | 类型 | 教务字段 | 示例 |
|------|------|---------|------|
| `name` | `str` | `kcmc` | 大学英语(2) |
| `teacher` | `str` | `teaxms` | 小明 |
| `classroom` | `str` | `jxcdmc` | XXX教学楼203 |
| `start_time` | `str` | `qssj` | 08:15:00 |
| `end_time` | `str` | `jssj` | 09:50:00 |
| `weekday` | `int` | `jsxq` | 2 (1=周一 ... 7=周日) |
| `weeks` | `List[int]` | `zc` | [1,2,3,4,5,7,8,9,...] |
| `term_code` | `str` | `xnxqdm` | 202502 |
| `course_code` | `str` | `kcbh` | 0400012 |

### Grade（成绩）

| 属性 | 类型 | 教务字段 | 示例 |
|------|------|---------|------|
| `course_name` | `str` | `kcmc` | 高等数学 |
| `score` | `str` | `zcj` | 88 |
| `credit` | `float` | `xf` | 5.0 |
| `term` | `str` | `xnxqmc` | 2025-2026-2 |
| `department` | `str` | `kkbmmc` | XX学院 |
| `nature` | `str` | `xdfsmc` | 必修 |
| `course_code` | `str` | `kcbh` | 2120410020 |
| `student_name` | `str` | `xsxm` | 张三 |

### Exam（考试）

| 属性 | 类型 | 教务字段 | 示例 |
|------|------|---------|------|
| `course_name` | `str` | `kcmc` | 大学物理 |
| `date` | `str` | `ksrq` | 2026-07-06 |
| `time` | `str` | `kssj` | 15:00:00--17:00:00 |
| `classroom` | `str` | `kscdmc` | XXX教学楼201 |
| `exam_form` | `str` | `ksxsmc` | 闭卷 |
| `exam_type` | `str` | `khxsmc` | 笔试 |

### StudentInfo（学籍）

数据来自 welcome 页（`data-userbh`/`data-userxm`）+ edit.page 表单。

| 属性 | 类型 | 教务字段 | 示例 |
|------|------|---------|------|
| `student_id` | `str` | `data-userbh` | 2021000000 |
| `name` | `str` | `data-userxm` | 张三 |
| `id_number` | `str` | `sfzh` | 440000200001010001 |
| `phone` | `str` | `dh` | 13800000000 |
| `email` | `str` | `email` | example@qq.com |
| `home_address` | `str` | `jtdz` | XX省XX市... |
| `exam_number` | `str` | `ksh` | 25440000000000 |
| `previous_school` | `str` | `lyzx` | XX中学 |
| `enrollment_date` | `str` | `rxrq` | 20240901 |
| `pinyin_name` | `str` | `py` | Zhang San |
| `english_name` | `str` | `xsywxm` | Zhang San |

## Session 复用

```python
client.save_session("cookie.cache")
client = Client.from_session("cookie.cache")   # 免重新登录
```

## 验证码处理

默认使用 ddddocr 自动识别。如需手动输入回退：

```python
from wyu_jwxt import Client, ManualSolver

def my_callback(image_bytes):
    with open("captcha.jpg", "wb") as f:
        f.write(image_bytes)
    return input("请输入验证码: ").strip()

client = Client(manual_solver=ManualSolver(my_callback))
```

## 其他乘方学校兼容

```python
from wyu_jwxt import Client, SchoolConfig

class MySchool(SchoolConfig):
    base_url = "https://jwxt.other.edu.cn"
    # 接口路径或加密方式不同时在此 override

client = Client(config=MySchool())
```

## 异常

| 异常 | 触发条件 |
|------|---------|
| `LoginError` | 登录失败（密码错/验证码错/双因素触发） |
| `CaptchaError` | 验证码获取或识别失败 |
| `SessionExpiredError` | 未登录时调用数据接口 |
| `ChengfangError` | 基类，可统一捕获所有 SDK 异常 |

## 许可

MIT License

## 贡献

此 SDK 的接口协议全部逆向自五邑大学乘方教务系统实测。如果你所在学校也使用乘方教务，欢迎测试兼容性并提交 PR。
