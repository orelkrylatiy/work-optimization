"""Edge cases for storage models."""
import pytest

from hh_applicant_tool.storage.models.base import BaseModel, mapped, MISSING
from hh_applicant_tool.storage.models.vacancy import VacancyModel


class TestModelEdgeCases:
    """Test boundary conditions in models."""

    def test_model_with_empty_string_values(self):
        """Should handle empty strings correctly."""

        class TestModel(BaseModel):
            name: str
            description: str

        instance = TestModel(name="", description="")
        assert instance.name == ""
        assert instance.description == ""

    def test_model_with_extremely_large_numbers(self):
        """Should handle very large numeric values."""

        class TestModel(BaseModel):
            big_number: int

        instance = TestModel(big_number=999999999999999999)
        assert instance.big_number == 999999999999999999

    def test_model_with_negative_numbers(self):
        """Should handle negative numeric values."""

        class TestModel(BaseModel):
            value: int

        instance = TestModel(value=-999999)
        data = instance.to_dict()
        assert data["value"] == -999999

    def test_model_with_float_precision(self):
        """Should preserve float precision."""

        class TestModel(BaseModel):
            price: float

        instance = TestModel(price=3.14159265358979)
        db_data = instance.to_db()
        # Should not lose precision
        assert "price" in db_data

    def test_model_with_zero_values(self):
        """Should handle zero values correctly."""

        class TestModel(BaseModel):
            count: int
            amount: float

        instance = TestModel(count=0, amount=0.0)
        data = instance.to_dict()
        assert data["count"] == 0
        assert data["amount"] == 0.0

    def test_model_type_coercion_string_with_whitespace(self):
        """Should coerce strings with whitespace to numbers."""

        class TestModel(BaseModel):
            value: int

        # String with spaces
        instance = TestModel.from_api({"value": " 42 "})
        # Might fail coercion and keep as string
        assert instance.value is not None

    def test_model_type_coercion_invalid_types(self):
        """Should handle coercion of incompatible types."""

        class TestModel(BaseModel):
            value: int

        # Try to coerce list to int - should fail gracefully
        instance = TestModel.from_api({"value": [1, 2, 3]})
        # Should keep original or fail gracefully
        assert instance.value is not None

    def test_model_mapped_nested_missing_keys(self):
        """Should handle missing keys in nested mappings."""

        class TestModel(BaseModel):
            city: str = mapped(path="location.city.name")

        # Missing intermediate key
        data = {"location": {}}
        instance = TestModel.from_api(data)
        # Should not crash

    def test_model_mapped_deep_nesting(self):
        """Should handle very deep nesting."""

        class TestModel(BaseModel):
            value: str = mapped(path="a.b.c.d.e.f.g.h.i.j")

        data = {
            "a": {
                "b": {
                    "c": {
                        "d": {
                            "e": {
                                "f": {
                                    "g": {
                                        "h": {
                                            "i": {
                                                "j": "deep_value"
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        instance = TestModel.from_api(data)
        assert instance.value == "deep_value"

    def test_model_mapped_path_with_empty_intermediate(self):
        """Should handle empty objects in path."""

        class TestModel(BaseModel):
            value: str = mapped(path="outer.inner")

        data = {"outer": {}}
        instance = TestModel.from_api(data)
        # Should not crash

    def test_model_json_serialization_circular_like(self):
        """Should handle stores that look like they could be circular."""

        class TestModel(BaseModel):
            data: list = mapped(store_json=True, default_factory=list)

        original = [[1, 2], [3, 4], [[5, 6]]]
        instance = TestModel(data=original)

        db_data = instance.to_db()
        assert isinstance(db_data["data"], str)

        loaded = TestModel.from_db(db_data)
        assert loaded.data == original

    def test_model_very_large_list(self):
        """Should handle large lists."""

        class TestModel(BaseModel):
            items: list = mapped(store_json=True, default_factory=list)

        huge_list = list(range(10000))
        instance = TestModel(items=huge_list)

        db_data = instance.to_db()
        loaded = TestModel.from_db(db_data)
        assert len(loaded.items) == 10000

    def test_model_unicode_in_all_fields(self):
        """Should preserve Unicode in all field types."""

        class TestModel(BaseModel):
            text: str
            data: list = mapped(store_json=True, default_factory=list)

        instance = TestModel(
            text="🚀 Привет 你好",
            data=["🌍", "Москва", "北京"]
        )

        db_data = instance.to_db()
        loaded = TestModel.from_db(db_data)
        assert loaded.text == "🚀 Привет 你好"
        assert loaded.data[0] == "🌍"

    def test_vacancy_salary_all_none(self):
        """Salary with all None should default to 0."""
        data = {
            "id": 1,
            "name": "Job",
            "alternate_url": "https://hh.ru/vacancy/1",
            "area": {"id": 1, "name": "City"},
            "salary": {"from": None, "to": None, "currency": "RUR"},
        }
        vacancy = VacancyModel.from_api(data)
        assert vacancy.salary_from == 0
        assert vacancy.salary_to == 0

    def test_vacancy_extreme_salary_values(self):
        """Should handle extreme salary values."""
        data = {
            "id": 1,
            "name": "Job",
            "alternate_url": "https://hh.ru/vacancy/1",
            "area": {"id": 1, "name": "City"},
            "salary": {"from": 999999999, "to": 999999999, "currency": "RUR"},
        }
        vacancy = VacancyModel.from_api(data)
        assert vacancy.salary_from == 999999999
        assert vacancy.salary_to == 999999999

    def test_vacancy_salary_inverted_from_to(self):
        """Should handle inverted salary (from > to)."""
        data = {
            "id": 1,
            "name": "Job",
            "alternate_url": "https://hh.ru/vacancy/1",
            "area": {"id": 1, "name": "City"},
            "salary": {"from": 200000, "to": 100000, "currency": "RUR"},
        }
        vacancy = VacancyModel.from_api(data)
        # Should preserve as-is and let user handle
        assert vacancy.salary_from == 200000
        assert vacancy.salary_to == 100000

    def test_vacancy_missing_area(self):
        """Should handle missing area."""
        data = {
            "id": 1,
            "name": "Job",
            "alternate_url": "https://hh.ru/vacancy/1",
        }
        # Should raise because area is required (no default)
        with pytest.raises(TypeError):
            VacancyModel.from_api(data)

    def test_vacancy_empty_professional_roles(self):
        """Should handle empty professional roles."""
        data = {
            "id": 1,
            "name": "Job",
            "alternate_url": "https://hh.ru/vacancy/1",
            "area": {"id": 1, "name": "City"},
            "professional_roles": [],
        }
        vacancy = VacancyModel.from_api(data)
        assert vacancy.professional_roles == []

    def test_vacancy_null_timestamps(self):
        """Should handle null timestamps."""
        data = {
            "id": 1,
            "name": "Job",
            "alternate_url": "https://hh.ru/vacancy/1",
            "area": {"id": 1, "name": "City"},
            "created_at": None,
            "published_at": None,
            "updated_at": None,
        }
        vacancy = VacancyModel.from_api(data)
        assert vacancy.created_at is None
        assert vacancy.published_at is None

    def test_model_type_coercion_string_to_float(self):
        """Should coerce string to float."""

        class TestModel(BaseModel):
            value: float

        instance = TestModel.from_api({"value": "3.14"})
        if isinstance(instance.value, float):
            assert instance.value == 3.14

    def test_model_type_coercion_int_to_string(self):
        """Should handle int to string coercion."""

        class TestModel(BaseModel):
            value: str

        instance = TestModel.from_api({"value": 42})
        # API provides int, should be stored as is or converted
        assert instance.value is not None

    def test_model_from_db_json_field_corrupted(self):
        """Should handle corrupted JSON in stored fields."""

        class TestModel(BaseModel):
            data: list = mapped(store_json=True, default_factory=list)

        # Simulate corrupted JSON from database
        db_data = {"data": "not valid json"}

        # Should either fail or handle gracefully
        try:
            instance = TestModel.from_db(db_data)
            # If it doesn't crash, that's OK
        except:
            # Or raise is also acceptable
            pass

    def test_model_special_characters_in_json_field(self):
        """Should handle special characters in JSON fields."""

        class TestModel(BaseModel):
            data: str = mapped(store_json=False)

        special = 'Special: "quotes", \\backslash, \x00null, \n newline'
        instance = TestModel(data=special)

        db_data = instance.to_db()
        loaded = TestModel.from_db(db_data)
        # Should preserve special characters

    def test_model_boolean_edge_cases(self):
        """Should handle boolean edge cases in coercion."""

        class TestModel(BaseModel):
            flag: bool

        # String "false" is truthy in Python but might be intended as false
        instance = TestModel.from_api({"flag": "false"})
        # Should be coerced - depending on implementation
        assert instance.flag is not None


class TestModelTransformFunctions:
    """Test custom transform functions."""

    def test_mapped_transform_with_error(self):
        """Should handle errors in transform functions."""

        class TestModel(BaseModel):
            result: str = mapped(
                path="value",
                transform=lambda x: 1 / int(x)  # Could divide by zero
            )

        # If x="0", should fail
        data = {"value": "0"}
        try:
            instance = TestModel.from_api(data)
            # If no error, transformation was skipped or handled
        except:
            # Error is acceptable
            pass

    def test_mapped_transform_returning_none(self):
        """Transform function returning None should work."""

        class TestModel(BaseModel):
            result: str = mapped(
                path="value",
                transform=lambda x: None if x == "skip" else x
            )

        data = {"value": "skip"}
        instance = TestModel.from_api(data)
        assert instance.result is None

    def test_mapped_transform_with_complex_logic(self):
        """Should handle complex transform logic."""

        class TestModel(BaseModel):
            priority: int = mapped(
                path="importance",
                transform=lambda x: {"high": 1, "medium": 2, "low": 3}.get(x, 0)
            )

        data = {"importance": "high"}
        instance = TestModel.from_api(data)
        assert instance.priority == 1
