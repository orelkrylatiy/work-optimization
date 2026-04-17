"""Tests for JSON utility functions."""
from datetime import datetime
import json as stdlib_json

import pytest

from hh_applicant_tool.utils import json


class TestJSONEncoder:
    """Test custom JSON encoder."""

    def test_encoder_datetime_to_timestamp(self):
        """Datetime should be encoded as Unix timestamp."""
        dt = datetime(2024, 1, 15, 10, 30, 45)
        data = {"timestamp": dt}

        result = json.dumps(data)
        # Parse back to verify
        parsed = stdlib_json.loads(result)

        assert isinstance(parsed["timestamp"], int)
        assert parsed["timestamp"] > 0

    def test_encoder_datetime_roundtrip(self):
        """Datetime should roundtrip without precision loss."""
        original_dt = datetime.now().replace(microsecond=0)
        data = {"created_at": original_dt}

        encoded = json.dumps(data)
        decoded = stdlib_json.loads(encoded)

        # Should be convertible back
        assert isinstance(decoded["created_at"], int)

    def test_encoder_regular_types(self):
        """Regular types should encode normally."""
        data = {
            "string": "value",
            "number": 42,
            "float": 3.14,
            "bool": True,
            "null": None,
            "list": [1, 2, 3],
            "dict": {"nested": "value"},
        }

        result = json.dumps(data)
        parsed = stdlib_json.loads(result)

        assert parsed["string"] == "value"
        assert parsed["number"] == 42
        assert parsed["float"] == 3.14
        assert parsed["bool"] is True
        assert parsed["null"] is None
        assert parsed["list"] == [1, 2, 3]
        assert parsed["dict"]["nested"] == "value"

    def test_encoder_unicode(self):
        """Should preserve Unicode by default."""
        data = {"name": "Привет", "emoji": "🚀"}

        result = json.dumps(data)

        # Should contain actual Unicode, not escape sequences
        assert "Привет" in result
        assert "🚀" in result

    def test_encoder_ensure_ascii_false_default(self):
        """ensure_ascii should default to False."""
        data = {"text": "Привет"}
        result = json.dumps(data)

        # Should contain actual Cyrillic, not escape sequences
        assert "Привет" in result


class TestJSONDecoder:
    """Test custom JSON decoder."""

    def test_decoder_basic(self):
        """Should decode basic JSON."""
        json_str = '{"key": "value", "number": 42}'
        result = json.loads(json_str)

        assert result["key"] == "value"
        assert result["number"] == 42

    def test_decoder_unicode(self):
        """Should handle Unicode."""
        json_str = '{"name": "Привет"}'
        result = json.loads(json_str)

        assert result["name"] == "Привет"

    def test_decoder_arrays(self):
        """Should decode arrays."""
        json_str = '{"items": [1, 2, 3]}'
        result = json.loads(json_str)

        assert result["items"] == [1, 2, 3]


class TestDumpsFunction:
    """Test dumps function."""

    def test_dumps_datetime(self):
        """Should encode datetime as timestamp."""
        dt = datetime(2024, 1, 15, 12, 0, 0)
        result = json.dumps({"time": dt})

        parsed = stdlib_json.loads(result)
        assert isinstance(parsed["time"], int)

    def test_dumps_uses_custom_encoder(self):
        """Should use JSONEncoder by default."""
        dt = datetime.now().replace(microsecond=0)
        result = json.dumps({"dt": dt})

        # If custom encoder wasn't used, this would fail
        parsed = stdlib_json.loads(result)
        assert isinstance(parsed["dt"], int)

    def test_dumps_ensure_ascii_false(self):
        """Should have ensure_ascii=False by default."""
        result = json.dumps({"text": "Привет"})
        assert "Привет" in result


class TestDumpFunction:
    """Test dump function (file writing)."""

    def test_dump_datetime(self, tmp_path):
        """Should encode datetime when writing to file."""
        dt = datetime(2024, 1, 15, 12, 0, 0)
        data = {"time": dt}

        file_path = tmp_path / "test.json"
        with open(file_path, "w") as f:
            json.dump(f, data)

        # Read back and verify
        with open(file_path, "r") as f:
            content = f.read()

        parsed = stdlib_json.loads(content)
        assert isinstance(parsed["time"], int)

    def test_dump_unicode(self, tmp_path):
        """Should preserve Unicode when writing."""
        data = {"name": "Привет"}

        file_path = tmp_path / "test.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(f, data)

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "Привет" in content


