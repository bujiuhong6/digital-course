"""任务 10：教师 Web 页面可访问。"""

from __future__ import annotations


def test_teacher_web_form_login_sets_cookie_on_redirect_response(client) -> None:
    """成功登录的 303 上须带上 teacher_session（见 teacher_ui 里 _set_teacher_cookie(redir)）。"""
    client.post(
        "/v1/admin/bootstrap",
        json={"password": "form-login-pw-99"},
    )
    r = client.post(
        "/teacher/do-login",
        data={"password": "form-login-pw-99"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers.get("location", "").endswith("/teacher")
    # TestClient/httpx 把 Set-Cookie 放进 client.cookies，不一定留在 response headers
    assert "teacher_session" in client.cookies
    assert client.cookies.get("teacher_session", "").startswith("v1.")
    dash = client.get("/teacher")
    assert dash.status_code == 200
    assert "章" in dash.text


def test_teacher_delete_chapter_from_dashboard_post(client) -> None:
    client.post(
        "/v1/admin/bootstrap",
        json={"password": "del-dash-pw-02"},
    )
    r = client.post(
        "/teacher/chapters/new",
        data={"title": "可删之章"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    loc = r.headers.get("location", "")
    # /teacher/chapters/{uuid}/edit
    from uuid import UUID

    part = loc.split("/chapters/")[1]
    chapter_id = part.split("/edit")[0]
    _ = UUID(chapter_id)
    d = client.post(
        f"/teacher/chapters/{chapter_id}/delete",
        follow_redirects=False,
    )
    assert d.status_code == 303
    assert d.headers.get("location", "").endswith("/teacher")
    p = client.get("/teacher", follow_redirects=True)
    assert p.status_code == 200
    assert "可删之章" not in p.text


def test_chapter_save_draft_full_page_redirects_without_htmx(client) -> None:
    """无 HTMX 时须能用普通 POST+action 保存（不依赖外网 htmx.js）。"""
    client.post(
        "/v1/admin/bootstrap",
        json={"password": "ch-save-pw-77"},
    )
    r = client.post(
        "/teacher/chapters/new",
        data={"title": "HTMX fallback"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    loc = r.headers.get("location", "")
    assert "/teacher/chapters/" in loc and loc.endswith("/edit")
    r2 = client.post(
        loc.replace("/edit", "/save-draft"),
        data={'draft': '{"x":1}'},
        follow_redirects=False,
    )
    assert r2.status_code == 303
    assert "saved=1" in (r2.headers.get("location") or "")
    after = client.get(r2.headers["location"])
    assert after.status_code == 200
    assert "草稿已保存" in after.text


def test_teacher_ui_requires_session_then_works_with_cookie(client) -> None:
    c0 = client.get("/teacher", follow_redirects=False)
    assert c0.status_code in (301, 302, 303, 307, 308)
    assert c0.headers.get("location", "").endswith("/teacher/login")

    client.post(
        "/v1/admin/bootstrap",
        json={"password": "teacher-ui-test-pw-88"},
    )
    p = client.get("/teacher", follow_redirects=True)
    assert p.status_code == 200
    assert "章" in p.text
