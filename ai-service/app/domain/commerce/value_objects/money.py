from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, model_validator


class Money(BaseModel):
    amount: Decimal = Field(..., ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)

    @model_validator(mode="after")
    def validate_currency(self) -> "Money":
        if not self.currency.isalpha() or not self.currency.isupper():
            raise ValueError(f"Currency must be a 3-letter uppercase code, got '{self.currency}'")
        return self

    def __add__(self, other: Any) -> "Money":
        if not isinstance(other, Money):
            return NotImplemented
        if self.currency != other.currency:
            raise ValueError(f"Cannot add {self.currency} to {other.currency}")
        return Money(amount=self.amount + other.amount, currency=self.currency)

    def __sub__(self, other: Any) -> "Money":
        if not isinstance(other, Money):
            return NotImplemented
        if self.currency != other.currency:
            raise ValueError(f"Cannot subtract {self.currency} from {other.currency}")
        result = self.amount - other.amount
        if result < 0:
            raise ValueError("Resulting amount cannot be negative")
        return Money(amount=result, currency=self.currency)

    def __mul__(self, multiplier: int | float | Decimal) -> "Money":
        if not isinstance(multiplier, (int, float, Decimal)):
            return NotImplemented
        return Money(amount=self.amount * Decimal(str(multiplier)), currency=self.currency)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        return self.currency == other.currency and self.amount == other.amount

    def __repr__(self) -> str:
        return f"{self.amount:.2f} {self.currency}"
