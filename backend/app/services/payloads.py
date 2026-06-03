import secrets
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import Payload


TOKEN_BYTES = 16


async def generate_payload(session: AsyncSession, user_id: UUID, label: str | None = None) -> Payload:
    settings = get_settings()

    while True:
        token = secrets.token_urlsafe(TOKEN_BYTES).replace("_", "-").lower()
        existing = await session.execute(select(Payload.id).where(Payload.token == token))
        if existing.scalar_one_or_none() is None:
            break

    subdomain = f"{token}.{settings.root_domain}"
    payload = Payload(
        user_id=user_id,
        token=token,
        subdomain=subdomain,
        http_url=f"{str(settings.public_base_url).rstrip('/')}/p/{token}",
        dns_name=subdomain,
        label=label,
    )
    session.add(payload)
    await session.commit()
    await session.refresh(payload)
    return payload


def token_from_host_or_path(host: str | None, path: str | None = None) -> str | None:
    settings = get_settings()
    if host:
        host_without_port = host.split(":", 1)[0].strip(".").lower()
        suffix = f".{settings.root_domain}"
        if host_without_port.endswith(suffix):
            return host_without_port.removesuffix(suffix).split(".")[-1]

    if path:
        parts = [part for part in path.split("/") if part]
        if len(parts) >= 2 and parts[0] == "p":
            return parts[1].lower()
    return None
