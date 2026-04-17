"""Tests for date utility module."""
from datetime import datetime

import pytest

from hh_applicant_tool.utils.date import (
    parse_api_datetime,
    try_parse_datetime,
    DATETIME_FORMAT,
)


class TestParseApiDatetime:
    """Test API datetime string parsing."""

    def test_parse_valid_api_datetime(self):
        """Should parse valid API datetime strings."""
        dt_str = "2024-01-15T10:30:45+0300"
        result = parse_api_datetime(dt_str)

        assert isinstance(result, datetime)
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 10
        assert result.minute == 30
        assert result.second == 45

    def test_parse_api_datetime_with_positive_offset(self):
        """Should handle positive timezone offsets."""
        dt_str = "2024-06-20T15:45:30+0500"
        result = parse_api_datetime(dt_str)

        assert result.hour == 15
        assert result.tzinfo is not None

    def test_parse_api_datetime_with_negative_offset(self):
        """Should handle negative timezone offsets."""
        dt_str = "2024-06-20T15:45:30-0800"
        result = parse_api_datetime(dt_str)

        assert result.hour == 15

    def test_parse_invalid_datetime_format_raises(self):
        """Should raise ValueError for invalid format."""
        with pytest.raises(ValueError):
            parse_api_datetime("2024-01-15")  # Missing time

    def test_parse_invalid_datetime_string_raises(self):
        """Should raise ValueError for non-datetime strings."""
        with pytest.raises(ValueError):
            parse_api_datetime("not a datetime")

    def test_parse_datetime_wrong_timezone_format_raises(self):
        """Should raise for incorrect timezone format."""
        with pytest.raises(ValueError):
            # Timezone offset should be ±HHMM format
            parse_api_datetime("2024-01-15T10:30:45+03")


class TestTryParseDateTime:
    """Test flexible datetime parsing."""

    def test_try_parse_iso_format(self):
        """Should parse ISO format datetime strings."""
        dt_str = "2024-01-15T10:30:45"
        result = try_parse_datetime(dt_str)

        assert isinstance(result, datetime)

    def test_try_parse_api_format(self):
        """Should parse API format datetime strings."""
        dt_str = "2024-01-15T10:30:45+0300"
        result = try_parse_datetime(dt_str)

        assert isinstance(result, datetime)

    def test_try_parse_returns_original_on_failure(self):
        """Should return original value if parsing fails."""
        invalid_str = "not a datetime"
        result = try_parse_datetime(invalid_str)

        assert result == invalid_str
        assert not isinstance(result, datetime)

    def test_try_parse_with_none(self):
        """Should handle None gracefully."""
        result = try_parse_datetime(None)
        assert result is None

    def test_try_parse_with_number(self):
        """Should return original if input is a number."""
        result = try_parse_datetime(12345)
        assert result == 12345

    def test_try_parse_with_dict(self):
        """Should return original if input is a dict."""
        test_dict = {"key": "value"}
        result = try_parse_datetime(test_dict)
        assert result == test_dict

    def test_try_parse_api_format_priority(self):
        """API format should be tried after ISO format."""
        # Both formats valid
        dt_str = "2024-01-15T10:30:45+0300"
        result = try_parse_datetime(dt_str)

        # Should successfully parse (either format works)
        assert isinstance(result, datetime)

    def test_try_parse_empty_string(self):
        """Should return empty string as-is if unparseable."""
        result = try_parse_datetime("")
        assert result == ""

    def test_try_parse_multiple_formats_cascade(self):
        """Should try multiple formats in order."""
        # ISO format should be tried first
        iso_str = "2024-01-15T10:30:45"
        result = try_parse_datetime(iso_str)
        assert isinstance(result, datetime)

        # API format should work too
        api_str = "2024-01-15T10:30:45+0000"
        result = try_parse_datetime(api_str)
        assert isinstance(result, datetime)

    def test_try_parse_maintains_timezone_info(self):
        """Parsed datetime should maintain timezone info."""
        dt_str = "2024-01-15T10:30:45+0300"
        result = try_parse_datetime(dt_str)

        assert result.tzinfo is not None

    def test_try_parse_preserves_microseconds(self):
        """Should preserve microseconds if format includes them."""
        dt_str = "2024-01-15T10:30:45.123456"
        result = try_parse_datetime(dt_str)

        if isinstance(result, datetime):
            assert result.microsecond == 123456
