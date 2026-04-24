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
from app.db.models import AdminConfig, Chapter, RosterEntry, Student  # noqa: E402
from app.services.chapter_json import sample_published_v1  # noqa: E402
from app.services.crypto import encrypt_password  # noqa: E402

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

_OUT = Path("/tmp/ai-python-teach-task11-demo.db")
_ADMIN_PW = "AdminPass123"
_STU_NO = "2026001"
_STU_NAME = "演示学生"
_STU_PW = "StuPass123"


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
        re = RosterEntry(
            id=uuid.uuid4(),
            student_no=_STU_NO,
            full_name=_STU_NAME,
            status="pending",
        )
        db.add(re)
        await db.flush()
        st = Student(
            id=uuid.uuid4(),
            student_no=_STU_NO,
            full_name=_STU_NAME,
            password_ciphertext=encrypt_password(_STU_PW),
            must_change_password=False,
        )
        db.add(st)
        await db.flush()
        re.student_id = st.id
        re.status = "bound"
        pc = sample_published_v1()
        ch = Chapter(
            id=uuid.uuid4(),
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


if __name__ == "__main__":
    asyncio.run(main())
