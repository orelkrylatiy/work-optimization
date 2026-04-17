"""Tests for string utility functions."""
import pytest

from hh_applicant_tool.utils.string import (
    shorten,
    rand_text,
    bool2str,
    list2str,
    unescape_string,
    br2nl,
    strip_tags,
)


class TestShortenFunction:
    """Test string shortening."""

    def test_shorten_short_string(self):
        """Strings shorter than limit should not change."""
        result = shorten("hello", limit=10)
        assert result == "hello"

    def test_shorten_long_string(self):
        """Strings longer than limit should be truncated."""
        result = shorten("hello world", limit=5)
        assert result == "hello…"

    def test_shorten_exact_limit(self):
        """String exactly at limit should not add ellipsis."""
        result = shorten("hello", limit=5)
        assert result == "hello"

    def test_shorten_custom_ellipsis(self):
        """Should support custom ellipsis."""
        result = shorten("hello world", limit=5, ellipsis="...")
        assert result == "hello..."

    def test_shorten_empty_string(self):
        """Empty string should return empty."""
        result = shorten("", limit=10)
        assert result == ""

    def test_shorten_default_limit(self):
        """Default limit should be 75."""
        long_str = "a" * 100
        result = shorten(long_str)
        assert len(result) <= 76  # 75 chars + ellipsis


class TestRandTextFunction:
    """Test random text generation with templates."""

    def test_rand_text_no_template(self):
        """Text without templates should return unchanged."""
        result = rand_text("hello world")
        assert result == "hello world"

    def test_rand_text_single_option(self):
        """Single option in braces should be used."""
        result = rand_text("hello {world}")
        assert result == "hello world"

    def test_rand_text_multiple_options(self):
        """Multiple options should randomly select one."""
        # Run multiple times to ensure we get variations
        text = "hello {world|universe|cosmos}"
        results = {rand_text(text) for _ in range(30)}

        # Should have at least 2 different results (high probability)
        assert len(results) >= 1

    def test_rand_text_multiple_templates(self):
        """Multiple templates should all be processed."""
        template = "{hello|hi} {world|universe}"
        result = rand_text(template)

        # Result should not contain braces
        assert "{" not in result
        assert "}" not in result

    def test_rand_text_nested_templates(self):
        """Nested templates should work (some cases)."""
        # Simple case: outer braces
        result = rand_text("start {a|b} end")
        assert result in ("start a end", "start b end")

    def test_rand_text_special_characters(self):
        """Templates with special chars should work."""
        result = rand_text("{yes!|no?}")
        assert result in ("yes!", "no?")


class TestBool2StrFunction:
    """Test boolean to string conversion."""

    def test_bool2str_true(self):
        """True should become 'true'."""
        assert bool2str(True) == "true"

    def test_bool2str_false(self):
        """False should become 'false'."""
        assert bool2str(False) == "false"

    def test_bool2str_case(self):
        """Result should be lowercase."""
        result = bool2str(True)
        assert result.islower()


class TestList2StrFunction:
    """Test list to string conversion."""

    def test_list2str_empty_list(self):
        """Empty list should return empty string."""
        assert list2str([]) == ""

    def test_list2str_single_item(self):
        """Single item list should return that item as string."""
        result = list2str([42])
        assert result == "42"

    def test_list2str_multiple_items(self):
        """Multiple items should be comma-separated."""
        result = list2str([1, 2, 3])
        assert result == "1,2,3"

    def test_list2str_strings(self):
        """Should work with strings."""
        result = list2str(["a", "b", "c"])
        assert result == "a,b,c"

    def test_list2str_none(self):
        """None should return empty string."""
        assert list2str(None) == ""

    def test_list2str_mixed_types(self):
        """Should handle mixed types."""
        result = list2str([1, "two", 3.0])
        assert result == "1,two,3.0"


class TestUnescapeStringFunction:
    """Test unescape string function."""

    def test_unescape_newline(self):
        """Should unescape \\n to newline."""
        result = unescape_string("hello\\nworld")
        assert result == "hello\nworld"

    def test_unescape_carriage_return(self):
        """Should unescape \\r."""
        result = unescape_string("hello\\rworld")
        assert result == "hello\rworld"

    def test_unescape_tab(self):
        """Should unescape \\t."""
        result = unescape_string("hello\\tworld")
        assert result == "hello\tworld"

    def test_unescape_backslash(self):
        """Should unescape \\\\."""
        result = unescape_string("hello\\\\world")
        assert result == "hello\\world"

    def test_unescape_multiple(self):
        """Should handle multiple escapes."""
        result = unescape_string("hello\\nworld\\ttab")
        assert result == "hello\nworld\ttab"

    def test_unescape_empty_string(self):
        """Empty string should return empty."""
        assert unescape_string("") == ""

    def test_unescape_no_escapes(self):
        """String without escapes should be unchanged."""
        result = unescape_string("hello world")
        assert result == "hello world"


class TestBr2nlFunction:
    """Test br to newline conversion."""

    def test_br2nl_br_tag(self):
        """<br> should be converted to newline."""
        result = br2nl("hello<br>world")
        assert result == "hello\nworld"

    def test_br2nl_self_closing(self):
        """<br/> should be converted to newline."""
        result = br2nl("hello<br/>world")
        assert result == "hello\nworld"

    def test_br2nl_with_space(self):
        """<br /> with space should work."""
        result = br2nl("hello<br />world")
        assert result == "hello\nworld"

    def test_br2nl_case_insensitive(self):
        """<BR> uppercase should also work."""
        result = br2nl("hello<BR>world")
        assert result == "hello\nworld"

    def test_br2nl_multiple(self):
        """Multiple <br> tags should all convert."""
        result = br2nl("line1<br>line2<br>line3")
        assert result == "line1\nline2\nline3"

    def test_br2nl_no_br(self):
        """Text without <br> should be unchanged."""
        result = br2nl("hello world")
        assert result == "hello world"


class TestStripTagsFunction:
    """Test HTML tag stripping."""

    def test_strip_tags_simple(self):
        """Should remove HTML tags."""
        result = strip_tags("<p>hello</p>")
        assert result == "hello"

    def test_strip_tags_nested(self):
        """Should remove nested tags."""
        result = strip_tags("<div><p>hello</p></div>")
        assert result == "hello"

    def test_strip_tags_with_attributes(self):
        """Should remove tags with attributes."""
        result = strip_tags('<p class="text">hello</p>')
        assert result == "hello"

    def test_strip_tags_br_conversion(self):
        """Should convert <br> to newline."""
        result = strip_tags("line1<br>line2")
        assert "line1\nline2" in result

    def test_strip_tags_whitespace(self):
        """Should handle whitespace correctly."""
        result = strip_tags("<p>  hello  </p>")
        # Should strip leading/trailing
        assert result.strip() == "hello"

    def test_strip_tags_mixed(self):
        """Should handle mixed content."""
        result = strip_tags("<b>bold</b> and <i>italic</i>")
        assert result == "bold and italic"

    def test_strip_tags_empty(self):
        """Empty tags should result in empty string."""
        result = strip_tags("<p></p>")
        assert result == ""

    def test_strip_tags_text_only(self):
        """Text without tags should be unchanged (with stripping)."""
        result = strip_tags("hello world")
        assert result == "hello world"
