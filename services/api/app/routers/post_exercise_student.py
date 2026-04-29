from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from ..config import merge_openai_compat_llm_headers, openai_compat_chat_completions_url
from ..db.models import PostExercise, PostExerciseSubmission
from ..deps import CurrentStudent, DBSession
from ..services.llm_config import get_effective_llm_config
from ..services.post_exercise_grader import grade_post_exercise


router = APIRouter(prefix="/v1/student/post-exercises", tags=["student", "post-exercises"])


class ExerciseAnswer(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    question_id: str = Field(alias="questionId", min_length=1, max_length=128)
    choice_id: str | None = Field(default=None, alias="choiceId", max_length=128)
    text: str | None = Field(default=None, max_length=100_000)
    code: str | None = Field(default=None, max_length=100_000)


class ExerciseSubmitBody(BaseModel):
    answers: list[ExerciseAnswer] = Field(min_length=1, max_length=20)


class PostExerciseChatBody(BaseModel):
    messages: list[dict] = Field(min_length=1, max_length=100)
    question_id: str | None = Field(default=None, alias="questionId", max_length=128)
    current_answer: str | None = Field(default=None, alias="currentAnswer", max_length=100_000)


def _submission_to_dict(sub: PostExerciseSubmission | None) -> dict | None:
    if sub is None:
        return None
    return {
        "score": sub.score,
        "feedback": sub.ai_feedback,
        "submittedAt": sub.submitted_at.isoformat(),
        "answers": sub.answers,
    }


def _student_safe_content(content: dict) -> dict:
    questions = []
    for raw in content.get("questions", []):
        if not isinstance(raw, dict):
            continue
        q = {
            "id": raw.get("id"),
            "type": raw.get("type"),
            "prompt": raw.get("prompt"),
            "points": raw.get("points"),
        }
        if raw.get("type") == "singleChoice":
            q["choices"] = raw.get("choices", [])
        if raw.get("type") == "code" and raw.get("starterCode"):
            q["starterCode"] = raw.get("starterCode")
        questions.append(q)
    return {"version": 1, "questions": questions}


def _validate_answers(content: dict, answers: list[dict]) -> None:
    questions = content.get("questions", [])
    qmap = {str(q.get("id")): q for q in questions if isinstance(q, dict)}
    answer_ids = [str(a.get("questionId")) for a in answers]
    if set(answer_ids) != set(qmap) or len(answer_ids) != len(set(answer_ids)):
        raise HTTPException(status_code=400, detail="answers_must_match_questions")
    for answer in answers:
        q = qmap[str(answer.get("questionId"))]
        qtype = q.get("type")
        if qtype == "singleChoice":
            valid = {str(c.get("id")) for c in q.get("choices", []) if isinstance(c, dict)}
            if not answer.get("choiceId") or str(answer.get("choiceId")) not in valid:
                raise HTTPException(status_code=400, detail="invalid_choice_answer")
        elif qtype == "subjective":
            if not str(answer.get("text") or "").strip():
                raise HTTPException(status_code=400, detail="subjective_answer_required")
        elif qtype == "code":
            if not str(answer.get("code") or "").strip():
                raise HTTPException(status_code=400, detail="code_answer_required")
        else:
            raise HTTPException(status_code=400, detail="unknown_question_type")


async def _get_published_or_404(db: DBSession, exercise_id: uuid.UUID) -> PostExercise:
    row = (
        await db.execute(
            select(PostExercise).where(
                PostExercise.id == exercise_id,
                PostExercise.status == "published",
            )
        )
    ).scalar_one_or_none()
    if row is None or row.published_content is None:
        raise HTTPException(status_code=404, detail="post_exercise_not_found")
    return row


@router.get("")
async def list_post_exercises(me: CurrentStudent, db: DBSession) -> dict:
    rows = (
        await db.execute(
            select(PostExercise)
            .where(PostExercise.status == "published")
            .order_by(PostExercise.order, PostExercise.title)
        )
    ).scalars().all()
    submitted = (
        await db.execute(
            select(PostExerciseSubmission.exercise_id).where(PostExerciseSubmission.student_id == me.id)
        )
    ).scalars().all()
    submitted_ids = set(submitted)
    return {
        "ok": True,
        "exercises": [
            {
                "exerciseId": str(x.id),
                "title": x.title,
                "order": x.order,
                "submitted": x.id in submitted_ids,
                "updatedAt": x.updated_at.isoformat() if x.updated_at else None,
            }
            for x in rows
        ],
    }


@router.get("/{exercise_id}")
async def get_post_exercise(me: CurrentStudent, db: DBSession, exercise_id: uuid.UUID) -> dict:
    ex = await _get_published_or_404(db, exercise_id)
    sub = (
        await db.execute(
            select(PostExerciseSubmission).where(
                PostExerciseSubmission.exercise_id == ex.id,
                PostExerciseSubmission.student_id == me.id,
            )
        )
    ).scalar_one_or_none()
    return {
        "ok": True,
        "exercise": {
            "exerciseId": str(ex.id),
            "title": ex.title,
            "content": _student_safe_content(ex.published_content),
            "submitted": sub is not None,
            "submission": _submission_to_dict(sub),
        },
    }


@router.post("/{exercise_id}/submit")
async def submit_post_exercise(
    me: CurrentStudent,
    db: DBSession,
    exercise_id: uuid.UUID,
    body: ExerciseSubmitBody,
) -> dict:
    ex = await _get_published_or_404(db, exercise_id)
    answers = [
        {
            "questionId": a.question_id,
            "choiceId": a.choice_id,
            "text": a.text,
            "code": a.code,
        }
        for a in body.answers
    ]
    _validate_answers(ex.published_content, answers)
    score, feedback, raw = await grade_post_exercise(db, content=ex.published_content, answers=answers)
    existing = (
        await db.execute(
            select(PostExerciseSubmission).where(
                PostExerciseSubmission.student_id == me.id,
                PostExerciseSubmission.exercise_id == ex.id,
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        existing = PostExerciseSubmission(
            student_id=me.id,
            exercise_id=ex.id,
            answers=answers,
            score=score,
            ai_feedback=feedback,
            graded_raw=raw,
        )
        db.add(existing)
    else:
        existing.answers = answers
        existing.score = score
        existing.ai_feedback = feedback
        existing.graded_raw = raw
        existing.submitted_at = datetime.now(timezone.utc)
    await db.flush()
    return {"ok": True, "score": score, "feedback": feedback}


@router.post("/{exercise_id}/chat")
async def post_exercise_chat(
    _me: CurrentStudent,
    db: DBSession,
    exercise_id: uuid.UUID,
    body: PostExerciseChatBody,
):
    ex = await _get_published_or_404(db, exercise_id)
    cfg = await get_effective_llm_config(db)
    if not cfg.base_url:
        return {"ok": True, "mock": True, "message": "尚未连接 AI 模型。"}
    url = openai_compat_chat_completions_url(cfg.base_url)
    headers = {"Content-Type": "application/json"}
    if cfg.api_key:
        headers["Authorization"] = f"Bearer {cfg.api_key}"
    headers = merge_openai_compat_llm_headers(cfg.base_url, headers)
    context = json.dumps(_student_safe_content(ex.published_content), ensure_ascii=False)[:12000]
    user_msgs = "\n".join(
        f"{str(m.get('role', 'user'))}: {str(m.get('content', ''))[:4000]}"
        for m in body.messages[-20:]
    )
    prompt = (
        f"课后作业上下文：\n{context}\n\n"
        f"当前题目：{body.question_id or '未指定'}\n"
        f"学生当前答案：\n{body.current_answer or ''}\n\n"
        f"对话：\n{user_msgs}"
    )
    req_body = {
        "model": cfg.chat_model,
        "messages": [
            {
                "role": "system",
                "content": "你是课后作业辅导助手。给提示和引导，避免直接替学生完成整份答案。",
            },
            {"role": "user", "content": prompt},
        ],
    }
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, json=req_body, headers=headers)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"upstream_unavailable: {e!s}"[:500]) from e
    if resp.status_code >= 400:
        raise HTTPException(status_code=502, detail=resp.text[:1000] or f"http {resp.status_code}")
    try:
        text = resp.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise HTTPException(status_code=502, detail=f"bad upstream shape: {e!s}") from e
    return {"ok": True, "message": text, "at": datetime.now(timezone.utc).isoformat()}
