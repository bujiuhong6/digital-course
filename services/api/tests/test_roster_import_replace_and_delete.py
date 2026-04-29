"""名单：管理员仍为全量覆盖导入；教师端为增量合并；教师端未分班批量删除。"""

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


def test_admin_import_replaces_entire_roster_including_class_rows(client) -> None:
    """第二次导入只含新学号时，此前已分班但未出现在新文件中的名单行被移除。"""
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
    assert "C1" not in d.text


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


def test_teacher_web_roster_import_native_post_redirects(client) -> None:
    """无 HTMX 时用 multipart POST /teacher/roster/import：成功则 303 回首屏并写入名单。"""
    _bootstrap(client)
    assert (
        client.post(
            "/teacher/do-login",
            data={"password": "roster-replace-pw-01"},
            follow_redirects=False,
        ).status_code
        == 303
    )
    form_page = client.get("/teacher/roster", follow_redirects=True)
    assert form_page.status_code == 200
    assert 'action="/teacher/roster/import"' in form_page.text
    assert 'method="post"' in form_page.text
    assert 'enctype="multipart/form-data"' in form_page.text

    csv_body = "学号,姓名,班级\nWEB1,网页导入,\n".encode("utf-8-sig")
    imp = client.post(
        "/teacher/roster/import",
        files={"file": ("import.csv", csv_body, "text/csv")},
        follow_redirects=False,
    )
    assert imp.status_code == 303
    loc = imp.headers.get("location") or ""
    assert "import_ok=1" in loc
    assert "n=1" in loc
    page = client.get(loc, follow_redirects=True)
    assert page.status_code == 200
    assert "WEB1" in page.text
    assert "网页导入" in page.text
    assert (
        "本次导入新增 1 条名单（已在系统中的学号未改动）。列表按学号升序。"
        in page.text
    )


def test_teacher_web_roster_import_htmx_shows_parse_error(client) -> None:
    _bootstrap(client)
    assert (
        client.post(
            "/teacher/do-login",
            data={"password": "roster-replace-pw-01"},
            follow_redirects=False,
        ).status_code
        == 303
    )
    bad_csv = "student_no,name\nBAD1,坏表头\n".encode("utf-8-sig")
    r = client.post(
        "/teacher/roster/import",
        files={"file": ("bad.csv", bad_csv, "text/csv")},
        headers={"HX-Request": "true"},
        follow_redirects=False,
    )
    assert r.status_code == 200
    assert "导入失败" in r.text
    assert "学号" in r.text
    assert "姓名" in r.text
    assert "班级" in r.text


def test_teacher_web_roster_import_htmx_redirects_to_success_flash(client) -> None:
    _bootstrap(client)
    assert (
        client.post(
            "/teacher/do-login",
            data={"password": "roster-replace-pw-01"},
            follow_redirects=False,
        ).status_code
        == 303
    )
    csv_body = "学号,姓名,班级\nHX1,导入成功,24金融学\n".encode("utf-8-sig")
    r = client.post(
        "/teacher/roster/import",
        files={"file": ("ok.csv", csv_body, "text/csv")},
        headers={"HX-Request": "true"},
        follow_redirects=False,
    )
    assert r.status_code == 200
    assert r.headers.get("HX-Redirect") == "/teacher/roster?import_ok=1&n=1"
    page = client.get(r.headers["HX-Redirect"], follow_redirects=True)
    assert (
        "本次导入新增 1 条名单（已在系统中的学号未改动）。列表按学号升序。"
        in page.text
    )


def test_teacher_web_roster_import_incremental_skips_existing(client) -> None:
    _bootstrap(client)
    client.post(
        "/v1/admin/roster/import",
        json={"rows": [{"studentNo": "OLD1", "fullName": "已有"}]},
    )
    assert client.post(
        "/teacher/do-login",
        data={"password": "roster-replace-pw-01"},
        follow_redirects=False,
    ).status_code == 303
    csv_body = (
        "学号,姓名,班级\n"
        "OLD1,跳过,\n"
        "NEW2,追加,\n"
    ).encode("utf-8-sig")
    imp = client.post(
        "/teacher/roster/import",
        files={"file": ("merged.csv", csv_body, "text/csv")},
        follow_redirects=False,
    )
    assert imp.status_code == 303
    assert "import_ok=1" in (imp.headers.get("location") or "")
    assert "n=1" in (imp.headers.get("location") or "")
    page = client.get(
        "/teacher/roster?import_ok=1&n=1",
        follow_redirects=True,
    )
    assert page.status_code == 200
    assert "NEW2" in page.text
    assert "追加" in page.text

    csv_same = csv_body
    dup = client.post(
        "/teacher/roster/import",
        files={"file": ("merged.csv", csv_same, "text/csv")},
        follow_redirects=False,
    )
    assert dup.status_code == 303
    assert "n=0" in (dup.headers.get("location") or "")
    zp = client.get(
        "/teacher/roster?import_ok=1&n=0",
        follow_redirects=True,
    )
    assert "本次暂无新增" in zp.text
