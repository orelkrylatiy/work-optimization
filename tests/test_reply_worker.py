from __future__ import annotations

from typing import Any
from unittest.mock import Mock

import pytest

from hh_applicant_tool.automation.reply_worker import (
    APPLICANT_ROLE,
    EMPLOYER_ROLE,
    HHCLIError,
    ReplyDecision,
    ReplyWorker,
    ReplyWorkerConfig,
    deterministic_idempotency_key,
    reply_quality_issues,
    select_ai_config,
)


def _message(message_id: str, role: str, text: str, timestamp: str) -> dict[str, Any]:
    return {
        "id": message_id,
        "creation_time": timestamp,
        "sender_display_info": {"role": role},
        "payload": {"text": text},
    }


def _detail(*messages: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": "chat-1",
        "display": {"title": "Frontend developer"},
        "vacancy_id": "vacancy-1",
        "chat_states": {"write_message_state": {"allowed": True}},
        "messages": list(messages),
    }


def _decision() -> ReplyDecision:
    return ReplyDecision(
        chat_id="chat-1",
        expected_last_message_id="employer-1",
        context=["Работодатель: Когда удобно созвониться?"],
        initiated_by_us=True,
        vacancy_name="Frontend developer",
        employer_name="Acme",
    )


def test_reply_ai_config_falls_back_to_cover_letter() -> None:
    config = {
        "openai_cover_letter": {
            "api_key": "key",
            "base_url": "https://example.test/v1/chat/completions",
            "model": "model",
        }
    }

    section, provider = select_ai_config(config)

    assert section == "openai_cover_letter"
    assert provider["model"] == "model"


def test_reply_ai_config_prefers_dedicated_reply_section() -> None:
    config = {
        "openai_cover_letter": {"model": "cover"},
        "openai_reply": {"model": "reply"},
    }

    section, provider = select_ai_config(config)

    assert section == "openai_reply"
    assert provider["model"] == "reply"


def test_humanizer_rejects_placeholders_long_dash_and_ai_cliches() -> None:
    issues = reply_quality_issues(
        "Важно отметить — могу обсудить [название компании] завтра."
    )

    assert "contains a long dash" in issues
    assert "contains a placeholder" in issues
    assert "contains an AI-style cliche" in issues


def test_idempotency_key_is_stable_per_employer_turn() -> None:
    first = deterministic_idempotency_key("chat-1", "message-42")
    second = deterministic_idempotency_key("chat-1", "message-42")
    other_turn = deterministic_idempotency_key("chat-1", "message-43")

    assert first == second
    assert first != other_turn


def test_collect_candidate_chats_only_keeps_unblocked_employer_turns() -> None:
    hh = Mock()
    hh.call_api.return_value = {
        "items": [
            {
                "id": "reply-me",
                "type": "NEGOTIATION",
                "block_reason": None,
                "last_message": _message("1", EMPLOYER_ROLE, "Привет", "2026-01-01"),
            },
            {
                "id": "already-replied",
                "type": "NEGOTIATION",
                "block_reason": None,
                "last_message": _message("2", APPLICANT_ROLE, "Ответ", "2026-01-01"),
            },
            {
                "id": "blocked",
                "type": "NEGOTIATION",
                "block_reason": "BLOCKED",
                "last_message": _message("3", EMPLOYER_ROLE, "Привет", "2026-01-01"),
            },
        ],
        "pages": 1,
    }
    worker = ReplyWorker(
        ReplyWorkerConfig(max_chats=100),
        hh=hh,
        ai=None,
        system_prompt="prompt",
    )

    chats = worker.collect_candidate_chats()

    assert [chat["id"] for chat in chats] == ["reply-me"]


def test_is_still_current_fails_closed_when_chat_changed() -> None:
    hh = Mock()
    hh.call_api.return_value = _detail(
        _message("employer-1", EMPLOYER_ROLE, "Вопрос", "2026-01-01T10:00:00"),
        _message("applicant-2", APPLICANT_ROLE, "Уже ответил вручную", "2026-01-01T10:01:00"),
    )
    worker = ReplyWorker(
        ReplyWorkerConfig(dry_run=False),
        hh=hh,
        ai=Mock(),
        system_prompt="prompt",
    )

    assert worker.is_still_current(_decision()) is False


def test_send_uses_common_chat_json_and_deterministic_idempotency_key() -> None:
    calls: list[tuple[str, str, dict[str, Any] | None]] = []

    class FakeHH:
        def call_api(
            self,
            endpoint: str,
            *,
            method: str = "GET",
            json_data: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            calls.append((endpoint, method, json_data))
            return {"id": "sent-1"}

    worker = ReplyWorker(
        ReplyWorkerConfig(dry_run=False),
        hh=FakeHH(),  # type: ignore[arg-type]
        ai=Mock(),
        system_prompt="prompt",
    )

    assert worker.send_reply(_decision(), "Готов созвониться завтра") is True
    endpoint, method, payload = calls[0]
    assert endpoint == "/common/chats/chat-1/messages"
    assert method == "POST"
    assert payload == {
        "idempotency_key": deterministic_idempotency_key("chat-1", "employer-1"),
        "text": "Готов созвониться завтра",
    }


def test_failed_send_is_treated_as_success_if_message_is_already_visible() -> None:
    class FakeHH:
        def __init__(self) -> None:
            self.calls = 0

        def call_api(
            self,
            endpoint: str,
            *,
            method: str = "GET",
            json_data: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            self.calls += 1
            if method == "POST":
                raise HHCLIError("network response lost")
            return _detail(
                _message(
                    "applicant-2",
                    APPLICANT_ROLE,
                    "Готов созвониться завтра",
                    "2026-01-01T10:01:00",
                )
            )

    worker = ReplyWorker(
        ReplyWorkerConfig(dry_run=False, send_retries=2),
        hh=FakeHH(),  # type: ignore[arg-type]
        ai=Mock(),
        system_prompt="prompt",
    )

    assert worker.send_reply(_decision(), "Готов созвониться завтра") is True


def test_missing_ai_config_fails_closed() -> None:
    with pytest.raises(ValueError):
        select_ai_config({})
