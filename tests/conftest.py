"""Shared fixtures for tests."""
import sqlite3
from pathlib import Path

import pytest

from hh_applicant_tool.storage.facade import StorageFacade
from hh_applicant_tool.storage.utils import init_db


@pytest.fixture
def db_conn() -> sqlite3.Connection:
    """Create in-memory SQLite database for testing."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


@pytest.fixture
def storage(db_conn: sqlite3.Connection) -> StorageFacade:
    """Create initialized storage facade with empty database."""
    return StorageFacade(db_conn)


@pytest.fixture
def sample_vacancy_data() -> dict:
    """Sample vacancy data from hh.ru API response."""
    return {
        "id": 12345,
        "name": "Python Developer",
        "alternate_url": "https://hh.ru/vacancy/12345",
        "area": {"id": 1, "name": "Москва"},
        "salary": {
            "from": 100000,
            "to": 150000,
            "currency": "RUR",
            "gross": False,
        },
        "schedule": {"id": "remote"},
        "experience": {"id": "between1And3"},
        "professional_roles": [{"id": 96, "name": "Backend Developer"}],
    }


@pytest.fixture
def sample_employer_data() -> dict:
    """Sample employer data from hh.ru API response."""
    return {
        "id": 999,
        "name": "Tech Corp",
        "accredited_it_employer": False,
        "trusted": False,
        "insider_view": False,
    }


@pytest.fixture
def sample_resume_data() -> dict:
    """Sample resume data from hh.ru API response."""
    return {
        "id": "resume_123",
        "title": "Senior Python Developer",
        "status": {"id": "published"},
    }
