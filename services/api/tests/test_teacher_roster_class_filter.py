"""教师端：班级与名单页行为；名单页仅以「当前导入名单」展示录入与注册状态。"""

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
    assert "班甲" in roster_all.text

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

    rem = client.post(
        f"/teacher/students/{sid}/remove-from-class",
        data={"from_class_id": class_id},
        follow_redirects=False,
    )
    assert rem.status_code == 303
    assert f"/teacher/classes/{class_id}" in (rem.headers.get("location") or "")

    roster2 = client.get("/teacher/roster", follow_redirects=True)
    assert roster2.status_code == 200
    assert "S901" in roster2.text
    assert "王五" in roster2.text


def test_roster_bulk_set_class(client) -> None:
    _bootstrap_and_teacher(client)
    client.post(
        "/v1/admin/roster/import",
        json={
            "rows": [
                {"studentNo": "S711", "fullName": "甲", "className": ""},
                {"studentNo": "S712", "fullName": "乙", "className": ""},
            ],
        },
    )
    sids: list[str] = []
    for sn, name in (("S711", "甲"), ("S712", "乙")):
        reg = client.post(
            "/v1/student/register",
            json={
                "studentNo": sn,
                "fullName": name,
                "password": "pw12345678",
            },
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
    roster_after = client.get("/teacher/roster?saved=1", follow_redirects=True)
    assert roster_after.status_code == 200
    assert "已更新班级" in roster_after.text
    assert "大融合" in roster_after.text
    assert "S711" in roster_after.text
    assert "S712" in roster_after.text


def test_roster_unassigned_filter_shows_only_unassigned_rows(client) -> None:
    _bootstrap_and_teacher(client)
    client.post(
        "/v1/admin/roster/import",
        json={
            "rows": [
                {"studentNo": "S_RF_1", "fullName": "甲", "className": ""},
                {"studentNo": "S_RF_2", "fullName": "乙", "className": "筛选用班"},
            ],
        },
    )
    assert client.post(
        "/teacher/do-login",
        data={"password": "roster-class-pw-01"},
        follow_redirects=False,
    ).status_code == 303
    roster_all = client.get("/teacher/roster", follow_redirects=True)
    assert roster_all.status_code == 200
    assert "S_RF_1" in roster_all.text
    assert "S_RF_2" in roster_all.text
    unassigned = client.get(
        "/teacher/roster?roster_class=unassigned",
        follow_redirects=True,
    )
    assert unassigned.status_code == 200
    assert "<code>S_RF_1</code>" in unassigned.text
    assert "<code>S_RF_2</code>" not in unassigned.text


def test_delete_class_unassigns_students_and_flash(client) -> None:
    _bootstrap_and_teacher(client)
    client.post(
        "/v1/admin/roster/import",
        json={
            "rows": [
                {"studentNo": "S-DEL-1", "fullName": "删班测", "className": ""},
            ],
        },
    )
    reg = client.post(
        "/v1/student/register",
        json={
            "studentNo": "S-DEL-1",
            "fullName": "删班测",
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
    assert (
        client.post(
            "/teacher/classes/new",
            data={"name": "待删班级"},
            follow_redirects=False,
        ).status_code
        == 303
    )
    lp = client.get("/teacher/classes", follow_redirects=True)
    m = re.search(
        r'href="/teacher/classes/([0-9a-f-]{36})"[^>]*>[\s\S]*?待删班级',
        lp.text,
    )
    assert m is not None, lp.text
    cid = m.group(1)
    assert (
        client.post(
            f"/teacher/students/{sid}/set-class",
            data={"class_id": cid, "return_to": "roster"},
            follow_redirects=False,
        ).status_code
        == 303
    )
    roster_before = client.get("/teacher/roster", follow_redirects=True)
    assert "待删班级" in roster_before.text
    del_r = client.post(
        f"/teacher/classes/{cid}/delete",
        follow_redirects=False,
    )
    assert del_r.status_code == 303
    assert "deleted=1" in (del_r.headers.get("location") or "")
    classes_after = client.get("/teacher/classes?deleted=1", follow_redirects=True)
    assert classes_after.status_code == 200
    assert "已删除班级" in classes_after.text
    assert "待删班级" not in classes_after.text
    roster_after = client.get("/teacher/roster", follow_redirects=True)
    assert "S-DEL-1" in roster_after.text
    assert "待删班级" not in roster_after.text


def test_class_page_bulk_remove_imported_roster_from_class(client) -> None:
    _bootstrap_and_teacher(client)
    client.post(
        "/v1/admin/roster/import",
        json={
            "rows": [
                {
                    "studentNo": "T900",
                    "fullName": "测移出",
                    "className": "班级移出测",
                },
            ],
        },
    )
    assert client.post(
        "/teacher/do-login",
        data={"password": "roster-class-pw-01"},
        follow_redirects=False,
    ).status_code == 303
    lp = client.get("/teacher/classes", follow_redirects=True)
    m = re.search(
        r'href="/teacher/classes/([0-9a-f-]{36})"[^>]*>[\s\S]*?班级移出测',
        lp.text,
    )
    assert m is not None, lp.text
    cid = m.group(1)
    detail = client.get(f"/teacher/classes/{cid}", follow_redirects=True)
    assert detail.status_code == 200
    assert "T900" in detail.text
    mx = re.search(
        r'class="js-class-roster-cb"[^>]*value="([0-9a-f-]{36})"',
        detail.text,
    )
    assert mx is not None, detail.text
    eid = mx.group(1)
    out = client.post(
        f"/teacher/classes/{cid}/roster-entries/remove-from-class",
        data={"entry_id": eid},
        follow_redirects=False,
    )
    assert out.status_code == 303
    loc = out.headers.get("location") or ""
    assert f"/teacher/classes/{cid}" in loc
    assert "class_roster_out=1" in loc
    again = client.get(f"/teacher/classes/{cid}", follow_redirects=True)
    assert again.status_code == 200
    assert "T900" not in again.text
    roster = client.get("/teacher/roster", follow_redirects=True)
    assert roster.status_code == 200
    assert "T900" in roster.text
