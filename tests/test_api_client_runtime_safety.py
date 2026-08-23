"""Regression tests for HTTP client runtime safety."""

from unittest.mock import Mock

import pytest
from requests import Session

from hh_applicant_tool.api.client import BaseClient, DEFAULT_TIMEOUT


def _successful_response() -> Mock:
    response = Mock()
    response.status_code = 200
    response.text = "{}"
    response.json.return_value = {}
    return response


def test_request_uses_finite_default_timeout() -> None:
    session = Mock(spec=Session)
    session.proxies = {}
    session.request.return_value = _successful_response()
    client = BaseClient(base_url="https://api.example.com/", session=session)

    client.get("/me")

    assert session.request.call_args.kwargs["timeout"] == DEFAULT_TIMEOUT


def test_request_respects_custom_timeout() -> None:
    session = Mock(spec=Session)
    session.proxies = {}
    session.request.return_value = _successful_response()
    client = BaseClient(
        base_url="https://api.example.com/",
        session=session,
        timeout=(3.0, 12.0),
    )

    client.get("/me")

    assert session.request.call_args.kwargs["timeout"] == (3.0, 12.0)


def test_invalid_http_method_is_rejected_at_runtime() -> None:
    client = BaseClient(base_url="https://api.example.com/")

    with pytest.raises(ValueError, match="Unsupported HTTP method"):
        client.request("PATCH", "/me")  # type: ignore[arg-type]
