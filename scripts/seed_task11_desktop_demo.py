"""
一次性写入 SQLite：管理员、名单+学生、已发布章。供任务 11 学生桌面演示。
运行：在仓库根 `PYTHONPATH=services/api python3 scripts/seed_task11_desktop_demo.py`
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from pathlib import Path

# 在导入 app 前
os.environ.setdefault("JWT_SECRET", "demo-seed-jwt-teacher-cookie-consistent-12345")
os.environ.setdefault(
    "STUDENT_PASSWORD_KEY",
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
)

_API = Path(__file__).resolve().parent.parent / "services" / "api"
if str(_API) not in sys.path:
    sys.path.insert(0, str(_API))

from passlib.context import CryptContext  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    async_sessionmaker,
    create_async_engine,
)

from app.db import models  # noqa: F401, E402
from app.db.base import Base  # noqa: E402
from app.db.models import AdminConfig, Chapter, Class, RosterEntry, Student  # noqa: E402
from app.services.chapter_json import sample_published_v1  # noqa: E402
from app.services.crypto import encrypt_password  # noqa: E402

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

_OUT = Path("/tmp/ai-python-teach-task11-demo.db")
_ADMIN_PW = "AdminPass123"
_STU_NO = "2026001"
_STU_NAME = "演示学生"
_STU_PW = "StuPass123"
# 与 `record_mvp_features_demo.mjs` 中 URL 一致，便于固定演示
_DEMO_CHAPTER_ID = uuid.UUID("d065d28b-e0c8-414c-a220-745d31ec2dc9")
_DEMO_CLASS_ID = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")


async def main() -> None:
    _OUT.unlink(missing_ok=True)
    url = f"sqlite+aiosqlite:///{_OUT}"
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as db:
        db.add(AdminConfig(id=1, password_hash=_pwd.hash(_ADMIN_PW)))
        demo_cls = Class(id=_DEMO_CLASS_ID, name="演示班")
        db.add(demo_cls)
        await db.flush()
        re = RosterEntry(
            id=uuid.uuid4(),
            student_no=_STU_NO,
            full_name=_STU_NAME,
            status="pending",
            class_id=demo_cls.id,
        )
        db.add(re)
        await db.flush()
        st = Student(
            id=uuid.uuid4(),
            student_no=_STU_NO,
            full_name=_STU_NAME,
            password_ciphertext=encrypt_password(_STU_PW),
            must_change_password=False,
            class_id=demo_cls.id,
        )
        db.add(st)
        await db.flush()
        re.student_id = st.id
        re.status = "bound"
        pc = sample_published_v1()
        ch = Chapter(
            id=_DEMO_CHAPTER_ID,
            slug="demo-published",
            title="演示章（任务 11）",
            order=0,
            content_status="published",
            published_content=pc,
        )
        db.add(ch)
        await db.commit()
    await engine.dispose()
    print(f"Wrote {_OUT}", file=sys.stderr)
    print("ADMIN_PASSWORD=" + _ADMIN_PW, file=sys.stderr)
    print("STUDENT_NO=" + _STU_NO, file=sys.stderr)
    print("STUDENT_FULL_NAME=" + _STU_NAME, file=sys.stderr)
    print("STUDENT_PASSWORD=" + _STU_PW, file=sys.stderr)
    print("CHAPTER_ID=" + str(_DEMO_CHAPTER_ID), file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
