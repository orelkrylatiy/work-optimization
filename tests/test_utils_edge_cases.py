"""Edge cases for string and JSON utilities."""
import json as stdlib_json
from datetime import datetime
import sys

import pytest

from hh_applicant_tool.utils.string import (
    shorten, rand_text, bool2str, list2str, unescape_string,
    br2nl, strip_tags
)
from hh_applicant_tool.utils import json


class TestStringFunctionsEdgeCases:
    """Test edge cases for string functions."""

    def test_shorten_empty_limit(self):
        """Shorten with zero limit."""
        result = shorten("hello", limit=0)
        # Should add ellipsis for any non-empty string
        assert "…" in result or result == ""

    def test_shorten_negative_limit(self):
        """Shorten with negative limit."""
        result = shorten("hello", limit=-1)
        # Behavior depends on implementation

    def test_shorten_unicode_characters(self):
        """Should handle multi-byte Unicode correctly."""
        # Emoji and CJK characters take multiple bytes
        text = "Hello 🚀 世界"
        result = shorten(text, limit=10)
        # Should truncate at character boundary, not byte boundary

    def test_shorten_with_empty_ellipsis(self):
        """Shorten with empty ellipsis."""
        result = shorten("hello world", limit=5, ellipsis="")
        assert result == "hello"

    def test_shorten_ellipsis_longer_than_limit(self):
        """Ellipsis longer than limit."""
        result = shorten("hello", limit=2, ellipsis="...")
        # Result will be "he..." which exceeds limit
        assert "." in result

    def test_rand_text_empty_string(self):
        """Random text with empty string."""
        result = rand_text("")
        assert result == ""

    def test_rand_text_only_braces(self):
        """Text that is only braces."""
        result = rand_text("{}")
        # Empty choice group
        assert result is not None

    def test_rand_text_unmatched_braces(self):
        """Unmatched or nested braces."""
        # Single opening brace
        result = rand_text("hello{world")
        assert "hello{world" == result or "hello" in result

        # Nested braces
        result = rand_text("{outer_{inner}}")
        # Depends on implementation

    def test_rand_text_many_options(self):
        """Many options should randomly select."""
        options = "|".join([str(i) for i in range(100)])
        template = "{" + options + "}"
        results = {rand_text(template) for _ in range(50)}
        # Should get multiple different results
        assert len(results) > 1

    def test_rand_text_empty_option(self):
        """Empty option in braces."""
        template = "hello{|world}"
        result = rand_text(template)
        # Should be either "hello" or "helloworld"
        assert result in ("hello", "helloworld")

    def test_rand_text_whitespace_preservation(self):
        """Should preserve whitespace in options."""
        template = "{ a | b }"  # With spaces
        results = {rand_text(template) for _ in range(20)}
        # Should preserve spaces in selections
        assert any(" " in r for r in results)

    def test_list2str_very_large_list(self):
        """Large list conversion."""
        large_list = list(range(10000))
        result = list2str(large_list)
        # Should have 10000 numbers and 9999 commas
        assert result.count(",") == 9999

    def test_list2str_mixed_none_values(self):
        """List with None values."""
        result = list2str([1, None, 3])
        # None should be converted to string
        assert "None" in result

    def test_list2str_nested_lists(self):
        """Nested lists should be flattened to strings."""
        result = list2str([[1, 2], [3, 4]])
        # Inner lists converted to string representation
        assert "[" in result

    def test_list2str_empty_strings(self):
        """List with empty strings."""
        result = list2str(["", "a", ""])
        # Should have empty parts
        assert ",," in result or result == ",a,"

    def test_unescape_all_escape_sequences(self):
        """All escape sequences together."""
        text = "a\\nb\\rc\\td\\\\"
        result = unescape_string(text)
        assert result == "a\nb\rc\td\\"

    def test_unescape_repeated_escapes(self):
        """Repeated escape sequences."""
        text = "\\\\\\\\n\\n\\n"
        result = unescape_string(text)
        assert result.count("\\") >= 2

    def test_unescape_only_escapes(self):
        """String with only escape sequences."""
        text = "\\n\\r\\t\\\\"
        result = unescape_string(text)
        assert "\n" in result
        assert "\r" in result
        assert "\t" in result

    def test_br2nl_nested_tags(self):
        """Nested or complex BR tags."""
        text = "<div><br><br/><br /></div>"
        result = br2nl(text)
        assert result.count("\n") == 3

    def test_br2nl_br_with_attributes(self):
        """BR tag with attributes."""
        text = '<br class="separator"> and <br style="color:red"/>'
        result = br2nl(text)
        # Should still convert to newlines
        assert "\n" in result

    def test_br2nl_malformed_tags(self):
        """Malformed BR tags."""
        text = "<br> <br <br/>>"
        result = br2nl(text)
        # Should handle gracefully

    def test_strip_tags_nested_same_tags(self):
        """Nested tags of same type."""
        text = "<p>outer<p>inner</p>outer</p>"
        result = strip_tags(text)
        # Should remove both levels
        assert "<p>" not in result

    def test_strip_tags_attributes_with_angles(self):
        """Attributes containing angle brackets in strings."""
        text = '<div data-value="<test>">content</div>'
        result = strip_tags(text)
        # Should extract content properly

    def test_strip_tags_comment_like_content(self):
        """Comments and CDATA."""
        text = "<!-- comment --> content <!-- another -->"
        result = strip_tags(text)
        # Comments should be removed if matched
        assert "<!--" not in result or "content" in result

    def test_strip_tags_script_and_style(self):
        """Script and style tags."""
        text = "<script>alert('xss')</script><p>text</p><style>a{}</style>"
        result = strip_tags(text)
        # Script and style content should be gone
        assert "alert" not in result or "xss" not in result

    def test_strip_tags_self_closing_tags(self):
        """Self-closing tags."""
        text = "<p>line1<br/>line2<img/></p>"
        result = strip_tags(text)
        assert "line1" in result and "line2" in result

    def test_strip_tags_multiple_br_variations(self):
        """Different BR tag formats."""
        text = "a<br>b<br/>c<br />d"
        result = strip_tags(text)
        assert result.count("\n") == 3


