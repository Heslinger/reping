from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import parse_access_token
from app.db.models import Subscription, SubscriptionStatus, User
from app.db.session import get_session


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    try:
        user_id: UUID = parse_access_token(token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


async def require_active_subscription(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> User:
    statement: Select[tuple[Subscription]] = (
        select(Subscription)
        .where(Subscription.user_id == user.id)
        .where(Subscription.status.in_([SubscriptionStatus.active, SubscriptionStatus.trialing]))
    )
    subscription = (await session.execute(statement)).scalar_one_or_none()
    if subscription is None:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="Active subscription required")
    return user
