"""教师端：批量取消注册，删除学生账号并恢复名单为可再次注册。"""

from __future__ import annotations


def _bootstrap_and_teacher(client) -> None:
    client.post("/v1/admin/bootstrap", json={"password": "bulk-unreg-pw-99"})


def test_bulk_unregister_removes_login_and_allows_re_register(client) -> None:
    _bootstrap_and_teacher(client)
    client.post(
        "/v1/admin/roster/import",
        json={
            "rows": [
                {"studentNo": "BU1", "fullName": "张三", "className": ""},
            ],
        },
    )
    reg = client.post(
        "/v1/student/register",
        json={
            "studentNo": "BU1",
            "fullName": "张三",
            "password": "secretBU1x",
        },
    )
    assert reg.status_code == 201, reg.text
    sid = reg.json()["studentId"]

    login1 = client.post(
        "/v1/student/login",
        json={"studentNo": "BU1", "password": "secretBU1x"},
    )
    assert login1.status_code == 200, login1.text

    assert client.post(
        "/teacher/do-login",
        data={"password": "bulk-unreg-pw-99"},
        follow_redirects=False,
    ).status_code == 303

    r = client.post(
        "/teacher/students/bulk-unregister",
        data={"student_ids": [sid], "return_class_id": ""},
        follow_redirects=False,
    )
    assert r.status_code == 303
    loc = r.headers.get("location") or ""
    assert "unreg_ok=1" in loc

    login_fail = client.post(
        "/v1/student/login",
        json={"studentNo": "BU1", "password": "secretBU1x"},
    )
    assert login_fail.status_code == 401

    reg2 = client.post(
        "/v1/student/register",
        json={
            "studentNo": "BU1",
            "fullName": "张三",
            "password": "newpassBU1y",
        },
    )
    assert reg2.status_code == 201, reg2.text
    login3 = client.post(
        "/v1/student/login",
        json={"studentNo": "BU1", "password": "newpassBU1y"},
    )
    assert login3.status_code == 200
    assert login3.json().get("ok") is True


def test_bulk_unregister_empty_selection_redirects_error(client) -> None:
    _bootstrap_and_teacher(client)
    assert client.post(
        "/teacher/do-login",
        data={"password": "bulk-unreg-pw-99"},
        follow_redirects=False,
    ).status_code == 303
    r = client.post(
        "/teacher/students/bulk-unregister",
        data={},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert "err=unreg_none" in (r.headers.get("location") or "")
