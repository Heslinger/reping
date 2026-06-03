from datetime import UTC, datetime
from uuid import UUID

import stripe
from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import SubscriptionProvider
from app.services.subscriptions import normalize_stripe_status, upsert_subscription


def _configure_stripe() -> None:
    stripe.api_key = get_settings().stripe_secret_key


async def create_checkout_session(user_id: UUID, email: str) -> str:
    settings = get_settings()
    if not settings.stripe_secret_key or not settings.stripe_price_id:
        raise HTTPException(status_code=503, detail="Stripe is not configured")

    _configure_stripe()
    checkout_session = stripe.checkout.Session.create(
        mode="subscription",
        customer_email=email,
        client_reference_id=str(user_id),
        line_items=[{"price": settings.stripe_price_id, "quantity": 1}],
        success_url=f"{settings.frontend_url}/billing/success?provider=stripe",
        cancel_url=f"{settings.frontend_url}/billing/cancelled?provider=stripe",
        allow_promotion_codes=False,
        metadata={"user_id": str(user_id)},
    )
    return checkout_session.url


async def create_customer_portal(provider_customer_id: str) -> str:
    settings = get_settings()
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=503, detail="Stripe is not configured")

    _configure_stripe()
    portal_session = stripe.billing_portal.Session.create(
        customer=provider_customer_id,
        return_url=f"{settings.frontend_url}/settings/billing",
    )
    return portal_session.url


async def handle_webhook(request: Request, session: AsyncSession) -> dict[str, str]:
    settings = get_settings()
    if not settings.stripe_webhook_secret:
        raise HTTPException(status_code=503, detail="Stripe webhook secret is not configured")

    payload = await request.body()
    signature = request.headers.get("stripe-signature")
    try:
        event = stripe.Webhook.construct_event(payload, signature, settings.stripe_webhook_secret)
    except (ValueError, stripe.SignatureVerificationError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Stripe webhook") from exc

    event_type = event["type"]
    data = event["data"]["object"]
    if event_type == "checkout.session.completed":
        user_id = UUID(data["client_reference_id"])
        subscription = stripe.Subscription.retrieve(data["subscription"])
        await _persist_stripe_subscription(session, user_id, data["customer"], subscription)
    elif event_type in {"customer.subscription.created", "customer.subscription.updated", "customer.subscription.deleted"}:
        subscription = data
        user_id = UUID(subscription["metadata"].get("user_id") or subscription.get("client_reference_id"))
        await _persist_stripe_subscription(session, user_id, subscription.get("customer"), subscription)

    return {"status": "ok"}


async def _persist_stripe_subscription(
    session: AsyncSession,
    user_id: UUID,
    customer_id: str | None,
    subscription: dict,
) -> None:
    period_end = subscription.get("current_period_end")
    await upsert_subscription(
        session,
        user_id=user_id,
        provider=SubscriptionProvider.stripe,
        provider_customer_id=customer_id,
        provider_subscription_id=subscription.get("id"),
        status=normalize_stripe_status(subscription.get("status")),
        current_period_end=datetime.fromtimestamp(period_end, tz=UTC) if period_end else None,
    )
