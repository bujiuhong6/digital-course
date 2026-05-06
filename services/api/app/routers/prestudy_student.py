from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from ..db.models import PrestudyChapter, PrestudyResponse
from ..deps import CurrentStudent, DBSession
from ..services.student_drill import is_admin_drill_student


router = APIRouter(prefix="/v1/student/prestudy", tags=["student", "prestudy"])


class PrestudyRating(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    item_id: str = Field(alias="itemId", min_length=1, max_length=128)
    score: int = Field(ge=1, le=7)


class PrestudySubmitBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    ratings: list[PrestudyRating] = Field(min_length=1, max_length=100)
    feedback_text: str | None = Field(default=None, max_length=4000, alias="feedbackText")


def _items(content: object) -> list[dict]:
    if not isinstance(content, dict) or content.get("version") != 1:
        raise HTTPException(status_code=400, detail="invalid_prestudy_content")
    items = content.get("items")
    if not isinstance(items, list) or not items:
        raise HTTPException(status_code=400, detail="invalid_prestudy_content")
    return [x for x in items if isinstance(x, dict)]


def _prestudy_to_list_item(ch: PrestudyChapter, submitted_ids: set[uuid.UUID]) -> dict:
    return {
        "prestudyId": str(ch.id),
        "title": ch.title,
        "order": ch.order,
        "submitted": ch.id in submitted_ids,
        "updatedAt": ch.updated_at.isoformat() if ch.updated_at else None,
    }


@router.get("")
async def list_prestudy(me: CurrentStudent, db: DBSession) -> dict:
    rows = (
        await db.execute(
            select(PrestudyChapter)
            .where(PrestudyChapter.status == "published")
            .order_by(PrestudyChapter.order, PrestudyChapter.title)
        )
    ).scalars().all()
    submitted_ids: set[uuid.UUID] = set()
    if not is_admin_drill_student(me):
        submitted = (
            await db.execute(select(PrestudyResponse.prestudy_id).where(PrestudyResponse.student_id == me.id))
        ).scalars().all()
        submitted_ids = set(submitted)
    return {"ok": True, "prestudies": [_prestudy_to_list_item(x, submitted_ids) for x in rows]}


@router.get("/{prestudy_id}")
async def get_prestudy(me: CurrentStudent, db: DBSession, prestudy_id: uuid.UUID) -> dict:
    ch = (
        await db.execute(
            select(PrestudyChapter).where(
                PrestudyChapter.id == prestudy_id,
                PrestudyChapter.status == "published",
            )
        )
    ).scalar_one_or_none()
    if ch is None or ch.published_content is None:
        raise HTTPException(status_code=404, detail="prestudy_not_found")
    resp = None
    if not is_admin_drill_student(me):
        resp = (
            await db.execute(
                select(PrestudyResponse).where(
                    PrestudyResponse.prestudy_id == ch.id,
                    PrestudyResponse.student_id == me.id,
                )
            )
        ).scalar_one_or_none()
    return {
        "ok": True,
        "prestudy": {
            "prestudyId": str(ch.id),
            "title": ch.title,
            "content": ch.published_content,
            "submitted": resp is not None,
            "response": {
                "ratings": resp.ratings,
                "feedbackText": resp.feedback_text,
                "submittedAt": resp.submitted_at.isoformat(),
            }
            if resp is not None
            else None,
        },
    }


@router.post("/{prestudy_id}/responses")
async def submit_prestudy_response(
    me: CurrentStudent,
    db: DBSession,
    prestudy_id: uuid.UUID,
    body: PrestudySubmitBody,
) -> dict:
    ch = (
        await db.execute(
            select(PrestudyChapter).where(
                PrestudyChapter.id == prestudy_id,
                PrestudyChapter.status == "published",
            )
        )
    ).scalar_one_or_none()
    if ch is None or ch.published_content is None:
        raise HTTPException(status_code=404, detail="prestudy_not_found")
    expected = {str(x.get("id")) for x in _items(ch.published_content)}
    received = {x.item_id for x in body.ratings}
    if received != expected or len(received) != len(body.ratings):
        raise HTTPException(status_code=400, detail="ratings_must_match_items")
    if is_admin_drill_student(me):
        return {"ok": True, "submitted": False, "drill": True}
    existing = (
        await db.execute(
            select(PrestudyResponse).where(
                PrestudyResponse.student_id == me.id,
                PrestudyResponse.prestudy_id == prestudy_id,
            )
        )
    ).scalar_one_or_none()
    ratings = [{"itemId": x.item_id, "score": x.score} for x in body.ratings]
    feedback = (body.feedback_text or "").strip() or None
    if existing is None:
        existing = PrestudyResponse(
            student_id=me.id,
            prestudy_id=prestudy_id,
            ratings=ratings,
            feedback_text=feedback,
        )
        db.add(existing)
    else:
        existing.ratings = ratings
        existing.feedback_text = feedback
    await db.flush()
    return {"ok": True, "submitted": True}
