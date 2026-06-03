import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class SubscriptionProvider(str, enum.Enum):
    stripe = "stripe"
    paypal = "paypal"


class SubscriptionStatus(str, enum.Enum):
    none = "none"
    incomplete = "incomplete"
    trialing = "trialing"
    active = "active"
    past_due = "past_due"
    canceled = "canceled"
    unpaid = "unpaid"


class PingbackProtocol(str, enum.Enum):
    http = "http"
    dns = "dns"


def utc_now() -> datetime:
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    payloads: Mapped[list["Payload"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    pingbacks: Mapped[list["Pingback"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        UniqueConstraint("provider", "provider_subscription_id", name="uq_subscription_provider_subscription"),
        Index("ix_subscriptions_user_status", "user_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[SubscriptionProvider] = mapped_column(Enum(SubscriptionProvider, name="subscription_provider"), nullable=False)
    provider_customer_id: Mapped[str | None] = mapped_column(Text)
    provider_subscription_id: Mapped[str | None] = mapped_column(Text)
    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus, name="subscription_status"),
        default=SubscriptionStatus.incomplete,
        nullable=False,
    )
    price_usd: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    user: Mapped[User] = relationship(back_populates="subscriptions")


class Payload(Base):
    __tablename__ = "payloads"
    __table_args__ = (
        UniqueConstraint("token", name="uq_payloads_token"),
        Index("ix_payloads_user_created", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token: Mapped[str] = mapped_column(String(64), nullable=False)
    subdomain: Mapped[str] = mapped_column(String(255), nullable=False)
    http_url: Mapped[str] = mapped_column(Text, nullable=False)
    dns_name: Mapped[str] = mapped_column(String(255), nullable=False)
    label: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="payloads")
    pingbacks: Mapped[list["Pingback"]] = relationship(back_populates="payload", cascade="all, delete-orphan")


class Pingback(Base):
    __tablename__ = "pingbacks"
    __table_args__ = (
        Index("ix_pingbacks_user_created", "user_id", "created_at"),
        Index("ix_pingbacks_payload_created", "payload_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payload_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("payloads.id", ondelete="SET NULL"))
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    protocol: Mapped[PingbackProtocol] = mapped_column(Enum(PingbackProtocol, name="pingback_protocol"), nullable=False)
    source_ip: Mapped[str | None] = mapped_column(INET)
    method: Mapped[str | None] = mapped_column(String(16))
    host: Mapped[str | None] = mapped_column(String(255))
    path: Mapped[str | None] = mapped_column(Text)
    query_params: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    headers: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    dns_record_type: Mapped[str | None] = mapped_column(String(16))
    dns_query_name: Mapped[str | None] = mapped_column(String(255))
    raw_event: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    user: Mapped[User | None] = relationship(back_populates="pingbacks")
    payload: Mapped[Payload | None] = relationship(back_populates="pingbacks")
