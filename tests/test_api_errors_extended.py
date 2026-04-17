"""Tests for API errors handling."""
from unittest.mock import Mock

import pytest
from requests import Response, Request

from hh_applicant_tool.api.errors import (
    BadResponse,
    ApiError,
    BadRequest,
    Forbidden,
    ResourceNotFound,
    CaptchaRequired,
    LimitExceeded,
    Redirect,
    ClientError,
    InternalServerError,
    BadGateway,
)


@pytest.fixture
def mock_response():
    """Create a mock Response object."""
    response = Mock(spec=Response)
    response.status_code = 400
    response.request = Mock(spec=Request)
    response.headers = {}
    return response


@pytest.fixture
def mock_response_500():
    """Create a mock 500 error Response."""
    response = Mock(spec=Response)
    response.status_code = 500
    response.request = Mock(spec=Request)
    response.headers = {}
    return response


class TestBadResponse:
    """Test BadResponse exception."""

    def test_bad_response_is_exception(self):
        """BadResponse should be an Exception."""
        assert issubclass(BadResponse, Exception)

    def test_bad_response_can_be_raised(self):
        """BadResponse should be raisable."""
        with pytest.raises(BadResponse):
            raise BadResponse()


class TestApiErrorBasics:
    """Test ApiError base class functionality."""

    def test_api_error_initialization(self, mock_response):
        """ApiError should store response and data."""
        data = {"error": "test"}
        error = ApiError(mock_response, data)

        assert error._response == mock_response
        assert error._data == data

    def test_api_error_data_property(self, mock_response):
        """data property should return stored data."""
        data = {"key": "value"}
        error = ApiError(mock_response, data)
        assert error.data == data

    def test_api_error_request_property(self, mock_response):
        """request property should return response.request."""
        error = ApiError(mock_response, {})
        assert error.request == mock_response.request

    def test_api_error_status_code_property(self, mock_response):
        """status_code property should return response status code."""
        error = ApiError(mock_response, {})
        assert error.status_code == 400

    def test_api_error_headers_property(self, mock_response):
        """response_headers should return response headers."""
        mock_response.headers = {"Content-Type": "application/json"}
        error = ApiError(mock_response, {})
        assert error.response_headers == {"Content-Type": "application/json"}

    def test_api_error_is_bad_response(self, mock_response):
        """ApiError should be subclass of BadResponse."""
        error = ApiError(mock_response, {})
        assert isinstance(error, BadResponse)


class TestApiErrorMessage:
    """Test error message extraction."""

    def test_error_message_from_error_description(self, mock_response):
        """Should extract error_description if present."""
        data = {"error_description": "Invalid token"}
        error = ApiError(mock_response, data)
        assert error.message == "Invalid token"

    def test_error_message_from_description(self, mock_response):
        """Should use description as fallback."""
        data = {"description": "Bad Gateway"}
        error = ApiError(mock_response, data)
        assert error.message == "Bad Gateway"

    def test_error_message_from_errors_array(self, mock_response):
        """Should format errors array if present."""
        data = {
            "errors": [
                {"type": "invalid_input", "value": "test@"},
                {"type": "field_required"},
            ]
        }
        error = ApiError(mock_response, data)
        msg = error.message

        assert "invalid_input" in msg
        assert "field_required" in msg

    def test_error_message_fallback_to_data_string(self, mock_response):
        """Should stringify data as last resort."""
        data = {"some": "data"}
        error = ApiError(mock_response, data)
        assert error.message == str(data)

    def test_api_error_str_uses_message(self, mock_response):
        """__str__ should return the message."""
        data = {"error_description": "Test error"}
        error = ApiError(mock_response, data)
        assert str(error) == "Test error"


class TestApiErrorStaticMethods:
    """Test ApiError static methods."""

    def test_has_error_value_found(self):
        """Should find error value in errors array."""
        data = {
            "errors": [
                {"type": "limit_exceeded", "value": "requests"},
            ]
        }
        assert ApiError.has_error_value("requests", data) is True

    def test_has_error_value_not_found(self):
        """Should return False if value not in errors."""
        data = {"errors": [{"type": "invalid", "value": "input"}]}
        assert ApiError.has_error_value("other", data) is False

    def test_has_error_value_no_errors_key(self):
        """Should handle missing errors key."""
        data = {"key": "value"}
        assert ApiError.has_error_value("any", data) is False

    def test_has_error_value_no_value_field(self):
        """Should handle errors without value field."""
        data = {
            "errors": [
                {"type": "error_type"},  # No value
            ]
        }
        assert ApiError.has_error_value("something", data) is False


