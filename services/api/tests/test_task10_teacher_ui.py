"""任务 10：教师 Web 页面可访问。"""

from __future__ import annotations


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
