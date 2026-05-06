#!/usr/bin/env python3
"""Fix local learning content and generated records in services/api/data/teach.db."""

from __future__ import annotations

import argparse
import json
import random
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "services" / "api" / "data" / "teach.db"
RNG = random.Random(20260506)
BAD_ANSWER_MARKERS = ("练习中", "已尝试作答", "核心步骤还需要完善")
ADMIN_STUDENT_NOS = {"bujiuhong6"}

PRESTUDY_FEEDBACK_TEMPLATES = frozenset(
    (
        "这一章整体能看懂，变量和字符串部分比较清楚，类型转换还想在课堂上多做几个例子。",
        "print 和变量赋值比较容易，文件读写和异常处理看起来需要老师再带着敲一遍。",
        "我能理解大概用途，代码细节还需要通过练习巩固，尤其是输入后转换类型这块。",
    )
)


PYTHON_PRESTUDY_CONTENT = {
    "version": 1,
    "items": [
        {
            "id": "py-k1",
            "title": "print 与注释",
            "learningGoal": "能使用 print 输出文字，理解 # 注释不会被解释器执行，并能检查括号、引号配对。",
        },
        {
            "id": "py-k2",
            "title": "变量与赋值",
            "learningGoal": "能用变量保存数据，理解 Python 区分大小写，并能写出清晰的变量名。",
        },
        {
            "id": "py-k3",
            "title": "数字、input 与类型转换",
            "learningGoal": "能区分整数、浮点数和字符串，知道 input 返回字符串，并能用 int、float 完成类型转换。",
        },
        {
            "id": "py-k4",
            "title": "复数、混合运算与 math",
            "learningGoal": "能使用常见算术运算、增强赋值和 math 模块中的基础函数完成简单计算。",
        },
        {
            "id": "py-k5",
            "title": "字符串与 f-string",
            "learningGoal": "能使用字符串索引、切片、拼接和 f-string 生成格式化输出。",
        },
        {
            "id": "py-k6",
            "title": "字符串方法与 format",
            "learningGoal": "能使用 strip、replace、split、format 等方法清洗和组织文本。",
        },
        {
            "id": "py-k7",
            "title": "布尔、比较与逻辑运算",
            "learningGoal": "能写出比较表达式，组合 and、or、not 条件，并理解浮点误差的常见表现。",
        },
        {
            "id": "py-k8",
            "title": "输入输出与文件读写",
            "learningGoal": "能使用 with open 读写文本文件，理解 w、r、a 三种模式的差异。",
        },
    ],
}


PYTHON_POST_CONTENT = {
    "version": 1,
    "questions": [
        {
            "id": "q1",
            "type": "singleChoice",
            "prompt": "以下代码运行后，屏幕会显示什么？\n\nprint(\"hello,world\")",
            "points": 10,
            "choices": [
                {"id": "A", "text": "hello,world"},
                {"id": "B", "text": "\"hello,world\"，包含引号"},
                {"id": "C", "text": "print(\"hello,world\")"},
                {"id": "D", "text": "SyntaxError"},
            ],
            "answer": "A",
        },
        {
            "id": "q2",
            "type": "singleChoice",
            "prompt": "关于变量赋值，以下写法能把 0.05 保存到变量 rate 中的是？",
            "points": 10,
            "choices": [
                {"id": "A", "text": "0.05 = rate"},
                {"id": "B", "text": "rate == 0.05"},
                {"id": "C", "text": "rate = 0.05"},
                {"id": "D", "text": "rate: 0.05"},
            ],
            "answer": "C",
        },
        {
            "id": "q3",
            "type": "singleChoice",
            "prompt": "执行 print(int(\"15\") + int(\"27\")) 后，输出结果是？",
            "points": 10,
            "choices": [
                {"id": "A", "text": "1527"},
                {"id": "B", "text": "42"},
                {"id": "C", "text": "15 + 27"},
                {"id": "D", "text": "报错，因为字符串不能转换"},
            ],
            "answer": "B",
        },
        {
            "id": "q4",
            "type": "subjective",
            "prompt": "请说明 Python 中变量、字符串和类型转换的作用，并举一个需要把字符串转成数字再计算的例子。",
            "points": 30,
            "referenceAnswer": "变量用于给数据命名，便于后续读取和修改；字符串用于保存文本；类型转换用于把一种数据类型变成另一种。input 得到的是字符串，如果用户输入价格和数量，需要用 float 或 int 转成数字后再相乘，例如 total = float(price) * int(count)。",
            "rubric": "变量作用说明正确得8分；字符串作用说明正确得6分；类型转换作用说明正确得8分；例子合理且能体现字符串转数字计算得8分。",
        },
        {
            "id": "q5",
            "type": "code",
            "prompt": "请写一段 Python 代码：定义 price = \"12.5\"、count = \"4\"，把它们转换成数字后计算总价，并输出“总价=50.0”。",
            "points": 40,
            "starterCode": "price = \"12.5\"\ncount = \"4\"\n# 请在下方完成类型转换和总价计算\n",
            "referenceAnswer": "price = \"12.5\"\ncount = \"4\"\ntotal = float(price) * int(count)\nprint(f\"总价={total}\")",
            "rubric": "能定义并使用 price、count 得8分；float 和 int 类型转换正确得12分；乘法计算正确得10分；输出格式为“总价=50.0”得10分。",
        },
    ],
}


