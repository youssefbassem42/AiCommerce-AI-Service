from datetime import datetime
from decimal import Decimal

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


class TestStrip:
    def test_strip_whitespace(self, registry: TransformerRegistry) -> None:
        assert registry.apply("strip", "  hello  ") == "hello"

    def test_strip_non_string(self, registry: TransformerRegistry) -> None:
        assert registry.apply("strip", 123) == 123


class TestMoneyToCurrency:
    def test_numeric_value(self, registry: TransformerRegistry) -> None:
        assert registry.apply("money_to_currency", 55.0) == {"amount": 55.0, "currency": "USD"}

    def test_numeric_string(self, registry: TransformerRegistry) -> None:
        assert registry.apply("money_to_currency", "29.99") == {"amount": 29.99, "currency": "USD"}

    def test_money_dict(self, registry: TransformerRegistry) -> None:
        assert registry.apply("money_to_currency", {"amount": 12.5, "currency": "EUR"}) == {
            "amount": 12.5,
            "currency": "EUR",
        }

    def test_negative_clamped(self, registry: TransformerRegistry) -> None:
        assert registry.apply("money_to_currency", -5) == {"amount": 0.0, "currency": "USD"}

    def test_non_money_passthrough(self, registry: TransformerRegistry) -> None:
        value = registry.apply("money_to_currency", "n/a")
        assert value == "n/a"


class TestMoneyToAmount:
    def test_numeric(self, registry: TransformerRegistry) -> None:
        assert registry.apply("money_to_amount", 55.0) == 55.0

    def test_numeric_string(self, registry: TransformerRegistry) -> None:
        assert registry.apply("money_to_amount", "29.99") == 29.99

    def test_money_dict(self, registry: TransformerRegistry) -> None:
        assert registry.apply("money_to_amount", {"amount": 8.25, "currency": "USD"}) == 8.25

    def test_non_money_passthrough(self, registry: TransformerRegistry) -> None:
        assert registry.apply("money_to_amount", None) is None


class TestUrlJoin:
    def test_absolute_url_unchanged(self, registry: TransformerRegistry) -> None:
        assert registry.apply("url_join", "https://example.com/img.png") == "https://example.com/img.png"

    def test_relative_path_passthrough(self, registry: TransformerRegistry) -> None:
        assert registry.apply("url_join", "/images/1.png") == "/images/1.png"

    def test_non_string(self, registry: TransformerRegistry) -> None:
        assert registry.apply("url_join", 123) == 123
