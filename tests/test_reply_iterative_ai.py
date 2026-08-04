"""Focused checks for the cron-oriented contextual reply worker."""

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def reply_worker(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "openai_reply": {
                    "api_key": "test-key",
                    "base_url": "http://localhost/v1/chat/completions",
                    "model": "test-model",
                }
            }
        ),
        encoding="utf-8",
    )

    def fake_run(*_args, **_kwargs):
        return subprocess.CompletedProcess([], 0, stdout=f"{config_path}\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    script_path = Path(__file__).parents[1] / "scripts" / "reply_iterative_ai.py"
    spec = importlib.util.spec_from_file_location("reply_iterative_ai_test", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def message(author, text, created_at):
    return {
        "author": {"participant_type": author},
        "text": text,
        "created_at": created_at,
    }


def test_skips_when_applicant_sent_last_message(reply_worker):
    messages = [
        message("employer", "Когда удобно созвониться?", "2026-01-01T10:00:00+0300"),
        message("applicant", "Завтра после 12:00", "2026-01-01T10:05:00+0300"),
    ]

    assert reply_worker.should_reply(messages) == (False, None, None)


def test_builds_context_when_employer_sent_last_message(reply_worker):
    messages = [
        message("applicant", "Здравствуйте", "2026-01-01T10:00:00+0300"),
        message("employer", "Расскажите про React", "2026-01-01T10:05:00+0300"),
    ]

    needs_reply, context, initiated_by_us = reply_worker.should_reply(messages)

    assert needs_reply is True
    assert initiated_by_us is True
    assert context == ["Я: Здравствуйте", "Работодатель: Расскажите про React"]


def test_unknown_author_is_not_treated_as_employer(reply_worker):
    messages = [{"text": "Системное сообщение", "created_at": "2026-01-01"}]

    assert reply_worker.should_reply(messages) == (False, None, None)


def test_send_reply_passes_message_as_json_body(reply_worker, monkeypatch):
    captured = {}

    def fake_run_hh(*args):
        captured["args"] = args
        return {}

    monkeypatch.setattr(reply_worker, "run_hh", fake_run_hh)
    message_text = "Здравствуйте!\nГотов обсудить вакансию. Telegram: @maxxwway"

    success, error = reply_worker.send_reply("12345", message_text)

    assert success is True
    assert error is None
    assert captured["args"][:5] == (
        "call-api",
        "/negotiations/12345/messages",
        "--method",
        "POST",
        "--data",
    )
    assert json.loads(captured["args"][5]) == {"message": message_text}
