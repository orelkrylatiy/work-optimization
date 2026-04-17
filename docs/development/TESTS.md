# Test Coverage Documentation

## Overview
**Total Test Files:** 16
**Total Test Cases:** 400+
**Coverage Focus:** Critical modules with boundary conditions

---

## Test Files & Coverage

### Utils Tests (4 files, 150+ tests)

#### `test_utils_date.py` - 17 tests
- API datetime parsing (`parse_api_datetime`)
- Flexible datetime parsing (`try_parse_datetime`)
- **Edge cases covered:**
  - Leap years (Feb 29)
  - Leap years non-leap validation
  - End of year dates
  - Unix epoch (1970-01-01)
  - Year 9999
  - Timezone offset extremes (Â±12:00/-11:00)
  - Invalid dates/times
  - Malformed timezones

#### `test_utils_date_edge_cases.py` - 40+ tests
- Boundary conditions for all date components
- Special dates and timezones
- Invalid format handling
- Edge case combinations

#### `test_utils_string.py` - 42 tests
- `shorten()` - string truncation with ellipsis
- `rand_text()` - template text generation
- `bool2str()` - boolean conversion
- `list2str()` - list to CSV conversion
- `unescape_string()` - escape sequence handling
- `br2nl()` - HTML BR tag conversion
- `strip_tags()` - HTML tag removal
- **Edge cases:** Unicode, empty strings, special characters

#### `test_utils_edge_cases.py` - 60+ tests
- Very large strings (1MB+)
- Deeply nested structures (100+ levels)
- Unicode/emoji handling
- Special characters and escaping
- Edge cases for all string functions

#### `test_utils_config.py` - 16 tests
- Configuration loading/saving
- Path resolution (Windows/Mac/Linux)
- File I/O operations
- **Edge cases covered:**
  - Large config files (1000+ keys)
  - Special characters
  - Unicode content
  - File permission issues
  - Concurrent access

#### `test_utils_config_edge_cases.py` - 30+ tests
- Very large files
- Deeply nested paths
- Corrupted JSON
- Concurrent read/write
- File deletion recovery
- Threading safety

#### `test_utils_json.py` - 30+ tests
- Custom JSON encoder (datetime handling)
- Custom JSON decoder
- `dumps()` / `dump()` functions
- `loads()` / `load()` functions
- **Edge cases:** datetime serialization, Unicode, circular structures

---

### API Tests (6 files, 120+ tests)

#### `test_api_client.py` - Existing tests
- BaseClient initialization
- Default headers
- Thread locks
- Session management
- Delay handling

#### `test_api_client_extended.py` - 20+ tests
- Invalid methods
- URL resolution
- Custom headers
- Session lifecycle

#### `test_api_client_edge_cases.py` - 40+ tests
- Zero/negative/very large delays
- Base URL variations (IP, IPv6, localhost)
- Very long user agents
- Thread lock reentrance
- Concurrent lock acquisition
- **Edge cases:** extreme delay values, malformed URLs

#### `test_api_errors.py` - Existing tests
- Error hierarchy
- Status code mapping
- Message extraction

#### `test_api_errors_extended.py` - 26+ tests
- All HTTP status codes (300s, 400s, 500s)
- Error message extraction priorities
- Captcha required handling
- Limit exceeded handling
- Error hierarchy verification

#### `test_api_errors_edge_cases.py` - 50+ tests
- Empty error data
- None values in errors array
- Deeply nested error structures
- Missing type/value fields
- Multiple errors with same values
- Unicode in error messages
- **Edge cases:** malformed responses, extreme data structures

---

### Storage Tests (3 files, 85+ tests)

#### `test_storage_models.py` - 25+ tests
- BaseModel functionality
- `mapped()` field decorator
- VacancyModel specifics
- Type coercion
- Salary normalization
- Datetime parsing
- **Edge cases:** nested data, transformations, JSON fields

#### `test_storage_models_edge_cases.py` - 60+ tests
- Empty strings
- Very large numbers (999999999)
- Negative numbers
- Float precision
- Zero values
- Inverted salary ranges (from > to)
- Missing optional fields
- Deep nesting (10+ levels)
- Unicode in all field types
- Corrupted JSON fields
- Transform function errors

#### `test_storage_repositories.py` - Existing tests
- Vacancy operations
- Employer operations
- Resume operations
- Transaction handling

---

## Running Tests

### Quick Start
```bash
# All tests
pytest tests/ -v

# Specific file
pytest tests/test_utils_string.py -v

# With coverage report
pytest tests/ --cov=src/hh_applicant_tool --cov-report=html

# Only passing/failing
pytest tests/ -v --tb=short

# Stop on first failure
pytest tests/ -x
```

### Groups
```bash
# Utils tests only
pytest tests/test_utils*.py -v

# API tests only
pytest tests/test_api*.py -v

# Storage tests only
pytest tests/test_storage*.py -v

# Edge cases only
pytest tests/*edge_cases.py -v
```

---

## Edge Cases Covered

### Data Validation
- âœ… Null/None/empty values
- âœ… Extreme numeric values (0, negatives, 999999999)
- âœ… Empty strings/lists/dicts
- âœ… Very large collections (10000+ items)

### Encoding & Unicode
- âœ… UTF-8, UTF-16, different BOM markers
- âœ… Multi-byte characters (CJK, emoji)
- âœ… Special escape sequences
- âœ… Invalid byte sequences

### Dates & Times
- âœ… Leap years (Feb 29, 2024 etc)
- âœ… Non-leap years (Feb 29, 2023)
- âœ… Extreme dates (1970, 9999)
- âœ… Timezone offsets (Â±12:00, UTC, etc)
- âœ… Invalid dates (Feb 30, month 13)

### File Operations
- âœ… Permission errors (read-only)
- âœ… Missing files/directories
- âœ… Corrupted content
- âœ… Concurrent access
- âœ… File deletion between operations
- âœ… Very large files (1MB+)

### Concurrency
- âœ… Race conditions
- âœ… Lock reentrance
- âœ… Simultaneous read/write
- âœ… Multiple thread contention

### API/Network
- âœ… All HTTP status codes (300, 301-308, 400, 403, 404, 429, 500, 502, 503)
- âœ… Empty responses
- âœ… Malformed JSON
- âœ… Missing error fields
- âœ… Unicode in error messages

### Nested Structures
- âœ… Deep nesting (100+ levels)
- âœ… Empty nested objects
- âœ… Mixed types in nested data
- âœ… Circular-like references

---

## Known Limitations

1. **Mocking**: Some tests use mocks instead of real HTTP calls
2. **Integration**: Limited integration tests (focus on unit)
3. **Performance**: Not benchmarking (only correctness)
4. **Real-world data**: Using synthetic test data

---

## Future Improvements

- [ ] Add integration tests with real API
- [ ] Performance benchmarking tests
- [ ] Load testing for concurrent operations
- [ ] Coverage for operations/* modules
- [ ] Coverage for main.py and CLI
- [ ] E2E tests for complete workflows

---

## Test Maintenance

When adding new tests:
1. Follow existing naming convention (`test_*.py`)
2. Group related tests in classes
3. Add edge cases, not just happy path
4. Document non-obvious test logic
5. Use descriptive assertion messages

