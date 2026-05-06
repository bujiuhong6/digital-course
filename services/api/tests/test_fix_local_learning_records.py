from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts.fix_local_learning_records import fill_prestudy


def test_fill_prestudy_backfills_blank_feedback_for_existing_responses() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        create table prestudy_chapters (
            id text primary key,
            title text not null,
            status text not null,
            published_content text not null
        );
        create table prestudy_responses (
            id text primary key,
            student_id text not null,
            prestudy_id text not null,
            ratings text not null,
            feedback_text text,
            submitted_at text not null
        );
        """
    )
    conn.execute(
        """
        insert into prestudy_chapters (id, title, status, published_content)
        values ('p1', 'python基础语法', 'published', '{"items":[{"id":"k1"},{"id":"k2"}]}')
        """
    )
    conn.execute(
        """
        insert into prestudy_responses (id, student_id, prestudy_id, ratings, feedback_text, submitted_at)
        values ('r1', 's1', 'p1', '[]', null, '2025-03-10 20:00:00.000000')
        """
    )
    stats = {"prestudy_responses_inserted": 0, "prestudy_responses_feedback_updated": 0}

    fill_prestudy(conn, [{"id": "s1", "student_no": "2401", "full_name": "学生1"}], stats)

    row = conn.execute("select feedback_text from prestudy_responses where id = 'r1'").fetchone()
    assert row["feedback_text"]
    assert stats["prestudy_responses_feedback_updated"] == 1
    ratings = json.loads(conn.execute("select ratings from prestudy_responses where id = 'r1'").fetchone()[0])
    assert ratings[0].get("score") is not None


def test_fill_prestudy_text_feedback_count_between_two_and_five() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        create table prestudy_chapters (
            id text primary key,
            title text not null,
            status text not null,
            published_content text not null
        );
        create table prestudy_responses (
            id text primary key,
            student_id text not null,
            prestudy_id text not null,
            ratings text not null,
            feedback_text text,
            submitted_at text not null
        );
        """
    )
    conn.execute(
        """
        insert into prestudy_chapters (id, title, status, published_content)
        values ('p1', 'python基础语法', 'published', '{"items":[{"id":"k1"},{"id":"k2"}]}')
        """
    )
    pupils = [
        {"id": f"s{i}", "student_no": f"24{i:04d}", "full_name": f"学生{i}"}
        for i in range(10)
    ]
    stats = {"prestudy_responses_inserted": 0, "prestudy_responses_feedback_updated": 0}
    fill_prestudy(conn, pupils, stats)
    with_fb = conn.execute(
        "select count(*) from prestudy_responses where prestudy_id='p1' and feedback_text is not null and trim(feedback_text)<>''"
    ).fetchone()[0]
    assert 2 <= with_fb <= 5
    assert stats["prestudy_responses_inserted"] == 10
