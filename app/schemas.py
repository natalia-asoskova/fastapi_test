from datetime import UTC, datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator, model_validator

from app.pricing import INSTALLMENT_TERMS
from app.statuses import Method, Status


class TariffOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    price: int


class PaymentCreate(BaseModel):
    tariff_id: str
    email: EmailStr
    method: Method
    installment_months: int | None = None
    promo_code: str | None = None

    @model_validator(mode="after")
    def check_installment(self) -> Self:
        if self.method is Method.installment:
            if self.installment_months not in INSTALLMENT_TERMS:
                raise ValueError(f"installment_months must be one of {INSTALLMENT_TERMS}")
        elif self.installment_months is not None:
            raise ValueError("installment_months is allowed only for method=installment")
        return self


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: Status
    tariff_id: str
    amount: int
    discount: int
    method: Method
    installment_months: int | None
    schedule: list[int] | None
    email: str
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def _as_utc(cls, value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value


class WebhookIn(BaseModel):
    payment_id: str
    status: Status
