from decimal import Decimal

import pytest

from app.domain.commerce.value_objects.money import Money


class TestMoneyCreation:

    def test_valid_money(self):
        m = Money(amount=Decimal("10.50"), currency="USD")
        assert m.amount == Decimal("10.50")
        assert m.currency == "USD"

    def test_zero_amount(self):
        m = Money(amount=Decimal("0"), currency="USD")
        assert m.amount == Decimal("0")

    def test_invalid_negative_amount(self):
        with pytest.raises(ValueError):
            Money(amount=Decimal("-1"), currency="USD")

    def test_invalid_currency_lowercase(self):
        with pytest.raises(ValueError):
            Money(amount=Decimal("10"), currency="usd")

    def test_invalid_currency_numbers(self):
        with pytest.raises(ValueError):
            Money(amount=Decimal("10"), currency="US1")

    def test_invalid_currency_too_short(self):
        with pytest.raises(ValueError):
            Money(amount=Decimal("10"), currency="U")

    def test_invalid_currency_too_long(self):
        with pytest.raises(ValueError):
            Money(amount=Decimal("10"), currency="USDD")

    def test_invalid_currency_empty(self):
        with pytest.raises(ValueError):
            Money(amount=Decimal("10"), currency="")


class TestMoneyArithmetic:

    def test_addition_same_currency(self):
        a = Money(amount=Decimal("10"), currency="USD")
        b = Money(amount=Decimal("20"), currency="USD")
        result = a + b
        assert result.amount == Decimal("30")
        assert result.currency == "USD"

    def test_addition_different_currency(self):
        a = Money(amount=Decimal("10"), currency="USD")
        b = Money(amount=Decimal("20"), currency="EUR")
        with pytest.raises(ValueError, match="Cannot add USD to EUR"):
            a + b

    def test_subtraction_same_currency(self):
        a = Money(amount=Decimal("30"), currency="USD")
        b = Money(amount=Decimal("10"), currency="USD")
        result = a - b
        assert result.amount == Decimal("20")

    def test_subtraction_negative_result(self):
        a = Money(amount=Decimal("10"), currency="USD")
        b = Money(amount=Decimal("20"), currency="USD")
        with pytest.raises(ValueError, match="Resulting amount cannot be negative"):
            a - b

    def test_subtraction_different_currency(self):
        a = Money(amount=Decimal("10"), currency="USD")
        b = Money(amount=Decimal("5"), currency="EUR")
        with pytest.raises(ValueError):
            a - b

    def test_multiplication(self):
        m = Money(amount=Decimal("10"), currency="USD")
        result = m * 3
        assert result.amount == Decimal("30")
        assert result.currency == "USD"

    def test_multiplication_float(self):
        m = Money(amount=Decimal("10"), currency="USD")
        result = m * 1.5
        assert result.amount == Decimal("15.0")

    def test_multiplication_decimal(self):
        m = Money(amount=Decimal("10"), currency="USD")
        result = m * Decimal("2.5")
        assert result.amount == Decimal("25.0")


class TestMoneyEquality:

    def test_equal(self):
        a = Money(amount=Decimal("10"), currency="USD")
        b = Money(amount=Decimal("10"), currency="USD")
        assert a == b

    def test_not_equal_amount(self):
        a = Money(amount=Decimal("10"), currency="USD")
        b = Money(amount=Decimal("20"), currency="USD")
        assert a != b

    def test_not_equal_currency(self):
        a = Money(amount=Decimal("10"), currency="USD")
        b = Money(amount=Decimal("10"), currency="EUR")
        assert a != b

    def test_compare_with_non_money(self):
        m = Money(amount=Decimal("10"), currency="USD")
        assert (m == "not money") is False


class TestMoneyRepresentation:

    def test_repr(self):
        m = Money(amount=Decimal("10.50"), currency="USD")
        assert repr(m) == "10.50 USD"
