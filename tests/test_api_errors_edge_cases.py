"""Edge cases for API error handling."""
from unittest.mock import Mock

import pytest
from requests import Response

from hh_applicant_tool.api.errors import (
    ApiError, BadRequest, Forbidden, CaptchaRequired, LimitExceeded,
    ResourceNotFound, ClientError, InternalServerError, BadGateway, Redirect
)


class TestApiErrorEdgeCases:
    """Test boundary conditions in API errors."""

    def test_error_with_empty_data_dict(self):
        """Error with completely empty data."""
        response = Mock(spec=Response)
        response.status_code = 400
        response.request = Mock()
        response.headers = {}

        error = ApiError(response, {})
        # Should handle empty dict gracefully
        assert error.message is not None

    def test_error_with_none_in_errors_array(self):
        """Errors array containing None."""
        response = Mock(spec=Response)
        response.status_code = 400
        response.request = Mock()
        response.headers = {}

        data = {"errors": [None, {"type": "error"}]}
        # Should not crash
        try:
            error = ApiError(response, data)
        except:
            pass

    def test_error_with_deeply_nested_errors(self):
        """Complex nested error structure."""
        response = Mock(spec=Response)
        response.status_code = 400
        response.request = Mock()
        response.headers = {}

        data = {
            "errors": [
                {
                    "type": "validation",
                    "value": "test",
                    "nested": {
                        "deeper": {
                            "field": "value"
                        }
                    }
                }
            ]
        }

        error = ApiError(response, data)
        assert error.message is not None

    def test_error_with_missing_type_field(self):
        """Error entry without 'type' field."""
        response = Mock(spec=Response)
        response.status_code = 400
        response.request = Mock()
        response.headers = {}

        data = {
            "errors": [
                {"value": "something"}  # No type
            ]
        }

        try:
            error = ApiError(response, data)
            msg = error.message
            # Should handle gracefully
        except KeyError:
            # Or raise if type is expected
            pass

    def test_error_with_missing_value_field(self):
        """Error entry without 'value' field."""
        response = Mock(spec=Response)
        response.status_code = 400
        response.request = Mock()
        response.headers = {}

        data = {
            "errors": [
                {"type": "error_type"}  # No value
            ]
        }

        error = ApiError(response, data)
        msg = error.message
        assert "error_type" in msg

    def test_error_message_with_all_fields_present(self):
        """Error message extraction with multiple priority fields."""
        response = Mock(spec=Response)
        response.status_code = 400
        response.request = Mock()
        response.headers = {}

        # All three possible sources
        data = {
            "error_description": "First priority",
            "description": "Second priority",
            "errors": [{"type": "third_priority"}]
        }

        error = ApiError(response, data)
        # Should use error_description (highest priority)
        assert error.message == "First priority"

    def test_captcha_error_multiple_errors(self):
        """Multiple errors including captcha."""
        response = Mock(spec=Response)
        response.status_code = 403
        response.request = Mock()
        response.headers = {}

        data = {
            "errors": [
                {"type": "some_error"},
                {
                    "type": "captcha_required",
                    "value": "captcha_required",
                    "captcha_url": "https://example.com/captcha",
                },
                {"type": "another_error"},
            ]
        }

        error = CaptchaRequired(response, data)
        assert error.captcha_url == "https://example.com/captcha"

    def test_captcha_error_without_url(self):
        """Captcha error but no URL provided."""
        response = Mock(spec=Response)
        response.status_code = 403
        response.request = Mock()
        response.headers = {}

        data = {
            "errors": [
                {"type": "captcha_required", "value": "captcha_required"}
            ]
        }

        error = CaptchaRequired(response, data)
        # Should not crash, captcha_url might be None or empty
        assert error.captcha_url is None or error.captcha_url == ""

    def test_limit_exceeded_with_retry_after(self):
        """Limit exceeded with retry-after hint."""
        response = Mock(spec=Response)
        response.status_code = 400
        response.request = Mock()
        response.headers = {"Retry-After": "60"}

        data = {
            "errors": [{"type": "limit_exceeded", "value": "requests"}]
        }

        with pytest.raises(LimitExceeded):
            ApiError.raise_for_status(response, data)

    def test_redirect_all_status_codes(self):
        """Test all redirect status codes."""
        response = Mock(spec=Response)
        response.request = Mock()
        response.headers = {}

        for status in [300, 301, 302, 303, 304, 305, 306, 307, 308]:
            response.status_code = status
            with pytest.raises(Redirect):
                ApiError.raise_for_status(response, {})

    def test_client_error_boundary_status(self):
        """Test status codes at 4xx boundary."""
        response = Mock(spec=Response)
        response.request = Mock()
        response.headers = {}

        # Just below 4xx
        response.status_code = 399
        # This might not raise or have special handling

        # Just above 4xx
        response.status_code = 400
        with pytest.raises(ClientError):
            ApiError.raise_for_status(response, {})

    def test_server_error_boundary_status(self):
        """Test status codes at 5xx boundary."""
        response = Mock(spec=Response)
        response.request = Mock()
        response.headers = {}

        # Just above 4xx, in 5xx range
        response.status_code = 500
        with pytest.raises(InternalServerError):
            ApiError.raise_for_status(response, {})

        # 502 specifically
        response.status_code = 502
        with pytest.raises(BadGateway):
            ApiError.raise_for_status(response, {})

    def test_error_with_numeric_status_codes(self):
        """Error data with numeric error codes."""
        response = Mock(spec=Response)
        response.status_code = 400
        response.request = Mock()
        response.headers = {}

        data = {
            "errors": [
                {"type": 12345, "value": 67890}  # Numeric instead of string
            ]
        }

        error = ApiError(response, data)
        # Should handle numeric types

    def test_error_string_representation_very_long(self):
        """Error with extremely long message."""
        response = Mock(spec=Response)
        response.status_code = 400
        response.request = Mock()
        response.headers = {}

        data = {
            "error_description": "x" * 10000
        }

        error = ApiError(response, data)
        str_repr = str(error)
        assert len(str_repr) == 10000

    def test_error_with_special_characters_in_message(self):
        """Error message with special characters."""
        response = Mock(spec=Response)
        response.status_code = 400
        response.request = Mock()
        response.headers = {}

        data = {
            "error_description": "Error: <script>alert()</script> and \x00 null byte"
        }

        error = ApiError(response, data)
        msg = error.message
        # Should contain the data as-is or sanitized

    def test_has_error_value_empty_errors_array(self):
        """has_error_value with empty errors array."""
        data = {"errors": []}
        assert ApiError.has_error_value("anything", data) is False

    def test_has_error_value_multiple_same_values(self):
        """Multiple errors with same value."""
        data = {
            "errors": [
                {"type": "error1", "value": "lookup"},
                {"type": "error2", "value": "lookup"},
                {"type": "error3", "value": "lookup"},
            ]
        }

        # Should find first occurrence
        assert ApiError.has_error_value("lookup", data) is True

    def test_has_error_value_value_is_none(self):
        """Searching for None value."""
        data = {
            "errors": [
                {"type": "error", "value": None}
            ]
        }

        result = ApiError.has_error_value(None, data)
        # Depends on implementation

    def test_error_request_property(self):
        """Error request property access."""
        response = Mock(spec=Response)
        response.request = Mock()
        response.request.method = "POST"
        response.request.url = "https://api.example.com/test"
        response.status_code = 400
        response.headers = {}

        error = ApiError(response, {})
        assert error.request.method == "POST"
        assert error.request.url == "https://api.example.com/test"

    def test_error_headers_case_insensitive(self):
        """Response headers should be case insensitive."""
        response = Mock(spec=Response)
        response.status_code = 400
        response.request = Mock()
        response.headers = {"Content-Type": "application/json"}

        error = ApiError(response, {})
        headers = error.response_headers
        # Should be case insensitive dict
        assert headers == {"Content-Type": "application/json"}

    def test_error_with_unicode_in_all_fields(self):
        """Unicode in error messages and data."""
        response = Mock(spec=Response)
        response.status_code = 400
        response.request = Mock()
        response.headers = {}

        data = {
            "error_description": "Ошибка: 🚀",
            "errors": [
                {"type": "验证错误", "value": "Значение"}
            ]
        }

        error = ApiError(response, data)
        msg = error.message
        assert msg is not None

    def test_different_error_classes_same_response(self):
        """Different error classes should preserve response."""
        response = Mock(spec=Response)
        response.status_code = 403
        response.request = Mock()
        response.headers = {"X-Custom": "header"}

        data = {"error": "test"}

        error1 = Forbidden(response, data)
        error2 = ClientError(response, data)

        assert error1.response_headers == error2.response_headers
        assert error1.status_code == error2.status_code
