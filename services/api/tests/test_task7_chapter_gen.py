"""任务 7：`chapter_gen` mock 固定 JSON、httpx LLM 路径、429 重试。"""

from __future__ import annotations

import asyncio
import json
import os

import httpx
import pytest
import respx

from app import config
from app.services.chapter_gen import _mock_from_env_and_settings, generate_chapter_draft
from app.services.chapter_json import sample_published_v1


def test_chapter_gen_mock_env_returns_fixed_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHAPTER_GEN_MOCK", "1")
    monkeypatch.setattr(config.settings, "chapter_gen_mock", False)
    assert _mock_from_env_and_settings() is True
    a, b, err = asyncio.run(generate_chapter_draft("hi"))
    assert err is None
    assert a == sample_published_v1() or a.get("version") == 1
    assert b is not None
    d = json.loads(b)
    assert d["version"] == 1


def test_chapter_gen_mock_0_uses_httpx(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHAPTER_GEN_MOCK", "0")
    monkeypatch.setattr(config.settings, "chapter_gen_mock", True)  # env wins
    assert _mock_from_env_and_settings() is False
    a, b, err = asyncio.run(generate_chapter_draft("x"))
    assert err and "LLM_BASE_URL" in err
    assert a is None


@respx.mock
def test_httpx_429_backoff_then_success(
    monkeypatch: pytest.MonkeyPatch, respx_mock: respx.MockRouter
) -> None:
    monkeypatch.delenv("CHAPTER_GEN_MOCK", raising=False)
    monkeypatch.setattr(config.settings, "chapter_gen_mock", False)
    monkeypatch.setattr(config.settings, "llm_base_url", "https://llm.test")
    monkeypatch.setattr(config.settings, "llm_api_key", "sk-test")
    monkeypatch.setattr(config.settings, "chapter_gen_model", "test-model")

    good = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(sample_published_v1(), ensure_ascii=False)
                }
            }
        ]
    }
    respx_mock.post("https://llm.test/v1/chat/completions").mock(
        side_effect=[
            httpx.Response(429, json={"error": "rate limit"}),
            httpx.Response(200, json=good),
        ],
    )
    a, b, err = asyncio.run(generate_chapter_draft("source"))
    assert err is None
    assert a is not None
    assert a.get("version") == 1


@respx.mock
def test_httpx_success(
    monkeypatch: pytest.MonkeyPatch, respx_mock: respx.MockRouter
) -> None:
    os.environ.pop("CHAPTER_GEN_MOCK", None)
    monkeypatch.setattr(config.settings, "chapter_gen_mock", False)
    monkeypatch.setattr(config.settings, "llm_base_url", "https://llm2.test")
    monkeypatch.setattr(config.settings, "llm_api_key", "k")
    good = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(sample_published_v1(), ensure_ascii=False)
                }
            }
        ]
    }
    route = respx_mock.post("https://llm2.test/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=good)
    )
    a, b, err = asyncio.run(generate_chapter_draft(None))
    assert err is None
    assert a["version"] == 1
    assert route.call_count == 1
