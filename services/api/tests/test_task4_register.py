"""任务 4：名单导入 + 学生注册，不匹配与成功两种路径。"""

from __future__ import annotations


def _bootstrap_and_login(client) -> None:
    client.post("/v1/admin/bootstrap", json={"password": "admin-secret-12345"})


def _import_one(client) -> None:
    r = client.post(
        "/v1/admin/roster/import",
        json={
            "rows": [
                {"studentNo": "S001", "fullName": "张三", "className": "测试班"},
            ],
        },
    )
    assert r.status_code == 200, r.text
    assert r.json().get("imported") == 1


def test_register_roster_mismatch_and_success(client) -> None:
    _bootstrap_and_login(client)
    _import_one(client)
    r_bad = client.post(
        "/v1/student/register",
        json={"studentNo": "S001", "fullName": "李四", "password": "pw12345678"},
    )
    assert r_bad.status_code == 400
    assert r_bad.json().get("detail") == "roster_name_mismatch"

    r_ok = client.post(
        "/v1/student/register",
        json={"studentNo": "S001", "fullName": "张三", "password": "pw12345678"},
    )
    assert r_ok.status_code == 201, r_ok.text
    assert r_ok.json().get("ok") is True
    assert "studentId" in r_ok.json()

    r_dup = client.post(
        "/v1/student/register",
        json={"studentNo": "S001", "fullName": "张三", "password": "other"},
    )
    assert r_dup.status_code == 409
