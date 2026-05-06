from __future__ import annotations

import httpx
import respx
from uuid import uuid4

from test_task8_student_chapters import _student_token


def _create_published_prestudy(client) -> str:
    client.post("/v1/admin/bootstrap", json={"password": "pw-123456"})
    create = client.post("/v1/admin/prestudy", json={"title": "第1章 认识AI", "order": 1})
    assert create.status_code == 201, create.text
    pid = create.json()["prestudyId"]
    publish = client.post(
        f"/v1/admin/prestudy/{pid}/publish",
        json={
            "items": [
                {
                    "id": "k1",
                    "title": "生成式AI",
                    "learningGoal": "能说明生成式AI的基本用途",
                },
                {
                    "id": "k2",
                    "title": "提示词",
                    "learningGoal": "能写出清晰的问题描述",
                },
            ]
        },
    )
    assert publish.status_code == 200, publish.text
    return pid


def _admin_drill_token(client) -> str:
    client.post(
        "/v1/admin/bootstrap",
        json={"username": "bujiuhong6", "password": "admin-secret-12345"},
    )
    r = client.post(
        "/v1/student/login",
        json={"studentNo": "bujiuhong6", "password": "admin-secret-12345"},
    )
    assert r.status_code == 200, r.text
    return r.json()["accessToken"]


def _published_prestudy_with_response(client) -> str:
    pid = _create_published_prestudy(client)
    tok = _student_token(client)
    submit = client.post(
        f"/v1/student/prestudy/{pid}/responses",
        headers={"Authorization": f"Bearer {tok}"},
        json={
            "ratings": [{"itemId": "k1", "score": 6}, {"itemId": "k2", "score": 4}],
            "feedbackText": "希望多举案例",
        },
    )
    assert submit.status_code == 200, submit.text
    return pid


def test_feedback_view_data_accepts_legacy_rating_field() -> None:
    from datetime import datetime, timezone
    from types import SimpleNamespace

    from app.routers.prestudy_admin import _feedback_view_data

    pid = uuid4()
    ch = SimpleNamespace(
        id=pid,
        title="演示",
        published_content={
            "items": [
                {"id": "k1", "title": "知识点1", "learningGoal": "目标"},
            ]
        },
    )
    resp = SimpleNamespace(
        ratings=[{"itemId": "k1", "rating": 6}],
        feedback_text="匿",
        submitted_at=datetime.now(timezone.utc),
    )
    st = SimpleNamespace()
    out = _feedback_view_data(ch, [(resp, st)])
    assert out["rating_summary"]["total"] == 1
    assert out["rating_summary"]["average"] == 6.0


def test_student_lists_published_prestudy_and_submits_feedback(client) -> None:
    pid = _create_published_prestudy(client)
    tok = _student_token(client)
    h = {"Authorization": f"Bearer {tok}"}
    lst = client.get("/v1/student/prestudy", headers=h)
    assert lst.status_code == 200
    assert lst.json()["prestudies"][0]["prestudyId"] == pid

    detail = client.get(f"/v1/student/prestudy/{pid}", headers=h)
    assert detail.status_code == 200
    assert detail.json()["prestudy"]["content"]["items"][0]["id"] == "k1"

    submit = client.post(
        f"/v1/student/prestudy/{pid}/responses",
        headers=h,
        json={
            "ratings": [{"itemId": "k1", "score": 6}, {"itemId": "k2", "score": 4}],
            "feedbackText": "希望多举案例",
        },
    )
    assert submit.status_code == 200
    assert submit.json()["submitted"] is True

    lst_after = client.get("/v1/student/prestudy", headers=h)
    assert lst_after.json()["prestudies"][0]["submitted"] is True


def test_student_prestudy_ratings_must_match_items(client) -> None:
    pid = _create_published_prestudy(client)
    tok = _student_token(client)
    bad = client.post(
        f"/v1/student/prestudy/{pid}/responses",
        headers={"Authorization": f"Bearer {tok}"},
        json={"ratings": [{"itemId": "k1", "score": 6}], "feedbackText": ""},
    )
    assert bad.status_code == 400


