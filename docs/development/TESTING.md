# Testing Guide

## Running Tests

### Basic Commands

```bash
# Run all tests
pytest tests/

# Run with verbose output
pytest tests/ -v

# Run specific test file
pytest tests/test_utils_string.py -v

# Run specific test class
pytest tests/test_utils_string.py::TestShortenFunction -v

# Run specific test
pytest tests/test_utils_string.py::TestShortenFunction::test_shorten_short_string -v
```

### Coverage

```bash
# Generate coverage report
pytest tests/ --cov=src/hh_applicant_tool --cov-report=html

# View coverage report
open htmlcov/index.html

# Coverage with terminal output
pytest tests/ --cov=src/hh_applicant_tool --cov-report=term-missing
```

### Filtering Tests

```bash
# Run only unit tests
pytest tests/ -m unit

# Run only edge case tests
pytest tests/ -m edge_cases

# Run tests for specific module
pytest tests/test_utils*.py -v

# Skip slow tests
pytest tests/ -m "not slow"
```

### Test Options

```bash
# Stop on first failure
pytest tests/ -x

# Show print statements
pytest tests/ -s

# Run last failed tests
pytest tests/ --lf

# Run failed tests first
pytest tests/ --ff

# Parallel execution
pytest tests/ -n auto
```

## Test Organization

### Test Files

- `test_utils_*.py` - Utility module tests (date, string, config, json, edge cases)
- `test_api_*.py` - API module tests (client, errors, edge cases)
- `test_storage_*.py` - Storage module tests (models, repositories, edge cases)
- `test_operations.py` - Operations module tests
- `test_main.py` - Main module and CLI tests

### Test Categories

Each test file contains multiple test classes:

```python
class TestFeature:
    """Test specific feature."""
    
    def test_basic_operation(self):
        """Test basic functionality."""
        
    def test_edge_case(self):
        """Test edge case."""
        
    def test_error_handling(self):
        """Test error handling."""
```

## Writing Tests

### Test Template

```python
import pytest
from hh_applicant_tool.module_path import function_or_class

class TestFeatureName:
    """Test feature description."""
    
    def test_basic_case(self):
        """Short description of what's tested."""
        # Arrange
        input_data = ...
        expected = ...
        
        # Act
        result = function_or_class(input_data)
        
        # Assert
        assert result == expected
    
    def test_error_case(self):
        """Should handle errors."""
        with pytest.raises(ValueError):
            function_or_class(invalid_data)
    
    def test_edge_case(self):
        """Should handle edge cases."""
        # Empty, None, extreme values, etc.
```

### Using Fixtures

```python
@pytest.fixture
def sample_data():
    """Provide sample data for tests."""
    return {"key": "value"}

class TestWithFixture:
    def test_using_fixture(self, sample_data):
        """Test using fixture."""
        assert sample_data["key"] == "value"
```

### Mocking

```python
from unittest.mock import Mock, patch

def test_with_mock():
    """Test with mocked dependency."""
    mock_obj = Mock(return_value=42)
    result = function_using_mock(mock_obj)
    assert result == 42

def test_with_patch():
    """Test with patching."""
    with patch('module.function') as mock_func:
        mock_func.return_value = "mocked"
        result = code_that_uses_function()
        assert result == "mocked"
```

## Test Coverage

### Current Coverage

- ✅ Utils module: 150+ tests (date, string, config, json)
- ✅ API module: 120+ tests (client, errors)
- ✅ Storage module: 85+ tests (models, repositories)
- 📋 Operations module: Placeholder tests
- 📋 Main module: Placeholder tests

### Coverage Goals

- Minimum: 70% line coverage
- Target: 85% line coverage
- Critical paths: 95% coverage

### Checking Coverage

```bash
# Generate coverage report
pytest tests/ --cov=src/hh_applicant_tool --cov-report=html

# View report
open htmlcov/index.html

# Show uncovered lines in terminal
pytest tests/ --cov=src/hh_applicant_tool --cov-report=term-missing
```

## CI/CD Integration

### GitHub Actions

Tests run automatically on:
- Push to main/develop
- Pull requests

Config: `.github/workflows/tests.yml`

### Local Pre-commit Hook

```bash
# Create pre-commit hook
cat > .git/hooks/pre-commit << 'EOF'
#!/bin/bash
pytest tests/ --tb=short || exit 1
EOF

chmod +x .git/hooks/pre-commit
```

## Debugging Tests

### Verbose Output

```bash
# Show all output including print statements
pytest tests/test_file.py::TestClass::test_method -vv -s

# Show local variables on failure
pytest tests/ -l

# Show full diff for assertions
pytest tests/ --tb=long
```

### Debugging Tools

```bash
# Drop into debugger on failure
pytest tests/ --pdb

# Drop into debugger on errors
pytest tests/ --pdbcls=IPython.terminal.debugger:TerminalPdb

# Show captured output
pytest tests/ --capture=no
```

## Performance

### Slow Tests

Tests marked as `@pytest.mark.slow`:

```bash
# Run only slow tests
pytest tests/ -m slow

# Skip slow tests
pytest tests/ -m "not slow"

# Set timeout
pytest tests/ --timeout=60
```

### Parallel Testing

```bash
# Install pytest-xdist
pip install pytest-xdist

# Run in parallel
pytest tests/ -n auto

# With specific worker count
pytest tests/ -n 4
```

## Troubleshooting

### Import Errors

```bash
# Verify PYTHONPATH
export PYTHONPATH=$PWD/src

# Run again
pytest tests/
```

### Missing Dependencies

```bash
# Install test dependencies
poetry install --with dev

# Or pip
pip install pytest pytest-cov pytest-mock
```

### Tests Not Found

```bash
# Check test discovery
pytest tests/ --collect-only

# Verify naming: test_*.py, Test*, test_*
```

## Best Practices

1. **One assertion per test** (when possible)
2. **Clear test names** describing what's tested
3. **Use fixtures** for common setup
4. **Mock external dependencies** (API, files)
5. **Test edge cases** (null, empty, extreme values)
6. **Keep tests independent** (no order dependency)
7. **Use parametrize** for multiple test cases

### Example Good Test

```python
@pytest.mark.parametrize("input,expected", [
    ("hello", "hello"),
    ("hello world", "hello w…"),  # 10 char limit
    ("", ""),
    (None, None),  # Edge case
])
def test_shorten_various_inputs(input, expected):
    """Test shorten with various inputs."""
    result = shorten(input, limit=10)
    assert result == expected
```

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Pytest Fixtures](https://docs.pytest.org/en/stable/fixture.html)
- [Coverage.py](https://coverage.readthedocs.io/)
- [Testing Best Practices](https://docs.pytest.org/en/stable/goodpractices.html)
