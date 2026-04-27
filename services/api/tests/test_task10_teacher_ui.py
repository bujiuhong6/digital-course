"""任务 10：教师 Web 页面可访问。"""

from __future__ import annotations

import json


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


def test_chapter_rename_post_redirects_with_renamed_query(client) -> None:
    client.post(
        "/v1/admin/bootstrap",
        json={"password": "ch-rename-pw-60"},
    )
    r = client.post(
        "/teacher/chapters/new",
        data={"title": "原名章"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    loc = r.headers.get("location", "")
    assert "/edit" in loc
    part = loc.split("/chapters/")[1]
    chapter_id = part.split("/edit")[0]
    r2 = client.post(
        f"/teacher/chapters/{chapter_id}/rename",
        data={"title": " 新名章 "},
        follow_redirects=False,
    )
    assert r2.status_code == 303
    assert "renamed=1" in (r2.headers.get("location") or "")
    after = client.get(r2.headers["location"])
    assert after.status_code == 200
    assert "章标题已更新" in after.text
    assert "新名章" in after.text
    assert "原名章" not in after.text


def test_chapter_rename_with_dashboard_referer_redirects_home(client) -> None:
    client.post(
        "/v1/admin/bootstrap",
        json={"password": "ch-rename-dash-ref-61"},
    )
    r = client.post(
        "/teacher/chapters/new",
        data={"title": "列表改名源"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    loc = r.headers.get("location", "")
    part = loc.split("/chapters/")[1]
    chapter_id = part.split("/edit")[0]
    r2 = client.post(
        f"/teacher/chapters/{chapter_id}/rename",
        data={"title": "列表改名后"},
        headers={"Referer": "http://testserver/teacher"},
        follow_redirects=False,
    )
    assert r2.status_code == 303
    loc2 = r2.headers.get("location") or ""
    assert loc2.startswith("/teacher?") or loc2.startswith("http://testserver/teacher?")
    assert "renamed=1" in loc2
    home = client.get("/teacher?renamed=1")
    assert home.status_code == 200
    assert "章标题已更新" in home.text
    assert "列表改名后" in home.text


def test_chapter_save_draft_htmx_redirects_to_edit_with_saved_query(client) -> None:
    """HTMX 保存成功后须整页可更新预览：响应带 HX-Redirect 至带 saved=1 的编辑页。"""
    client.post(
        "/v1/admin/bootstrap",
        json={"password": "ch-htmx-redirect-01"},
    )
    r = client.post(
        "/teacher/chapters/new",
        data={"title": "HTMX 预览"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    loc = r.headers.get("location", "")
    save_url = loc.replace("/edit", "/save-draft")
    r2 = client.post(
        save_url,
        data={'draft': '{"version":1,"blocks":[]}'},
        headers={"HX-Request": "true"},
        follow_redirects=False,
    )
    assert r2.status_code == 200
    assert (r2.headers.get("HX-Redirect") or "").endswith("/edit?saved=1")


def test_chapter_edit_htmx_buttons_include_current_draft_textarea(client) -> None:
    """保存与发布按钮的 HTMX 请求须显式带上右侧编辑区 JSON。"""
    client.post(
        "/v1/admin/bootstrap",
        json={"password": "ch-htmx-include-01"},
    )
    r = client.post(
        "/teacher/chapters/new",
        data={"title": "HTMX include 草稿"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    page = client.get(r.headers["location"])
    assert page.status_code == 200
    assert 'hx-post="' in page.text
    assert 'hx-include="#id-draft"' in page.text


def test_chapter_save_draft_htmx_then_edit_shows_draft_in_publish_preview(client) -> None:
    """保存草稿后重载的编辑页中，发布预览区须能渲染刚落库的草稿（依赖保存成功即 commit）。"""
    from app.services.chapter_json import sample_published_v1

    client.post(
        "/v1/admin/bootstrap",
        json={"password": "preview-htmx-pw-01"},
    )
    r = client.post(
        "/teacher/chapters/new",
        data={"title": "HTMX 预览联调"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    loc = r.headers.get("location", "")
    save_url = loc.replace("/edit", "/save-draft")
    draft = sample_published_v1()
    marker = "PREVIEW_DRAFT_MARKER_htmx_9f2a"
    guide_answer_marker = "GUIDE_BACKDROP_PREVIEW_6b51"
    extension_answer_marker = "EXTENSION_REF_PREVIEW_a2c7"
    draft["chapterIntroHtml"] = f"<p>{marker}</p>"
    draft["blocks"][0]["guideCell"]["starterCode"] = ""
    draft["blocks"][0]["guideCell"]["referenceAnswer"] = None
    draft["blocks"][0]["guideCell"]["codeBackdropCode"] = f"print('{guide_answer_marker}')"
    draft["blocks"][0]["guideCell"]["expectedImageDataUrl"] = "data:image/png;base64,GUIDEIMG"
    draft["blocks"][0]["guideCell"]["expectedImageAlt"] = "基础题参考图"
    draft["blocks"][0]["extensionCell"]["starterCode"] = None
    draft["blocks"][0]["extensionCell"]["referenceAnswer"] = f"print('{extension_answer_marker}')"
    draft["blocks"][0]["extensionCell"]["expectedImageDataUrl"] = "data:image/png;base64,EXTIMG"
    draft["blocks"][0]["extensionCell"]["expectedImageAlt"] = "扩展题参考图"
    r2 = client.post(
        save_url,
        data={"draft": json.dumps(draft, ensure_ascii=False)},
        headers={"HX-Request": "true"},
        follow_redirects=False,
    )
    assert r2.status_code == 200
    redir = r2.headers.get("HX-Redirect") or ""
    assert "saved=1" in redir
    page = client.get(redir)
    assert page.status_code == 200
    assert "发布预览" in page.text
    assert marker in page.text
    assert guide_answer_marker in page.text
    assert extension_answer_marker in page.text
    assert 'class="jnb-expected-img"' in page.text
    assert 'src="data:image/png;base64,GUIDEIMG"' in page.text
    assert 'alt="基础题参考图"' in page.text
    assert 'src="data:image/png;base64,EXTIMG"' in page.text
    assert 'alt="扩展题参考图"' in page.text


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


def test_merge_raw_reference_answers_fills_stale_published() -> None:
    """已发布快照缺 referenceAnswer 时，用草稿同格补全，供教师预览。"""
    from app.routers.teacher_ui import _merge_raw_reference_answers

    preview: dict = {
        "version": 1,
        "blocks": [
            {
                "id": "b1",
                "knowledgeHtml": "",
                "extensionCell": {
                    "id": "e1",
                    "promptHtml": "<p>x</p>",
                    "starterCode": "# 占位\n",
                },
            }
        ],
    }
    raw: dict = {
        "version": 1,
        "blocks": [
            {
                "id": "b1",
                "knowledgeHtml": "",
                "extensionCell": {
                    "id": "e1",
                    "promptHtml": "<p>x</p>",
                    "starterCode": "# 占位\n",
                    "referenceAnswer": "print(1)\n",
                },
            }
        ],
    }
    m = _merge_raw_reference_answers(preview, raw)
    assert m is not None
    assert m["blocks"][0]["extensionCell"].get("referenceAnswer") == "print(1)\n"
    assert preview["blocks"][0]["extensionCell"].get("referenceAnswer") is None


def test_merge_raw_reference_answers_matches_by_block_id_not_index() -> None:
    """块顺序在草稿与预览中不一致时，按块 id 合并 referenceAnswer。"""
    from app.routers.teacher_ui import _merge_raw_reference_answers

    preview: dict = {
        "version": 1,
        "blocks": [
            {
                "id": "blk-second",
                "knowledgeHtml": "",
                "extensionCell": {
                    "id": "ex2",
                    "promptHtml": "<p>y</p>",
                    "starterCode": "# 在此编写你的代码\n",
                },
            },
            {
                "id": "blk-first",
                "knowledgeHtml": "",
                "extensionCell": {
                    "id": "ex1",
                    "promptHtml": "<p>x</p>",
                    "starterCode": "# 在此编写你的代码\n",
                },
            },
        ],
    }
    raw: dict = {
        "version": 1,
        "blocks": [
            {
                "id": "blk-first",
                "knowledgeHtml": "",
                "extensionCell": {
                    "id": "ex1",
                    "promptHtml": "<p>x</p>",
                    "starterCode": "# 在此编写你的代码\n",
                    "referenceAnswer": "print('ok')\n",
                },
            },
            {
                "id": "blk-second",
                "knowledgeHtml": "",
                "extensionCell": {
                    "id": "ex2",
                    "promptHtml": "<p>y</p>",
                    "starterCode": "# 在此编写你的代码\n",
                },
            },
        ],
    }
    m = _merge_raw_reference_answers(preview, raw)
    assert m is not None
    assert m["blocks"][0]["extensionCell"].get("referenceAnswer") is None
    assert m["blocks"][1]["extensionCell"].get("referenceAnswer") == "print('ok')\n"


def test_merge_raw_reference_answers_fills_guide_code_backdrop_when_stale() -> None:
    """已发布快照缺 codeBackdrop* 时，用草稿同格补全，供教师预览；不覆盖已发布的非空值。"""
    from app.routers.teacher_ui import _merge_raw_reference_answers

    preview: dict = {
        "version": 1,
        "blocks": [
            {
                "id": "b1",
                "knowledgeHtml": "",
                "guideCell": {
                    "id": "g1",
                    "promptHtml": "<p>q</p>",
                    "starterCode": "",
                },
            }
        ],
    }
    raw: dict = {
        "version": 1,
        "blocks": [
            {
                "id": "b1",
                "knowledgeHtml": "",
                "guideCell": {
                    "id": "g1",
                    "promptHtml": "<p>q</p>",
                    "starterCode": "",
                    "codeBackdropCode": "MARKER_BACKDROP\n",
                    "codeBackdropLabel": "L1",
                },
            }
        ],
    }
    m = _merge_raw_reference_answers(preview, raw)
    assert m is not None
    gc = m["blocks"][0]["guideCell"]
    assert gc.get("codeBackdropCode") == "MARKER_BACKDROP\n"
    assert gc.get("codeBackdropLabel") == "L1"

    # preview already has non-empty codeBackdropCode → do not replace
    preview2: dict = {
        "version": 1,
        "blocks": [
            {
                "id": "b1",
                "knowledgeHtml": "",
                "guideCell": {
                    "id": "g1",
                    "promptHtml": "<p>q</p>",
                    "starterCode": "",
                    "codeBackdropCode": "keep me\n",
                },
            }
        ],
    }
    m2 = _merge_raw_reference_answers(preview2, raw)
    assert m2["blocks"][0]["guideCell"].get("codeBackdropCode") == "keep me\n"


def test_teacher_ui_publish_submits_current_draft_field(client) -> None:
    """发布请求携带 `draft` 时，以编辑区内容为准，避免未点「保存草稿」时仍发布旧库内草稿。"""
    from app.services.chapter_json import sample_published_v1

    client.post("/v1/admin/bootstrap", json={"password": "pub-form-pw-01"})
    r0 = client.post(
        "/v1/admin/chapters",
        json={"title": "表单发布测", "order": 0},
    )
    assert r0.status_code == 201
    cid = r0.json()["id"]
    base = sample_published_v1()
    client.patch(
        f"/v1/admin/chapters/{cid}",
        json={"aiGeneratedDraft": base},
    )
    r_pub0 = client.post(f"/v1/admin/chapters/{cid}/publish")
    assert r_pub0.status_code == 200
    marker = "FORM_BODY_PUBLISH_INTRO"
    base2 = sample_published_v1()
    base2["chapterIntroHtml"] = f"<p>{marker}</p>"
    body = json.dumps(base2, ensure_ascii=False)
    r_ui = client.post(
        f"/teacher/chapters/{cid}/publish",
        data={"draft": body},
        follow_redirects=False,
    )
    assert r_ui.status_code == 303
    assert "pub_ok=1" in (r_ui.headers.get("location") or "")
    r_ch = client.get(f"/v1/admin/chapters/{cid}")
    assert r_ch.status_code == 200
    intro = r_ch.json()["chapter"]["publishedContent"].get("chapterIntroHtml", "")
    assert marker in intro


def test_teacher_ui_publish_same_content_returns_warning(client) -> None:
    """当前编辑区内容已发布时，HTMX 发布返回黄色提示。"""
    from app.services.chapter_json import sample_published_v1

    client.post("/v1/admin/bootstrap", json={"password": "pub-same-pw-01"})
    r0 = client.post(
        "/v1/admin/chapters",
        json={"title": "重复发布提示测", "order": 0},
    )
    assert r0.status_code == 201
    cid = r0.json()["id"]
    draft = sample_published_v1()
    body = json.dumps(draft, ensure_ascii=False)
    first = client.post(
        f"/teacher/chapters/{cid}/publish",
        data={"draft": body},
        follow_redirects=False,
    )
    assert first.status_code == 303
    second = client.post(
        f"/teacher/chapters/{cid}/publish",
        data={"draft": body},
        headers={"HX-Request": "true"},
        follow_redirects=False,
    )
    assert second.status_code == 200
    assert second.headers.get("HX-Redirect") is None
    assert "flash-warn" in second.text
    assert "当前内容已发布，请勿重复发布" in second.text
