"""Retry behavior for transient OpenAI-compatible endpoint failures."""

from unittest.mock import Mock

import requests

from hh_applicant_tool.ai.openai import ChatOpenAI


def make_client(session, max_retries=2):
    return ChatOpenAI(
        api_key="test-key",
        base_url="https://example.test/v1/chat/completions",
        model="test-model",
        max_retries=max_retries,
        rate_limit=0,
        session=session,
    )


def response(status_code, payload=None):
    result = Mock(spec=requests.Response)
    result.status_code = status_code
    result.headers = {}
    result.json.return_value = payload or {}
    if status_code >= 400:
        result.raise_for_status.side_effect = requests.HTTPError(
            f"HTTP {status_code}"
        )
    return result


def test_retries_transient_server_error(monkeypatch):
    session = Mock()
    session.post.side_effect = [
        response(503),
        response(200, {"choices": [{"message": {"content": "ok"}}]}),
    ]
    monkeypatch.setattr("hh_applicant_tool.ai.openai.time.sleep", Mock())

    assert make_client(session).complete("hello") == "ok"
    assert session.post.call_count == 2


def test_retries_network_error(monkeypatch):
    session = Mock()
    session.post.side_effect = [
        requests.ConnectionError("temporary"),
        response(200, {"choices": [{"message": {"content": "ok"}}]}),
    ]
    monkeypatch.setattr("hh_applicant_tool.ai.openai.time.sleep", Mock())

    assert make_client(session).complete("hello") == "ok"
    assert session.post.call_count == 2
