from __future__ import annotations

import httpx
import respx

from test_task8_student_chapters import _student_token


def _content() -> dict:
    return {
        "questions": [
            {
                "id": "mc1",
                "type": "singleChoice",
                "prompt": "Q1",
                "choices": [{"id": "A", "text": "A"}, {"id": "B", "text": "B"}],
                "answer": "A",
                "points": 10,
            },
            {
                "id": "mc2",
                "type": "singleChoice",
                "prompt": "Q2",
                "choices": [{"id": "A", "text": "A"}, {"id": "B", "text": "B"}],
                "answer": "A",
                "points": 10,
            },
            {
                "id": "mc3",
                "type": "singleChoice",
                "prompt": "Q3",
                "choices": [{"id": "A", "text": "A"}, {"id": "B", "text": "B"}],
                "answer": "A",
                "points": 10,
            },
            {
                "id": "subj1",
                "type": "subjective",
                "prompt": "解释概念",
                "referenceAnswer": "标准答案",
                "points": 30,
            },
            {
                "id": "code1",
                "type": "code",
                "prompt": "写代码",
                "starterCode": "import math\n\n",
                "referenceAnswer": "print('hello')",
                "rubric": "正确性和可读性",
                "points": 40,
            },
        ]
    }


def _save_llm_config(client, base_url: str = "https://grade.test") -> None:
    client.post(
        "/v1/admin/llm-config",
        json={
            "provider": "custom",
            "baseUrl": base_url,
            "apiKey": "k",
            "chapterModel": "chapter",
            "chatModel": "grader",
            "enabled": True,
        },
    )


def _published_post_exercise(client) -> str:
    client.post("/v1/admin/bootstrap", json={"password": "pw-123456"})
    create = client.post("/v1/admin/post-exercises", json={"title": "课后作业1", "order": 1})
    assert create.status_code == 201, create.text
    eid = create.json()["exerciseId"]
    publish = client.post(f"/v1/admin/post-exercises/{eid}/publish", json=_content())
    assert publish.status_code == 200, publish.text
    return eid


