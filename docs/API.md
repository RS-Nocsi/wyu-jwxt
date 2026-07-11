# wyu-jwxt API 参考

## Client

### `Client.__init__`

```python
Client(
    base_url: Optional[str] = None,
    *,
    config: Optional[SchoolConfig] = None,
    captcha_solver: Optional[CaptchaSolver] = None,
    manual_solver: Optional[CaptchaSolver] = None,
    max_login_retries: int = 5,
    timeout: float = 30,
    verify: bool = False,
)
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `base_url` | `str\|None` | `"https://jxgl.wyu.edu.cn"` | 教务系统地址 |
| `config` | `SchoolConfig\|None` | `SchoolConfig()` | 学校配置（与 base_url 二选一） |
| `captcha_solver` | `CaptchaSolver\|None` | `None` | 自定义验证码识别器 |
| `manual_solver` | `CaptchaSolver\|None` | `None` | OCR 失败时的回退验证码识别器 |
| `max_login_retries` | `int` | `5` | 登录最大重试次数 |
| `timeout` | `float` | `30` | HTTP 请求超时秒数 |
| `verify` | `bool` | `False` | 是否验证 SSL 证书 |

### `Client.login`

```python
client.login(username: str, password: str) -> None
```

登录教务系统。成功设置 `logged_in = True`。失败抛出异常。

**异常：**
- `LoginError` — 密码错误、验证码错误、双因素认证触发
- `CaptchaError` — 验证码获取失败

**重试逻辑：** 最多 `max_login_retries` 次。每次：获取验证码 → OCR/手动识别 → 加密 → POST 登录。验证码识别不准（非4字符）会重新取码，连续3次失败会提前终止。

### `Client.get_schedule`

```python
client.get_schedule(xn: int, xq: int, week: Optional[int] = None) -> List[Course]
```

获取课表。

| 参数 | 类型 | 说明 |
|------|------|------|
| `xn` | `int` | 学年起始年，如 2025 |
| `xq` | `int` | 学期，1 或 2 |
| `week` | `int\|None` | 指定周次，None 返回整学期 |

**异常：** `ChengfangError` — 接口返回错误

### `Client.get_grades`

```python
client.get_grades(xn: Optional[int] = None, xq: Optional[int] = None) -> List[Grade]
```

获取成绩。

| 参数 | 类型 | 说明 |
|------|------|------|
| `xn` | `int\|None` | 学年起始年，None 表示全部 |
| `xq` | `int\|None` | 学期，None 表示全部 |

**异常：** `ChengfangError` — 接口返回错误

### `Client.get_exams`

```python
client.get_exams(xn: int, xq: int) -> List[Exam]
```

获取考试安排。

**异常：** `ChengfangError` — 接口返回错误

### `Client.get_student_info`

```python
client.get_student_info() -> StudentInfo
```

获取学籍卡片信息。

**异常：** `ChengfangError` — welcome 页面格式变更导致无法提取学号/姓名

### `Client.save_session`

```python
client.save_session(path: str) -> None
```

将当前登录态（cookie + base_url）保存到磁盘 JSON 文件。

### `Client.from_session`

```python
Client.from_session(path: str, *, config: Optional[SchoolConfig] = None) -> Client
```

从磁盘加载登录态。

**异常：** `ChengfangError` — 文件不存在或损坏

---

## SchoolConfig

```python
@dataclass
class SchoolConfig:
    base_url: str = "https://jxgl.wyu.edu.cn"
    login_path: str = "/new/login"
    captcha_path: str = "/yzm"
    home_path: str = "/"
    schedule_page_path: str = "/new/student/xsgrkb/main.page"
    schedule_data_path: str = "/new/student/xsgrkb/getCalendarWeekDatas"
    grades_page_path: str = "/new/student/xskccj/main.page"
    grades_list_path: str = "/new/student/xskccj/kccjList.page"
    grades_data_path: str = "/new/student/xskccj/kccjDatas"
    exams_page_path: str = "/new/student/xsksrw/list.page"
    exams_data_path: str = "/new/student/xsksrw/paginateXsksrw"
    student_info_path: str = "/new/student/xjkpxx/edit.page"
    welcome_path: str = "/new/welcome.page"

    @property
    def password_encryptor(self) -> Callable[[str, str], str]: ...

    def term_code(self, xn: int, xq: int) -> str: ...
```

其他学校可通过继承 override 差异点。

---

## 验证码

### `CaptchaSolver`（抽象基类）

```python
class CaptchaSolver(ABC):
    @abstractmethod
    def solve(self, image_bytes: bytes) -> str: ...