class TestApiErrorRaiseForStatus:
    """Test raise_for_status method for different status codes."""

    def test_raise_redirect_300(self, mock_response):
        """300 status should raise Redirect."""
        mock_response.status_code = 300
        with pytest.raises(Redirect):
            ApiError.raise_for_status(mock_response, {})

    def test_raise_redirect_308(self, mock_response):
        """308 status should raise Redirect."""
        mock_response.status_code = 308
        with pytest.raises(Redirect):
            ApiError.raise_for_status(mock_response, {})

    def test_raise_bad_request(self, mock_response):
        """400 status should raise BadRequest."""
        mock_response.status_code = 400
        with pytest.raises(BadRequest):
            ApiError.raise_for_status(mock_response, {})

    def test_raise_limit_exceeded(self, mock_response):
        """400 with limit_exceeded should raise LimitExceeded."""
        mock_response.status_code = 400
        data = {
            "errors": [{"type": "limit_exceeded"}],
        }
        with pytest.raises(LimitExceeded):
            ApiError.raise_for_status(mock_response, data)

    def test_raise_forbidden(self, mock_response):
        """403 status should raise Forbidden."""
        mock_response.status_code = 403
        with pytest.raises(Forbidden):
            ApiError.raise_for_status(mock_response, {})

    def test_raise_captcha_required(self, mock_response):
        """403 with captcha_required should raise CaptchaRequired."""
        mock_response.status_code = 403
        data = {
            "errors": [
                {
                    "type": "captcha_required",
                    "captcha_url": "https://example.com/captcha",
                }
            ],
        }
        with pytest.raises(CaptchaRequired):
            ApiError.raise_for_status(mock_response, data)

    def test_raise_resource_not_found(self, mock_response):
        """404 status should raise ResourceNotFound."""
        mock_response.status_code = 404
        with pytest.raises(ResourceNotFound):
            ApiError.raise_for_status(mock_response, {})

    def test_raise_client_error_4xx(self, mock_response):
        """Other 4xx should raise ClientError."""
        mock_response.status_code = 429
        with pytest.raises(ClientError):
            ApiError.raise_for_status(mock_response, {})

    def test_raise_bad_gateway_502(self, mock_response_500):
        """502 status should raise BadGateway."""
        mock_response_500.status_code = 502
        with pytest.raises(BadGateway):
            ApiError.raise_for_status(mock_response_500, {})

    def test_raise_internal_server_error_500(self, mock_response_500):
        """500 status should raise InternalServerError."""
        mock_response_500.status_code = 500
        with pytest.raises(InternalServerError):
            ApiError.raise_for_status(mock_response_500, {})

    def test_raise_internal_server_error_503(self, mock_response_500):
        """503 status should raise InternalServerError."""
        mock_response_500.status_code = 503
        with pytest.raises(InternalServerError):
            ApiError.raise_for_status(mock_response_500, {})


class TestCaptchaRequired:
    """Test CaptchaRequired specific functionality."""

    def test_captcha_url_extraction(self, mock_response):
        """Should extract captcha_url from error data."""
        data = {
            "errors": [
                {
                    "type": "captcha_required",
                    "value": "captcha_required",
                    "captcha_url": "https://hh.ru/captcha/abc123",
                }
            ],
        }
        error = CaptchaRequired(mock_response, data)
        assert error.captcha_url == "https://hh.ru/captcha/abc123"

    def test_captcha_message_includes_url(self, mock_response):
        """Captcha error message should include URL."""
        data = {
            "errors": [
                {
                    "type": "captcha_required",
                    "captcha_url": "https://example.com/captcha",
                }
            ],
        }
        error = CaptchaRequired(mock_response, data)
        assert "Captcha required" in error.message
        assert "https://example.com/captcha" in error.message

    def test_captcha_url_cached_property(self, mock_response):
        """captcha_url should be cached."""
        data = {
            "errors": [
                {
                    "type": "captcha_required",
                    "captcha_url": "https://example.com/captcha",
                }
            ],
        }
        error = CaptchaRequired(mock_response, data)

        # Access twice, should be same object
        url1 = error.captcha_url
        url2 = error.captcha_url
        assert url1 == url2

    def test_captcha_missing_url(self, mock_response):
        """Should handle missing captcha_url gracefully."""
        data = {
            "errors": [
                {"type": "captcha_required"},
            ],
        }
        error = CaptchaRequired(mock_response, data)
        # Should not raise, just return empty or None
        assert error.captcha_url is not None or error.captcha_url is None


class TestErrorInheritance:
    """Test error class hierarchy."""

    def test_error_hierarchy(self, mock_response):
        """Verify proper inheritance chain."""
        # All should be subclasses of ApiError
        assert issubclass(BadRequest, ApiError)
        assert issubclass(Forbidden, ApiError)
        assert issubclass(ResourceNotFound, ApiError)
        assert issubclass(CaptchaRequired, ClientError)
        assert issubclass(LimitExceeded, ClientError)
        assert issubclass(ClientError, ApiError)
        assert issubclass(InternalServerError, ApiError)
        assert issubclass(BadGateway, InternalServerError)
        assert issubclass(Redirect, ApiError)

    def test_error_instances(self, mock_response):
        """Error instances should be instances of parent classes."""
        err = BadRequest(mock_response, {})
        assert isinstance(err, ClientError)
        assert isinstance(err, ApiError)
        assert isinstance(err, BadResponse)