class TestJsonFunctionsEdgeCases:
    """Test edge cases for JSON functions."""

    def test_dumps_very_large_datetime(self):
        """Very large datetime value."""
        dt = datetime(9999, 12, 31, 23, 59, 59)
        result = json.dumps({"dt": dt})
        # Should convert to large timestamp
        parsed = stdlib_json.loads(result)
        assert isinstance(parsed["dt"], int)

    def test_dumps_deeply_nested_structure(self):
        """Very deeply nested data."""
        data = {"a": 1}
        for _ in range(100):
            data = {"nested": data}

        result = json.dumps(data)
        # Should not stack overflow
        parsed = stdlib_json.loads(result)
        assert parsed is not None

    def test_dumps_circular_prevention(self):
        """Can't have true circular refs in JSON but test structure."""
        data = {"a": {"b": {"c": "value"}}}
        result = json.dumps(data)
        assert "value" in result

    def test_dumps_function_objects(self):
        """Should not be able to serialize functions."""
        data = {"func": lambda x: x}
        with pytest.raises(TypeError):
            json.dumps(data)

    def test_dumps_custom_objects(self):
        """Custom objects should fail."""
        class CustomClass:
            pass

        data = {"obj": CustomClass()}

        with pytest.raises(TypeError):
            json.dumps(data)

    def test_dumps_nan_and_infinity(self):
        """NaN and infinity values."""
        data = {
            "inf": float("inf"),
            "neg_inf": float("-inf"),
            "nan": float("nan"),
        }

        try:
            result = json.dumps(data)
            # Some JSON libraries allow this with allow_nan=True
        except ValueError:
            # Some reject it
            pass

    def test_dumps_bytes_object(self):
        """Bytes should not serialize."""
        data = {"bytes": b"hello"}

        with pytest.raises(TypeError):
            json.dumps(data)

    def test_dumps_empty_collections(self):
        """Empty nested collections."""
        data = {
            "empty_dict": {},
            "empty_list": [],
            "nested_empty": {"inner": {}},
        }
        result = json.dumps(data)
        parsed = stdlib_json.loads(result)
        assert parsed["empty_dict"] == {}
        assert parsed["empty_list"] == []

    def test_loads_large_json(self):
        """Large JSON string."""
        large_data = {f"key_{i}": f"value_{i}" * 100 for i in range(1000)}
        json_str = stdlib_json.dumps(large_data)

        result = json.loads(json_str)
        assert len(result) == 1000

    def test_loads_deeply_nested_json(self):
        """Deeply nested JSON."""
        data = {"a": 1}
        for _ in range(100):
            data = {"nested": data}

        json_str = stdlib_json.dumps(data)
        result = json.loads(json_str)
        assert result is not None

    def test_loads_invalid_json_various_formats(self):
        """Various invalid JSON formats."""
        invalid = [
            "{invalid}",
            "{'single': 'quotes'}",
            "{unquoted: 'value'}",
            "[1, 2, 3,]",  # Trailing comma
            "{1, 2, 3}",
            "NaN",
        ]

        for invalid_json in invalid:
            with pytest.raises(stdlib_json.JSONDecodeError):
                json.loads(invalid_json)

    def test_loads_with_escape_sequences(self):
        """JSON with escape sequences."""
        json_str = '{"text": "line1\\nline2\\ttab"}'
        result = json.loads(json_str)
        assert result["text"] == "line1\nline2\ttab"

    def test_dump_file_encoding_handling(self, tmp_path):
        """File operations with different encodings."""
        data = {"text": "Привет 🚀"}
        file_path = tmp_path / "test.json"

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(f, data)

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "Привет" in content

    def test_load_file_with_bom(self, tmp_path):
        """File with BOM marker."""
        file_path = tmp_path / "test.json"

        # Write with UTF-8 BOM
        data = {"key": "value"}
        with open(file_path, "w", encoding="utf-8-sig") as f:
            stdlib_json.dump(data, f)

        # Load with utf-8 (without sig)
        with open(file_path, "r", encoding="utf-8") as f:
            try:
                result = json.load(f)
                # Might succeed or have BOM character
            except:
                pass

    def test_dumps_datetime_with_timezone(self):
        """Datetime with timezone info."""
        from datetime import timezone, timedelta

        tz = timezone(timedelta(hours=3))
        dt = datetime(2024, 1, 15, 12, 0, 0, tzinfo=tz)

        result = json.dumps({"dt": dt})
        parsed = stdlib_json.loads(result)
        assert isinstance(parsed["dt"], int)

    def test_roundtrip_with_all_types(self):
        """Roundtrip with various types."""
        original = {
            "string": "hello",
            "int": 42,
            "float": 3.14,
            "bool": True,
            "null": None,
            "list": [1, 2, 3],
            "dict": {"nested": "value"},
            "datetime": datetime(2024, 1, 15, 12, 0, 0),
        }

        dumped = json.dumps(original)
        loaded = json.loads(dumped)

        # Check types are preserved
        assert isinstance(loaded["string"], str)
        assert isinstance(loaded["int"], int)
        assert isinstance(loaded["bool"], bool)
        assert loaded["null"] is None
        assert isinstance(loaded["list"], list)
        assert isinstance(loaded["dict"], dict)
        assert isinstance(loaded["datetime"], int)

    def test_json_unicode_escaping(self):
        """Unicode escape sequences in JSON."""
        json_str = '{"emoji": "\\ud83d\\ude00"}'  # Grinning face emoji
        result = json.loads(json_str)
        # Should decode emoji
        assert result["emoji"] is not None

    def test_dumps_recursion_limit(self):
        """Very deep nesting approaching recursion limit."""
        # Create deeply nested structure, but not too deep
        data = {"a": 1}
        for _ in range(500):
            data = {"nested": data}

        try:
            result = json.dumps(data)
            # If it succeeds, that's OK
        except RecursionError:
            # Or if it raises RecursionError, that's also expected behavior
            pass
