import pytest

from app.domain.commerce.value_objects.address import Address


class TestAddress:

    def test_valid_address(self):
        addr = Address(
            first_name="John",
            last_name="Doe",
            line1="123 Main St",
            city="New York",
            state="NY",
            zip="10001",
            country="US",
        )
        assert addr.first_name == "John"
        assert addr.last_name == "Doe"
        assert addr.country == "US"

    def test_empty_first_name_raises(self):
        with pytest.raises(ValueError):
            Address(
                first_name="",
                last_name="Doe",
                line1="123 Main St",
                city="New York",
                state="NY",
                zip="10001",
                country="US",
            )

    def test_empty_last_name_raises(self):
        with pytest.raises(ValueError):
            Address(
                first_name="John",
                last_name="",
                line1="123 Main St",
                city="New York",
                state="NY",
                zip="10001",
                country="US",
            )

    def test_optional_fields(self):
        addr = Address(
            first_name="John",
            last_name="Doe",
            line1="123 Main St",
            line2="Apt 4B",
            city="New York",
            state="NY",
            zip="10001",
            country="US",
            phone="+1234567890",
        )
        assert addr.line2 == "Apt 4B"
        assert addr.phone == "+1234567890"

    def test_missing_optional_fields(self):
        addr = Address(
            first_name="John",
            last_name="Doe",
            line1="123 Main St",
            city="New York",
            state="NY",
            zip="10001",
            country="US",
        )
        assert addr.line2 is None
        assert addr.phone is None
