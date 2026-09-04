from __future__ import annotations

import json
import subprocess
from typing import Any
from unittest.mock import Mock

import pytest

from hh_applicant_tool.ai.openai import OpenAIError
from hh_applicant_tool.automation.reply_worker import (
    APPLICANT_ROLE,
    EMPLOYER_ROLE,
    HHCLI,
    MAX_REPLY_CHARS,
    HHCLIError,
    ReplyDecision,
    ReplyWorker,
    ReplyWorkerConfig,
    build_ai_client,
    build_context,
    deterministic_idempotency_key,
    load_json_config,
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


def _live_worker(hh=None, ai=None, **config_overrides) -> ReplyWorker:
    return ReplyWorker(
        ReplyWorkerConfig(dry_run=False, **config_overrides),
        hh=hh or Mock(),
        ai=ai or Mock(),
        system_prompt="system",
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


def test_build_ai_client_forwards_provider_settings() -> None:
    client = build_ai_client(
        {
            "openai_reply": {
                "api_key": " reply-key ",
                "base_url": "https://example.test/v1/chat/completions",
                "model": "reply-model",
                "temperature": 0.2,
                "max_completion_tokens": 321,
                "rate_limit": 17,
                "timeout": 12,
                "max_retries": 4,
            }
        },
        "system prompt",
    )

    assert client.api_key == "reply-key"
    assert client.base_url == "https://example.test/v1/chat/completions"
    assert client.model == "reply-model"
    assert client.system_prompt == "system prompt"
    assert client.temperature == 0.2
    assert client.max_completion_tokens == 321
    assert client.rate_limit == 17
    assert client.timeout == 12
    assert client.max_retries == 4


@pytest.mark.parametrize("missing", ["api_key", "base_url", "model"])
def test_build_ai_client_rejects_incomplete_provider(missing: str) -> None:
    provider = {
        "api_key": "key",
        "base_url": "https://example.test/v1/chat/completions",
        "model": "model",
    }
    provider[missing] = ""

    with pytest.raises(ValueError, match=missing):
        build_ai_client({"openai_reply": provider}, "system")


def test_load_json_config_requires_object(tmp_path) -> None:
    path = tmp_path / "config.json"
    path.write_text('["not", "an", "object"]', encoding="utf-8")

    with pytest.raises(ValueError, match="JSON object"):
        load_json_config(path)


def test_humanizer_rejects_placeholders_long_dash_and_ai_cliches() -> None:
    issues = reply_quality_issues("Важно отметить — могу обсудить [название компании] завтра.")

    assert "contains a long dash" in issues
    assert "contains a placeholder" in issues
    assert "contains an AI-style cliche" in issues


def test_humanizer_accepts_short_natural_reply() -> None:
    assert reply_quality_issues("Да, завтра после 12 удобно. Могу созвониться.") == []


def test_humanizer_rejects_empty_and_oversized_reply() -> None:
    assert reply_quality_issues("   ") == ["empty reply"]
    assert "reply is too long" in reply_quality_issues("а" * (MAX_REPLY_CHARS + 1))


def test_build_context_sorts_and_ignores_unknown_roles() -> None:
    context, initiated_by_us = build_context(
        [
            _message("2", EMPLOYER_ROLE, "Второе", "2026-01-01T10:02:00"),
            _message("1", APPLICANT_ROLE, "Первое", "2026-01-01T10:01:00"),
            _message("3", "SYSTEM", "Системное", "2026-01-01T10:03:00"),
        ]
    )

    assert initiated_by_us is True
    assert context == ["Я: Первое", "Работодатель: Второе"]


def test_idempotency_key_is_stable_per_employer_turn() -> None:
    first = deterministic_idempotency_key("chat-1", "message-42")
    second = deterministic_idempotency_key("chat-1", "message-42")
    other_turn = deterministic_idempotency_key("chat-1", "message-43")

    assert first == second
    assert first != other_turn


def test_hhcli_builds_profile_command() -> None:
    assert HHCLI("account-10")._base_command() == [
        "hh-applicant-tool",
        "--no-auto-auth",
        "--profile-id",
        "account-10",
    ]


def test_hhcli_call_api_parses_json_and_formulates_json_post(monkeypatch) -> None:
    completed = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout='{"id":"sent"}',
        stderr="",
    )
    run = Mock(return_value=completed)
    monkeypatch.setattr("hh_applicant_tool.automation.reply_worker.subprocess.run", run)

    result = HHCLI("account-1").call_api(
        "/common/chats/chat-1/messages",
        method="POST",
        json_data={"text": "Привет"},
    )

    assert result == {"id": "sent"}
    command = run.call_args.args[0]
    assert command[:4] == [
        "hh-applicant-tool",
        "--no-auto-auth",
        "--profile-id",
        "account-1",
    ]
    assert "--method" in command
    assert "--data" in command
    assert json.loads(command[command.index("--data") + 1]) == {"text": "Привет"}


def test_hhcli_call_api_wraps_process_and_json_errors(monkeypatch) -> None:
    monkeypatch.setattr(
        "hh_applicant_tool.automation.reply_worker.subprocess.run",
        Mock(
            return_value=subprocess.CompletedProcess(
                args=[], returncode=1, stdout="", stderr="HH failed"
            )
        ),
    )
    with pytest.raises(HHCLIError, match="HH failed"):
        HHCLI().call_api("/me")

    monkeypatch.setattr(
        "hh_applicant_tool.automation.reply_worker.subprocess.run",
        Mock(
            return_value=subprocess.CompletedProcess(
                args=[], returncode=0, stdout="not-json", stderr=""
            )
        ),
    )
    with pytest.raises(HHCLIError, match="invalid HH JSON"):
        HHCLI().call_api("/me")


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
            {"id": "wrong-type", "type": "OTHER", "last_message": {}},
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


def test_make_decision_builds_context_and_vacancy_metadata() -> None:
    hh = Mock()
    hh.call_api.side_effect = [
        _detail(
            _message("applicant-1", APPLICANT_ROLE, "Здравствуйте", "2026-01-01T10:00:00"),
            _message("employer-1", EMPLOYER_ROLE, "Когда созвон?", "2026-01-01T10:01:00"),
        ),
        {"name": "React developer", "employer": {"name": "Acme"}},
    ]
    worker = ReplyWorker(ReplyWorkerConfig(), hh=hh, ai=None, system_prompt="prompt")

    decision = worker.make_decision({"id": "chat-1"})

    assert decision is not None
    assert decision.expected_last_message_id == "employer-1"
    assert decision.initiated_by_us is True
    assert decision.context[-1] == "Работодатель: Когда созвон?"
    assert decision.vacancy_name == "React developer"
    assert decision.employer_name == "Acme"


def test_make_decision_fails_closed_when_write_is_not_allowed() -> None:
    detail = _detail(_message("employer-1", EMPLOYER_ROLE, "Привет", "2026-01-01"))
    detail["chat_states"] = {"write_message_state": {"allowed": False}}
    hh = Mock()
    hh.call_api.return_value = detail
    worker = ReplyWorker(ReplyWorkerConfig(), hh=hh, ai=None, system_prompt="prompt")

    assert worker.make_decision({"id": "chat-1"}) is None


def test_generate_reply_returns_safe_first_attempt() -> None:
    ai = Mock()
    ai.complete.return_value = "Да, завтра после 12 удобно."
    worker = _live_worker(ai=ai)

    assert worker.generate_reply(_decision()) == "Да, завтра после 12 удобно."
    ai.complete.assert_called_once()


def test_generate_reply_retries_humanizer_failure_with_correction() -> None:
    ai = Mock()
    ai.complete.side_effect = [
        "Важно отметить — буду рад обсудить.",
        "Да, завтра после 12 удобно.",
    ]
    worker = _live_worker(ai=ai, ai_retries=1)

    assert worker.generate_reply(_decision()) == "Да, завтра после 12 удобно."
    assert ai.complete.call_count == 2
    assert "Исправь предыдущую попытку" in ai.complete.call_args_list[1].args[0]


def test_generate_reply_fails_closed_after_second_unsafe_result() -> None:
    ai = Mock()
    ai.complete.side_effect = ["Важно отметить — отвечу.", "Таким образом — отвечу."]
    worker = _live_worker(ai=ai, ai_retries=1)

    assert worker.generate_reply(_decision()) is None


def test_generate_reply_fails_closed_on_ai_error() -> None:
    ai = Mock()
    ai.complete.side_effect = OpenAIError("provider down")
    worker = _live_worker(ai=ai)

    assert worker.generate_reply(_decision()) is None


def test_is_still_current_accepts_same_employer_turn() -> None:
    hh = Mock()
    hh.call_api.return_value = _detail(
        _message("employer-1", EMPLOYER_ROLE, "Вопрос", "2026-01-01T10:00:00")
    )

    assert _live_worker(hh=hh).is_still_current(_decision()) is True


def test_is_still_current_fails_closed_when_chat_changed() -> None:
    hh = Mock()
    hh.call_api.return_value = _detail(
        _message("employer-1", EMPLOYER_ROLE, "Вопрос", "2026-01-01T10:00:00"),
        _message(
            "applicant-2", APPLICANT_ROLE, "Уже ответил вручную", "2026-01-01T10:01:00"
        ),
    )

    assert _live_worker(hh=hh).is_still_current(_decision()) is False


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

    worker = _live_worker(hh=FakeHH())  # type: ignore[arg-type]

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
        def call_api(
            self,
            endpoint: str,
            *,
            method: str = "GET",
            json_data: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
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

    worker = _live_worker(hh=FakeHH(), send_retries=2)  # type: ignore[arg-type]

    assert worker.send_reply(_decision(), "Готов созвониться завтра") is True


def test_failed_send_returns_false_when_message_is_not_visible() -> None:
    class FakeHH:
        def call_api(
            self,
            endpoint: str,
            *,
            method: str = "GET",
            json_data: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            if method == "POST":
                raise HHCLIError("network down")
            return _detail(
                _message("employer-1", EMPLOYER_ROLE, "Вопрос", "2026-01-01T10:00:00")
            )

    worker = _live_worker(hh=FakeHH(), send_retries=0)  # type: ignore[arg-type]

    assert worker.send_reply(_decision(), "Ответ") is False


def test_run_dry_run_plans_without_revalidation_or_send() -> None:
    worker = ReplyWorker(ReplyWorkerConfig(dry_run=True), hh=Mock(), ai=None, system_prompt="prompt")
    worker.collect_candidate_chats = Mock(return_value=[{"id": "chat-1"}])
    worker.make_decision = Mock(return_value=_decision())
    worker.generate_reply = Mock(return_value="preview")
    worker.is_still_current = Mock()
    worker.send_reply = Mock()

    stats = worker.run()

    assert stats["planned"] == 1
    assert stats["sent"] == 0
    worker.is_still_current.assert_not_called()
    worker.send_reply.assert_not_called()


def test_run_live_skips_stale_reply() -> None:
    worker = _live_worker()
    worker.collect_candidate_chats = Mock(return_value=[{"id": "chat-1"}])
    worker.make_decision = Mock(return_value=_decision())
    worker.generate_reply = Mock(return_value="Ответ")
    worker.is_still_current = Mock(return_value=False)
    worker.send_reply = Mock()

    stats = worker.run()

    assert stats["stale"] == 1
    worker.send_reply.assert_not_called()


def test_run_live_counts_success_and_failures() -> None:
    worker = _live_worker()
    worker.collect_candidate_chats = Mock(return_value=[{"id": "one"}, {"id": "two"}])
    worker.make_decision = Mock(side_effect=[_decision(), _decision()])
    worker.generate_reply = Mock(side_effect=["Ответ 1", "Ответ 2"])
    worker.is_still_current = Mock(return_value=True)
    worker.send_reply = Mock(side_effect=[True, False])

    stats = worker.run()

    assert stats["candidates"] == 2
    assert stats["sent"] == 1
    assert stats["errors"] == 1


def test_run_counts_chat_api_error_without_crashing_other_loop() -> None:
    worker = _live_worker()
    worker.collect_candidate_chats = Mock(return_value=[{"id": "chat-1"}])
    worker.make_decision = Mock(side_effect=HHCLIError("bad chat"))

    stats = worker.run()

    assert stats["errors"] == 1


def test_missing_ai_config_fails_closed() -> None:
    with pytest.raises(ValueError):
        select_ai_config({})
