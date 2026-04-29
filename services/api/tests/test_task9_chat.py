"""任务 9：学生聊天代理、限流、mock / httpx。"""

from __future__ import annotations

import httpx
import pytest
import respx

from app import config
from app.services.chat_limiter import _state

from test_task8_student_chapters import _published_chapter_id, _student_token


@pytest.fixture(autouse=True)
def isolate_chat_test_settings(monkeypatch: pytest.MonkeyPatch) -> object:
    monkeypatch.setattr(config.settings, "llm_base_url", "")
    monkeypatch.setattr(config.settings, "llm_api_key", "")
    monkeypatch.setattr(config.settings, "chat_llm_base_url", "")
    monkeypatch.setattr(config.settings, "chat_llm_api_key", "")
    _state.clear()
    yield
    _state.clear()


def test_chat_mock_without_upsteam(client) -> None:
    ch_id = _published_chapter_id(client)
    tok = _student_token(client)
    h = {"Authorization": f"Bearer {tok}"}
    r = client.post(
        "/v1/student/chat",
        json={
            "chapterId": ch_id,
            "cellId": "c1",
            "messages": [{"role": "user", "content": "What is 1+1?"}],
        },
        headers=h,
    )
    assert r.status_code == 200
    j = r.json()
    assert j.get("ok") is True
    assert j.get("mock") is True


def test_chat_rate_limit(client, monkeypatch: pytest.MonkeyPatch) -> None:
    ch_id = _published_chapter_id(client)
    tok = _student_token(client)
    h = {"Authorization": f"Bearer {tok}"}
    monkeypatch.setattr(config.settings, "chat_rpm", 1)
    body = {
        "chapterId": ch_id,
        "cellId": "c1",
        "messages": [{"role": "user", "content": "a"}],
    }
    r1 = client.post("/v1/student/chat", json=body, headers=h)
    assert r1.status_code == 200
    r2 = client.post("/v1/student/chat", json=body, headers=h)
    assert r2.status_code == 429


@respx.mock
def test_chat_upstream_connection_error_returns_502(
    client, monkeypatch: pytest.MonkeyPatch, respx_mock: respx.MockRouter
) -> None:
    ch_id = _published_chapter_id(client)
    tok = _student_token(client)
    h = {"Authorization": f"Bearer {tok}"}
    monkeypatch.setattr(config.settings, "chat_llm_base_url", "https://unreachable-llm.example")
    monkeypatch.setattr(config.settings, "chat_llm_api_key", "k")
    respx_mock.post("https://unreachable-llm.example/v1/chat/completions").mock(
        side_effect=httpx.ConnectError("simulated: no route to host"),
    )
    r = client.post(
        "/v1/student/chat",
        json={
            "chapterId": ch_id,
            "cellId": "c1",
            "messages": [{"role": "user", "content": "hi"}],
        },
        headers=h,
    )
    assert r.status_code == 502
    detail = r.json().get("detail", "")
    assert "upstream_unavailable" in str(detail) or "ConnectError" in str(detail)


@respx.mock
def test_chat_upstream_200(
    client, monkeypatch: pytest.MonkeyPatch, respx_mock: respx.MockRouter
) -> None:
    ch_id = _published_chapter_id(client)
    tok = _student_token(client)
    h = {"Authorization": f"Bearer {tok}"}
    monkeypatch.setattr(config.settings, "chat_llm_base_url", "https://ch.test")
    monkeypatch.setattr(config.settings, "chat_llm_api_key", "k")
    respx_mock.post("https://ch.test/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "Two.",
                        }
                    }
                ],
            },
        )
    )
    r = client.post(
        "/v1/student/chat",
        json={
            "chapterId": ch_id,
            "cellId": "c1",
            "messages": [{"role": "user", "content": "1+1?"}],
        },
        headers=h,
    )
    assert r.status_code == 200
    assert "Two" in r.json().get("message", "")


@respx.mock
def test_chat_uses_saved_llm_config(client, respx_mock: respx.MockRouter) -> None:
    ch_id = _published_chapter_id(client)
    tok = _student_token(client)
    h = {"Authorization": f"Bearer {tok}"}
    client.post(
        "/v1/admin/llm-config",
        json={
            "provider": "deepseek",
            "baseUrl": "https://api.deepseek.com",
            "apiKey": "k-db",
            "chapterModel": "m-chapter",
            "chatModel": "m-chat",
            "enabled": True,
        },
    )
    respx_mock.post("https://api.deepseek.com/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={"choices": [{"message": {"content": "ok"}}]},
        )
    )
    r = client.post(
        "/v1/student/chat",
        json={
            "chapterId": ch_id,
            "cellId": "c1",
            "messages": [{"role": "user", "content": "hi"}],
        },
        headers=h,
    )
    assert r.status_code == 200
    assert r.json()["message"] == "ok"
