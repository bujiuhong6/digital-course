"""任务 5：学生登录 JWT、GET /me；教师 reveal-password + 审计。"""

from __future__ import annotations


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
