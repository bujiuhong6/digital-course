"""
写入 E2E 用 SQLite：与 task11 同结构，但章 JSON 便于演示「先错后对」+ 标完成。
运行：在仓库根
  `JWT_SECRET=... STUDENT_PASSWORD_KEY=... \\
   DATABASE_URL=sqlite+aiosqlite://ABS_PATH/db.sqlite \\
   PYTHONPATH=services/api python3 scripts/seed_e2e_notebook_chapter.py`
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from pathlib import Path

os.environ.setdefault("JWT_SECRET", "e2e-seed-jwt-teacher-cookie-consistent-123")
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
from app.db.models import (  # noqa: E402
    AdminConfig,
    Chapter,
    ChapterCompletion,
    RosterEntry,
    Student,
)
from app.services.crypto import encrypt_password  # noqa: E402

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

_ADMIN_PW = "AdminPass123"
_STU_NO = "E2E0001"
_STU_NAME = "E2E演示"
_STU_PW = "E2EPass123"


def published_content() -> dict:
    return {
        "version": 1,
        "blocks": [
            {
                "id": "blk-e2e-1",
                "knowledgeHtml": "<p>在下方输入框中编辑代码，点「运行并上报」。引导关要求标准输出含 <code>ok</code>；扩展关要求含 <code>Hello</code>。</p>",
                "requiredExecutionMode": "pyodide",
                "guideCell": {
                    "id": "c-guide-e2e",
                    "starterCode": 'print("改这里，先故意写错再改对")',
                    "description": "引导：stdout 须包含子串 ok",
                    "passRule": {
                        "mode": "stdout_contains",
                        "expectedSubstring": "ok",
                    },
                },
                "extensionCell": {
                    "id": "c-ext-e2e",
                    "promptHtml": "<p>扩展：打印一行含 Hello 的问候。</p>",
                    "starterCode": 'print("先写错再改")',
                    "passRule": {
                        "mode": "stdout_contains",
                        "expectedSubstring": "Hello",
                    },
                },
            }
        ],
    }


def _resolve_sqlite_path(url: str) -> str:
    """`sqlite+aiosqlite:///../file` 或 `...:///./data/x.db` → 绝对路径。"""
    prefix = "sqlite+aiosqlite:///"
    if not url.startswith(prefix):
        raise ValueError("need sqlite+aiosqlite url")
    p = url.removeprefix(prefix).split("?")[0]
    path = Path(p)
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    return str(path)


async def main() -> None:
    e2e_path = os.environ.get("E2E_DB_PATH", "").strip()
    if e2e_path:
        out = str(Path(e2e_path).resolve())
    else:
        url = os.environ.get("DATABASE_URL", "").strip()
        if not url or "sqlite" not in url:
            print(
                "Set DATABASE_URL=sqlite+aiosqlite:///... or E2E_DB_PATH=...",
                file=sys.stderr,
            )
            sys.exit(1)
        out = _resolve_sqlite_path(url)

    Path(out).parent.mkdir(parents=True, exist_ok=True)
    if Path(out).exists():
        Path(out).unlink()
    url = f"sqlite+aiosqlite:///{out}"
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    ch_id = uuid.uuid4()
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
        db.add(
            Chapter(
                id=ch_id,
                slug="e2e-notebook",
                title="E2E 演示章（运行与标完成）",
                order=0,
                content_status="published",
                published_content=published_content(),
            )
        )
        if os.environ.get("SEED_DEMO_COMPLETION", "").strip() in ("1", "true", "yes"):
            db.add(
                ChapterCompletion(
                    id=uuid.uuid4(),
                    student_id=st.id,
                    chapter_id=ch_id,
                )
            )
        await db.commit()
    await engine.dispose()
    print("DATABASE_FILE=" + out, file=sys.stderr)
    print("CHAPTER_ID=" + str(ch_id), file=sys.stderr)
    print("ADMIN_PASSWORD=" + _ADMIN_PW, file=sys.stderr)
    print("STUDENT_NO=" + _STU_NO, file=sys.stderr)
    print("STUDENT_NAME=" + _STU_NAME, file=sys.stderr)
    print("STUDENT_PASSWORD=" + _STU_PW, file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
