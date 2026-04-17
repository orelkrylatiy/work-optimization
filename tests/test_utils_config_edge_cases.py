"""Edge cases and boundary tests for config utility."""
import json
import tempfile
from pathlib import Path
from threading import Thread, Lock
import time

import pytest

from hh_applicant_tool.utils.config import Config, get_config_path


class TestConfigEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_config_very_large_file(self):
        """Should handle large config files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.json"

            # Create large config with many keys
            large_data = {f"key_{i}": f"value_{i}" * 100 for i in range(1000)}
            with config_file.open("w") as f:
                json.dump(large_data, f)

            config = Config(config_file)
            assert len(config) == 1000
            assert config["key_500"] is not None

    def test_config_with_special_characters_in_values(self):
        """Should handle special characters correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.json"
            config = Config(config_file)

            special_data = {
                "quotes": 'He said "hello"',
                "backslash": "path\\to\\file",
                "newlines": "line1\nline2\nline3",
                "tabs": "col1\tcol2\tcol3",
                "unicode": "你好世界🌍",
            }
            config.save(special_data)

            config2 = Config(config_file)
            assert config2["quotes"] == 'He said "hello"'
            assert "line2" in config2["newlines"]
            assert config2["unicode"] == "你好世界🌍"

    def test_config_with_null_bytes(self):
        """Should handle files with problematic content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.json"

            # Valid JSON with special sequences
            data = {"value": "test\u0000null"}
            config = Config(config_file)
            config.save(data)

            config2 = Config(config_file)
            # Should have been saved and loaded

    def test_config_corrupted_json_graceful_handling(self):
        """Should not crash on corrupted JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.json"

            # Write partially corrupted JSON
            config_file.write_text('{"key": "value"')  # Missing closing brace

            # Should either load empty or handle gracefully
            config = Config(config_file)
            # Should not raise during init

    def test_config_file_permissions_issue(self):
        """Should handle file permission issues gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.json"
            config = Config(config_file)
            config.save({"key": "value"})

            # Try to make file read-only
            try:
                config_file.chmod(0o444)
                # Attempt to save should either fail or handle gracefully
                config.save({"new": "value"})
            finally:
                config_file.chmod(0o644)

    def test_config_concurrent_access(self):
        """Should handle concurrent read/write safely."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.json"
            config = Config(config_file)
            config.save({"initial": "value"})

            results = []
            errors = []

            def write_config(key, value):
                try:
                    config.save({key: value})
                    results.append((key, value))
                except Exception as e:
                    errors.append(e)

            # Start multiple threads writing
            threads = []
            for i in range(10):
                t = Thread(target=write_config, args=(f"key_{i}", f"value_{i}"))
                threads.append(t)
                t.start()

            for t in threads:
                t.join()

            # Should have completed without errors
            assert len(errors) == 0

    def test_config_deeply_nested_path(self):
        """Should handle deeply nested directory paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "a" / "b" / "c" / "d" / "e" / "config.json"
            config = Config(config_file)

            config.save({"nested": "value"})

            # Should have created all parent directories
            assert config_file.exists()

    def test_config_very_long_values(self):
        """Should handle very long string values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.json"
            config = Config(config_file)

            long_value = "x" * 1000000  # 1MB string
            config.save({"long": long_value})

            config2 = Config(config_file)
            assert len(config2["long"]) == 1000000

    def test_config_numeric_edge_values(self):
        """Should handle numeric edge values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.json"
            config = Config(config_file)

            config.save({
                "zero": 0,
                "negative": -999999,
                "large": 9999999999,
                "float": 3.14159265358979,
                "scientific": 1.23e-10,
            })

            config2 = Config(config_file)
            assert config2["zero"] == 0
            assert config2["negative"] == -999999
            assert config2["large"] == 9999999999

    def test_config_empty_nested_objects(self):
        """Should handle empty nested structures."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.json"
            config = Config(config_file)

            config.save({
                "empty_dict": {},
                "empty_list": [],
                "nested": {"inner": {}},
            })

            config2 = Config(config_file)
            assert config2["empty_dict"] == {}
            assert config2["empty_list"] == []

    def test_config_boolean_edge_cases(self):
        """Should handle boolean values correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.json"
            config = Config(config_file)

            config.save({
                "true": True,
                "false": False,
                "null": None,
            })

            config2 = Config(config_file)
            assert config2["true"] is True
            assert config2["false"] is False
            assert config2["null"] is None

    def test_config_key_name_edge_cases(self):
        """Should handle unusual key names."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.json"
            config = Config(config_file)

            config.save({
                "": "empty_key",
                " ": "space_key",
                "key with spaces": "value",
                "123": "numeric_key",
                "key.with.dots": "value",
                "key-with-dashes": "value",
            })

            config2 = Config(config_file)
            assert config2[""] == "empty_key"
            assert config2[" "] == "space_key"

    def test_config_repeated_saves_consistency(self):
        """Should maintain consistency across repeated saves."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.json"
            config = Config(config_file)

            initial = {"counter": 0}
            config.save(initial)

            for i in range(100):
                config.save({"counter": i})

            config2 = Config(config_file)
            assert config2["counter"] == 99

    def test_config_file_deleted_between_operations(self):
        """Should handle file being deleted after loading."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.json"
            config = Config(config_file)
            config.save({"key": "value"})

            # Delete file
            config_file.unlink()

            # Try to save - should recreate file
            config.save({"new_key": "new_value"})

            assert config_file.exists()

    def test_config_partial_write_recovery(self):
        """Should handle incomplete writes gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.json"

            # Write incomplete JSON
            config_file.write_text('{"incomplete":')

            # Loading should handle it
            config = Config(config_file)
            # Should not crash

    def test_config_with_circular_references(self):
        """Should handle data that could cause issues."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.json"
            config = Config(config_file)

            # Create structure (can't have actual circular refs in JSON)
            config.save({
                "a": {"b": {"c": {"d": "value"}}}
            })

            config2 = Config(config_file)
            assert config2["a"]["b"]["c"]["d"] == "value"

    def test_config_unicode_normalization(self):
        """Should handle Unicode normalization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.json"
            config = Config(config_file)

            # NFD vs NFC forms of the same character
            config.save({
                "café": "value1",  # NFC
                "café": "value2",  # NFD (same visual)
            })

            config2 = Config(config_file)
            # Should have loaded something

    def test_config_file_encoding_issues(self):
        """Should handle encoding issues gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.json"

            # Try to load with mismatched encoding
            config_file.write_bytes(b'\xff\xfe{"key": "value"}')  # UTF-16 BOM

            # Should handle or skip gracefully
            config = Config(config_file)

    def test_config_simultaneous_read_write(self):
        """Should handle simultaneous read and write."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.json"
            config = Config(config_file)
            config.save({"initial": "value"})

            def reader():
                for _ in range(50):
                    _ = config["initial"]
                    time.sleep(0.001)

            def writer():
                for i in range(50):
                    config.save({"counter": i})
                    time.sleep(0.001)

            t1 = Thread(target=reader)
            t2 = Thread(target=writer)

            t1.start()
            t2.start()

            t1.join()
            t2.join()

            # Should not crash or corrupt

    def test_config_getitem_always_returns_none_for_missing(self):
        """Override of __getitem__ should always use dict.get."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.json"
            config = Config(config_file)

            # Missing top-level keys return None instead of raising KeyError.
            assert config["a"] is None
