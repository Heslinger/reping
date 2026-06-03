from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_active_subscription
from app.db.models import Pingback, User
from app.db.session import get_session
from app.schemas import PingbackRead
from app.services.pingbacks import ingest_http_pingback


router = APIRouter(prefix="/pingbacks", tags=["pingbacks"])
capture_router = APIRouter(tags=["capture"])


@router.get("", response_model=list[PingbackRead])
async def list_pingbacks(
    user: User = Depends(require_active_subscription),
    session: AsyncSession = Depends(get_session),
) -> list[Pingback]:
    result = await session.execute(
        select(Pingback)
        .where(Pingback.user_id == user.id)
        .order_by(Pingback.created_at.desc())
        .limit(250)
    )
    return list(result.scalars().all())


@capture_router.api_route("/p/{token:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
async def capture_path_pingback(token: str, request: Request, session: AsyncSession = Depends(get_session)) -> Response:
    await _capture_request(request, session)
    return Response(content="ok\n", media_type="text/plain", status_code=status.HTTP_202_ACCEPTED)


@capture_router.api_route("/", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
async def capture_host_pingback(request: Request, session: AsyncSession = Depends(get_session)) -> Response:
    await _capture_request(request, session)
    return Response(content="ok\n", media_type="text/plain", status_code=status.HTTP_202_ACCEPTED)


async def _capture_request(request: Request, session: AsyncSession) -> None:
    body_bytes = await request.body()
    query_params: dict[str, list[str] | str] = {}
    for key, value in request.query_params.multi_items():
        existing = query_params.get(key)
        if existing is None:
            query_params[key] = value
        elif isinstance(existing, list):
            existing.append(value)
        else:
            query_params[key] = [existing, value]

    await ingest_http_pingback(
        session,
        host=request.headers.get("host"),
        path=request.url.path,
        method=request.method,
        source_ip=request.client.host if request.client else None,
        headers=dict(request.headers),
        query_params=query_params,
        body=body_bytes.decode("utf-8", errors="replace") if body_bytes else None,
    )
