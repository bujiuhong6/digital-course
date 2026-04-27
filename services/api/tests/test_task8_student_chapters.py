"""任务 8：学生读已发布章、cell 验证、章完成与幂等。"""

from __future__ import annotations

from app.services.chapter_json import sample_published_v1


def _admin_session(client) -> None:
    client.post("/v1/admin/bootstrap", json={"password": "admin-pw-888"})


def _published_chapter_id(client) -> str:
    _admin_session(client)
    r = client.post(
        "/v1/admin/chapters",
        json={"title": "L8", "slug": "l8", "order": 0, "sourceMaterial": "s"},
    )
    assert r.status_code == 201
    cid = r.json()["id"]
    patch = client.patch(
        f"/v1/admin/chapters/{cid}",
        json={"aiGeneratedDraft": sample_published_v1()},
    )
    assert patch.status_code == 200, patch.text
    p = client.post(f"/v1/admin/chapters/{cid}/publish")
    assert p.status_code == 200, p.text
    return cid


def _student_token(client) -> str:
    client.post(
        "/v1/admin/roster/import",
        json={"rows": [{"studentNo": "L8S", "fullName": "八测试"}]},
    )
    r = client.post(
        "/v1/student/register",
        json={"studentNo": "L8S", "fullName": "八测试", "password": "spw00000000"},
    )
    assert r.status_code == 201, r.text
    lr = client.post(
        "/v1/student/login",
        json={"studentNo": "L8S", "password": "spw00000000"},
    )
    assert lr.status_code == 200
    return lr.json()["accessToken"]


def test_task8_list_get_verify_complete(client) -> None:
    ch_id = _published_chapter_id(client)
    tok = _student_token(client)
    h = {"Authorization": f"Bearer {tok}"}

    lst = client.get("/v1/student/chapters", headers=h)
    assert lst.status_code == 200
    assert len(lst.json()["chapters"]) == 1
    assert lst.json()["chapters"][0].get("practiceStatus") == "pending"
    one = client.get(f"/v1/student/chapters/{ch_id}", headers=h)
    assert one.status_code == 200
    body = one.json()["chapter"]
    assert "sourceMaterial" not in body
    assert "aiGeneratedDraft" not in body
    assert body.get("contentStatus") == "published"
    assert body.get("publishedContent", {}).get("version") == 1
    assert body.get("hasCompletedChapter") is False
    assert body.get("cellsPassed") == []

    bad_complete = client.post(
        f"/v1/student/chapters/{ch_id}/complete", headers=h
    )
    assert bad_complete.status_code == 400

    c1 = client.post(
        "/v1/student/cells/verify",
        json={
            "chapterId": ch_id,
            "cellId": "c1",
            "runOk": True,
            "stdout": "",
            "stderr": "",
        },
        headers=h,
    )
    assert c1.json().get("passed") is True

    lst_mid = client.get("/v1/student/chapters", headers=h)
    assert lst_mid.json()["chapters"][0].get("practiceStatus") == "inProgress"

    c2_bad = client.post(
        "/v1/student/cells/verify",
        json={
            "chapterId": ch_id,
            "cellId": "c2",
            "runOk": True,
            "stdout": "no",
            "stderr": "",
        },
        headers=h,
    )
    assert c2_bad.json().get("passed") is False

    c2_ok = client.post(
        "/v1/student/cells/verify",
        json={
            "chapterId": ch_id,
            "cellId": "c2",
            "runOk": True,
            "stdout": "Hello, world",
            "stderr": "",
        },
        headers=h,
    )
    assert c2_ok.json().get("passed") is True

    ch_with_passes = client.get(f"/v1/student/chapters/{ch_id}", headers=h).json()[
        "chapter"
    ]
    assert set(ch_with_passes.get("cellsPassed", [])) == {"c1", "c2"}

    comp = client.post(
        f"/v1/student/chapters/{ch_id}/complete", headers=h
    )
    assert comp.status_code == 200
    assert comp.json().get("alreadyCompleted") is False

    comp2 = client.post(
        f"/v1/student/chapters/{ch_id}/complete", headers=h
    )
    assert comp2.status_code == 200
    assert comp2.json().get("alreadyCompleted") is True

    lst_done = client.get("/v1/student/chapters", headers=h)
    assert lst_done.json()["chapters"][0].get("practiceStatus") == "submitted"
    ch_one = client.get(f"/v1/student/chapters/{ch_id}", headers=h).json()["chapter"]
    assert ch_one.get("hasCompletedChapter") is True

    un = client.post(f"/v1/student/chapters/{ch_id}/uncomplete", headers=h)
    assert un.status_code == 200
    assert un.json().get("ok") is True
    assert un.json().get("withdrawn") is True

    lst_back = client.get("/v1/student/chapters", headers=h)
    assert lst_back.json()["chapters"][0].get("practiceStatus") == "inProgress"
    ch_two = client.get(f"/v1/student/chapters/{ch_id}", headers=h).json()["chapter"]
    assert ch_two.get("hasCompletedChapter") is False

    un2 = client.post(f"/v1/student/chapters/{ch_id}/uncomplete", headers=h)
    assert un2.status_code == 200
    j2 = un2.json()
    assert j2.get("ok") is False
    assert j2.get("withdrawn") is False
    assert j2.get("detail") == "not_completed"


def test_task8_uncomplete_requires_auth(client) -> None:
    ch_id = _published_chapter_id(client)
    r = client.post(f"/v1/student/chapters/{ch_id}/uncomplete")
    assert r.status_code == 401


def test_task8_uncomplete_unknown_chapter(client) -> None:
    _published_chapter_id(client)
    tok = _student_token(client)
    h = {"Authorization": f"Bearer {tok}"}
    bad_id = "00000000-0000-0000-0000-000000000099"
    r = client.post(f"/v1/student/chapters/{bad_id}/uncomplete", headers=h)
    assert r.status_code == 404
