"""Schemas for the gas-price-change email subscription."""

from pydantic import BaseModel, EmailStr, Field, field_validator


class PriceSubscriptionCreate(BaseModel):
    """Public subscribe request (double opt-in; consent is mandatory)."""

    email: EmailStr
    consent: bool = Field(description="Must be true; the user agrees to receive emails.")

    @field_validator("consent")
    @classmethod
    def consent_must_be_true(cls, value: bool) -> bool:
        if not value:
            raise ValueError("consent is required to subscribe")
        return value


class PriceSubscriptionToken(BaseModel):
    """Token payload for confirm / unsubscribe actions."""

    token: str = Field(min_length=1, max_length=64)


class PriceSubscriptionAck(BaseModel):
    """Generic acknowledgement (never reveals whether an email already exists)."""

    message: str


class PriceAlertNotifyResult(BaseModel):
    """Result of an admin-triggered price-change notification run."""

    sent_count: int
    recipient_count: int
