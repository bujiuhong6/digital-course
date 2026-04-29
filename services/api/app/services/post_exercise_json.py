from __future__ import annotations

from fastapi import HTTPException


def validate_post_exercise_content(obj: object) -> dict:
    if isinstance(obj, list):
        obj = {"version": 1, "questions": obj}
    if isinstance(obj, dict) and "questions" in obj and "version" not in obj:
        obj = {"version": 1, **obj}
    if not isinstance(obj, dict) or obj.get("version") != 1:
        raise HTTPException(status_code=400, detail="post_exercise_version_must_be_1")
    questions = obj.get("questions")
    if not isinstance(questions, list):
        raise HTTPException(status_code=400, detail="questions_required")
    clean: list[dict] = []
    seen: set[str] = set()
    counts = {"singleChoice": 0, "subjective": 0, "code": 0}
    for raw in questions:
        if not isinstance(raw, dict):
            raise HTTPException(status_code=400, detail="question_must_be_object")
        qid = str(raw.get("id") or "").strip()
        qtype = str(raw.get("type") or "").strip()
        prompt = str(raw.get("prompt") or "").strip()
        points = int(raw.get("points") or 0)
        if not qid or qid in seen or qtype not in counts or not prompt or points <= 0:
            raise HTTPException(status_code=400, detail="invalid_question")
        seen.add(qid)
        counts[qtype] += 1
        q = {"id": qid, "type": qtype, "prompt": prompt, "points": points}
        if qtype == "singleChoice":
            choices = raw.get("choices")
            answer = str(raw.get("answer") or "").strip()
            if not isinstance(choices, list) or len(choices) < 2 or not answer:
                raise HTTPException(status_code=400, detail="invalid_single_choice")
            q["choices"] = [
                {"id": str(c.get("id") or "").strip(), "text": str(c.get("text") or "").strip()}
                for c in choices
                if isinstance(c, dict)
            ]
            if len(q["choices"]) != len(choices) or answer not in {c["id"] for c in q["choices"]}:
                raise HTTPException(status_code=400, detail="invalid_single_choice")
            q["answer"] = answer
        else:
            q["referenceAnswer"] = str(raw.get("referenceAnswer") or "").strip()
            q["rubric"] = str(raw.get("rubric") or "").strip()
            if qtype == "code":
                starter = str(raw.get("starterCode") or raw.get("starter_code") or "")
                if starter:
                    q["starterCode"] = starter
        clean.append(q)
    if not (3 <= counts["singleChoice"] <= 5):
        raise HTTPException(status_code=400, detail="single_choice_count_must_be_3_to_5")
    if counts["subjective"] != 1:
        raise HTTPException(status_code=400, detail="subjective_count_must_be_1")
    if not (1 <= counts["code"] <= 2):
        raise HTTPException(status_code=400, detail="code_count_must_be_1_to_2")
    return {"version": 1, "questions": clean}


def default_post_exercise_content() -> dict:
    return {
        "version": 1,
        "questions": [
            {
                "id": "mc1",
                "type": "singleChoice",
                "prompt": "以下哪项最符合本章核心概念？",
                "choices": [{"id": "A", "text": "选项A"}, {"id": "B", "text": "选项B"}],
                "answer": "A",
                "points": 10,
            },
            {
                "id": "mc2",
                "type": "singleChoice",
                "prompt": "请选择正确说法。",
                "choices": [{"id": "A", "text": "选项A"}, {"id": "B", "text": "选项B"}],
                "answer": "A",
                "points": 10,
            },
            {
                "id": "mc3",
                "type": "singleChoice",
                "prompt": "请选择最佳实践。",
                "choices": [{"id": "A", "text": "选项A"}, {"id": "B", "text": "选项B"}],
                "answer": "A",
                "points": 10,
            },
            {
                "id": "subj1",
                "type": "subjective",
                "prompt": "请用自己的话解释本章重点。",
                "referenceAnswer": "围绕核心概念、应用场景和注意事项作答。",
                "points": 30,
            },
            {
                "id": "code1",
                "type": "code",
                "prompt": "请写出解决问题的 Python 代码。",
                "starterCode": "# 可在这里预置 import、数据或函数框架\n",
                "referenceAnswer": "代码能清晰表达解题思路。",
                "rubric": "关注正确性、可读性和关键步骤。",
                "points": 40,
            },
        ],
    }
