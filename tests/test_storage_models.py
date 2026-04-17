"""Tests for storage models."""
from datetime import datetime

import pytest

from hh_applicant_tool.storage.models.base import BaseModel, mapped, MISSING
from hh_applicant_tool.storage.models.vacancy import VacancyModel
from hh_applicant_tool.storage.models.employer import EmployerModel


class TestBaseModel:
    """Test BaseModel base functionality."""

    def test_base_model_is_dataclass(self):
        """BaseModel subclasses should be dataclasses."""

        class TestModel(BaseModel):
            name: str
            value: int

        instance = TestModel(name="test", value=42)
        assert instance.name == "test"
        assert instance.value == 42

    def test_base_model_to_dict(self):
        """to_dict() should convert to dictionary."""

        class TestModel(BaseModel):
            name: str
            value: int

        instance = TestModel(name="test", value=42)
        data = instance.to_dict()

        assert data == {"name": "test", "value": 42}

    def test_base_model_from_db(self):
        """from_db() should create instance from database dict."""

        class TestModel(BaseModel):
            name: str
            value: int

        data = {"name": "test", "value": 42}
        instance = TestModel.from_db(data)

        assert instance.name == "test"
        assert instance.value == 42

    def test_base_model_from_api(self):
        """from_api() should create instance from API response."""

        class TestModel(BaseModel):
            name: str
            value: int

        data = {"name": "test", "value": "42"}  # API returns string
        instance = TestModel.from_api(data)

        # Should coerce types
        assert instance.value == 42

    def test_base_model_to_db(self):
        """to_db() should prepare data for database."""

        class TestModel(BaseModel):
            name: str
            value: int

        instance = TestModel(name="test", value=42)
        db_data = instance.to_db()

        assert db_data["name"] == "test"
        assert db_data["value"] == 42


class TestMappedField:
    """Test mapped field decorator."""

    def test_mapped_with_path(self):
        """mapped() with path should extract nested values."""

        class TestModel(BaseModel):
            city: str = mapped(path="location.city.name")

        data = {
            "location": {
                "city": {
                    "id": 1,
                    "name": "Moscow",
                }
            }
        }
        instance = TestModel.from_api(data)
        assert instance.city == "Moscow"

    def test_mapped_with_transform(self):
        """mapped() with transform should apply function."""

        class TestModel(BaseModel):
            remote: bool = mapped(
                path="schedule.id",
                transform=lambda v: v == "remote"
            )

        data = {"schedule": {"id": "remote"}}
        instance = TestModel.from_api(data)
        assert instance.remote is True

        data = {"schedule": {"id": "office"}}
        instance = TestModel.from_api(data)
        assert instance.remote is False

    def test_mapped_with_default(self):
        """mapped() with default should use default if missing."""

        class TestModel(BaseModel):
            status: str = mapped(default="active")

        instance = TestModel.from_api({})
        assert instance.status == "active"

    def test_mapped_skip_src(self):
        """mapped() with skip_src should ignore source value."""

        class TestModel(BaseModel):
            name: str = mapped(skip_src=True)

        data = {"name": "from_api"}
        instance = TestModel.from_api(data)

        # Should not have the value since skip_src=True
        assert not hasattr(instance, "name") or instance.name is None

    def test_mapped_store_json(self):
        """mapped() with store_json should serialize to JSON in DB."""

        class TestModel(BaseModel):
            tags: list = mapped(store_json=True, default_factory=list)

        instance = TestModel(tags=["a", "b", "c"])
        db_data = instance.to_db()

        # Should be JSON string in database
        assert isinstance(db_data["tags"], str)
        assert "a" in db_data["tags"]


