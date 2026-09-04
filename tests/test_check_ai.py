from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def check_ai_module():
    path = Path(__file__).parents[1] / "scripts" / "check_ai.py"
    spec = importlib.util.spec_from_file_location("check_ai_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_reply_purpose_falls_back_to_cover_letter(check_ai_module) -> None:
    config = {"openai_cover_letter": {"model": "fallback"}}

    section, provider = check_ai_module.select_provider(config, "reply")

    assert section == "openai_cover_letter"
    assert provider["model"] == "fallback"


def test_reply_purpose_prefers_reply_provider(check_ai_module) -> None:
    config = {
        "openai_cover_letter": {"model": "cover"},
        "openai_reply": {"model": "reply"},
    }

    section, provider = check_ai_module.select_provider(config, "reply")

    assert section == "openai_reply"
    assert provider["model"] == "reply"


def test_cover_letter_requires_its_own_provider(check_ai_module) -> None:
    with pytest.raises(ValueError):
        check_ai_module.select_provider({"openai_reply": {"model": "reply"}}, "cover-letter")


def test_validate_provider_requires_key_url_and_model(check_ai_module) -> None:
    errors = check_ai_module.validate_provider("openai_reply", {})

    assert "openai_reply.api_key is required" in errors
    assert "openai_reply.base_url is required" in errors
    assert "openai_reply.model is required" in errors


def test_validate_provider_accepts_ollama_compatible_config(check_ai_module) -> None:
    errors = check_ai_module.validate_provider(
        "openai_reply",
        {
            "api_key": "ollama",
            "base_url": "http://localhost:11434/v1/chat/completions",
            "model": "qwen2.5:14b",
        },
    )

    assert errors == []
