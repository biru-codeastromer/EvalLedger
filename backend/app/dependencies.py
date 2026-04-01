from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, cast

from fastapi import Depends, Header, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.errors import AppError
from app.models.api_key import APIKey
from app.models.user import User
from app.security import decode_access_token, hash_api_key

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def _authenticate_api_key(api_key: str, session: AsyncSession) -> User:
    statement = (
        select(APIKey, User)
        .join(User, User.id == APIKey.user_id)
        .where(APIKey.key_hash == hash_api_key(api_key), APIKey.is_active.is_(True))
    )
    result = await session.execute(statement)
    record = result.first()
    if record is None:
        raise AppError(
            "invalid_api_key",
            "API key is invalid",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    key, user = cast(tuple[APIKey, User], record)
    key.last_used_at = datetime.now(UTC)
    await session.commit()
    return user


async def get_current_user(
    session: SessionDep,
    authorization: Annotated[str | None, Header()] = None,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> User:
    if x_api_key:
        return await _authenticate_api_key(x_api_key, session)

    if not authorization:
        raise AppError("not_authenticated", "Authentication is required", status_code=401)

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise AppError("invalid_auth_header", "Bearer token is required", status_code=401)

    payload = decode_access_token(token)
    statement = select(User).where(User.id == payload["sub"])
    user = cast(User | None, await session.scalar(statement))
    if user is None:
        raise AppError("user_not_found", "Authenticated user does not exist", status_code=401)
    return user


async def get_optional_user(
    session: SessionDep,
    authorization: Annotated[str | None, Header()] = None,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> User | None:
    try:
        return await get_current_user(session, authorization, x_api_key)
    except AppError:
        return None


async def get_admin_user(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    if not current_user.is_admin:
        raise AppError("forbidden", "Administrator access is required", status_code=403)
    return current_user


CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_optional_user)]
AdminUser = Annotated[User, Depends(get_admin_user)]
