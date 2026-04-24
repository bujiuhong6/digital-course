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
        "chapterIntroHtml": (
            "<p>本演示章介绍 <strong>标准输出</strong> 与过关条件。</p>"
            "<p>下方按知识点分块：基础练与扩展练各一题；"
            "顺序为题目说明 → 期望输出 → 代码区 → 运行结果与判题提示。</p>"
        ),
        "blocks": [
            {
                "id": "blk-e2e-1",
                "sectionTitle": "认识 print 与 stdout",
                "knowledgeHtml": (
                    "<p>函数 <code>print(...)</code> 会把内容写到标准输出。"
                    "本题要求运行后，标准输出中含有指定子串才算通过。</p>"
                ),
                "requiredExecutionMode": "pyodide",
                "guideCell": {
                    "id": "c-guide-e2e",
                    "exerciseTitle": "第 1 题（基础）：输出含 ok",
                    "starterCode": 'print("改这里，先故意写错再改对")',
                    "description": (
                        "<p>编辑代码后点「执行」。"
                        "过关条件：标准输出中须包含子串 <code>ok</code>。</p>"
                    ),
                    "expectedOutput": "含字母 ok 的一行或若干行，例如：ok 或 all ok",
                    "referenceAnswer": 'print("ok")',
                    "passRule": {
                        "mode": "stdout_contains",
                        "expectedSubstring": "ok",
                    },
                },
                "extensionCell": {
                    "id": "c-ext-e2e",
                    "exerciseTitle": "第 1 题（扩展）：问候中含 Hello",
                    "promptHtml": (
                        "<p>打印一行内容，<strong>必须包含</strong>子串 <code>Hello</code> "
                        "（可含其他字符）。</p>"
                    ),
                    "starterCode": 'print("先写错再改")',
                    "expectedOutput": "例如：Hello, world! 或 Hello 任意后缀",
                    "referenceAnswer": 'print("Hello!")',
                    "passRule": {
                        "mode": "stdout_contains",
                        "expectedSubstring": "Hello",
                    },
                },
            }
        ],
    }


def _resolve_sqlite_path(url: str) -> str:
    """相对路径以 `services/api` 为基准，与 `cd services/api && uvicorn` 一致。"""
    prefix = "sqlite+aiosqlite:///"
    if not url.startswith(prefix):
        raise ValueError("need sqlite+aiosqlite url")
    p = url.removeprefix(prefix).split("?")[0]
    if p.startswith("//"):
        return p[1:]
    path = Path(p)
    if path.is_absolute():
        return str(path)
    return str((_API / path).resolve())


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