class TestVacancyModel:
    """Test VacancyModel specifics."""

    def test_vacancy_minimal(self):
        """VacancyModel should work with minimal data."""
        data = {
            "id": 123,
            "name": "Developer",
            "alternate_url": "https://hh.ru/vacancy/123",
            "area": {"id": 1, "name": "Moscow"},
        }
        vacancy = VacancyModel.from_api(data)

        assert vacancy.id == 123
        assert vacancy.name == "Developer"
        assert vacancy.area_id == 1
        assert vacancy.area_name == "Moscow"

    def test_vacancy_salary_normalization(self):
        """Salary should be normalized in __post_init__."""
        data = {
            "id": 123,
            "name": "Developer",
            "alternate_url": "https://hh.ru/vacancy/123",
            "area": {"id": 1, "name": "Moscow"},
            "salary": {"from": 100000, "to": 150000, "currency": "RUR"},
        }
        vacancy = VacancyModel.from_api(data)

        assert vacancy.salary_from == 100000
        assert vacancy.salary_to == 150000

    def test_vacancy_salary_only_from(self):
        """If only 'from' specified, 'to' should be set to 'from'."""
        data = {
            "id": 123,
            "name": "Developer",
            "alternate_url": "https://hh.ru/vacancy/123",
            "area": {"id": 1, "name": "Moscow"},
            "salary": {"from": 100000, "to": None, "currency": "RUR"},
        }
        vacancy = VacancyModel.from_api(data)

        assert vacancy.salary_from == 100000
        assert vacancy.salary_to == 100000

    def test_vacancy_salary_only_to(self):
        """If only 'to' specified, 'from' should be set to 'to'."""
        data = {
            "id": 123,
            "name": "Developer",
            "alternate_url": "https://hh.ru/vacancy/123",
            "area": {"id": 1, "name": "Moscow"},
            "salary": {"from": None, "to": 150000, "currency": "RUR"},
        }
        vacancy = VacancyModel.from_api(data)

        assert vacancy.salary_from == 150000
        assert vacancy.salary_to == 150000

    def test_vacancy_salary_none(self):
        """If both salary fields are None, should be 0."""
        data = {
            "id": 123,
            "name": "Developer",
            "alternate_url": "https://hh.ru/vacancy/123",
            "area": {"id": 1, "name": "Moscow"},
            "salary": {"from": None, "to": None, "currency": "RUR"},
        }
        vacancy = VacancyModel.from_api(data)

        assert vacancy.salary_from == 0
        assert vacancy.salary_to == 0

    def test_vacancy_remote_schedule(self):
        """Remote schedule should be extracted correctly."""
        data = {
            "id": 123,
            "name": "Developer",
            "alternate_url": "https://hh.ru/vacancy/123",
            "area": {"id": 1, "name": "Moscow"},
            "schedule": {"id": "remote"},
        }
        vacancy = VacancyModel.from_api(data)
        assert vacancy.remote is True

        data = {
            "id": 123,
            "name": "Developer",
            "alternate_url": "https://hh.ru/vacancy/123",
            "area": {"id": 1, "name": "Moscow"},
            "schedule": {"id": "full_day"},
        }
        vacancy = VacancyModel.from_api(data)
        assert vacancy.remote is False

    def test_vacancy_defaults(self):
        """Missing fields should have proper defaults."""
        data = {
            "id": 123,
            "name": "Developer",
            "alternate_url": "https://hh.ru/vacancy/123",
            "area": {"id": 1, "name": "Moscow"},
        }
        vacancy = VacancyModel.from_api(data)

        assert vacancy.currency == "RUR"
        assert vacancy.gross is False
        assert vacancy.remote is False
        assert vacancy.professional_roles == []

    def test_vacancy_experience_mapping(self):
        """Experience should be mapped from nested structure."""
        data = {
            "id": 123,
            "name": "Developer",
            "alternate_url": "https://hh.ru/vacancy/123",
            "area": {"id": 1, "name": "Moscow"},
            "experience": {"id": "between_3_and_6"},
        }
        vacancy = VacancyModel.from_api(data)
        assert vacancy.experience == "between_3_and_6"

    def test_vacancy_professional_roles_json(self):
        """professional_roles should be stored as JSON."""
        roles = [
            {"id": "python", "name": "Python Developer"},
            {"id": "backend", "name": "Backend Developer"},
        ]
        vacancy = VacancyModel(
            id=123,
            name="Developer",
            alternate_url="https://hh.ru/vacancy/123",
            area_id=1,
            area_name="Moscow",
            professional_roles=roles,
        )

        db_data = vacancy.to_db()
        assert isinstance(db_data["professional_roles"], str)

        # Should be deserializable
        loaded = VacancyModel.from_db(db_data)
        assert loaded.professional_roles == roles

    def test_vacancy_timestamps(self):
        """Should handle datetime fields."""
        data = {
            "id": 123,
            "name": "Developer",
            "alternate_url": "https://hh.ru/vacancy/123",
            "area": {"id": 1, "name": "Moscow"},
            "created_at": "2024-01-15T10:30:45+0300",
            "published_at": "2024-01-15T11:00:00+0300",
        }
        vacancy = VacancyModel.from_api(data)

        assert isinstance(vacancy.created_at, datetime)
        assert isinstance(vacancy.published_at, datetime)


class TestTypeCoercion:
    """Test type coercion in BaseModel."""

    def test_string_to_int_coercion(self):
        """String should be coerced to int."""

        class TestModel(BaseModel):
            value: int

        instance = TestModel.from_api({"value": "42"})
        assert instance.value == 42
        assert isinstance(instance.value, int)

    def test_string_to_bool_coercion(self):
        """String should be coerced to bool."""

        class TestModel(BaseModel):
            active: bool

        instance = TestModel.from_api({"active": "true"})
        # bool("true") is True, bool("false") is also True
        assert instance.active

    def test_coercion_failure_keeps_original(self):
        """If coercion fails, original value is kept."""

        class TestModel(BaseModel):
            value: int

        instance = TestModel.from_api({"value": "not_a_number"})
        # Should keep original value since coercion fails
        assert instance.value == "not_a_number"

    def test_datetime_parsing(self):
        """Datetime strings should be parsed."""

        class TestModel(BaseModel):
            timestamp: datetime

        instance = TestModel.from_api({"timestamp": "2024-01-15T10:30:45"})
        assert isinstance(instance.timestamp, datetime)


class TestMissingHandling:
    """Test handling of missing fields."""

    def test_missing_required_field(self):
        """Missing required field should raise."""

        class TestModel(BaseModel):
            name: str
            value: int

        with pytest.raises(TypeError):
            TestModel.from_api({})

    def test_missing_optional_field_with_default(self):
        """Missing optional field with default should use default."""

        class TestModel(BaseModel):
            name: str
            status: str = mapped(default="active")

        instance = TestModel.from_api({"name": "test"})
        assert instance.status == "active"

    def test_to_db_skips_missing(self):
        """to_db() should skip fields that weren't set."""

        class TestModel(BaseModel):
            name: str
            optional: str = mapped(default=None)

        instance = TestModel(name="test")
        db_data = instance.to_db()

        # Should have name but might not have optional if not set
        assert "name" in db_data
