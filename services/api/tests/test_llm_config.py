from __future__ import annotations

import httpx
import respx


def test_teacher_can_save_and_read_masked_llm_config(client) -> None:
    client.post("/v1/admin/bootstrap", json={"username": "admin", "password": "pw-123456"})
    r = client.post(
        "/v1/admin/llm-config",
        json={
            "provider": "deepseek",
            "baseUrl": "https://api.deepseek.com",
            "apiKey": "sk-secret-value",
            "chapterModel": "deepseek-v4-flash",
            "chatModel": "deepseek-v4-flash",
            "enabled": True,
        },
    )
    assert r.status_code == 200, r.text

    got = client.get("/v1/admin/llm-config")
    assert got.status_code == 200
    body = got.json()["config"]
    assert body["provider"] == "deepseek"
    assert body["baseUrl"] == "https://api.deepseek.com"
    assert body["apiKeyMasked"].startswith("sk-")
    assert "secret-value" not in got.text


def test_teacher_llm_settings_page_and_nav(client) -> None:
    client.post("/v1/admin/bootstrap", json={"username": "admin", "password": "pw-123456"})
    page = client.get("/teacher/llm-settings")
    assert page.status_code == 200
    assert "大模型接入" in page.text
    dash = client.get("/teacher")
    assert "/teacher/llm-settings" in dash.text


@respx.mock
def test_teacher_llm_config_test_endpoint(client, respx_mock: respx.MockRouter) -> None:
    client.post("/v1/admin/bootstrap", json={"username": "admin", "password": "pw-123456"})
    client.post(
        "/v1/admin/llm-config",
        json={
            "provider": "deepseek",
            "baseUrl": "https://api.deepseek.com",
            "apiKey": "k",
            "chapterModel": "m1",
            "chatModel": "m2",
            "enabled": True,
        },
    )
    respx_mock.post("https://api.deepseek.com/chat/completions").mock(
        return_value=httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})
    )
    r = client.post("/v1/admin/llm-config/test")
    assert r.status_code == 200
    assert r.json()["ok"] is True
