"""任务 8：学生读已发布章、cell 验证、章完成与幂等。"""

from __future__ import annotations

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
    g = client.post(f"/v1/admin/chapters/{cid}/generate")
    assert g.status_code == 200, g.text
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
    one = client.get(f"/v1/student/chapters/{ch_id}", headers=h)
    assert one.status_code == 200
    body = one.json()["chapter"]
    assert "sourceMaterial" not in body
    assert "aiGeneratedDraft" not in body
    assert body.get("contentStatus") == "published"
    assert body.get("publishedContent", {}).get("version") == 1

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
