from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models import SubscriptionProvider, User
from app.db.session import get_session
from app.payments import paypal as paypal_payments
from app.payments import stripe as stripe_payments
from app.schemas import CheckoutSessionResponse, CustomerPortalResponse, PayPalSubscriptionResponse, SubscriptionRead
from app.services.subscriptions import latest_subscription


router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/subscription", response_model=SubscriptionRead | None)
async def subscription(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SubscriptionRead | None:
    return await latest_subscription(session, user.id)


@router.post("/stripe/checkout", response_model=CheckoutSessionResponse)
async def stripe_checkout(user: User = Depends(get_current_user)) -> CheckoutSessionResponse:
    checkout_url = await stripe_payments.create_checkout_session(user.id, user.email)
    return CheckoutSessionResponse(checkout_url=checkout_url)


@router.post("/stripe/portal", response_model=CustomerPortalResponse)
async def stripe_portal(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CustomerPortalResponse:
    subscription_row = await latest_subscription(session, user.id)
    if (
        subscription_row is None
        or subscription_row.provider != SubscriptionProvider.stripe
        or not subscription_row.provider_customer_id
    ):
        raise HTTPException(status_code=404, detail="Stripe customer not found")
    portal_url = await stripe_payments.create_customer_portal(subscription_row.provider_customer_id)
    return CustomerPortalResponse(portal_url=portal_url)


@router.post("/paypal/subscription", response_model=PayPalSubscriptionResponse)
async def paypal_subscription(user: User = Depends(get_current_user)) -> PayPalSubscriptionResponse:
    approval_url, provider_subscription_id = await paypal_payments.create_subscription(user.id)
    return PayPalSubscriptionResponse(
        approval_url=approval_url,
        provider_subscription_id=provider_subscription_id,
    )


@router.post("/webhooks/stripe", include_in_schema=False)
async def stripe_webhook(request: Request, session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    return await stripe_payments.handle_webhook(request, session)


@router.post("/webhooks/paypal", include_in_schema=False)
async def paypal_webhook(request: Request, session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    return await paypal_payments.handle_webhook(request, session)