@respx.mock
def test_post_exercise_submit_gets_ai_score(client, respx_mock: respx.MockRouter) -> None:
    eid = _published_post_exercise(client)
    _save_llm_config(client)
    tok = _student_token(client)
    respx_mock.post("https://grade.test/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"score": 86, "feedback": "整体正确"}'}}]},
        )
    )
    r = client.post(
        f"/v1/student/post-exercises/{eid}/submit",
        headers={"Authorization": f"Bearer {tok}"},
        json={
            "answers": [
                {"questionId": "mc1", "choiceId": "A"},
                {"questionId": "mc2", "choiceId": "A"},
                {"questionId": "mc3", "choiceId": "A"},
                {"questionId": "subj1", "text": "我的理解"},
                {"questionId": "code1", "code": 'print("hello")'},
            ]
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["score"] == 86


def test_student_post_exercise_response_hides_solution_fields(client) -> None:
    eid = _published_post_exercise(client)
    tok = _student_token(client)
    r = client.get(
        f"/v1/student/post-exercises/{eid}",
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 200
    text = r.text
    assert "referenceAnswer" not in text
    assert "rubric" not in text
    assert '"answer"' not in text
    questions = r.json()["exercise"]["content"]["questions"]
    code_question = next(q for q in questions if q["type"] == "code")
    assert code_question["starterCode"] == "import math\n\n"


@respx.mock
def test_post_exercise_chat_uses_sanitized_context(client, respx_mock: respx.MockRouter) -> None:
    eid = _published_post_exercise(client)
    _save_llm_config(client)
    tok = _student_token(client)
    route = respx_mock.post("https://grade.test/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={"choices": [{"message": {"content": "hint"}}]},
        )
    )
    r = client.post(
        f"/v1/student/post-exercises/{eid}/chat",
        headers={"Authorization": f"Bearer {tok}"},
        json={
            "questionId": "code1",
            "currentAnswer": "print('x')",
            "messages": [{"role": "user", "content": "提示一下"}],
        },
    )
    assert r.status_code == 200, r.text
    sent = route.calls.last.request.content.decode("utf-8")
    assert "referenceAnswer" not in sent
    assert "rubric" not in sent
    assert '"answer"' not in sent


def test_post_exercise_submit_rejects_duplicate_or_invalid_answers(client) -> None:
    eid = _published_post_exercise(client)
    tok = _student_token(client)
    h = {"Authorization": f"Bearer {tok}"}
    dup = client.post(
        f"/v1/student/post-exercises/{eid}/submit",
        headers=h,
        json={
            "answers": [
                {"questionId": "mc1", "choiceId": "A"},
                {"questionId": "mc1", "choiceId": "A"},
                {"questionId": "mc3", "choiceId": "A"},
                {"questionId": "subj1", "text": "x"},
                {"questionId": "code1", "code": "print(1)"},
            ]
        },
    )
    assert dup.status_code == 400
    bad_choice = client.post(
        f"/v1/student/post-exercises/{eid}/submit",
        headers=h,
        json={
            "answers": [
                {"questionId": "mc1", "choiceId": "Z"},
                {"questionId": "mc2", "choiceId": "A"},
                {"questionId": "mc3", "choiceId": "A"},
                {"questionId": "subj1", "text": "x"},
                {"questionId": "code1", "code": "print(1)"},
            ]
        },
    )
    assert bad_choice.status_code == 400


def _seed_two_post_exercise_submissions(client) -> None:
    eid = _published_post_exercise(client)
    _save_llm_config(client)
    tok = _student_token(client)
    import respx as _respx

    with _respx.mock:
        _respx.post("https://grade.test/v1/chat/completions").mock(
            return_value=httpx.Response(
                200,
                json={"choices": [{"message": {"content": '{"score": 86, "feedback": "整体正确"}'}}]},
            )
        )
        client.post(
            f"/v1/student/post-exercises/{eid}/submit",
            headers={"Authorization": f"Bearer {tok}"},
            json={
                "answers": [
                    {"questionId": "mc1", "choiceId": "A"},
                    {"questionId": "mc2", "choiceId": "A"},
                    {"questionId": "mc3", "choiceId": "A"},
                    {"questionId": "subj1", "text": "我的理解"},
                    {"questionId": "code1", "code": 'print("hello")'},
                ]
            },
        )


def test_teacher_exports_all_post_exercise_scores_csv(client) -> None:
    _seed_two_post_exercise_submissions(client)
    r = client.get("/teacher/post-exercises/submissions.csv")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert r.content.startswith(b"\xef\xbb\xbf")
    text = r.content.decode("utf-8-sig")
    assert "studentNo,fullName,exerciseTitle,score,submittedAt" in text
    assert "86" in text


def test_teacher_post_exercise_pages_and_nav(client) -> None:
    client.post("/v1/admin/bootstrap", json={"password": "pw-123456"})
    page = client.get("/teacher/post-exercises")
    assert page.status_code == 200
    assert "AI课后作业" in page.text
    dash = client.get("/teacher")
    assert "/teacher/post-exercises" in dash.text


def test_teacher_post_exercise_edit_page_has_dual_json_and_preview(client) -> None:
    client.post("/v1/admin/bootstrap", json={"password": "pw-123456"})
    create = client.post("/v1/admin/post-exercises", json={"title": "布局测试", "order": 0})
    assert create.status_code == 201
    eid = create.json()["exerciseId"]
    page = client.get(f"/teacher/post-exercises/{eid}/edit")
    assert page.status_code == 200
    assert "课后作业JSON模板" in page.text
    assert "生成的JSON模板请粘贴在这里" in page.text
    assert "课后作业发布" in page.text
    assert "保存草稿" in page.text
    assert "发布预览" in page.text
    assert "取消发布" in page.text
    assert page.text.count("返回课后作业列表") >= 2


def test_teacher_post_exercise_preview_includes_answers(client) -> None:
    client.post("/v1/admin/bootstrap", json={"password": "pw-123456"})
    create = client.post("/v1/admin/post-exercises", json={"title": "答案预览测试", "order": 0})
    assert create.status_code == 201
    eid = create.json()["exerciseId"]
    page = client.get(f"/teacher/post-exercises/{eid}/edit")
    assert page.status_code == 200
    assert "参考答案" in page.text
    assert "评分要点" in page.text
