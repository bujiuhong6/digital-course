"""教师 API：章完成记录列表。"""

import asyncio
import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import ChapterCompletion, Class, Student


def test_admin_list_chapter_completions(client, tmp_path: Path) -> None:
    client.post("/v1/admin/bootstrap", json={"password": "admin-cpl-123"})
    ch = client.post(
        "/v1/admin/chapters",
        json={"title": "T1", "slug": "t1-cpl"},
    ).json()
    cid = ch["id"]

    # 与 conftest 同一 sqlite 文件
    url = f"sqlite+aiosqlite:///{tmp_path / 'teach.db'}"
    engine = create_async_engine(url)
    sm = async_sessionmaker(engine, expire_on_commit=False)

    async def _seed() -> None:
        async with sm() as db:
            st = Student(
                id=uuid.uuid4(),
                student_no="S9001",
                full_name="测试生",
                password_ciphertext="x",
            )
            db.add(st)
            await db.flush()
            db.add(
                ChapterCompletion(
                    id=uuid.uuid4(),
                    student_id=st.id,
                    chapter_id=uuid.UUID(cid),
                )
            )
            await db.commit()

    asyncio.run(_seed())
    asyncio.run(engine.dispose())

    r = client.get(f"/v1/admin/chapters/{cid}/completions")
    assert r.status_code == 200
    j = r.json()
    assert j["ok"] is True
    assert j["chapterId"] == cid
    assert len(j["completions"]) == 1
    assert j["completions"][0]["studentNo"] == "S9001"
    assert j["completions"][0]["fullName"] == "测试生"
    assert "completedAt" in j["completions"][0]

    r_csv = client.get(f"/teacher/chapters/{cid}/completions/export")
    assert r_csv.status_code == 200
    assert "text/csv" in (r_csv.headers.get("content-type") or "")
    assert "S9001" in r_csv.text
    assert "测试生" in r_csv.text


def test_chapter_completions_respects_class_id_filter(client, tmp_path: Path) -> None:
    client.post("/v1/admin/bootstrap", json={"password": "admin-cpl-789"})
    ch = client.post(
        "/v1/admin/chapters",
        json={"title": "C2", "slug": "c2-flt"},
    ).json()
    cid = ch["id"]
    cl_id: uuid.UUID | None = None
    st_a: uuid.UUID | None = None
    st_b: uuid.UUID | None = None
    url = f"sqlite+aiosqlite:///{tmp_path / 'teach.db'}"
    engine = create_async_engine(url)
    sm = async_sessionmaker(engine, expire_on_commit=False)

    async def _seed() -> None:
        nonlocal cl_id, st_a, st_b
        async with sm() as db:
            cl = Class(name="一班")
            db.add(cl)
            await db.flush()
            cl_id = cl.id
            st_a = uuid.uuid4()
            st_b = uuid.uuid4()
            db.add(
                Student(
                    id=st_a,
                    student_no="SA",
                    full_name="甲",
                    password_ciphertext="x",
                    class_id=cl_id,
                )
            )
            db.add(
                Student(
                    id=st_b,
                    student_no="SB",
                    full_name="乙",
                    password_ciphertext="x",
                    class_id=None,
                )
            )
            await db.flush()
            db.add(
                ChapterCompletion(
                    id=uuid.uuid4(),
                    student_id=st_a,
                    chapter_id=uuid.UUID(cid),
                )
            )
            db.add(
                ChapterCompletion(
                    id=uuid.uuid4(),
                    student_id=st_b,
                    chapter_id=uuid.UUID(cid),
                )
            )
            await db.commit()

    asyncio.run(_seed())
    asyncio.run(engine.dispose())

    r_all = client.get(f"/v1/admin/chapters/{cid}/completions")
    assert len(r_all.json()["completions"]) == 2

    r_f = client.get(
        f"/v1/admin/chapters/{cid}/completions?classId={cl_id!s}",
    )
    assert r_f.status_code == 200
    assert len(r_f.json()["completions"]) == 1
    assert r_f.json()["completions"][0]["studentNo"] == "SA"
