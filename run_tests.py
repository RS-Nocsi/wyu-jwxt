#!/usr/bin/env python
"""wyu-jwxt SDK 全流程无死角测试"""
import os, sys, io, time, traceback
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from wyu_jwxt import Client
from wyu_jwxt.exceptions import LoginError

U = os.environ["WYU_USER"]
P = os.environ["WYU_PASS"]
B = "https://jxgl.wyu.edu.cn"

passed = 0
failed = 0
errors = []


def check(label, cond, extra=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  PASS  {label}")
    else:
        failed += 1
        print(f"  FAIL  {label}  {extra}")
        errors.append(f"{label}: {extra}")


print("=" * 60)
print("wyu-jwxt SDK 全流程无死角测试")
print("=" * 60)

# ============================================================
# 1. 登录
# ============================================================
print("\n[1] 登录")
t0 = time.time()
client = Client(base_url=B)
client.login(U, P)
check(f"登录成功 ({round(time.time() - t0, 1)}s)", client.logged_in)

# ============================================================
# 2. 错误密码应抛 LoginError
# ============================================================
print("\n[2] 错误密码")
try:
    c2 = Client(base_url=B)
    c2.login("0000000000", "wrongpassword")
    check("应抛 LoginError", False)
except LoginError:
    check("正确抛 LoginError", True)
except Exception as e:
    check("应抛 LoginError", False, f"got {type(e).__name__}: {e}")

# ============================================================
# 3. Session 持久化
# ============================================================
print("\n[3] Session 持久化")
client.save_session("/tmp/wyu_test_cache.json")
c3 = Client.from_session("/tmp/wyu_test_cache.json")
check("save_session 成功", True)
check("from_session logged_in=True", c3.logged_in)

# ============================================================
# 4. 课表 — 两个学期
# ============================================================
for term_name, xn, xq, min_count in [
    ("2025-2026-2", 2025, 2, 15),
    ("2025-2026-1", 2025, 1, 5),
]:
    print(f"\n[4] 课表 {term_name}")
    try:
        s = client.get_schedule(xn, xq)
        check(f"条目 >= {min_count}", len(s) >= min_count, f"got {len(s)}")
        names = {c.name for c in s}
        check(f"去重课程 >= 5", len(names) >= 5, f"got {len(names)}")

        # 抽查前 3 条课程的字段完整性
        for i, c in enumerate(s[:3]):
            check(f"  [{i}] name={c.name[:20]}", bool(c.name))
            check(f"  [{i}] teacher={c.teacher}", bool(c.teacher))
            check(f"  [{i}] classroom={c.classroom}", bool(c.classroom))
            check(f"  [{i}] start_time={c.start_time}", bool(c.start_time))
            check(f"  [{i}] end_time={c.end_time}", bool(c.end_time))
            check(f"  [{i}] weekday={c.weekday}", 1 <= c.weekday <= 7, f"got {c.weekday}")
            check(f"  [{i}] weeks 非空", len(c.weeks) >= 1, f"got {c.weeks}")
            check(f"  [{i}] term_code={c.term_code}", c.term_code == f"{xn}{xq:02d}")
            check(f"  [{i}] course_code={c.course_code}", bool(c.course_code))

        # week=1 过滤测试
        s1 = client.get_schedule(xn, xq, week=1)
        if s1:
            check(
                f"  week=1 全部含周 1",
                all(1 in c.weeks for c in s1),
                f"filtered to {len(s1)} courses",
            )

        # 课程名中不应全是一个老师（验证 teacher 映射正确）
        teachers = {c.teacher for c in s}
        check(
            f"  教师不全是同一个人 (got {len(teachers)} unique)",
            len(teachers) >= 2,
            f"all teachers: {teachers}",
        )

    except Exception as e:
        check(f"课表异常: {e}", False, traceback.format_exc()[-300:])

# ============================================================
# 5. 成绩 — 两个学期
# ============================================================
for term_name, xn, xq, min_count in [
    ("2025-2026-2", 2025, 2, 5),
    ("2025-2026-1", 2025, 1, 5),
]:
    print(f"\n[5] 成绩 {term_name}")
    try:
        g = client.get_grades(xn, xq)
        check(f"条目 >= {min_count}", len(g) >= min_count, f"got {len(g)}")
        for i, grade in enumerate(g[:3]):
            check(f"  [{i}] course_name={grade.course_name}", bool(grade.course_name))
            check(f"  [{i}] score={grade.score}", bool(grade.score) or grade.score == "0")
            check(f"  [{i}] credit={grade.credit}", grade.credit >= 0)
            check(f"  [{i}] term={grade.term}", bool(grade.term))
            check(f"  [{i}] department={grade.department}", bool(grade.department))
            check(f"  [{i}] nature={grade.nature}", bool(grade.nature))
            check(f"  [{i}] course_code={grade.course_code}", bool(grade.course_code))
            check(f"  [{i}] student_name={grade.student_name}", bool(grade.student_name))
    except Exception as e:
        check(f"成绩异常: {e}", False, traceback.format_exc()[-300:])

# ============================================================
# 6. 成绩 — 全部学期
# ============================================================
print("\n[6] 成绩 全部学期")
try:
    g_all = client.get_grades()
    check(f"条目 >= 10", len(g_all) >= 10, f"got {len(g_all)}")
    terms = {g.term for g in g_all}
    check(f"跨学期 >= 2", len(terms) >= 2, f"got {terms}")
except Exception as e:
    check(f"全学期异常: {e}", False)

# ============================================================
# 7. 考试 — 两个学期
# ============================================================
for term_name, xn, xq in [
    ("2025-2026-2", 2025, 2),
    ("2025-2026-1", 2025, 1),
]:
    print(f"\n[7] 考试 {term_name}")
    try:
        e = client.get_exams(xn, xq)
        check(f"可获取(get_exams返回list)", isinstance(e, list), f"got {len(e)} items")
        for i, exam in enumerate(e[:3]):
            check(f"  [{i}] course_name={exam.course_name}", bool(exam.course_name))
            check(f"  [{i}] date={exam.date}", "-" in exam.date or bool(exam.date))
            check(f"  [{i}] time={exam.time}", "--" in exam.time or bool(exam.time))
            check(
                f"  [{i}] classroom={exam.classroom}",
                bool(exam.classroom),
            )
            check(f"  [{i}] exam_form={exam.exam_form}", bool(exam.exam_form))
            check(f"  [{i}] exam_type={exam.exam_type}", bool(exam.exam_type))
            check(f"  [{i}] week={exam.week}", isinstance(exam.week, int))
            check(f"  [{i}] weekday={exam.weekday}", 1 <= exam.weekday <= 7, f"got {exam.weekday}")

        # xq=weekday 跨验证
        if e:
            import datetime

            for exam in e[:3]:
                try:
                    dt = datetime.date.fromisoformat(exam.date)
                    expected = dt.isoweekday()
                    check(
                        f"  xq→weekday 交叉验证 {exam.date} xq={exam.weekday}==周{expected}",
                        exam.weekday == expected,
                        f"mismatch: weekday={exam.weekday} expected={expected}",
                    )
                except Exception:
                    pass

    except Exception as ex:
        check(f"考试异常: {ex}", False)

# ============================================================
# 8. 学籍卡片
# ============================================================
print("\n[8] 学籍卡片")
try:
    info = client.get_student_info()
    check(f"student_id = {info.student_id}", info.student_id == U)
    check(f"name = {info.name}", bool(info.name))
    check(
        f"id_number = {info.id_number[:4]}...",
        len(info.id_number) >= 15,
        f"len={len(info.id_number)}",
    )
    check(f"phone = {info.phone}", len(info.phone) >= 10)
    check(f"email = {info.email}", "@" in info.email)
    check(
        f"home_address 非空",
        len(info.home_address) >= 10,
        f"got: {info.home_address[:20]}",
    )
    check(f"exam_number = {info.exam_number}", bool(info.exam_number))
    check(f"previous_school = {info.previous_school}", bool(info.previous_school))
    check(
        f"enrollment_date = {info.enrollment_date}",
        len(info.enrollment_date) == 8,
        f"len={len(info.enrollment_date)}",
    )
    check(f"pinyin_name = {info.pinyin_name}", bool(info.pinyin_name))
    check(f"english_name = {info.english_name}", bool(info.english_name))
except Exception as e:
    check(f"学籍异常: {e}", False, traceback.format_exc()[-300:])

# ============================================================
# SUMMARY
# ============================================================
total = passed + failed
print(f"\n{'=' * 60}")
print(f"测试结果: {passed} PASS / {failed} FAIL / {total} TOTAL")
print(f"通过率: {passed / total * 100:.1f}%" if total else "N/A")
if errors:
    print(f"\n❌ 失败详情:")
    for err in errors:
        print(f"  - {err}")
else:
    print("\n✅ 全部测试通过，零遗漏。")
print(f"{'=' * 60}")
