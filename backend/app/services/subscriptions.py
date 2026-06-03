from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import Subscription, SubscriptionProvider, SubscriptionStatus


async def upsert_subscription(
    session: AsyncSession,
    *,
    user_id: UUID,
    provider: SubscriptionProvider,
    provider_customer_id: str | None,
    provider_subscription_id: str | None,
    status: SubscriptionStatus,
    current_period_end: datetime | None = None,
) -> Subscription:
    statement = (
        select(Subscription)
        .where(Subscription.user_id == user_id)
        .where(Subscription.provider == provider)
    )
    subscription = (await session.execute(statement)).scalar_one_or_none()
    if subscription is None:
        subscription = Subscription(
            user_id=user_id,
            provider=provider,
            price_usd=get_settings().subscription_price_usd,
        )
        session.add(subscription)

    subscription.provider_customer_id = provider_customer_id
    subscription.provider_subscription_id = provider_subscription_id
    subscription.status = status
    subscription.current_period_end = current_period_end
    subscription.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(subscription)
    return subscription


async def latest_subscription(session: AsyncSession, user_id: UUID) -> Subscription | None:
    statement = (
        select(Subscription)
        .where(Subscription.user_id == user_id)
        .order_by(Subscription.updated_at.desc())
        .limit(1)
    )
    return (await session.execute(statement)).scalar_one_or_none()


def normalize_stripe_status(status: str | None) -> SubscriptionStatus:
    mapping = {
        "active": SubscriptionStatus.active,
        "trialing": SubscriptionStatus.trialing,
        "past_due": SubscriptionStatus.past_due,
        "canceled": SubscriptionStatus.canceled,
        "unpaid": SubscriptionStatus.unpaid,
        "incomplete": SubscriptionStatus.incomplete,
        "incomplete_expired": SubscriptionStatus.canceled,
    }
    return mapping.get(status or "", SubscriptionStatus.incomplete)


def normalize_paypal_status(status: str | None) -> SubscriptionStatus:
    mapping = {
        "APPROVAL_PENDING": SubscriptionStatus.incomplete,
        "APPROVED": SubscriptionStatus.incomplete,
        "ACTIVE": SubscriptionStatus.active,
        "SUSPENDED": SubscriptionStatus.past_due,
        "CANCELLED": SubscriptionStatus.canceled,
        "EXPIRED": SubscriptionStatus.canceled,
    }
    return mapping.get((status or "").upper(), SubscriptionStatus.incomplete)
