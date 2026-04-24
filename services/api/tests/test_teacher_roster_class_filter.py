"""教师端：已分班学生不出现在名单「当前名单行 / 已注册未分班」；「移除班级」可回到名单。"""

from __future__ import annotations

import re


def _bootstrap_and_teacher(client) -> None:
    client.post("/v1/admin/bootstrap", json={"password": "roster-class-pw-01"})


def test_roster_hides_class_assigned_and_remove_from_class_restores(
    client,
) -> None:
    _bootstrap_and_teacher(client)
    client.post(
        "/v1/admin/roster/import",
        json={
            "rows": [
                {
                    "studentNo": "S901",
                    "fullName": "王五",
                    "className": "班甲",
                },
            ],
        },
    )
    reg = client.post(
        "/v1/student/register",
        json={
            "studentNo": "S901",
            "fullName": "王五",
            "password": "pw12345678",
        },
    )
    assert reg.status_code == 201, reg.text
    sid = reg.json()["studentId"]

    assert client.post(
        "/teacher/do-login",
        data={"password": "roster-class-pw-01"},
        follow_redirects=False,
    ).status_code == 303

    roster_all = client.get("/teacher/roster", follow_redirects=True)
    assert roster_all.status_code == 200
    assert "S901" in roster_all.text

    roster_unassigned = client.get(
        "/teacher/roster?classId=unassigned",
        follow_redirects=True,
    )
    assert roster_unassigned.status_code == 200
    assert "S901" not in roster_unassigned.text

    classes_page = client.get("/teacher/classes", follow_redirects=True)
    m = re.search(
        r'href="/teacher/classes/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"',
        classes_page.text,
    )
    assert m is not None, classes_page.text
    class_id = m.group(1)

    detail = client.get(
        f"/teacher/classes/{class_id}",
        follow_redirects=True,
    )
    assert detail.status_code == 200
    assert "S901" in detail.text
    assert "王五" in detail.text
    assert "remove-from-class" in detail.text

    rem = client.post(
        f"/teacher/students/{sid}/remove-from-class",
        data={"from_class_id": class_id},
        follow_redirects=False,
    )
    assert rem.status_code == 303
    assert f"/teacher/classes/{class_id}" in (rem.headers.get("location") or "")

    roster2 = client.get(
        "/teacher/roster?classId=unassigned",
        follow_redirects=True,
    )
    assert roster2.status_code == 200
    assert "S901" in roster2.text
    assert "王五" in roster2.text


def test_roster_bulk_set_class(client) -> None:
    _bootstrap_and_teacher(client)
    sids: list[str] = []
    for sn, name in (("S711", "甲"), ("S712", "乙")):
        client.post(
            "/v1/admin/roster/import",
            json={"rows": [{"studentNo": sn, "fullName": name, "className": ""}]},
        )
        reg = client.post(
            "/v1/student/register",
            json={"studentNo": sn, "fullName": name, "password": "pw12345678"},
        )
        assert reg.status_code == 201, reg.text
        sids.append(reg.json()["studentId"])
    assert client.post(
        "/teacher/do-login",
        data={"password": "roster-class-pw-01"},
        follow_redirects=False,
    ).status_code == 303
    new_cls = client.post(
        "/teacher/classes/new",
        data={"name": "大融合"},
        follow_redirects=False,
    )
    assert new_cls.status_code == 303
    list2 = client.get("/teacher/classes", follow_redirects=True)
    m2 = re.search(
        r'href="/teacher/classes/([0-9a-f-]{36})"[^>]*>[\s\S]*?大融合',
        list2.text,
    )
    assert m2 is not None, list2.text
    target_class_id = m2.group(1)

    r_bulk = client.post(
        "/teacher/students/bulk-set-class",
        data={
            "class_id": target_class_id,
            "student_ids": sids,
            "return_class_id": "unassigned",
        },
        follow_redirects=False,
    )
    assert r_bulk.status_code == 303
    assert "classId=unassigned" in (r_bulk.headers.get("location") or "")
    after = client.get(
        "/teacher/roster?classId=unassigned",
        follow_redirects=True,
    )
    assert "S711" not in after.text
    assert "S712" not in after.text
    in_class = client.get(
        f"/teacher/roster?classId={target_class_id}",
        follow_redirects=True,
    )
    assert "S711" in in_class.text
    assert "S712" in in_class.text
