"""名单：未分班池全量覆盖导入；教师端删除未分班名单行。"""

from __future__ import annotations

import re


def _bootstrap(client) -> None:
    client.post("/v1/admin/bootstrap", json={"password": "roster-replace-pw-01"})


def test_admin_import_replaces_unassigned_roster_pool(client) -> None:
    _bootstrap(client)
    r1 = client.post(
        "/v1/admin/roster/import",
        json={
            "rows": [
                {"studentNo": "R1", "fullName": "甲"},
                {"studentNo": "R2", "fullName": "乙"},
            ],
        },
    )
    assert r1.status_code == 200, r1.text
    assert r1.json()["imported"] == 2

    r2 = client.post(
        "/v1/admin/roster/import",
        json={"rows": [{"studentNo": "R3", "fullName": "丙"}]},
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["imported"] == 1

    assert client.post(
        "/teacher/do-login",
        data={"password": "roster-replace-pw-01"},
        follow_redirects=False,
    ).status_code == 303

    page = client.get("/teacher/roster", follow_redirects=True)
    assert page.status_code == 200
    assert "R3" in page.text
    assert "丙" in page.text
    assert "R1" not in page.text
    assert "R2" not in page.text


def test_admin_import_does_not_remove_class_assigned_roster(client) -> None:
    _bootstrap(client)
    client.post(
        "/v1/admin/roster/import",
        json={
            "rows": [
                {
                    "studentNo": "C1",
                    "fullName": "在班",
                    "className": "固定班",
                },
            ],
        },
    )
    client.post(
        "/v1/admin/roster/import",
        json={"rows": [{"studentNo": "N1", "fullName": "新未分"}]},
    )
    assert client.post(
        "/teacher/do-login",
        data={"password": "roster-replace-pw-01"},
        follow_redirects=False,
    ).status_code == 303
    p = client.get("/teacher/classes", follow_redirects=True)
    assert p.status_code == 200
    m = re.search(
        r'href="/teacher/classes/([0-9a-f-]{36})"',
        p.text,
    )
    assert m is not None
    d = client.get(f"/teacher/classes/{m.group(1)}", follow_redirects=True)
    assert d.status_code == 200
    assert "C1" in d.text


def test_teacher_delete_unassigned_roster_rows(client) -> None:
    _bootstrap(client)
    client.post(
        "/v1/admin/roster/import",
        json={"rows": [{"studentNo": "D1", "fullName": "待删"}]},
    )
    assert client.post(
        "/teacher/do-login",
        data={"password": "roster-replace-pw-01"},
        follow_redirects=False,
    ).status_code == 303
    p0 = client.get("/teacher/roster", follow_redirects=True)
    assert p0.status_code == 200
    m = re.search(
        r'name="entry_id"\s+value="([0-9a-f-]{36})"\s+form="roster-pending-delete-form"',
        p0.text,
    )
    assert m is not None, p0.text
    eid = m.group(1)
    del_r = client.post(
        "/teacher/roster/entries/delete",
        data={"entry_id": eid},
        follow_redirects=False,
    )
    assert del_r.status_code == 303
    assert "roster_del=1" in (del_r.headers.get("location") or "")
    p1 = client.get("/teacher/roster", follow_redirects=True)
    assert p1.status_code == 200
    assert "D1" not in p1.text
