from __future__ import annotations

from fastapi import APIRouter, status
from sqlalchemy import or_, select

from app.dependencies import CurrentUser, SessionDep
from app.errors import AppError
from app.models.api_key import APIKey
from app.models.user import User
from app.schemas.auth import (
    APIKeyCreateRequest,
    APIKeyCreateResponse,
    APIKeyResponse,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
)
from app.schemas.common import UserSummary
from app.security import (
    create_access_token,
    generate_api_key,
    hash_api_key,
    hash_password,
    verify_password,
)

router = APIRouter()


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, session: SessionDep) -> TokenResponse:
    existing = await session.scalar(
        select(User).where(or_(User.email == payload.email, User.username == payload.username))
    )
    if existing is not None:
        raise AppError("user_exists", "A user with that email or username already exists", status_code=409)

    user = User(
        email=payload.email,
        username=payload.username,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        bio=payload.bio,
        website=payload.website,
        affiliation=payload.affiliation,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token, user=UserSummary.model_validate(user))


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, session: SessionDep) -> TokenResponse:
    user = await session.scalar(select(User).where(User.email == payload.email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise AppError("invalid_credentials", "Email or password is incorrect", status_code=401)
    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token, user=UserSummary.model_validate(user))


@router.post("/api-keys", response_model=APIKeyCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    payload: APIKeyCreateRequest,
    session: SessionDep,
    current_user: CurrentUser,
) -> APIKeyCreateResponse:
    plain_key = generate_api_key()
    api_key = APIKey(user_id=current_user.id, name=payload.name, key_hash=hash_api_key(plain_key))
    session.add(api_key)
    await session.commit()
    await session.refresh(api_key)
    return APIKeyCreateResponse(api_key=plain_key, metadata=APIKeyResponse.model_validate(api_key))


@router.delete("/api-keys/{api_key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_api_key(api_key_id: str, session: SessionDep, current_user: CurrentUser) -> None:
    api_key = await session.scalar(
        select(APIKey).where(APIKey.id == api_key_id, APIKey.user_id == current_user.id)
    )
    if api_key is None:
        raise AppError("api_key_not_found", "API key does not exist", status_code=404)
    api_key.is_active = False
    await session.commit()


@router.get("/me")
async def me(session: SessionDep, current_user: CurrentUser) -> dict[str, object]:
    api_keys = list(
        (
            await session.scalars(
                select(APIKey).where(APIKey.user_id == current_user.id).order_by(APIKey.created_at.desc())
            )
        ).all()
    )
    return {
        "user": UserSummary.model_validate(current_user),
        "api_keys": [APIKeyResponse.model_validate(item) for item in api_keys],
    }