def test_admin_drill_prestudy_submit_does_not_persist_response(client) -> None:
    tok = _admin_drill_token(client)
    create = client.post("/v1/admin/prestudy", json={"title": "管理员演练预习", "order": 1})
    assert create.status_code == 201, create.text
    pid = create.json()["prestudyId"]
    publish = client.post(
        f"/v1/admin/prestudy/{pid}/publish",
        json={
            "items": [
                {"id": "k1", "title": "概念", "learningGoal": "能说明概念"},
                {"id": "k2", "title": "应用", "learningGoal": "能举例应用"},
            ]
        },
    )
    assert publish.status_code == 200, publish.text
    h = {"Authorization": f"Bearer {tok}"}

    submit = client.post(
        f"/v1/student/prestudy/{pid}/responses",
        headers=h,
        json={
            "ratings": [{"itemId": "k1", "score": 3}, {"itemId": "k2", "score": 4}],
            "feedbackText": "管理员演练",
        },
    )
    assert submit.status_code == 200, submit.text
    assert submit.json()["drill"] is True
    assert submit.json()["submitted"] is False

    detail = client.get(f"/v1/student/prestudy/{pid}", headers=h)
    assert detail.status_code == 200
    assert detail.json()["prestudy"]["submitted"] is False
    assert detail.json()["prestudy"]["response"] is None


def test_teacher_prestudy_feedback_page_shows_distribution(client) -> None:
    pid = _published_prestudy_with_response(client)
    page = client.get(f"/teacher/prestudy/{pid}/feedback")
    assert page.status_code == 200
    assert "学生预习情况反馈" in page.text
    assert "预习难度整体分布" in page.text
    assert "各知识点平均难度" in page.text
    assert "平均难度 / 7" in page.text
    assert "生成式AI" in page.text
    assert "希望多举案例" in page.text
    assert "生成教学建议" in page.text


@respx.mock
def test_teacher_prestudy_feedback_generates_ai_teaching_advice(
    client, respx_mock: respx.MockRouter
) -> None:
    pid = _published_prestudy_with_response(client)
    client.post(
        "/v1/admin/llm-config",
        json={
            "provider": "custom",
            "baseUrl": "https://advice.test",
            "apiKey": "k",
            "chapterModel": "chapter",
            "chatModel": "teacher-advice",
            "enabled": True,
        },
    )
    route = respx_mock.post("https://advice.test/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "**重点**：先用案例讲生成式AI。\n\n- 项一\n- 项二\n\n行内示例：`a and b`",
                        }
                    }
                ]
            },
        )
    )
    r = client.post(f"/teacher/prestudy/{pid}/feedback/advice")
    assert r.status_code == 200, r.text
    assert "教学建议" in r.text
    assert "<strong>重点</strong>" in r.text
    assert "<ul>" in r.text
    assert "<code>" in r.text
    page_reload = client.get(f"/teacher/prestudy/{pid}/feedback")
    assert page_reload.status_code == 200
    assert "<strong>重点</strong>" in page_reload.text
    assert "teaching-advice-prose" in page_reload.text
    sent = route.calls.last.request.content.decode("utf-8")
    assert "生成式AI" in sent
    assert "希望多举案例" in sent


def test_teacher_prestudy_pages_and_nav(client) -> None:
    client.post("/v1/admin/bootstrap", json={"password": "pw-123456"})
    page = client.get("/teacher/prestudy")
    assert page.status_code == 200
    assert "AI智能预习" in page.text
    dash = client.get("/teacher")
    assert "/teacher/prestudy" in dash.text


def test_prestudy_unpublish_hides_from_student(client) -> None:
    pid = _create_published_prestudy(client)
    tok = _student_token(client)
    h = {"Authorization": f"Bearer {tok}"}
    assert len(client.get("/v1/student/prestudy", headers=h).json()["prestudies"]) == 1
    unpub = client.post(f"/teacher/prestudy/{pid}/unpublish", follow_redirects=False)
    assert unpub.status_code == 303
    assert len(client.get("/v1/student/prestudy", headers=h).json()["prestudies"]) == 0


def test_prestudy_edit_page_has_dual_json_and_preview(client) -> None:
    client.post("/v1/admin/bootstrap", json={"password": "pw-123456"})
    create = client.post("/v1/admin/prestudy", json={"title": "预览页测试", "order": 0})
    assert create.status_code == 201
    pid = create.json()["prestudyId"]
    page = client.get(f"/teacher/prestudy/{pid}/edit")
    assert page.status_code == 200
    assert "预习内容JSON模板" in page.text
    assert "生成的JSON模板请粘贴在这里" in page.text
    assert "保存草稿" in page.text
    assert "发布预览" in page.text
    assert "取消发布" in page.text
