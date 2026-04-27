"""OpenAI 兼容基址归一化（…/v1 去重）与厂商示例（硅基流动、OpenRouter 等）。"""

from __future__ import annotations

import asyncio
import json
import os

import httpx
import pytest
import respx

from app import config
from app.services.chapter_gen import generate_chapter_draft
from app.services.chapter_json import sample_published_v1

from test_task8_student_chapters import _published_chapter_id, _student_token


def test_normalize_openai_compat_base_url() -> None:
    assert config.normalize_openai_compat_base_url("") == ""
    assert config.normalize_openai_compat_base_url("  ") == ""
    assert (
        config.normalize_openai_compat_base_url("https://api.siliconflow.cn")
        == "https://api.siliconflow.cn"
    )
    assert (
        config.normalize_openai_compat_base_url("https://api.siliconflow.cn/")
        == "https://api.siliconflow.cn"
    )
    assert (
        config.normalize_openai_compat_base_url("https://api.siliconflow.cn/v1")
        == "https://api.siliconflow.cn"
    )
    assert (
        config.normalize_openai_compat_base_url("https://api.siliconflow.cn/v1/")
        == "https://api.siliconflow.cn"
    )
    # OpenRouter 官方常写 base_url = https://openrouter.ai/api/v1；本仓库拼 /v1/chat/completions 故用 api 为根
    assert (
        config.normalize_openai_compat_base_url("https://openrouter.ai/api/v1")
        == "https://openrouter.ai/api"
    )
    assert (
        config.normalize_openai_compat_base_url("https://openrouter.ai/api/v1/")
        == "https://openrouter.ai/api"
    )


def test_openai_compat_chat_completions_url_handles_deepseek_docs_path() -> None:
    assert (
        config.openai_compat_chat_completions_url("https://api.deepseek.com")
        == "https://api.deepseek.com/chat/completions"
    )
    assert (
        config.openai_compat_chat_completions_url("https://api.siliconflow.cn")
        == "https://api.siliconflow.cn/v1/chat/completions"
    )


def test_merge_adds_openrouter_optional_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config.settings, "openrouter_http_referer", "https://example.edu/")
    monkeypatch.setattr(config.settings, "openrouter_title", "DigitalCourse")
    h = config.merge_openai_compat_llm_headers(
        "https://openrouter.ai/api",
        {"Content-Type": "application/json", "Authorization": "Bearer x"},
    )
    assert h["Authorization"] == "Bearer x"
    assert h.get("HTTP-Referer") == "https://example.edu/"
    assert h.get("X-OpenRouter-Title") == "DigitalCourse"


def test_merge_skips_referer_title_for_non_openrouter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config.settings, "openrouter_http_referer", "https://x.com/")
    h = config.merge_openai_compat_llm_headers(
        "https://api.siliconflow.cn",
        {"Content-Type": "application/json"},
    )
    assert "HTTP-Referer" not in h


@respx.mock
def test_chapter_gen_requests_v1_chat_completions_when_base_has_trailing_v1(
    monkeypatch: pytest.MonkeyPatch, respx_mock: respx.MockRouter
) -> None:
    os.environ.pop("CHAPTER_GEN_MOCK", None)
    monkeypatch.setattr(config.settings, "chapter_gen_mock", False)
    monkeypatch.setattr(
        config.settings,
        "llm_base_url",
        "https://api.siliconflow.cn/v1",
    )
    monkeypatch.setattr(config.settings, "llm_api_key", "sk-test")
    monkeypatch.setattr(config.settings, "chapter_gen_model", "Qwen/Qwen2.5-7B-Instruct")
    good = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(sample_published_v1(), ensure_ascii=False)
                }
            }
        ]
    }
    route = respx_mock.post("https://api.siliconflow.cn/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=good)
    )
    a, _b, err = asyncio.run(generate_chapter_draft("素材"))
    assert err is None
    assert a is not None
    assert a.get("version") == 1
    assert route.call_count == 1


@respx.mock
def test_chat_upstream_200_when_base_has_trailing_v1(
    client, monkeypatch: pytest.MonkeyPatch, respx_mock: respx.MockRouter
) -> None:
    ch_id = _published_chapter_id(client)
    tok = _student_token(client)
    h = {"Authorization": f"Bearer {tok}"}
    monkeypatch.setattr(
        config.settings,
        "chat_llm_base_url",
        "https://ch-sf.example/v1",
    )
    monkeypatch.setattr(config.settings, "chat_llm_api_key", "k")
    respx_mock.post("https://ch-sf.example/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "ok-upstream",
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
            "messages": [{"role": "user", "content": "ping"}],
        },
        headers=h,
    )
    assert r.status_code == 200
    assert (r.json().get("message") or "") == "ok-upstream"
