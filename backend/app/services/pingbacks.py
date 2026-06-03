import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis
from app.db.models import Payload, Pingback, PingbackProtocol
from app.services.payloads import token_from_host_or_path


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def serialize_pingback(pingback: Pingback) -> dict[str, Any]:
    return {
        "id": str(pingback.id),
        "payload_id": str(pingback.payload_id) if pingback.payload_id else None,
        "protocol": pingback.protocol.value,
        "source_ip": pingback.source_ip,
        "method": pingback.method,
        "host": pingback.host,
        "path": pingback.path,
        "query_params": pingback.query_params,
        "headers": pingback.headers,
        "body": pingback.body,
        "dns_record_type": pingback.dns_record_type,
        "dns_query_name": pingback.dns_query_name,
        "raw_event": pingback.raw_event,
        "created_at": pingback.created_at.isoformat(),
    }


async def ingest_http_pingback(
    session: AsyncSession,
    *,
    host: str | None,
    path: str,
    method: str,
    source_ip: str | None,
    headers: dict[str, str],
    query_params: dict[str, list[str] | str],
    body: str | None,
) -> Pingback:
    token = token_from_host_or_path(host, path)
    payload = await _payload_from_token(session, token)
    pingback = Pingback(
        payload_id=payload.id if payload else None,
        user_id=payload.user_id if payload else None,
        protocol=PingbackProtocol.http,
        source_ip=source_ip,
        method=method,
        host=host,
        path=path,
        query_params=query_params,
        headers=headers,
        body=body,
        raw_event={"captured_at": datetime.now(UTC).isoformat()},
    )
    session.add(pingback)
    await session.commit()
    await session.refresh(pingback)
    await publish_pingback(pingback)
    return pingback


async def ingest_dns_pingback(
    session: AsyncSession,
    *,
    query_name: str,
    record_type: str,
    source_ip: str | None,
    raw_event: dict[str, Any],
) -> Pingback:
    token = token_from_host_or_path(query_name)
    payload = await _payload_from_token(session, token)
    pingback = Pingback(
        payload_id=payload.id if payload else None,
        user_id=payload.user_id if payload else None,
        protocol=PingbackProtocol.dns,
        source_ip=source_ip,
        dns_record_type=record_type,
        dns_query_name=query_name,
        raw_event=raw_event,
    )
    session.add(pingback)
    await session.commit()
    await session.refresh(pingback)
    await publish_pingback(pingback)
    return pingback


async def publish_pingback(pingback: Pingback) -> None:
    if pingback.user_id is None:
        return
    redis = await get_redis()
    channel = f"pingbacks:{pingback.user_id}"
    await redis.publish(channel, json.dumps(serialize_pingback(pingback), default=_json_default))


async def _payload_from_token(session: AsyncSession, token: str | None) -> Payload | None:
    if token is None:
        return None
    result = await session.execute(select(Payload).where(Payload.token == token).where(Payload.revoked_at.is_(None)))
    return result.scalar_one_or_none()
