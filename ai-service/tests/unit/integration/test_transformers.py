from decimal import Decimal
from datetime import datetime

import pytest

from app.application.integration.mapping.transformers import TransformerRegistry


@pytest.fixture
def registry() -> TransformerRegistry:
    return TransformerRegistry()


class TestStringToDecimal:
    def test_string(self, registry: TransformerRegistry) -> None:
        assert registry.apply("string_to_decimal", "29.99") == Decimal("29.99")

    def test_with_dollar(self, registry: TransformerRegistry) -> None:
        assert registry.apply("string_to_decimal", "$1,234.56") == Decimal("1234.56")

    def test_int(self, registry: TransformerRegistry) -> None:
        assert registry.apply("string_to_decimal", 100) == Decimal("100")

    def test_float(self, registry: TransformerRegistry) -> None:
        assert registry.apply("string_to_decimal", 100.5) == Decimal("100.5")

    def test_invalid_string(self, registry: TransformerRegistry) -> None:
        result = registry.apply("string_to_decimal", "not_a_number")
        assert result == "not_a_number"


class TestStringToInt:
    def test_string(self, registry: TransformerRegistry) -> None:
        assert registry.apply("string_to_int", "100") == 100

    def test_float(self, registry: TransformerRegistry) -> None:
        assert registry.apply("string_to_int", 100.7) == 100

    def test_invalid(self, registry: TransformerRegistry) -> None:
        result = registry.apply("string_to_int", "abc")
        assert result == "abc"


class TestIsoDate:
    def test_valid(self, registry: TransformerRegistry) -> None:
        result = registry.apply("iso_date", "2024-01-15T10:30:00Z")
        assert isinstance(result, datetime)

    def test_invalid(self, registry: TransformerRegistry) -> None:
        result = registry.apply("iso_date", "not_a_date")
        assert result == "not_a_date"


class TestSplitByComma:
    def test_split(self, registry: TransformerRegistry) -> None:
        assert registry.apply("split_by_comma", "a,b,c") == ["a", "b", "c"]

    def test_empty(self, registry: TransformerRegistry) -> None:
        assert registry.apply("split_by_comma", "") == []

    def test_list_input(self, registry: TransformerRegistry) -> None:
        assert registry.apply("split_by_comma", ["a", "b"]) == ["a", "b"]


class TestLowercase:
    def test(self, registry: TransformerRegistry) -> None:
        assert registry.apply("lowercase", "HELLO") == "hello"

    def test_non_string(self, registry: TransformerRegistry) -> None:
        assert registry.apply("lowercase", 123) == 123


class TestUppercase:
    def test(self, registry: TransformerRegistry) -> None:
        assert registry.apply("uppercase", "hello") == "HELLO"


class TestTrim:
    def test(self, registry: TransformerRegistry) -> None:
        assert registry.apply("trim", "  hello  ") == "hello"


class TestFirstImageUrl:
    def test_from_list_of_dicts(self, registry: TransformerRegistry) -> None:
        images = [{"src": "https://example.com/img1.jpg"}, {"src": "https://example.com/img2.jpg"}]
        assert registry.apply("first_image_url", images) == "https://example.com/img1.jpg"

    def test_empty_list(self, registry: TransformerRegistry) -> None:
        assert registry.apply("first_image_url", []) == ""

    def test_inline_string(self, registry: TransformerRegistry) -> None:
        assert registry.apply("first_image_url", "https://example.com/img.jpg") == "https://example.com/img.jpg"


class TestRegister:
    def test_custom_transformer(self, registry: TransformerRegistry) -> None:
        registry.register("double", lambda x: x * 2)
        assert registry.apply("double", 5) == 10

    def test_unknown_transformer(self, registry: TransformerRegistry) -> None:
        with pytest.raises(ValueError):
            registry.apply("unknown", "test")


class TestConcatFields:
    def test_list_of_strings(self, registry: TransformerRegistry) -> None:
        assert registry.apply("concat_fields", ["hello", "world"]) == "hello world"

    def test_none_values(self, registry: TransformerRegistry) -> None:
        assert registry.apply("concat_fields", []) == ""

    def test_string_value(self, registry: TransformerRegistry) -> None:
        assert registry.apply("concat_fields", "hello") == "hello"