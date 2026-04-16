"""Tests for API error handling."""
from unittest.mock import Mock

import pytest

from hh_applicant_tool.api.errors import (
    ApiError,
    BadRequest,
    CaptchaRequired,
    Forbidden,
    LimitExceeded,
    ResourceNotFound,
    BadGateway,
    InternalServerError,
)


class TestApiErrorParsing:
    """Test API error detection and classification."""

    def _make_response(self, status_code: int, data: dict):
        """Helper to create mock response."""
        response = Mock()
        response.status_code = status_code
        response.request = Mock()
        response.headers = {}
        return response, data

    def test_limit_exceeded_error_detection(self):
        """429/400 with limit_exceeded should raise LimitExceeded."""
        response, data = self._make_response(400, {
            "errors": [{"type": "limit_exceeded", "value": "vacancy_search"}]
        })

        with pytest.raises(LimitExceeded) as exc_info:
            ApiError.raise_for_status(response, data)

        assert "limit_exceeded" in str(exc_info.value)

    def test_captcha_required_error_detection(self):
        """403 with captcha_required should raise CaptchaRequired."""
        response, data = self._make_response(403, {
            "errors": [
                {
                    "type": "captcha_required",
                    "value": "captcha_required",
                    "captcha_url": "https://hh.ru/captcha?token=abc123",
                }
            ]
        })

        with pytest.raises(CaptchaRequired) as exc_info:
            ApiError.raise_for_status(response, data)

        # Should have captcha URL
        assert exc_info.value.captcha_url == "https://hh.ru/captcha?token=abc123"

    def test_generic_403_forbidden(self):
        """403 without captcha should raise Forbidden."""
        response, data = self._make_response(403, {
            "errors": [{"type": "other_error"}]
        })

        with pytest.raises(Forbidden):
            ApiError.raise_for_status(response, data)

    def test_404_not_found(self):
        """404 should raise ResourceNotFound."""
        response, data = self._make_response(404, {
            "description": "Resource not found"
        })

        with pytest.raises(ResourceNotFound):
            ApiError.raise_for_status(response, data)

    def test_500_internal_server_error(self):
        """500+ should raise InternalServerError."""
        response, data = self._make_response(500, {
            "description": "Internal server error"
        })

        with pytest.raises(InternalServerError):
            ApiError.raise_for_status(response, data)

    def test_502_bad_gateway(self):
        """502 should raise BadGateway (not generic InternalServerError)."""
        response, data = self._make_response(502, {
            "errors": [{"type": "bad_gateway"}]
        })

        with pytest.raises(BadGateway):
            ApiError.raise_for_status(response, data)

    def test_400_bad_request(self):
        """400 without limit_exceeded should raise BadRequest."""
        response, data = self._make_response(400, {
            "errors": [{"type": "invalid_field", "value": "some_field"}]
        })

        with pytest.raises(BadRequest):
            ApiError.raise_for_status(response, data)

    def test_error_message_extraction(self):
        """Error message should be extracted from response."""
        response, data = self._make_response(400, {
            "errors": [
                {
                    "type": "validation_error",
                    "value": "salary_from must be positive",
                }
            ]
        })

        try:
            ApiError.raise_for_status(response, data)
        except BadRequest as e:
            message = str(e)
            assert "validation_error" in message
            assert "salary_from must be positive" in message

    def test_error_message_from_description(self):
        """Fallback to 'description' field if 'errors' is missing."""
        response, data = self._make_response(400, {
            "description": "Bad request description"
        })

        try:
            ApiError.raise_for_status(response, data)
        except BadRequest as e:
            assert str(e) == "Bad request description"

    def test_error_with_error_description_field(self):
        """Use 'error_description' if available."""
        response, data = self._make_response(403, {
            "error_description": "Invalid token"
        })

        try:
            ApiError.raise_for_status(response, data)
        except Forbidden as e:
            assert "Invalid token" in str(e)

    def test_has_error_value_check(self):
        """Test helper method for checking specific error values."""
        data = {
            "errors": [
                {"type": "error_1", "value": "value_1"},
                {"type": "error_2", "value": "value_2"},
                {"type": "error_3"},  # No value
            ]
        }

        assert ApiError.has_error_value("value_1", data) is True
        assert ApiError.has_error_value("value_2", data) is True
        assert ApiError.has_error_value("value_3", data) is False

    def test_multiple_errors_in_message(self):
        """Message should include all errors if multiple."""
        response, data = self._make_response(400, {
            "errors": [
                {"type": "error_1"},
                {"type": "error_2", "value": "some_value"},
            ]
        })

        try:
            ApiError.raise_for_status(response, data)
        except BadRequest as e:
            message = str(e)
            assert "error_1" in message
            assert "error_2" in message
            assert "some_value" in message
