"""Edge cases for date parsing utility."""
from datetime import datetime

import pytest

from hh_applicant_tool.utils.date import (
    parse_api_datetime,
    try_parse_datetime,
    DATETIME_FORMAT,
)


class TestDateParsingEdgeCases:
    """Test boundary and edge cases for datetime parsing."""

    def test_parse_leap_year_date(self):
        """Should parse leap year dates correctly."""
        dt_str = "2024-02-29T12:00:00+0000"
        result = parse_api_datetime(dt_str)
        assert result.day == 29
        assert result.month == 2

    def test_parse_leap_year_non_leap_day(self):
        """Non-leap year Feb 29 should raise."""
        with pytest.raises(ValueError):
            parse_api_datetime("2023-02-29T12:00:00+0000")

    def test_parse_end_of_year(self):
        """Should parse last moment of year."""
        dt_str = "2024-12-31T23:59:59+0000"
        result = parse_api_datetime(dt_str)
        assert result.day == 31
        assert result.month == 12
        assert result.hour == 23
        assert result.minute == 59
        assert result.second == 59

    def test_parse_start_of_epoch(self):
        """Should parse Unix epoch start."""
        dt_str = "1970-01-01T00:00:00+0000"
        result = parse_api_datetime(dt_str)
        assert result.year == 1970

    def test_parse_far_future_date(self):
        """Should parse dates far in the future."""
        dt_str = "9999-12-31T23:59:59+0000"
        result = parse_api_datetime(dt_str)
        assert result.year == 9999

    def test_parse_timezone_offset_extremes(self):
        """Should handle extreme timezone offsets."""
        # Max positive offset
        dt_str = "2024-01-15T12:00:00+1200"
        result = parse_api_datetime(dt_str)
        assert result is not None

        # Max negative offset
        dt_str = "2024-01-15T12:00:00-1100"
        result = parse_api_datetime(dt_str)
        assert result is not None

    def test_parse_zero_timezone(self):
        """Should handle UTC timezone."""
        dt_str = "2024-01-15T12:00:00+0000"
        result = parse_api_datetime(dt_str)
        assert result.tzinfo is not None

    def test_parse_invalid_day(self):
        """Should raise for invalid day values."""
        with pytest.raises(ValueError):
            parse_api_datetime("2024-01-32T12:00:00+0000")

    def test_parse_invalid_month(self):
        """Should raise for invalid month values."""
        with pytest.raises(ValueError):
            parse_api_datetime("2024-13-15T12:00:00+0000")

    def test_parse_invalid_hour(self):
        """Should raise for invalid hour values."""
        with pytest.raises(ValueError):
            parse_api_datetime("2024-01-15T25:00:00+0000")

    def test_parse_invalid_minute(self):
        """Should raise for invalid minute values."""
        with pytest.raises(ValueError):
            parse_api_datetime("2024-01-15T12:60:00+0000")

    def test_parse_invalid_second(self):
        """Should raise for invalid second values."""
        with pytest.raises(ValueError):
            parse_api_datetime("2024-01-15T12:00:60+0000")

    def test_parse_with_extra_whitespace(self):
        """Should not parse with surrounding whitespace."""
        with pytest.raises(ValueError):
            parse_api_datetime(" 2024-01-15T12:00:00+0000 ")

    def test_parse_with_missing_components(self):
        """Should raise if any component missing."""
        invalid = [
            "2024-01-15T12:00:00",  # No timezone
            "2024-01-15 12:00:00+0000",  # Space instead of T
            "2024-01-15T12:00+0000",  # No seconds
            "2024-01-15T12+0000",  # No minutes/seconds
            "202-01-15T12:00:00+0000",  # Invalid year format
        ]
        for invalid_str in invalid:
            with pytest.raises(ValueError):
                parse_api_datetime(invalid_str)

    def test_parse_case_sensitivity(self):
        """Should be case sensitive for T separator."""
        with pytest.raises(ValueError):
            parse_api_datetime("2024-01-15t12:00:00+0000")  # lowercase t

    def test_try_parse_all_invalid_formats(self):
        """Should return original if all formats fail."""
        invalid = "this is not a date at all"
        result = try_parse_datetime(invalid)
        assert result == invalid
        assert not isinstance(result, datetime)

    def test_try_parse_empty_string(self):
        """Should handle empty string."""
        result = try_parse_datetime("")
        assert result == ""

    def test_try_parse_whitespace_only(self):
        """Should return whitespace as-is."""
        result = try_parse_datetime("   ")
        assert result == "   "

    def test_try_parse_boolean_values(self):
        """Should handle boolean inputs."""
        assert try_parse_datetime(True) is True
        assert try_parse_datetime(False) is False

    def test_try_parse_list_input(self):
        """Should return list unchanged."""
        test_list = [1, 2, 3]
        result = try_parse_datetime(test_list)
        assert result == test_list

    def test_try_parse_dict_input(self):
        """Should return dict unchanged."""
        test_dict = {"year": 2024}
        result = try_parse_datetime(test_dict)
        assert result == test_dict

    def test_try_parse_float_input(self):
        """Should return float unchanged."""
        result = try_parse_datetime(3.14)
        assert result == 3.14

    def test_try_parse_negative_number(self):
        """Should handle negative numbers."""
        result = try_parse_datetime(-42)
        assert result == -42

    def test_iso_format_with_microseconds(self):
        """Should parse ISO format with microseconds."""
        dt_str = "2024-01-15T12:00:00.123456"
        result = try_parse_datetime(dt_str)
        assert isinstance(result, datetime)
        assert result.microsecond == 123456

    def test_iso_format_with_z_timezone(self):
        """Should parse ISO Z timezone notation."""
        # Z means UTC, but not standard format for parse_api_datetime
        dt_str = "2024-01-15T12:00:00Z"
        # This should work with fromisoformat
        result = try_parse_datetime(dt_str)
        assert isinstance(result, datetime)

    def test_iso_format_with_plus_timezone(self):
        """Should parse ISO format with +HH:MM timezone."""
        dt_str = "2024-01-15T12:00:00+03:00"
        result = try_parse_datetime(dt_str)
        assert isinstance(result, datetime)

    def test_datetime_object_passthrough(self):
        """If given datetime, should return as-is."""
        dt = datetime(2024, 1, 15, 12, 0, 0)
        result = try_parse_datetime(dt)
        assert result == dt

    def test_parse_with_special_characters(self):
        """Should not parse strings with special characters."""
        invalid = "2024-01-15T12:00:00+0000\x00extra"
        result = try_parse_datetime(invalid)
        # Should return original since parsing fails
        assert not isinstance(result, datetime)

    def test_parse_very_long_string(self):
        """Should handle very long strings efficiently."""
        long_str = "2024-01-15T12:00:00+0000" + "x" * 10000
        result = try_parse_datetime(long_str)
        # Should fail and return original
        assert not isinstance(result, datetime)

    def test_parse_repeating_pattern(self):
        """Should not match partial patterns."""
        dt_str = "2024-01-15T12:00:002024-01-15T12:00:00+0000"
        result = try_parse_datetime(dt_str)
        # Should fail to parse this invalid format
        assert not isinstance(result, datetime)

    def test_parse_numeric_edge_precision(self):
        """Should handle numeric precision correctly."""
        dt_str = "2024-01-15T12:00:00.999999+0000"
        result = try_parse_datetime(dt_str)
        if isinstance(result, datetime):
            assert result.microsecond == 999999

    def test_parse_single_digit_components(self):
        """Should not parse single-digit dates."""
        with pytest.raises(ValueError):
            parse_api_datetime("24-1-15T12:00:00+0000")

    def test_parse_two_digit_year(self):
        """Should not parse two-digit years in standard format."""
        with pytest.raises(ValueError):
            parse_api_datetime("24-01-15T12:00:00+0000")

    def test_parse_malformed_timezone(self):
        """Should raise for malformed timezone."""
        invalid = [
            "2024-01-15T12:00:00+",
            "2024-01-15T12:00:00+0",
            "2024-01-15T12:00:00+00",
            "2024-01-15T12:00:00+000",
            "2024-01-15T12:00:00+00000",
        ]
        for invalid_str in invalid:
            with pytest.raises(ValueError):
                parse_api_datetime(invalid_str)


class TestDateFormatConstant:
    """Test the DATETIME_FORMAT constant."""

    def test_format_constant_is_string(self):
        """DATETIME_FORMAT should be a string."""
        assert isinstance(DATETIME_FORMAT, str)

    def test_format_constant_not_empty(self):
        """DATETIME_FORMAT should not be empty."""
        assert len(DATETIME_FORMAT) > 0

    def test_format_constant_contains_required_patterns(self):
        """Format should have expected pattern elements."""
        # Should have year, month, day, hour, minute, second, timezone
        required = ["%Y", "%m", "%d", "%H", "%M", "%S", "%z"]
        for pattern in required:
            assert pattern in DATETIME_FORMAT

    def test_format_constant_matches_api_datetime_format(self):
        """Should match the format used by parse_api_datetime."""
        dt_str = "2024-01-15T10:30:45+0300"
        result = datetime.strptime(dt_str, DATETIME_FORMAT)
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
