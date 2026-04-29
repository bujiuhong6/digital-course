from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.db import models as _models  # noqa: F401
from app.db.base import Base
from app.db.models import Chapter, Class, PostExercise, PrestudyChapter, RosterEntry, Student
from app.services.crypto import encrypt_password


def _load_initialize_module():
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / "scripts" / "initialize_content_db.py"
    spec = importlib.util.spec_from_file_location("initialize_content_db_for_test", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_initialize_preserves_designed_content_by_default(tmp_path, monkeypatch) -> None:
    mod = _load_initialize_module()
    db_path = tmp_path / "teach.db"
    seed = tmp_path / "chapters.json"
    seed.write_text(
        json.dumps(
            {
                "chapters": [
                    {
                        "id": uuid.uuid4().hex,
                        "slug": "existing",
                        "title": "Seed Title",
                        "order": 1,
                        "content_status": "published",
                        "published_content": {"from": "seed"},
                    },
                    {
                        "id": uuid.uuid4().hex,
                        "slug": "new-seed",
                        "title": "New Seed",
                        "order": 2,
                        "content_status": "published",
                        "published_content": {"from": "new"},
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", poolclass=NullPool)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)

    async def run() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with session_maker() as session:
            class_id = uuid.uuid4()
            student_id = uuid.uuid4()
            session.add_all(
                [
                    Chapter(
                        id=uuid.uuid4(),
                        slug="existing",
                        title="Teacher Designed Title",
                        order=99,
                        content_status="published",
                        published_content={"from": "teacher"},
                    ),
                    Chapter(
                        id=uuid.uuid4(),
                        slug="teacher-extra",
                        title="Teacher Extra Chapter",
                        order=100,
                        content_status="published",
                        published_content={"from": "teacher-extra"},
                    ),
                    PrestudyChapter(
                        id=uuid.uuid4(),
                        title="AI智能预习",
                        order=1,
                        status="published",
                        published_content={"version": 1, "items": []},
                    ),
                    PostExercise(
                        id=uuid.uuid4(),
                        title="AI课后作业",
                        order=1,
                        status="published",
                        published_content={"version": 1, "questions": []},
                    ),
                    Class(id=class_id, name="24金融学"),
                    Student(
                        id=student_id,
                        student_no="2401",
                        full_name="学生",
                        password_ciphertext=encrypt_password("pw"),
                        class_id=class_id,
                    ),
                    RosterEntry(
                        id=uuid.uuid4(),
                        student_no="2401",
                        full_name="学生",
                        status="bound",
                        student_id=student_id,
                        class_id=class_id,
                    ),
                ]
            )
            await session.commit()

        monkeypatch.setattr(mod, "get_async_session_maker", lambda: session_maker)
        async def dispose_engine_noop() -> None:
            return None

        monkeypatch.setattr(mod, "dispose_engine", dispose_engine_noop)
        await mod.initialize(
            seed,
            keep_runtime=False,
            prune_extra_chapters=True,
            allow_delete_designed_content=False,
        )

        async with session_maker() as session:
            chapters = (await session.execute(select(Chapter))).scalars().all()
            by_slug = {chapter.slug: chapter for chapter in chapters}
            assert set(by_slug) == {"existing", "teacher-extra", "new-seed"}
            assert by_slug["existing"].title == "Teacher Designed Title"
            assert by_slug["existing"].published_content == {"from": "teacher"}
            assert by_slug["teacher-extra"].published_content == {"from": "teacher-extra"}
            assert by_slug["new-seed"].title == "New Seed"

            assert len((await session.execute(select(PrestudyChapter))).scalars().all()) == 1
            assert len((await session.execute(select(PostExercise))).scalars().all()) == 1
            assert len((await session.execute(select(Student))).scalars().all()) == 0
            assert len((await session.execute(select(RosterEntry))).scalars().all()) == 0
            assert len((await session.execute(select(Class))).scalars().all()) == 0

    try:
        asyncio.run(run())
    finally:
        asyncio.run(engine.dispose())
