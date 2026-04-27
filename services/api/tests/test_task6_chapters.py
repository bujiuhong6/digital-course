"""任务 6：章 CRUD、generate、publish 校验。"""

from __future__ import annotations

from app.services.chapter_json import validate_for_publish


def _admin(client) -> None:
    client.post("/v1/admin/bootstrap", json={"password": "admin-secret-12345"})


def test_chapter_crud_generate_publish(client) -> None:
    _admin(client)
    r0 = client.post(
        "/v1/admin/chapters",
        json={"title": "第一章", "order": 1, "sourceMaterial": "print lesson"},
    )
    assert r0.status_code == 201, r0.text
    cid = r0.json()["id"]
    assert r0.json()["contentStatus"] == "draft"

    r_list = client.get("/v1/admin/chapters")
    assert r_list.status_code == 200
    assert len(r_list.json()["chapters"]) == 1

    r_g = client.post(f"/v1/admin/chapters/{cid}/generate")
    assert r_g.status_code == 200, r_g.text
    ch = r_g.json()["chapter"]
    assert ch["contentStatus"] == "draft"
    assert ch["aiGeneratedDraft"] is not None

    r_pub = client.post(f"/v1/admin/chapters/{cid}/publish")
    assert r_pub.status_code == 200, r_pub.text
    assert r_pub.json()["chapter"]["contentStatus"] == "published"
    assert r_pub.json()["chapter"]["publishedContent"]["version"] == 1

    r_del = client.delete(f"/v1/admin/chapters/{cid}")
    assert r_del.status_code == 200
    assert r_del.json().get("ok") is True


def test_publish_rejects_weak_extension_rule(client, monkeypatch) -> None:
    from app.config import settings

    _admin(client)
    r = client.post("/v1/admin/chapters", json={"title": "T2", "slug": "t2"})
    assert r.status_code == 201
    cid = r.json()["id"]
    weak = {
        "version": 1,
        "blocks": [
            {
                "id": "blk-x",
                "knowledgeHtml": "",
                "requiredExecutionMode": "pyodide",
                "guideCell": {
                    "id": "c1",
                    "starterCode": "1",
                    "codeBackdropLabel": "提示",
                    "codeBackdropCode": "# 参考",
                    "description": "d",
                    "passRule": {"mode": "no_exception"},
                },
                "extensionCell": {
                    "id": "c2",
                    "promptHtml": "<p>p</p>",
                    "starterCode": None,
                    "passRule": {"mode": "no_exception"},
                },
            }
        ],
    }
    client.patch(
        f"/v1/admin/chapters/{cid}",
        json={"aiGeneratedDraft": weak},
    )
    monkeypatch.setattr(settings, "chapter_publish_reject_extension_no_exception", True)
    r_pub = client.post(f"/v1/admin/chapters/{cid}/publish")
    assert r_pub.status_code == 400

    monkeypatch.setattr(settings, "chapter_publish_reject_extension_no_exception", False)
    r_pub2 = client.post(f"/v1/admin/chapters/{cid}/publish")
    assert r_pub2.status_code == 200, r_pub2.text


def test_publish_autofills_missing_guide_backdrop() -> None:
    d = {
        "version": 1,
        "blocks": [
            {
                "id": "b1",
                "knowledgeHtml": "<p></p>",
                "guideCell": {
                    "id": "g1",
                    "starterCode": "# 数据已预加载为 df，请在下方补全代码\nprint(df.shape)",
                    "description": "<p>x</p>",
                    "referenceAnswer": "print(df.shape)",
                    "passRule": {"mode": "no_exception"},
                },
                "extensionCell": {
                    "id": "e1",
                    "promptHtml": "<p>y</p>",
                    "starterCode": None,
                    "passRule": {
                        "mode": "stdout_contains",
                        "expectedSubstring": "a",
                    },
                },
            }
        ],
    }
    r = validate_for_publish(d)
    assert r.ok is True
    assert r.content is not None
    g = r.content["blocks"][0]["guideCell"]
    assert g["codeBackdropLabel"]
    assert g["codeBackdropCode"] == "print(df.shape)"
    assert g["starterCode"] == ""


def test_publish_warns_on_invalid_reference_python_snippet() -> None:
    d = {
        "version": 1,
        "blocks": [
            {
                "id": "b1",
                "knowledgeHtml": "<p></p>",
                "guideCell": {
                    "id": "g1",
                    "starterCode": "",
                    "description": "<p>x</p>",
                    "codeBackdropLabel": "提示",
                    "codeBackdropCode": "print('ok')",
                    "passRule": {"mode": "no_exception"},
                },
                "extensionCell": {
                    "id": "e1",
                    "promptHtml": "<p>y</p>",
                    "starterCode": None,
                    "referenceAnswer": 'f.write("a\nb\n")',
                    "passRule": {
                        "mode": "stdout_contains",
                        "expectedSubstring": "a",
                    },
                },
            }
        ],
    }
    r = validate_for_publish(d)
    assert r.ok is True
    assert any("referenceAnswer is not valid Python" in w for w in r.warnings)


def test_publish_keeps_expected_image_fields() -> None:
    d = {
        "version": 1,
        "requiresMatplotlibOutput": True,
        "blocks": [
            {
                "id": "b1",
                "knowledgeHtml": "<p></p>",
                "guideCell": {
                    "id": "g1",
                    "starterCode": "",
                    "description": "<p>x</p>",
                    "codeBackdropLabel": "提示",
                    "codeBackdropCode": "print('ok')",
                    "expectedImageDataUrl": "data:image/png;base64,AAAA",
                    "expectedImageAlt": "折线图参考效果",
                    "passRule": {"mode": "no_exception"},
                },
                "extensionCell": {
                    "id": "e1",
                    "promptHtml": "<p>y</p>",
                    "starterCode": "print('ok')",
                    "expectedImageDataUrl": "data:image/png;base64,BBBB",
                    "expectedImageAlt": "柱状图参考效果",
                    "passRule": {
                        "mode": "stdout_contains",
                        "expectedSubstring": "ok",
                    },
                },
            }
        ],
    }
    r = validate_for_publish(d)
    assert r.ok is True
    assert r.content is not None
    block = r.content["blocks"][0]
    assert block["guideCell"]["expectedImageDataUrl"] == "data:image/png;base64,AAAA"
    assert block["guideCell"]["expectedImageAlt"] == "折线图参考效果"
    assert block["extensionCell"]["expectedImageDataUrl"] == "data:image/png;base64,BBBB"
    assert block["extensionCell"]["expectedImageAlt"] == "柱状图参考效果"
