"""`test_bootstrap_and_login`：任务 3 — 管理员首次 bootstrap 与后续登录、Cookie 会话。"""

from __future__ import annotations


def test_bootstrap_and_login(client) -> None:
    r0 = client.get("/v1/admin/me")
    assert r0.status_code == 401

    r1 = client.post("/v1/admin/bootstrap", json={"password": "first-admin-secret"})
    assert r1.status_code == 201
    assert client.cookies.get("teacher_session")

    r2 = client.get("/v1/admin/me")
    assert r2.status_code == 200
    body = r2.json()
    assert body.get("ok") is True
    assert body.get("sub") == "admin"

    r3 = client.post("/v1/admin/bootstrap", json={"password": "another-try"})
    assert r3.status_code == 403

    r4 = client.post("/v1/admin/login", json={"password": "wrong"})
    assert r4.status_code == 401

    r5 = client.post("/v1/admin/login", json={"password": "first-admin-secret"})
    assert r5.status_code == 200
    assert client.cookies.get("teacher_session")

    r6 = client.get("/v1/admin/me")
    assert r6.status_code == 200