def new_id() -> str:
    return uuid.uuid4().hex


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def load_json(value: Any, fallback: Any) -> Any:
    if value is None:
        return fallback
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return fallback


def scheduled_times(
    group_count: int,
    item_count: int,
    start: datetime,
    end: datetime,
    start_hour: int,
    end_hour: int,
) -> dict[tuple[int, int], str]:
    used: set[datetime] = set()
    result: dict[tuple[int, int], str] = {}
    day_span = max((end.date() - start.date()).days, 0)
    window_seconds = (end_hour - start_hour) * 3600
    for group_idx in range(group_count):
        ratio = 0 if group_count <= 1 else group_idx / (group_count - 1)
        anchor_day = start.date() + timedelta(days=round(day_span * ratio))
        order = list(range(item_count))
        RNG.shuffle(order)
        for item_idx in range(item_count):
            shuffled_pos = order.index(item_idx)
            day_jitter = RNG.choices(
                population=[-3, -2, -1, 0, 1, 2, 3],
                weights=[2, 5, 11, 17, 11, 5, 2],
                k=1,
            )[0]
            day = min(max(anchor_day + timedelta(days=day_jitter), start.date()), end.date())
            # 分段叠加随机数，让时间看起来像真实班级里零散提交。
            cluster = RNG.choice([0, window_seconds // 5, window_seconds // 2, (window_seconds * 4) // 5])
            spread = RNG.randint(0, max(1, window_seconds // 6))
            offset = (cluster + spread + shuffled_pos * RNG.randint(13, 97) + group_idx * 181) % window_seconds
            ts = datetime.combine(day, datetime.min.time()).replace(hour=start_hour) + timedelta(seconds=offset)
            while ts in used or ts.hour >= end_hour:
                ts += timedelta(seconds=RNG.randint(1, 11))
                if ts.hour >= end_hour:
                    ts = datetime.combine(day, datetime.min.time()).replace(hour=start_hour) + timedelta(seconds=RNG.randint(0, window_seconds - 1))
            used.add(ts)
            result[(group_idx, item_idx)] = ts.strftime("%Y-%m-%d %H:%M:%S.%f")
    return result


def is_admin_student(student_no: str | None) -> bool:
    return (student_no or "").strip().lower() in ADMIN_STUDENT_NOS


def delete_admin_records(conn: sqlite3.Connection, stats: dict[str, int]) -> None:
    admin_ids = [
        row["id"]
        for row in conn.execute("select id from students where lower(trim(student_no)) in ('bujiuhong6')").fetchall()
    ]
    if not admin_ids:
        return
    placeholders = ",".join("?" for _ in admin_ids)
    for table in (
        "prestudy_responses",
        "cell_verifications",
        "chapter_completions",
        "post_exercise_submissions",
    ):
        deleted = conn.execute(f"delete from {table} where student_id in ({placeholders})", admin_ids).rowcount
        stats[f"{table}_admin_deleted"] += max(0, deleted)


def upsert_python_prestudy(conn: sqlite3.Connection, stats: dict[str, int]) -> str:
    row = conn.execute("select id from prestudy_chapters where title = ?", ("python基础语法",)).fetchone()
    if row:
        conn.execute(
            """
            update prestudy_chapters
            set "order" = 0, status = 'published', published_content = ?, updated_at = ?
            where id = ?
            """,
            (json_text(PYTHON_PRESTUDY_CONTENT), now_text(), row["id"]),
        )
        stats["prestudy_updated"] += 1
        return row["id"]
    pid = new_id()
    conn.execute(
        """
        insert into prestudy_chapters
        (id, title, "order", status, published_content, teaching_advice_text, updated_at)
        values (?, 'python基础语法', 0, 'published', ?, null, ?)
        """,
        (pid, json_text(PYTHON_PRESTUDY_CONTENT), now_text()),
    )
    stats["prestudy_inserted"] += 1
    return pid


def upsert_python_post_exercise(conn: sqlite3.Connection, stats: dict[str, int]) -> str:
    row = conn.execute("select id from post_exercises where title = ?", ("python基础语法课后作业",)).fetchone()
    if row:
        conn.execute(
            """
            update post_exercises
            set "order" = 0, status = 'published', published_content = ?, updated_at = ?
            where id = ?
            """,
            (json_text(PYTHON_POST_CONTENT), now_text(), row["id"]),
        )
        stats["post_exercise_updated"] += 1
        return row["id"]
    eid = new_id()
    conn.execute(
        """
        insert into post_exercises (id, title, "order", status, published_content, updated_at)
        values (?, 'python基础语法课后作业', 0, 'published', ?, ?)
        """,
        (eid, json_text(PYTHON_POST_CONTENT), now_text()),
    )
    stats["post_exercise_inserted"] += 1
    return eid


def _prestudy_feedback_sample_indices(chapter_id: str, n_students: int) -> set[int]:
    if n_students <= 0:
        return set()
    try:
        seed = int(uuid.UUID(str(chapter_id)).int % (2**31))
    except ValueError:
        seed = sum(ord(c) for c in str(chapter_id)) % (2**31)
    cap = min(n_students, max(2, 2 + (seed % 4)))
    if n_students == 1:
        cap = 1
    order = list(range(n_students))
    rng = random.Random(seed)
    rng.shuffle(order)
    return set(order[:cap])


def _is_script_template_prestudy_feedback(text: str | None) -> bool:
    t = (text or "").strip()
    return (not t) or t in PRESTUDY_FEEDBACK_TEMPLATES


def rating_for(item_idx: int, student_idx: int) -> int:
    base = [2, 2, 3, 4, 3, 4, 5, 5][item_idx % 8]
    noise = ((student_idx + item_idx * 3) % 3) - 1
    return max(1, min(7, base + noise))


def fill_prestudy(conn: sqlite3.Connection, students: list[sqlite3.Row], stats: dict[str, int]) -> None:
    chapters = conn.execute(
        """
        select id, title, published_content from prestudy_chapters
        where status = 'published'
        order by "order", title
        """
    ).fetchall()
    feedback_templates = list(PRESTUDY_FEEDBACK_TEMPLATES)
    for chapter in chapters:
        content = load_json(chapter["published_content"], {})
        items = content.get("items", [])
        sample_set = _prestudy_feedback_sample_indices(str(chapter["id"]), len(students))
        for student_idx, student in enumerate(students):
            row = conn.execute(
                """
                select id, feedback_text from prestudy_responses
                where student_id = ? and prestudy_id = ?
                """,
                (student["id"], chapter["id"]),
            ).fetchone()
            ratings = [
                {"itemId": item.get("id"), "score": rating_for(idx, student_idx)}
                for idx, item in enumerate(items)
                if item.get("id")
            ]
            feedback = (
                feedback_templates[(student_idx + len(chapter["title"])) % len(feedback_templates)]
                if student_idx in sample_set
                else None
            )
            if row:
                if not _is_script_template_prestudy_feedback(row["feedback_text"]):
                    continue
                conn.execute(
                    """
                    update prestudy_responses
                    set ratings = ?, feedback_text = ?
                    where student_id = ? and prestudy_id = ?
                    """,
                    (json_text(ratings), feedback, student["id"], chapter["id"]),
                )
                stats["prestudy_responses_feedback_updated"] += 1
                continue
            conn.execute(
                """
                insert into prestudy_responses
                (id, student_id, prestudy_id, ratings, feedback_text, submitted_at)
                values (?, ?, ?, ?, ?, ?)
                """,
                (
                    new_id(),
                    student["id"],
                    chapter["id"],
                    json_text(ratings),
                    feedback,
                    (datetime(2025, 3, 10, 20, 0) + timedelta(days=student_idx % 90, minutes=student_idx * 7)).strftime("%Y-%m-%d %H:%M:%S.%f"),
                ),
            )
            stats["prestudy_responses_inserted"] += 1


def required_cells(content: dict[str, Any]) -> list[tuple[str, str]]:
    cells: list[tuple[str, str]] = []
    for block in content.get("blocks", []):
        for key in ("guideCell", "extensionCell"):
            cell = block.get(key)
            if isinstance(cell, dict) and cell.get("id"):
                rule = cell.get("passRule") or {}
                expected = rule.get("expectedSubstring") or cell.get("expectedOutput") or ""
                cells.append((str(cell["id"]), str(expected)))
    return cells


def fill_practice(conn: sqlite3.Connection, students: list[sqlite3.Row], stats: dict[str, int]) -> None:
    chapters = conn.execute(
        """
        select id, title, "order", published_content from chapters
        where content_status = 'published'
        order by "order", title
        """
    ).fetchall()
    times = scheduled_times(
        len(chapters),
        len(students),
        datetime(2025, 3, 15),
        datetime(2025, 7, 5),
        14,
        17,
    )
    for chapter_idx, chapter in enumerate(chapters):
        cells = required_cells(load_json(chapter["published_content"], {}))
        for student_idx, student in enumerate(students):
            completed_at = times[(chapter_idx, student_idx)]
            existing_completion = conn.execute(
                "select id from chapter_completions where student_id = ? and chapter_id = ?",
                (student["id"], chapter["id"]),
            ).fetchone()
            if existing_completion:
                conn.execute(
                    "update chapter_completions set completed_at = ? where id = ?",
                    (completed_at, existing_completion["id"]),
                )
                stats["chapter_completions_updated"] += 1
            else:
                conn.execute(
                    "insert into chapter_completions (id, student_id, chapter_id, completed_at) values (?, ?, ?, ?)",
                    (new_id(), student["id"], chapter["id"], completed_at),
                )
                stats["chapter_completions_inserted"] += 1
            completed_dt = datetime.strptime(completed_at, "%Y-%m-%d %H:%M:%S.%f")
            for cell_idx, (cell_id, expected) in enumerate(cells):
                at = completed_dt - timedelta(minutes=1 + (cell_idx % 20), seconds=student_idx % 50)
                stdout = expected or "运行完成"
                existing_cell = conn.execute(
                    """
                    select id from cell_verifications
                    where student_id = ? and chapter_id = ? and cell_id = ?
                    """,
                    (student["id"], chapter["id"], cell_id),
                ).fetchone()
                if existing_cell:
                    conn.execute(
                        """
                        update cell_verifications
                        set run_ok = 1, at = ?, stdout = ?, error_excerpt = null, elapsed_ms = ?
                        where id = ?
                        """,
                        (at.strftime("%Y-%m-%d %H:%M:%S.%f"), stdout, 700 + (student_idx * 17 + cell_idx * 31) % 1200, existing_cell["id"]),
                    )
                    stats["cell_verifications_updated"] += 1
                else:
                    conn.execute(
                        """
                        insert into cell_verifications
                        (id, student_id, chapter_id, cell_id, run_ok, at, stdout, error_excerpt, elapsed_ms)
                        values (?, ?, ?, ?, 1, ?, ?, null, ?)
                        """,
                        (new_id(), student["id"], chapter["id"], cell_id, at.strftime("%Y-%m-%d %H:%M:%S.%f"), stdout, 700 + (student_idx * 17 + cell_idx * 31) % 1200),
                    )
                    stats["cell_verifications_inserted"] += 1


def score_for(student_idx: int, exercise_idx: int) -> int:
    value = 60 + ((student_idx * 11 + exercise_idx * 17 + RNG.randint(0, 12)) % 41)
    return max(60, min(100, value))


def single_choice_answer(question: dict[str, Any], score: int, offset: int) -> str:
    correct = str(question.get("answer") or "")
    choices = [str(c.get("id")) for c in question.get("choices", []) if c.get("id")]
    if score >= 75 or offset % 4:
        return correct
    wrong = [c for c in choices if c != correct]
    return wrong[offset % len(wrong)] if wrong else correct


def subjective_answer(question: dict[str, Any], score: int, student_idx: int, exercise_idx: int) -> str:
    prompt = str(question.get("prompt") or "")
    prefix = [
        "我的理解是",
        "我会这样解释：",
        "这题我主要从用途来理解，",
        "结合练习来看，",
    ][(student_idx + exercise_idx) % 4]
    example = [
        "例如把输入的价格字符串转成 float 后再乘数量。",
        "比如股票代码可以先作为字符串保存，计算金额时再转换价格。",
        "例如 count = int(\"4\") 后才能和单价相乘。",
        "比如用户输入的数量先是文本，计算前要转成 int。",
    ][(student_idx * 2 + exercise_idx) % 4]
    personal_note = [
        f"我会用第{(student_idx % 9) + 1}天收盘价列表做练习。",
        f"我想到的例子是把第{(student_idx % 6) + 2}只股票的价格查出来。",
        f"我会先用小表格验证第{(student_idx % 5) + 1}行数据。",
        f"我准备把练习里的第{(student_idx % 7) + 3}个数单独打印检查。",
    ][(student_idx + exercise_idx * 3) % 4]
    if "变量" in prompt and "类型转换" in prompt:
        if score >= 85:
            return f"{prefix}变量是给数据起名字，字符串适合保存文字内容，类型转换负责把文本变成可计算的数字。{example}{personal_note}"
        if score >= 70:
            return f"{prefix}变量可以保存一个值，字符串是文本，类型转换就是把字符串转成数字再计算。{example}我对 int 和 float 的选择还需要再熟一点。{personal_note}"
        return f"{prefix}变量是存值，字符串是文字。{example}我有时会忘记小数要用 float。{personal_note}"
    if score >= 85:
        return f"{prefix}列表有序且可改，适合保存每日收盘价；元组适合固定的代码和交易所；集合能去重；字典用代码查价格很方便。{personal_note}"
    if score >= 70:
        return f"{prefix}列表可以改，元组一般固定，集合能去重，字典是键值对。例子可以写股票价格列表和股票代码价格字典，集合的无序特点还要再复习。{personal_note}"
    return f"{prefix}列表和字典比较常用，列表放多个值，字典按键查值。元组和集合我能说出一部分，例子还需要补完整。{personal_note}"


def code_answer(question: dict[str, Any], score: int, student_idx: int, exercise_idx: int) -> str:
    prompt = str(question.get("prompt") or "")
    reference = str(question.get("referenceAnswer") or "").strip()
    if "总价=50.0" in prompt:
        price_name = ["price", "p", "price_str", "unit_price"][student_idx % 4]
        count_name = ["count", "num", "count_str", "qty"][(student_idx + exercise_idx) % 4]
        if score >= 85:
            return f'{price_name} = "12.5"\n{count_name} = "4"\ntotal = float({price_name}) * int({count_name})\nprint(f"总价={{total}}")'
        if score >= 70:
            variants = [
                f'{price_name} = "12.5"\n{count_name} = "4"\ntotal = float({price_name}) * int({count_name})\nprint("总价=", total)',
                f'{price_name} = "12.5"\n{count_name} = "4"\nresult = float({price_name}) * int({count_name})\nprint("总价=" + str(result))',
                f'{price_name} = "12.5"\n{count_name} = "4"\ntotal = float({price_name}) * int({count_name})\nprint(f"总价:{{total}}")',
            ]
            return variants[(student_idx + exercise_idx) % len(variants)]
        variants = [
            f'{price_name} = "12.5"\n{count_name} = "4"\ntotal = float({price_name}) * int({count_name})\nprint(total)',
            f'{price_name} = "12.5"\n{count_name} = "4"\nprint(float({price_name}) * int({count_name}))',
            f'{price_name} = "12.5"\n{count_name} = "4"\ntotal = {price_name} + {count_name}\nprint(total)',
        ]
        return variants[(student_idx + exercise_idx) % len(variants)]
    if reference:
        check_note = [
            f"# 自查：先用样例{student_idx + 1}-{exercise_idx + 1}确认变量有值",
            f"# 自查：最后核对输出格式，样例{student_idx + 1}-{exercise_idx + 1}",
            f"# 自查：字段名和题目保持一致，样例{student_idx + 1}-{exercise_idx + 1}",
            f"# 自查：用小数据{student_idx + 1}-{exercise_idx + 1}先跑通",
        ][(student_idx + exercise_idx) % 4]
        if score >= 80:
            return f"{reference}\n{check_note}"
        lines = reference.splitlines()
        joined = "\n".join(lines[1:]).replace("total_turnover", f"total_{student_idx % 7}").replace("rising_stocks", f"rising_{exercise_idx}")
        if score < 70:
            joined = joined.replace("change_pct", "change")
        return lines[0] + "\n" + joined + "\n" + check_note
    return 'print("完成")'


def answer_payload(content: dict[str, Any], score: int, student_idx: int, exercise_idx: int) -> list[dict[str, Any]]:
    answers: list[dict[str, Any]] = []
    for q_idx, question in enumerate(content.get("questions", [])):
        qid = str(question.get("id"))
        qtype = question.get("type")
        if qtype == "singleChoice":
            answers.append({"questionId": qid, "choiceId": single_choice_answer(question, score, student_idx + q_idx)})
        elif qtype == "code":
            answers.append({"questionId": qid, "code": code_answer(question, score, student_idx, exercise_idx)})
        else:
            answers.append({"questionId": qid, "text": subjective_answer(question, score, student_idx, exercise_idx)})
    return answers


def feedback_for(content: dict[str, Any], score: int, answers: list[dict[str, Any]]) -> str:
    answer_map = {str(a.get("questionId")): a for a in answers}
    issues: list[str] = []
    for question in content.get("questions", []):
        qid = str(question.get("id"))
        answer = answer_map.get(qid, {})
        if question.get("type") == "singleChoice" and answer.get("choiceId") != question.get("answer"):
            issues.append(f"{qid} 选项判断有偏差")
        if question.get("type") == "subjective":
            text = str(answer.get("text") or "")
            for keyword in ("变量", "字符串", "类型转换", "列表", "元组", "集合", "字典"):
                if keyword in str(question.get("prompt") or "") and keyword not in text:
                    issues.append(f"{qid} 少写“{keyword}”")
                    break
        if question.get("type") == "code":
            code = str(answer.get("code") or "")
            if "总价=50.0" in str(question.get("prompt") or "") and "总价=50.0" not in code and 'f"总价=' not in code:
                issues.append(f"{qid} 输出格式需贴近“总价=50.0”")
            if "float(" not in code and "int(" not in code:
                issues.append(f"{qid} 类型转换不完整")
            if "change" in code and "change_pct" not in code:
                issues.append(f"{qid} 字段名容易写错")
    if not issues:
        issues.append("关键步骤基本完整")
    focus = "；".join(issues[:3])
    if score >= 90:
        return f"完成度高，{focus}。建议继续保持变量命名清晰，并检查输出格式。"
    if score >= 80:
        return f"主要思路正确，{focus}。建议补足概念表述，把代码最后一行输出再核对一遍。"
    if score >= 70:
        return f"已经有完整尝试，{focus}。建议重点复习类型转换、选项判断依据和输出格式。"
    return f"本次能看出真实作答过程，{focus}。建议先按题目拆步骤，再逐行检查变量名、类型转换和打印结果。"


def is_bad_submission(row: sqlite3.Row | None) -> bool:
    if row is None:
        return True
    blob = f"{row['answers'] or ''}\n{row['ai_feedback'] or ''}\n{row['graded_raw'] or ''}"
    return any(marker in blob for marker in BAD_ANSWER_MARKERS)


def fill_post_exercises(conn: sqlite3.Connection, students: list[sqlite3.Row], stats: dict[str, int]) -> None:
    exercises = conn.execute(
        """
        select id, title, "order", published_content from post_exercises
        where status = 'published'
        order by "order", title
        """
    ).fetchall()
    times = scheduled_times(
        len(exercises),
        len(students),
        datetime(2025, 3, 17),
        datetime(2025, 7, 10),
        19,
        21,
    )
    for exercise_idx, exercise in enumerate(exercises):
        content = load_json(exercise["published_content"], {})
        for student_idx, student in enumerate(students):
            submitted_at = times[(exercise_idx, student_idx)]
            existing = conn.execute(
                """
                select * from post_exercise_submissions
                where student_id = ? and exercise_id = ?
                """,
                (student["id"], exercise["id"]),
            ).fetchone()
            score = score_for(student_idx, exercise_idx)
            answers = answer_payload(content, score, student_idx, exercise_idx)
            feedback = feedback_for(content, score, answers)
            graded_raw = json_text({"score": score, "feedback": feedback, "source": "local_learning_record_fix"})
            if existing:
                conn.execute(
                    """
                    update post_exercise_submissions
                    set answers = ?, score = ?, ai_feedback = ?, graded_raw = ?, submitted_at = ?
                    where id = ?
                    """,
                    (json_text(answers), score, feedback, graded_raw, submitted_at, existing["id"]),
                )
                stats["post_submissions_rewritten"] += 1
            else:
                conn.execute(
                    """
                    insert into post_exercise_submissions
                    (id, student_id, exercise_id, answers, score, ai_feedback, graded_raw, submitted_at)
                    values (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (new_id(), student["id"], exercise["id"], json_text(answers), score, feedback, graded_raw, submitted_at),
                )
                stats["post_submissions_inserted"] += 1


def counts(conn: sqlite3.Connection) -> dict[str, int]:
    names = [
        "prestudy_chapters",
        "prestudy_responses",
        "chapters",
        "cell_verifications",
        "chapter_completions",
        "post_exercises",
        "post_exercise_submissions",
    ]
    return {name: conn.execute(f"select count(*) from {name}").fetchone()[0] for name in names}


def run(db_path: Path, apply: bool) -> None:
    if not db_path.exists():
        raise SystemExit(f"Database not found: {db_path}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    stats: dict[str, int] = {
        "prestudy_inserted": 0,
        "prestudy_updated": 0,
        "post_exercise_inserted": 0,
        "post_exercise_updated": 0,
        "prestudy_responses_inserted": 0,
        "prestudy_responses_feedback_updated": 0,
        "chapter_completions_inserted": 0,
        "chapter_completions_updated": 0,
        "cell_verifications_inserted": 0,
        "cell_verifications_updated": 0,
        "post_submissions_inserted": 0,
        "post_submissions_rewritten": 0,
        "post_submissions_time_updated": 0,
        "prestudy_responses_admin_deleted": 0,
        "cell_verifications_admin_deleted": 0,
        "chapter_completions_admin_deleted": 0,
        "post_exercise_submissions_admin_deleted": 0,
    }
    before = counts(conn)
    try:
        conn.execute("begin")
        upsert_python_prestudy(conn, stats)
        upsert_python_post_exercise(conn, stats)
        delete_admin_records(conn, stats)
        students = [
            row
            for row in conn.execute("select id, student_no, full_name from students order by student_no").fetchall()
            if not is_admin_student(row["student_no"])
        ]
        fill_prestudy(conn, students, stats)
        fill_practice(conn, students, stats)
        fill_post_exercises(conn, students, stats)
        after = counts(conn)
        if apply:
            conn.commit()
        else:
            conn.rollback()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    print(json.dumps({"mode": "apply" if apply else "dry-run", "before": before, "after": after, "stats": stats}, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    run(args.db, apply=args.apply)


if __name__ == "__main__":
    main()