```

### `OcrSolver`

```python
OcrSolver()   # 使用 ddddocr 自动识别
```

**依赖：** `pip install -e ".[ocr]"` 或 `pip install ddddocr`

### `ManualSolver`

```python
ManualSolver(callback: Callable[[bytes], Optional[str]])
```

- `callback(image_bytes)` 返回验证码字符串或 `None`（重新取码）
- `None` 会抛 `CaptchaError`

---

## 数据模型与字段映射

每个 SDK 属性的值均 1:1 对应教务系统原始 JSON/HTML 中的字段，无臆造。

### `Course`（课表）

数据源: `POST /new/student/xsgrkb/getCalendarWeekDatas` 返回 JSON

| SDK 属性 | 类型 | 教务原始字段 | 说明 |
|----------|------|-------------|------|
| `name` | `str` | `kcmc` | 课程名称 |
| `teacher` | `str` | `teaxms` | 任课教师 |
| `classroom` | `str` | `jxcdmc` | 教室名称 |
| `start_time` | `str` | `qssj` | 开始时间 |
| `end_time` | `str` | `jssj` | 结束时间 |
| `weekday` | `int` | `jsxq` | 星期几 (1=周一 ... 7=周日) |
| `weeks` | `List[int]` | `zc` | 上课周次列表（逗号分隔→int list） |
| `term_code` | `str` | `xnxqdm` | 学年学期代码 |
| `course_code` | `str` | `kcbh` | 课程编号 |

> 教务接口返回约 40 个字段，以上 9 个为核心字段。其余为教务系统内部字段（如 `islock`/`pkrdm`/`rownum_` 等），对学生无意义，按 YAGNI 原则不予暴露。

### `Grade`（成绩）

数据源: `POST /new/student/xskccj/kccjDatas` 返回 JSON

| SDK 属性 | 类型 | 教务原始字段 | 说明 |
|----------|------|-------------|------|
| `course_name` | `str` | `kcmc` | 课程名称 |
| `score` | `str` | `zcj` | 总成绩 |
| `credit` | `float` | `xf` | 学分 |
| `term` | `str` | `xnxqmc` | 学年学期名称 |
| `department` | `str` | `kkbmmc` | 开课学院 |
| `nature` | `str` | `xdfsmc` | 课程性质（必修/选修/任选） |
| `course_code` | `str` | `kcbh` | 课程编号 |
| `student_name` | `str` | `xsxm` | 学生姓名 |

> 教务接口返回约 39 个字段，以上 8 个为核心字段。

### `Exam`（考试）

数据源: `POST /new/student/xsksrw/paginateXsksrw` 返回 JSON

| SDK 属性 | 类型 | 教务原始字段 | 说明 |
|----------|------|-------------|------|
| `course_name` | `str` | `kcmc` | 课程名称 |
| `date` | `str` | `ksrq` | 考试日期 |
| `time` | `str` | `kssj` | 考试时间（格式 HH:MM:SS--HH:MM:SS） |
| `classroom` | `str` | `kscdmc` | 考场名称 |
| `exam_form` | `str` | `ksxsmc` | 考试形式（开卷/闭卷） |
| `exam_type` | `str` | `khxsmc` | 考试类型（笔试/机试/其它） |

> 教务接口返回约 27 个字段，以上 6 个为核心字段。

### `StudentInfo`（学籍）

数据源: 
- `GET /new/welcome.page` — `data-userbh`（学号）、`data-userxm`（姓名）
- `GET /new/student/xjkpxx/edit.page` — HTML 表单 input 字段

| SDK 属性 | 类型 | 教务原始字段 | 说明 |
|----------|------|-------------|------|
| `student_id` | `str` | welcome 页 `data-userbh` 属性 | 学号 |
| `name` | `str` | welcome 页 `data-userxm` 属性 | 学生姓名 |
| `id_number` | `str` | edit.page `sfzh` | 身份证号 |
| `phone` | `str` | edit.page `dh` | 手机号码 |
| `email` | `str` | edit.page `email` | 邮箱地址 |
| `home_address` | `str` | edit.page `jtdz` | 家庭地址 |
| `exam_number` | `str` | edit.page `ksh` | 考生号 |
| `previous_school` | `str` | edit.page `lyzx` | 毕业中学 |
| `enrollment_date` | `str` | edit.page `rxrq` | 入学日期 |
| `pinyin_name` | `str` | edit.page `py` | 拼音名 |
| `english_name` | `str` | edit.page `xsywxm` | 英文名 |

> 表单共 27 个字段，以上 9 个 + welcome 页 2 个为核心字段。

---

## 异常

```
ChengfangError          ← 所有 SDK 异常的基类
├── LoginError           ← 登录失败
├── CaptchaError         ← 验证码获取/识别失败
└── SessionExpiredError  ← 未登录时调用数据接口
```

所有异常都继承自 `ChengfangError(Exception)`，可统一捕获。
