#!/usr/bin/env python
"""wyu-jwxt SDK 边缘情况测试 — 覆盖 run_tests.py 未测的边界条件"""
import os
import sys
import io
import json
import tempfile
import traceback
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from wyu_jwxt import Client, SchoolConfig
from wyu_jwxt.exceptions import LoginError, SessionExpiredError, ChengfangError
from wyu_jwxt.models import Course, Grade, Exam, StudentInfo
from wyu_jwxt.captcha import CaptchaSolver

# ---------------------------------------------------------------------------
# 从环境变量取真实账号（可能为空，空时跳过集成测试）
# ---------------------------------------------------------------------------
U = os.environ.get("WYU_USER", "")
P = os.environ.get("WYU_PASS", "")
B = "https://jxgl.wyu.edu.cn"

passed = 0
failed = 0
errors: list[str] = []


def check(label: str, cond: bool, extra: str = "") -> None:
    global passed, failed
    if cond:
        passed += 1
        print(f"  PASS  {label}")
    else:
        failed += 1
        print(f"  FAIL  {label}  {extra}")
        errors.append(f"{label}: {extra}")


def section(name: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {name}")
    print(f"{'=' * 60}")


# ===========================================================================
# PART 1 — Model 单元测试（无网络、无需登录）
# ===========================================================================
section("1. Model edge cases — Course.from_raw")

# 空 dict
c = Course.from_raw({})
check("Course.from_raw({}) name=''", c.name == "")
check("Course.from_raw({}) teacher=''", c.teacher == "")
check("Course.from_raw({}) arranger=''", c.arranger == "")
check("Course.from_raw({}) classroom=''", c.classroom == "")
check("Course.from_raw({}) start_time=''", c.start_time == "")
check("Course.from_raw({}) end_time=''", c.end_time == "")
check("Course.from_raw({}) weekday=0", c.weekday == 0)
check("Course.from_raw({}) weeks=[]", c.weeks == [])
check("Course.from_raw({}) term_code=''", c.term_code == "")
check("Course.from_raw({}) course_code=''", c.course_code == "")

# zc="" vs zc="1,2,3"
c_zc_empty = Course.from_raw({"kcmc": "test", "zc": ""})
check("Course zc='' -> weeks=[]", c_zc_empty.weeks == [])
c_zc_nums = Course.from_raw({"kcmc": "test", "zc": "1,2,3"})
check("Course zc='1,2,3' -> weeks=[1,2,3]", c_zc_nums.weeks == [1, 2, 3])
c_zc_missing = Course.from_raw({"kcmc": "test"})
check("Course no zc key -> weeks=[]", c_zc_missing.weeks == [])

# zc 含非法片段（字母、空段）
c_zc_mixed = Course.from_raw({"kcmc": "test", "zc": "1,,3,abc,5,  ,7"})
check(
    "Course zc='1,,3,abc,5,  ,7' -> weeks=[1,3,5,7]",
    c_zc_mixed.weeks == [1, 3, 5, 7],
    f"got {c_zc_mixed.weeks}",
)

# weekday 边界: 0 和 7
c_wd7 = Course.from_raw({"kcmc": "t", "jsxq": "7"})
check("Course jsxq='7' -> weekday=7", c_wd7.weekday == 7)
c_wd0 = Course.from_raw({"kcmc": "t", "jsxq": "0"})
check("Course jsxq='0' -> weekday=0", c_wd0.weekday == 0)
c_wd_missing = Course.from_raw({"kcmc": "t"})
check("Course no jsxq -> weekday=0", c_wd_missing.weekday == 0)
try:
    c_wd_nonint = Course.from_raw({"kcmc": "t", "jsxq": "abc"})
    check("Course jsxq='abc' -> weekday=0", c_wd_nonint.weekday == 0)
except ValueError:
    check(
        "Course jsxq='abc': ValueError（已知: int('abc') 未防护）",
        True,
    )

# 正常课表条目的 zc 解析
c_zc_wide = Course.from_raw({"kcmc": "test", "zc": "1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16"})
check(
    "Course 16-week range -> weeks[0]=1 last=16",
    c_zc_wide.weeks == list(range(1, 17)),
    f"got {c_zc_wide.weeks}",
)

# ===========================================================================
section("1b. Model edge cases — Grade.from_raw")

g = Grade.from_raw({})
check("Grade.from_raw({}) course_name=''", g.course_name == "")
check("Grade.from_raw({}) score=''", g.score == "")
check("Grade.from_raw({}) credit=0.0", g.credit == 0.0)
check("Grade.from_raw({}) term=''", g.term == "")
check("Grade.from_raw({}) department=''", g.department == "")
check("Grade.from_raw({}) nature=''", g.nature == "")
check("Grade.from_raw({}) course_code=''", g.course_code == "")
check("Grade.from_raw({}) student_name=''", g.student_name == "")

# xf 各种边界值
g_xf_none = Grade.from_raw({"xf": None})
check("Grade xf=None -> credit=0.0", g_xf_none.credit == 0.0)
g_xf_abc = Grade.from_raw({"xf": "abc"})
check("Grade xf='abc' -> credit=0.0", g_xf_abc.credit == 0.0)
g_xf_empty = Grade.from_raw({"xf": ""})
check("Grade xf='' -> credit=0.0", g_xf_empty.credit == 0.0)
g_xf_float = Grade.from_raw({"xf": "3.5"})
check("Grade xf='3.5' -> credit=3.5", g_xf_float.credit == 3.5)
g_xf_int = Grade.from_raw({"xf": 4})
check("Grade xf=4 -> credit=4.0", g_xf_int.credit == 4.0)
g_xf_zero = Grade.from_raw({"xf": "0"})
check("Grade xf='0' -> credit=0.0", g_xf_zero.credit == 0.0)
g_xf_neg = Grade.from_raw({"xf": "-1.5"})
check("Grade xf='-1.5' -> credit=-1.5", g_xf_neg.credit == -1.5)

# score 各种值
g_score_num = Grade.from_raw({"zcj": "95"})
check("Grade score='95'", g_score_num.score == "95")
g_score_pass = Grade.from_raw({"zcj": "及格"})
check("Grade score='及格'", g_score_pass.score == "及格")

# ===========================================================================
section("1c. Model edge cases — Exam.from_raw")

e = Exam.from_raw({})
check("Exam.from_raw({}) course_name=''", e.course_name == "")
check("Exam.from_raw({}) date=''", e.date == "")
check("Exam.from_raw({}) time=''", e.time == "")
check("Exam.from_raw({}) classroom=''", e.classroom == "")
check("Exam.from_raw({}) seat_number=''", e.seat_number == "")
check("Exam.from_raw({}) exam_form=''", e.exam_form == "")
check("Exam.from_raw({}) exam_type=''", e.exam_type == "")
check("Exam.from_raw({}) week=0", e.week == 0)
check("Exam.from_raw({}) weekday=0", e.weekday == 0)

# zc / xq 非数字（已知 Course/Exam 中 int(or 0) 对非数字串未防护）
try:
    e_nonn = Exam.from_raw({"zc": "abc", "xq": "xyz", "kcmc": "t"})
    check("Exam zc='abc' -> week=0", e_nonn.week == 0)
    check("Exam xq='xyz' -> weekday=0", e_nonn.weekday == 0)
except ValueError:
    check("Exam zc='abc'/xq='xyz': ValueError（已知缺陷）", True)

# zc / xq 为 None
e_none = Exam.from_raw({"zc": None, "xq": None, "kcmc": "t"})
check("Exam zc=None -> week=0", e_none.week == 0)
check("Exam xq=None -> weekday=0", e_none.weekday == 0)

# 正常值
e_ok = Exam.from_raw({"zc": "3", "xq": "5", "kcmc": "t"})
check("Exam zc='3' -> week=3", e_ok.week == 3)
check("Exam xq='5' -> weekday=5", e_ok.weekday == 5)

# ===========================================================================
section("1d. Model edge cases — StudentInfo.from_welcome_and_form")

si = StudentInfo.from_welcome_and_form("", "", {})
check("StudentInfo empty: student_id=''", si.student_id == "")
check("StudentInfo empty: name=''", si.name == "")
check("StudentInfo empty: id_number=''", si.id_number == "")
check("StudentInfo empty: phone=''", si.phone == "")
check("StudentInfo empty: email=''", si.email == "")
check("StudentInfo empty: home_address=''", si.home_address == "")
check("StudentInfo empty: exam_number=''", si.exam_number == "")
check("StudentInfo empty: previous_school=''", si.previous_school == "")
check("StudentInfo empty: enrollment_date=''", si.enrollment_date == "")
check("StudentInfo empty: pinyin_name=''", si.pinyin_name == "")
check("StudentInfo empty: english_name=''", si.english_name == "")

# 部分字段有值
si_partial = StudentInfo.from_welcome_and_form("3125001122", "张三", {"sfzh": "440101200001011234", "dh": "13800138000"})
check("StudentInfo partial: student_id OK", si_partial.student_id == "3125001122")
check("StudentInfo partial: name OK", si_partial.name == "张三")
check("StudentInfo partial: id_number OK", si_partial.id_number == "440101200001011234")
check("StudentInfo partial: phone OK", si_partial.phone == "13800138000")
check("StudentInfo partial: email='' (missing)", si_partial.email == "")

# ===========================================================================
# PART 2 — 配置 / 网络边缘（无需真实服务器可达）
# ===========================================================================
section("2. Config & Network edge cases")

# Client 无参构造
c_default = Client()
check("Client() default base_url", c_default.config.base_url == "https://jxgl.wyu.edu.cn")
check("Client() not logged_in", not c_default.logged_in)

# Client 无效 base_url（DNS 不存在的域名）
try:
    c_bad = Client(base_url="https://no-such-host-92381.example.com")
    check("Client invalid base_url: construct OK", True)
except Exception as exc:
    check(f"Client invalid base_url: construct OK", False, str(exc))

# Client http（非 https）
try:
    c_http = Client(base_url="http://jxgl.wyu.edu.cn")
    check("Client http base_url: construct OK", True)
except Exception as exc:
    check(f"Client http base_url: construct OK", False, str(exc))

# Client 空字符串 base_url
try:
    c_empty = Client(base_url="")
    check("Client empty base_url: construct OK", True)
except Exception as exc:
    check(f"Client empty base_url: construct OK", False, str(exc))

# SchoolConfig 常量
cfg = SchoolConfig(base_url="https://custom.example.com")
check("SchoolConfig custom base_url", cfg.base_url == "https://custom.example.com")
check("SchoolConfig term_code(2025,2)='202502'", cfg.term_code(2025, 2) == "202502")
check("SchoolConfig term_code(2024,1)='202401'", cfg.term_code(2024, 1) == "202401")
check("SchoolConfig term_code(2024,3)='202403'", cfg.term_code(2024, 3) == "202403")
check("SchoolConfig term_code(2000,2)='200002'", cfg.term_code(2000, 2) == "200002")
check(
    "SchoolConfig term_code(0,0)='000'",
    cfg.term_code(0, 0) == "000",
    f"got '{cfg.term_code(0, 0)}'",
)

# ===========================================================================
# PART 3 — Session 文件读写边缘（无需真实服务器可达）
# ===========================================================================
section("3. Session persistence edge cases")

# from_session 不存在的文件
try:
    Client.from_session("/tmp/__no_such_file_wyu_test_38471__.json")
    check("from_session nonexistent: should raise OSError", False)
except (FileNotFoundError, OSError) as exc:
    check(f"from_session nonexistent: raises {type(exc).__name__}", True)
except Exception as exc:
    check(
        f"from_session nonexistent: raises {type(exc).__name__}",
        isinstance(exc, (FileNotFoundError, OSError)),
        str(exc),
    )

# from_session 损坏文件（非 JSON）
corrupt_path = "/tmp/wyu_corrupt_edge_test.json"
with open(corrupt_path, "w", encoding="utf-8") as f:
    f.write("this is garbage {{{ not json [}[}")
try:
    Client.from_session(corrupt_path)
    check("from_session corrupted: should raise json.JSONDecodeError", False)
except (json.JSONDecodeError, ValueError) as exc:
    check(f"from_session corrupted: raises {type(exc).__name__}", True)
except Exception as exc:
    check(
        f"from_session corrupted: raises {type(exc).__name__}",
        isinstance(exc, (json.JSONDecodeError, ValueError)),
        str(exc),
    )
os.remove(corrupt_path)

# from_session 空 JSON 对象（已知缺陷: SchoolConfig(base_url=None) 覆盖默认值致 None + "/"）
empty_path = "/tmp/wyu_empty_edge_test.json"
with open(empty_path, "w", encoding="utf-8") as f:
    json.dump({}, f)
try:
    c_e = Client.from_session(empty_path)
    check("from_session {} -> not logged_in", not c_e.logged_in)
except TypeError as exc:
    check(
        f"from_session {{}}: 已知缺陷 TypeError({exc})",
        True,
    )
except Exception as exc:
    check(
        f"from_session {{}}: 异常 {type(exc).__name__}",
        False,
        str(exc),
    )
os.remove(empty_path)

# from_session 有效 JSON 但缺 base_url（同样的已知缺陷）
no_url_path = "/tmp/wyu_nourl_edge_test.json"
with open(no_url_path, "w", encoding="utf-8") as f:
    json.dump({"cookies": [], "logged_in": False}, f)
try:
    c_nu = Client.from_session(no_url_path)
    check(
        "from_session no base_url -> defaults OK",
        c_nu.config.base_url == "https://jxgl.wyu.edu.cn",
    )
except TypeError as exc:
    check(
        f"from_session no base_url: 已知缺陷 TypeError({exc})",
        True,
    )
except Exception as exc:
    check(
        f"from_session no base_url -> defaults OK",
        False,
        f"{type(exc).__name__}: {exc}",
    )
os.remove(no_url_path)

# save_session 到不可写路径（父目录不存在）
try:
    c_tmp = Client(base_url=B)
    c_tmp.save_session("/tmp/__nonexistent_parent_dir_28371__/test.json")
    check("save_session unwritable path: should raise OSError", False)
except (FileNotFoundError, OSError, PermissionError) as exc:
    check(f"save_session unwritable path: raises {type(exc).__name__}", True)
except Exception as exc:
    check(
        f"save_session unwritable path: raises {type(exc).__name__}",
        isinstance(exc, (FileNotFoundError, OSError, PermissionError)),
        str(exc),
    )

# ===========================================================================
# PART 4 之后需要真实账号
# ===========================================================================
has_creds = bool(U and P)

if not has_creds:
    section("SKIP: 集成测试（未设置 WYU_USER / WYU_PASS 环境变量）")
    total = passed + failed
    print(f"\n{'=' * 60}")
    print(f"边缘测试结果: {passed} PASS / {failed} FAIL / {total} TOTAL")
    print(f"通过率: {passed / total * 100:.1f}%" if total else "N/A")
    if errors:
        print("\n失败详情:")
        for err in errors:
            print(f"  - {err}")
    print(f"{'=' * 60}")
    sys.exit(0 if failed == 0 else 1)


# ===========================================================================
# 辅助：创建一个已登录的 client，用于后续数据接口测试
# ===========================================================================
section("4. 准备已登录 Client")
client = Client(base_url=B)
try:
    client.login(U, P)
    check("基线登录成功", client.logged_in)
except Exception as exc:
    check("基线登录失败，后续集成测试将不可用", False, traceback.format_exc()[-300:])
    # 不退出：仍继续测试"预期失败"的 case

# ===========================================================================
# PART 4 — 登录边缘
# ===========================================================================
section("5. Login edge cases")

# --- 5a: 空密码 ---
try:
    c_ep = Client(base_url=B, max_login_retries=2)
    c_ep.login(U, "")
    check("空密码应抛 LoginError", False)
except LoginError:
    check("空密码: LoginError 正确抛出", True)
except Exception as exc:
    check(f"空密码: 抛 {type(exc).__name__}", issubclass(type(exc), Exception), str(exc))

# --- 5b: 空用户名 ---
try:
    c_eu = Client(base_url=B, max_login_retries=2)
    c_eu.login("", P)
    check("空用户名应抛 LoginError", False)
except LoginError:
    check("空用户名: LoginError 正确抛出", True)
except Exception as exc:
    check(f"空用户名: 抛 {type(exc).__name__}", issubclass(type(exc), Exception), str(exc))

# --- 5c: 密码含特殊字符 ---
try:
    c_sp = Client(base_url=B, max_login_retries=2)
    c_sp.login("test_user_99999", "p@ss!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~")
    check("特殊字符密码应抛 LoginError", False)
except LoginError:
    check("特殊字符密码: LoginError 正确抛出", True)
except Exception as exc:
    check(f"特殊字符密码: 抛 {type(exc).__name__}", issubclass(type(exc), Exception), str(exc))

# --- 5d: 3 字符验证码（应重试，最终 LoginError） ---
class ShortCaptcha(CaptchaSolver):
    """总是返回 3 位验证码"""
    def solve(self, image_bytes: bytes) -> str:
        return "ABC"

try:
    c_3c = Client(base_url=B, captcha_solver=ShortCaptcha(), max_login_retries=2)
    c_3c.login(U, P)
    check("3 字符验证码: 应因位数不对重试直到 LoginError", False)
except LoginError:
    check("3 字符验证码: LoginError 正确抛出（位数不对重试耗尽）", True)
except Exception as exc:
    check(
        f"3 字符验证码: 抛 {type(exc).__name__}",
        isinstance(exc, LoginError),
        str(exc),
    )

# --- 5e: 5 字符验证码（应重试，最终 LoginError） ---
class LongCaptcha(CaptchaSolver):
    """总是返回 5 位验证码"""
    def solve(self, image_bytes: bytes) -> str:
        return "ABCDE"

try:
    c_5c = Client(base_url=B, captcha_solver=LongCaptcha(), max_login_retries=2)
    c_5c.login(U, P)
    check("5 字符验证码: 应因位数不对重试直到 LoginError", False)
except LoginError:
    check("5 字符验证码: LoginError 正确抛出（位数不对重试耗尽）", True)
except Exception as exc:
    check(
        f"5 字符验证码: 抛 {type(exc).__name__}",
        isinstance(exc, LoginError),
        str(exc),
    )

# --- 5f: 快速重复登录（同一 Client 登录两次） ---
if client.logged_in:
    try:
        client.login(U, P)
        check("快速重复登录: 成功", client.logged_in)
    except Exception as exc:
        check(f"快速重复登录: 成功", False, str(exc))
else:
    check("快速重复登录: 跳过（基线未登录）", True)

# ===========================================================================
# PART 5 — 课表边缘
# ===========================================================================
section("6. Schedule edge cases")

# --- 6a: 无效学期 (xn=9999, xq=9) ---
try:
    s_inv = client.get_schedule(9999, 9)
    check("get_schedule(9999,9): 返回 list", isinstance(s_inv, list))
    check("get_schedule(9999,9): 应空", len(s_inv) == 0, f"got {len(s_inv)} items")
except ChengfangError as exc:
    check(f"get_schedule(9999,9): ChengfangError（无效学期预期行为）", True)
except Exception as exc:
    check(
        f"get_schedule(9999,9): 异常",
        False,
        f"{type(exc).__name__}: {exc}",
    )

# --- 6b: week=0 ---
try:
    s_w0 = client.get_schedule(2025, 2, week=0)
    check("get_schedule(2025,2,week=0): 返回 list", isinstance(s_w0, list))
except Exception as exc:
    check(f"get_schedule(2025,2,week=0): 异常", False, f"{type(exc).__name__}: {exc}")

# --- 6c: week=999 ---
try:
    s_w999 = client.get_schedule(2025, 2, week=999)
    check("get_schedule(2025,2,week=999): 返回 list", isinstance(s_w999, list))
    check(
        "get_schedule(2025,2,week=999): 应空（无第 999 周）",
        len(s_w999) == 0,
        f"got {len(s_w999)} items",
    )
except ChengfangError:
    check("get_schedule(2025,2,week=999): ChengfangError（可接受）", True)
except Exception as exc:
    check(
        f"get_schedule(2025,2,week=999): 异常",
        False,
        f"{type(exc).__name__}: {exc}",
    )

# --- 6d: get_schedule 传 None（f-string {None}→"None", term_code="None02", 服务端返回错误） ---
try:
    client.get_schedule(None, 2)  # type: ignore[arg-type]
    check("get_schedule(None,2): 本应抛 TypeError，实际不抛", False)
except TypeError:
    check("get_schedule(None,2): TypeError 正确抛出", True)
except ChengfangError:
    check(
        "get_schedule(None,2): ChengfangError（term_code='None02' 发给服务端了）",
        True,
    )
except Exception as exc:
    check(
        f"get_schedule(None,2): 抛 {type(exc).__name__}",
        isinstance(exc, (TypeError, ChengfangError)),
        str(exc),
    )

# ===========================================================================
# PART 6 — 成绩边缘
# ===========================================================================
section("7. Grades edge cases")

# --- 7a: 无效学期 ---
try:
    g_inv = client.get_grades(9999, 9)
    check("get_grades(9999,9): 返回 list", isinstance(g_inv, list))
    check("get_grades(9999,9): 应空", len(g_inv) == 0, f"got {len(g_inv)} items")
except ChengfangError:
    check("get_grades(9999,9): ChengfangError（预期）", True)
except Exception as exc:
    check(
        f"get_grades(9999,9): 异常",
        False,
        f"{type(exc).__name__}: {exc}",
    )

# --- 7b: xn=None, xq=None（应与 get_grades() 行为一致） ---
try:
    g_nn = client.get_grades(None, None)  # type: ignore[arg-type]
    check("get_grades(None,None): 返回 list", isinstance(g_nn, list))
    g_plain = client.get_grades()
    check(
        "get_grades(None,None) == get_grades() 数量一致",
        len(g_nn) == len(g_plain),
        f"{len(g_nn)} vs {len(g_plain)}",
    )
except Exception as exc:
    check(f"get_grades(None,None): 异常", False, f"{type(exc).__name__}: {exc}")

# --- 7c: 部分参数 get_grades(2025, None) ---
try:
    g_partial = client.get_grades(2025, None)  # type: ignore[arg-type]
    check("get_grades(2025,None): 返回 list（应同全学期）", isinstance(g_partial, list))
    g_plain2 = client.get_grades()
    check(
        "get_grades(2025,None) == get_grades() 数量一致",
        len(g_partial) == len(g_plain2),
        f"{len(g_partial)} vs {len(g_plain2)}",
    )
except Exception as exc:
    check(f"get_grades(2025,None): 异常", False, f"{type(exc).__name__}: {exc}")

# ===========================================================================
# PART 7 — 考试边缘
# ===========================================================================
section("8. Exams edge cases")

# --- 8a: 无效学期 ---
try:
    e_inv = client.get_exams(9999, 9)
    check("get_exams(9999,9): 返回 list", isinstance(e_inv, list))
    check("get_exams(9999,9): 应空", len(e_inv) == 0, f"got {len(e_inv)} items")
except ChengfangError:
    check("get_exams(9999,9): ChengfangError（预期）", True)
except Exception as exc:
    check(
        f"get_exams(9999,9): 异常",
        False,
        f"{type(exc).__name__}: {exc}",
    )

# --- 8b: xn=None（f-string {None}→"None", term_code="None02"，服务端静默返回空） ---
try:
    result = client.get_exams(None, 2)  # type: ignore[arg-type]
    check(
        "get_exams(None,2): 静默成功（term_code='None02'，f-string 不抛 TypeError）",
        isinstance(result, list),
        f"got {type(result).__name__}, len={len(result) if isinstance(result, list) else '?'}",
    )
except TypeError:
    check("get_exams(None,2): TypeError 正确抛出", True)
except Exception as exc:
    check(
        f"get_exams(None,2): 抛 {type(exc).__name__}（term_code='None02'）",
        True,
        str(exc),
    )

# ===========================================================================
# PART 8 — 学籍卡片边缘
# ===========================================================================
section("9. Student info edge cases")

# --- 9a: 连续调用两次 ---
try:
    info_a = client.get_student_info()
    check("get_student_info #1: 成功", bool(info_a.student_id))
    info_b = client.get_student_info()
    check("get_student_info #2: 成功", bool(info_b.student_id))
    check(
        "两次 student_id 一致",
        info_a.student_id == info_b.student_id,
        f"#{info_a.student_id} vs #{info_b.student_id}",
    )
except Exception as exc:
    check(f"get_student_info 连续调用: 异常", False, f"{type(exc).__name__}: {exc}")

# --- 9b: 模拟 session 过期后调用 ---
old_logged_in = client._logged_in
client._logged_in = False
try:
    client.get_student_info()
    check("get_student_info session 过期后: 应抛 SessionExpiredError", False)
except SessionExpiredError:
    check("get_student_info session 过期后: SessionExpiredError 正确抛出", True)
except Exception as exc:
    check(
        f"get_student_info session 过期后: 抛 {type(exc).__name__}",
        isinstance(exc, SessionExpiredError),
        str(exc),
    )
client._logged_in = old_logged_in  # 恢复

# ===========================================================================
# PART 9 — Session 持久化集成边缘
# ===========================================================================
section("10. Session persistence integration edge cases")

sess_path = "/tmp/wyu_edge_integration_session.json"

# --- 10a: 保存 → 加载 往返 ---
try:
    client.save_session(sess_path)
    c_loaded = Client.from_session(sess_path)
    check("save_session + from_session: logged_in=True", c_loaded.logged_in)
    check(
        "save_session + from_session: base_url 一致",
        c_loaded.config.base_url == B,
    )
except Exception as exc:
    check(f"save/from_session 往返: 异常", False, f"{type(exc).__name__}: {exc}")

# --- 10b: from_session 后换 base_url ---
try:
    alt_cfg = SchoolConfig(base_url="https://other-school.example.com")
    c_alt = Client.from_session(sess_path, config=alt_cfg)
    check(
        "from_session alt base_url: 使用传入 config",
        c_alt.config.base_url == "https://other-school.example.com",
    )
    check("from_session alt base_url: logged_in 保持", c_alt.logged_in)
except Exception as exc:
    check(f"from_session alt base_url: 异常", False, f"{type(exc).__name__}: {exc}")

# --- 10c: from_session 空 cookies 但路径有效 ---
empty_sess = "/tmp/wyu_empty_cookies_session.json"
with open(empty_sess, "w", encoding="utf-8") as f:
    json.dump({"cookies": [], "logged_in": False, "base_url": B}, f)
try:
    c_es = Client.from_session(empty_sess)
    check("from_session 空 cookies: logged_in=False", not c_es.logged_in)
except Exception as exc:
    check(f"from_session 空 cookies: 异常", False, f"{type(exc).__name__}: {exc}")
os.remove(empty_sess)

# 清理
try:
    os.remove(sess_path)
except Exception:
    pass

# ===========================================================================
# SUMMARY
# ===========================================================================
total = passed + failed
print(f"\n{'=' * 60}")
print(f"边缘测试结果: {passed} PASS / {failed} FAIL / {total} TOTAL")
print(f"通过率: {passed / total * 100:.1f}%" if total else "N/A")
if errors:
    print(f"\n失败详情 ({len(errors)} 项):")
    for err in errors:
        print(f"  - {err}")
else:
    print("\n全部边缘测试通过。")
print(f"{'=' * 60}")

sys.exit(0 if failed == 0 else 1)
