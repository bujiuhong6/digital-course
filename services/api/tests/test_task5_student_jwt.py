"""任务 5：学生登录 JWT、GET /me；教师 reveal-password + 审计。"""

from __future__ import annotations

from app.services.chapter_json import sample_published_v1


def _seed(client) -> None:
    client.post("/v1/admin/bootstrap", json={"password": "admin-secret-12345"})
    client.post(
        "/v1/admin/roster/import",
        json={"rows": [{"studentNo": "S900", "fullName": "王五"}]},
    )
    client.post(
        "/v1/student/register",
        json={"studentNo": "S900", "fullName": "王五", "password": "student-pw-99"},
    )


def test_student_login_me_and_reveal_password(client) -> None:
    _seed(client)
    bad = client.post(
        "/v1/student/login",
        json={"studentNo": "S900", "password": "wrong"},
    )
    assert bad.status_code == 401

    r = client.post(
        "/v1/student/login",
        json={"studentNo": "S900", "password": "student-pw-99"},
    )
    assert r.status_code == 200, r.text
    j = r.json()
    assert j.get("ok") is True
    assert "accessToken" in j
    assert j.get("expiresIn", 0) > 0
    token = j["accessToken"]

    me = client.get(
        "/v1/student/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me.status_code == 200
    assert me.json()["student"]["studentNo"] == "S900"

    rev = client.post(
        f"/v1/admin/students/{j['student']['studentId']}/reveal-password",
        json={"adminPassword": "admin-secret-12345"},
    )
    assert rev.status_code == 200
    assert rev.json().get("password") == "student-pw-99"

    bad_admin = client.post(
        f"/v1/admin/students/{j['student']['studentId']}/reveal-password",
        json={"adminPassword": "nope"},
    )
    assert bad_admin.status_code == 401


def test_student_login_accepts_admin_credentials_when_no_student_row(client) -> None:
    client.post("/v1/admin/bootstrap", json={"password": "admin-secret-12345"})
    bad = client.post(
        "/v1/student/login",
        json={"studentNo": "admin", "password": "wrong"},
    )
    assert bad.status_code == 401

    r = client.post(
        "/v1/student/login",
        json={"studentNo": "admin", "password": "admin-secret-12345"},
    )
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["student"]["studentNo"] == "admin"
    assert j["student"]["fullName"] == "admin"

    r2 = client.post(
        "/v1/student/login",
        json={"studentNo": "admin", "password": "admin-secret-12345"},
    )
    assert r2.status_code == 200


def test_admin_student_can_verify_and_complete_chapter(client) -> None:
    client.post("/v1/admin/bootstrap", json={"password": "admin-secret-12345"})
    created = client.post(
        "/v1/admin/chapters",
        json={"title": "管理员学生端测试", "slug": "admin-student", "order": 0, "sourceMaterial": "s"},
    )
    assert created.status_code == 201, created.text
    chapter_id = created.json()["id"]
    patched = client.patch(
        f"/v1/admin/chapters/{chapter_id}",
        json={"aiGeneratedDraft": sample_published_v1()},
    )
    assert patched.status_code == 200, patched.text
    published = client.post(f"/v1/admin/chapters/{chapter_id}/publish")
    assert published.status_code == 200, published.text

    login = client.post(
        "/v1/student/login",
        json={"studentNo": "admin", "password": "admin-secret-12345"},
    )
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['accessToken']}"}

    for cell_id, stdout in (("c1", ""), ("c2", "Hello, world")):
        verified = client.post(
            "/v1/student/cells/verify",
            json={
                "chapterId": chapter_id,
                "cellId": cell_id,
                "runOk": True,
                "stdout": stdout,
                "stderr": "",
            },
            headers=headers,
        )
        assert verified.status_code == 200, verified.text
        assert verified.json().get("passed") is True

    completed = client.post(f"/v1/student/chapters/{chapter_id}/complete", headers=headers)
    assert completed.status_code == 200, completed.text
    assert completed.json().get("alreadyCompleted") is False


def test_admin_drill_chapter_actions_do_not_persist_progress(client) -> None:
    client.post(
        "/v1/admin/bootstrap",
        json={"username": "bujiuhong6", "password": "admin-secret-12345"},
    )
    created = client.post(
        "/v1/admin/chapters",
        json={"title": "管理员演练课堂", "slug": "admin-drill", "order": 0, "sourceMaterial": "s"},
    )
    assert created.status_code == 201, created.text
    chapter_id = created.json()["id"]
    patched = client.patch(
        f"/v1/admin/chapters/{chapter_id}",
        json={"aiGeneratedDraft": sample_published_v1()},
    )
    assert patched.status_code == 200, patched.text
    published = client.post(f"/v1/admin/chapters/{chapter_id}/publish")
    assert published.status_code == 200, published.text

    login = client.post(
        "/v1/student/login",
        json={"studentNo": "bujiuhong6", "password": "admin-secret-12345"},
    )
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['accessToken']}"}

    verified = client.post(
        "/v1/student/cells/verify",
        json={
            "chapterId": chapter_id,
            "cellId": "c1",
            "runOk": True,
            "stdout": "",
            "stderr": "",
        },
        headers=headers,
    )
    assert verified.status_code == 200, verified.text
    assert verified.json()["drill"] is True
    assert verified.json()["passed"] is True

    detail = client.get(f"/v1/student/chapters/{chapter_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["chapter"]["cellsPassed"] == []

    completed = client.post(f"/v1/student/chapters/{chapter_id}/complete", headers=headers)
    assert completed.status_code == 200, completed.text
    assert completed.json()["drill"] is True
    after = client.get(f"/v1/student/chapters/{chapter_id}", headers=headers)
    assert after.json()["chapter"]["hasCompletedChapter"] is False


def test_student_login_syncs_password_when_student_no_matches_admin_username(client) -> None:
    client.post(
        "/v1/admin/bootstrap",
        json={"username": "S900", "password": "admin-plain"},
    )
    client.post(
        "/v1/admin/roster/import",
        json={"rows": [{"studentNo": "S900", "fullName": "王五"}]},
    )
    client.post(
        "/v1/student/register",
        json={"studentNo": "S900", "fullName": "王五", "password": "student-plain"},
    )
    assert (
        client.post(
            "/v1/student/login",
            json={"studentNo": "S900", "password": "admin-plain"},
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/v1/student/login",
            json={"studentNo": "S900", "password": "student-plain"},
        ).status_code
        == 401
    )
