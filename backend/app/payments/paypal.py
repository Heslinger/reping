from datetime import UTC, datetime
from uuid import UUID

import httpx
from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import SubscriptionProvider
from app.services.subscriptions import normalize_paypal_status, upsert_subscription


async def _paypal_token() -> str:
    settings = get_settings()
    if not settings.paypal_client_id or not settings.paypal_client_secret:
        raise HTTPException(status_code=503, detail="PayPal is not configured")

    async with httpx.AsyncClient(base_url=settings.paypal_base_url, timeout=15) as client:
        response = await client.post(
            "/v1/oauth2/token",
            data={"grant_type": "client_credentials"},
            auth=(settings.paypal_client_id, settings.paypal_client_secret),
        )
        response.raise_for_status()
        return response.json()["access_token"]


async def create_subscription(user_id: UUID) -> tuple[str, str]:
    settings = get_settings()
    if not settings.paypal_plan_id:
        raise HTTPException(status_code=503, detail="PayPal plan is not configured")

    token = await _paypal_token()
    async with httpx.AsyncClient(base_url=settings.paypal_base_url, timeout=15) as client:
        response = await client.post(
            "/v1/billing/subscriptions",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={
                "plan_id": settings.paypal_plan_id,
                "custom_id": str(user_id),
                "application_context": {
                    "brand_name": settings.app_name,
                    "user_action": "SUBSCRIBE_NOW",
                    "return_url": f"{settings.frontend_url}/billing/success?provider=paypal",
                    "cancel_url": f"{settings.frontend_url}/billing/cancelled?provider=paypal",
                },
            },
        )
        response.raise_for_status()
        data = response.json()
        approval_url = next(link["href"] for link in data["links"] if link["rel"] == "approve")
        return approval_url, data["id"]


async def handle_webhook(request: Request, session: AsyncSession) -> dict[str, str]:
    settings = get_settings()
    payload = await request.json()
    if settings.paypal_webhook_id:
        await _verify_webhook(request, payload)

    event_type = payload.get("event_type", "")
    resource = payload.get("resource", {})
    if event_type.startswith("BILLING.SUBSCRIPTION."):
        user_id = UUID(resource["custom_id"])
        status_value = resource.get("status")
        period_end = _parse_paypal_datetime(resource.get("billing_info", {}).get("next_billing_time"))
        await upsert_subscription(
            session,
            user_id=user_id,
            provider=SubscriptionProvider.paypal,
            provider_customer_id=resource.get("subscriber", {}).get("payer_id"),
            provider_subscription_id=resource.get("id"),
            status=normalize_paypal_status(status_value),
            current_period_end=period_end,
        )
    return {"status": "ok"}


async def _verify_webhook(request: Request, payload: dict) -> None:
    settings = get_settings()
    token = await _paypal_token()
    async with httpx.AsyncClient(base_url=settings.paypal_base_url, timeout=15) as client:
        response = await client.post(
            "/v1/notifications/verify-webhook-signature",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={
                "auth_algo": request.headers.get("paypal-auth-algo"),
                "cert_url": request.headers.get("paypal-cert-url"),
                "transmission_id": request.headers.get("paypal-transmission-id"),
                "transmission_sig": request.headers.get("paypal-transmission-sig"),
                "transmission_time": request.headers.get("paypal-transmission-time"),
                "webhook_id": settings.paypal_webhook_id,
                "webhook_event": payload,
            },
        )
        response.raise_for_status()
        if response.json().get("verification_status") != "SUCCESS":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid PayPal webhook")


def _parse_paypal_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
