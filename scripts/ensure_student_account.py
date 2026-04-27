#!/usr/bin/env python3
"""
在本机数据库中创建「与正式注册等效」的学生账号（名单行 + students 行），用于教师用学生端自测。

用法（在 `services/api` 目录下执行，与 uvicorn 共用同一 `DATABASE_URL` / `STUDENT_PASSWORD_KEY`）::

    cd services/api
    PYTHONPATH=. python ../../scripts/ensure_student_account.py \\
        --student-no bujiuhong6 --full-name 教师巡测 --password '你的密码'

或密码仅放在环境变量（避免进 shell 历史）::

    export STUDENT_BOOTSTRAP_PASSWORD='...'
    PYTHONPATH=. python ../../scripts/ensure_student_account.py \\
        --student-no bujiuhong6 --full-name 教师巡测

已存在同号学生时默认跳过；加 `--reset-password` 可只更新密码（不改姓名/班级逻辑）。
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
from pathlib import Path

_API = Path(__file__).resolve().parent.parent / "services" / "api"
if str(_API) not in sys.path:
    sys.path.insert(0, str(_API))

# 与 conftest/本地 API 一致：须与运行中的 API 相同，否则密文不兼容
os.chdir(_API)

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.db import models  # noqa: F401
from app.db.models import RosterEntry, Student
from app.services.crypto import encrypt_password


async def run(args: argparse.Namespace) -> int:
    pw = (args.password or os.environ.get("STUDENT_BOOTSTRAP_PASSWORD") or "").strip()
    if not pw:
        print(
            "error: 请传入 --password 或环境变量 STUDENT_BOOTSTRAP_PASSWORD",
            file=sys.stderr,
        )
        return 1

    url = settings.database_url
    engine = create_async_engine(url)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as db:
        st_r = await db.execute(
            select(Student).where(Student.student_no == args.student_no)
        )
        existing = st_r.scalar_one_or_none()
        if existing is not None:
            if args.reset_password:
                existing.password_ciphertext = encrypt_password(pw)
                await db.commit()
                print(
                    f"ok: 已更新学号 {args.student_no!r} 的密码（学生 id {existing.id}）。"
                )
                return 0
            print(
                f"ok: 学号 {args.student_no!r} 已存在（学生 id {existing.id}），未改动。"
            )
            return 0

        re_r = await db.execute(
            select(RosterEntry).where(RosterEntry.student_no == args.student_no)
        )
        entry = re_r.scalar_one_or_none()
        if entry is None:
            entry = RosterEntry(
                id=uuid.uuid4(),
                student_no=args.student_no,
                full_name=args.full_name,
                status="pending",
                deleted_at=None,
                student_id=None,
                class_id=None,
            )
            db.add(entry)
            await db.flush()
        else:
            if entry.deleted_at is not None:
                entry.deleted_at = None
            entry.full_name = args.full_name
            if entry.student_id is not None:
                print(
                    "error: 名单行已绑定其他学生 id，数据不一致，请人工检查。",
                    file=sys.stderr,
                )
                return 1

        st = Student(
            id=uuid.uuid4(),
            student_no=args.student_no,
            full_name=args.full_name,
            password_ciphertext=encrypt_password(pw),
            must_change_password=False,
            class_id=entry.class_id,
        )
        db.add(st)
        await db.flush()
        entry.student_id = st.id
        entry.status = "bound"
        await db.commit()
        print(
            f"ok: 已创建学生账号 studentNo={args.student_no!r} fullName={args.full_name!r} id={st.id}。"
        )
    await engine.dispose()
    return 0


def main() -> None:
    p = argparse.ArgumentParser(description="Create or update a test student account.")
    p.add_argument("--student-no", required=True, help="学号，与注册一致")
    p.add_argument(
        "--full-name",
        default="教师巡测",
        help="姓名，需与之后学生端「注册」一致；已存在账号时只用于新建名单行",
    )
    p.add_argument("--password", default=None, help="登录密码，或用环境变量 STUDENT_BOOTSTRAP_PASSWORD")
    p.add_argument(
        "--reset-password",
        action="store_true",
        help="学生已存在时仅重设密码",
    )
    args = p.parse_args()
    raise SystemExit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
