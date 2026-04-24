"""教师 API：章完成记录列表。"""

import asyncio
import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import ChapterCompletion, Student


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
