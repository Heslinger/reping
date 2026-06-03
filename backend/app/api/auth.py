from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.db.models import SubscriptionStatus, User
from app.db.session import get_session
from app.schemas import TokenResponse, UserCreate, UserLogin, UserRead
from app.services.subscriptions import latest_subscription


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate, session: AsyncSession = Depends(get_session)) -> TokenResponse:
    existing = await session.execute(select(User.id).where(User.email == payload.email.lower()))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(email=payload.email.lower(), password_hash=hash_password(payload.password))
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return TokenResponse(access_token=create_access_token(user.id))


@router.post("/login", response_model=TokenResponse)
async def login(payload: UserLogin, session: AsyncSession = Depends(get_session)) -> TokenResponse:
    user = (await session.execute(select(User).where(User.email == payload.email.lower()))).scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    return TokenResponse(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserRead)
async def me(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)) -> UserRead:
    subscription = await latest_subscription(session, user.id)
    return UserRead(
        id=user.id,
        email=user.email,
        created_at=user.created_at,
        subscription_status=subscription.status if subscription else SubscriptionStatus.none,
    )