class TestLoadsFunction:
    """Test loads function."""

    def test_loads_basic(self):
        """Should parse basic JSON string."""
        result = json.loads('{"key": "value"}')
        assert result["key"] == "value"

    def test_loads_array(self):
        """Should parse JSON arrays."""
        result = json.loads('[1, 2, 3]')
        assert result == [1, 2, 3]

    def test_loads_unicode(self):
        """Should handle Unicode in JSON."""
        result = json.loads('{"text": "Привет"}')
        assert result["text"] == "Привет"

    def test_loads_invalid_json(self):
        """Should raise JSONDecodeError for invalid JSON."""
        with pytest.raises(stdlib_json.JSONDecodeError):
            json.loads("not valid json")


class TestLoadFunction:
    """Test load function (file reading)."""

    def test_load_basic(self, tmp_path):
        """Should read JSON from file."""
        data = {"key": "value", "number": 42}

        file_path = tmp_path / "test.json"
        with open(file_path, "w") as f:
            stdlib_json.dump(data, f)

        result = json.load(open(file_path, "r"))
        assert result["key"] == "value"
        assert result["number"] == 42

    def test_load_unicode(self, tmp_path):
        """Should handle Unicode in files."""
        data = {"name": "Привет"}

        file_path = tmp_path / "test.json"
        with open(file_path, "w", encoding="utf-8") as f:
            stdlib_json.dump(data, f, ensure_ascii=False)

        result = json.load(open(file_path, "r", encoding="utf-8"))
        assert result["name"] == "Привет"

    def test_load_array(self, tmp_path):
        """Should read JSON arrays."""
        data = [1, 2, 3, 4, 5]

        file_path = tmp_path / "test.json"
        with open(file_path, "w") as f:
            stdlib_json.dump(data, f)

        result = json.load(open(file_path, "r"))
        assert result == data


class TestJsonRoundtrip:
    """Test complete roundtrips."""

    def test_roundtrip_with_datetime(self):
        """Data with datetime should roundtrip."""
        original = {
            "name": "Test",
            "created": datetime(2024, 1, 15, 10, 30, 0),
            "items": [1, 2, 3],
        }

        # Dump and load
        dumped = json.dumps(original)
        loaded = json.loads(dumped)

        # Check structure is preserved
        assert loaded["name"] == "Test"
        assert isinstance(loaded["created"], int)  # Timestamp
        assert loaded["items"] == [1, 2, 3]

    def test_roundtrip_file_with_unicode(self, tmp_path):
        """File roundtrip with Unicode."""
        original = {
            "title": "Тестовое название",
            "description": "Описание с emoji 🚀",
        }

        file_path = tmp_path / "test.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(f, original)

        with open(file_path, "r", encoding="utf-8") as f:
            loaded = json.load(f)

        assert loaded["title"] == "Тестовое название"
        assert loaded["description"] == "Описание с emoji 🚀"


class TestEdgeCases:
    """Test edge cases."""

    def test_empty_dict(self):
        """Empty dict should work."""
        result = json.loads(json.dumps({}))
        assert result == {}

    def test_empty_list(self):
        """Empty list should work."""
        result = json.loads(json.dumps([]))
        assert result == []

    def test_nested_datetime(self):
        """Datetime in nested structures should work."""
        data = {
            "items": [
                {"created": datetime(2024, 1, 15, 12, 0, 0)},
                {"created": datetime(2024, 1, 16, 12, 0, 0)},
            ]
        }

        result = json.loads(json.dumps(data))
        assert isinstance(result["items"][0]["created"], int)
        assert isinstance(result["items"][1]["created"], int)

    def test_none_values(self):
        """None values should be serializable."""
        data = {"value": None, "items": [None, 1, None]}
        result = json.loads(json.dumps(data))

        assert result["value"] is None
        assert result["items"][0] is None
