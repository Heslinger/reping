from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_active_subscription
from app.db.models import Payload, User, utc_now
from app.db.session import get_session
from app.schemas import PayloadCreate, PayloadRead
from app.services.payloads import generate_payload


router = APIRouter(prefix="/payloads", tags=["payloads"])


@router.post("", response_model=PayloadRead, status_code=status.HTTP_201_CREATED)
async def create_payload(
    payload: PayloadCreate,
    user: User = Depends(require_active_subscription),
    session: AsyncSession = Depends(get_session),
) -> Payload:
    return await generate_payload(session, user.id, label=payload.label)


@router.get("", response_model=list[PayloadRead])
async def list_payloads(
    user: User = Depends(require_active_subscription),
    session: AsyncSession = Depends(get_session),
) -> list[Payload]:
    result = await session.execute(
        select(Payload).where(Payload.user_id == user.id).order_by(Payload.created_at.desc())
    )
    return list(result.scalars().all())


@router.delete("/{payload_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_payload(
    payload_id: UUID,
    user: User = Depends(require_active_subscription),
    session: AsyncSession = Depends(get_session),
) -> None:
    payload = await session.get(Payload, payload_id)
    if payload is None or payload.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payload not found")
    payload.revoked_at = utc_now()
    await session.commit()
