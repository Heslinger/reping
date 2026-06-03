from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings


password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return password_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_context.verify(password, password_hash)


def create_access_token(user_id: UUID) -> str:
    settings = get_settings()
    expires = datetime.now(UTC) + timedelta(minutes=settings.access_token_minutes)
    payload: dict[str, Any] = {"sub": str(user_id), "exp": expires}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def parse_access_token(token: str) -> UUID:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        subject = payload.get("sub")
        if not subject:
            raise ValueError("Token subject is missing")
        return UUID(subject)
    except (JWTError, ValueError) as exc:
        raise ValueError("Invalid access token") from exc
