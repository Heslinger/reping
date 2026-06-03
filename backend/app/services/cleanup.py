import asyncio
from contextlib import suppress
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete

from app.core.config import get_settings
from app.db.models import Pingback
from app.db.session import AsyncSessionLocal


async def purge_expired_pingbacks() -> int:
    cutoff = datetime.now(UTC) - timedelta(days=get_settings().retention_days)
    async with AsyncSessionLocal() as session:
        result = await session.execute(delete(Pingback).where(Pingback.created_at < cutoff))
        await session.commit()
        return result.rowcount or 0


async def cleanup_loop(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        with suppress(Exception):
            await purge_expired_pingbacks()
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=60 * 60)
        except TimeoutError:
            continue
