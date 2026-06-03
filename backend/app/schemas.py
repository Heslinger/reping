from datetime import datetime
from uuid import UUID

from ipaddress import IPv4Address, IPv6Address

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.db.models import PingbackProtocol, SubscriptionProvider, SubscriptionStatus


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=256)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserRead(BaseModel):
    id: UUID
    email: EmailStr
    created_at: datetime
    subscription_status: SubscriptionStatus = SubscriptionStatus.none


class PayloadCreate(BaseModel):
    label: str | None = Field(default=None, max_length=120)


class PayloadRead(BaseModel):
    id: UUID
    token: str
    subdomain: str
    http_url: str
    dns_name: str
    label: str | None
    created_at: datetime
    revoked_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class PingbackRead(BaseModel):
    id: UUID
    payload_id: UUID | None
    protocol: PingbackProtocol
    source_ip: str | None
    method: str | None
    host: str | None
    path: str | None
    query_params: dict
    headers: dict
    body: str | None
    dns_record_type: str | None
    dns_query_name: str | None
    raw_event: dict
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_validator("source_ip", mode="before")
    @classmethod
    def normalize_source_ip(cls, value: object | None) -> str | None:
        if value is None or isinstance(value, str):
            return value
        if isinstance(value, (IPv4Address, IPv6Address)):
            return str(value)
        return str(value)


class CheckoutSessionResponse(BaseModel):
    checkout_url: str


class CustomerPortalResponse(BaseModel):
    portal_url: str


class PayPalSubscriptionResponse(BaseModel):
    approval_url: str
    provider_subscription_id: str


class SubscriptionRead(BaseModel):
    provider: SubscriptionProvider
    status: SubscriptionStatus
    current_period_end: datetime | None

    model_config = ConfigDict(from_attributes=True)
