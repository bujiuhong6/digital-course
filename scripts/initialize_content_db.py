from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select


REPO_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = REPO_ROOT / "services" / "api"
DEFAULT_SEED = API_ROOT / "seeds" / "chapters.json"
sys.path.insert(0, str(API_ROOT))
os.chdir(API_ROOT)

from app.db import dispose_engine, get_async_session_maker  # noqa: E402
from app.db.models import (  # noqa: E402
    AdminAudit,
    AdminConfig,
    CellVerification,
    Chapter,
    ChapterCompletion,
    Class,
    RosterEntry,
    Student,
)


def _parse_uuid(value: str | None) -> uuid.UUID | None:
    if not value:
        return None
    value = value.strip()
    return uuid.UUID(hex=value) if len(value) == 32 else uuid.UUID(value)


def _load_seed(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    chapters = payload.get("chapters")
    if not isinstance(chapters, list):
        raise ValueError(f"{path} must contain a top-level chapters list")
    return chapters


async def initialize(seed_path: Path, *, keep_runtime: bool, prune_extra_chapters: bool) -> None:
    chapters = _load_seed(seed_path)
    slugs = {str(ch["slug"]) for ch in chapters}
    session_maker = get_async_session_maker()
    async with session_maker() as session:
        if not keep_runtime:
            for model in (
                AdminAudit,
                ChapterCompletion,
                CellVerification,
                RosterEntry,
                Student,
                Class,
                AdminConfig,
            ):
                await session.execute(delete(model))

        if prune_extra_chapters and slugs:
            await session.execute(delete(Chapter).where(Chapter.slug.not_in(slugs)))

        for item in chapters:
            slug = str(item["slug"])
            existing = (
                await session.execute(select(Chapter).where(Chapter.slug == slug))
            ).scalar_one_or_none()
            chapter = existing or Chapter(id=_parse_uuid(item.get("id")) or uuid.uuid4(), slug=slug)
            chapter.title = str(item["title"])
            chapter.order = int(item.get("order", 0))
            chapter.content_status = str(item.get("content_status") or "published")
            chapter.source_material = item.get("source_material")
            chapter.ai_generated_draft = item.get("ai_generated_draft")
            chapter.ai_generated_raw = item.get("ai_generated_raw")
            chapter.generator_prompt_version = item.get("generator_prompt_version")
            chapter.generator_model = item.get("generator_model")
            chapter.published_content = item.get("published_content")
            session.add(chapter)

        await session.commit()
    await dispose_engine()
    print(
        f"initialized {len(chapters)} chapters"
        + ("; runtime data kept" if keep_runtime else "; runtime data cleared")
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Seed chapter practice content and clear runtime data such as admin account, "
            "students, roster, classes, and progress."
        )
    )
    parser.add_argument("--seed", type=Path, default=DEFAULT_SEED)
    parser.add_argument(
        "--keep-runtime",
        action="store_true",
        help="Keep admin, students, roster, classes, and progress.",
    )
    parser.add_argument(
        "--prune-extra-chapters",
        action="store_true",
        help="Delete chapters whose slugs are absent from the seed file.",
    )
    args = parser.parse_args()
    asyncio.run(
        initialize(
            args.seed,
            keep_runtime=args.keep_runtime,
            prune_extra_chapters=args.prune_extra_chapters,
        )
    )


if __name__ == "__main__":
    main()
