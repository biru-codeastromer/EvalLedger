"""OAuth 2.0 login endpoints — GitHub and Google.

Flow:
  GET /auth/oauth/{provider}           → redirect user to provider consent screen
  GET /auth/oauth/{provider}/callback  → exchange code, find/create user, redirect
                                         to frontend with a short-lived JWT

The state parameter is a signed JWT (5 min TTL) used as a CSRF nonce.
No external session store is required.
"""

from __future__ import annotations

from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from app.config import get_settings
from app.dependencies import SessionDep
from app.errors import AppError
from app.ratelimit import RateLimiter, RateLimitError, get_client_id, get_limiter
from app.security import create_access_token, decode_access_token
from app.services.oauth import find_or_create_oauth_user

router = APIRouter()
settings = get_settings()

# --------------------------------------------------------------------------- #
# State-token helpers                                                          #
# --------------------------------------------------------------------------- #

_STATE_PURPOSE = "oauth_state"
_STATE_TTL_MINUTES = 5


def _make_state_token() -> str:
    """Return a short-lived, signed JWT used as the OAuth CSRF state nonce."""
    return create_access_token(
        subject=_STATE_PURPOSE,
        extra_claims={"purpose": _STATE_PURPOSE},
        expiry_minutes=_STATE_TTL_MINUTES,
    )


def _verify_state_token(state: str) -> None:
    """Raise AppError if *state* is invalid, expired, or not an OAuth state token."""
    try:
        payload = decode_access_token(state)
    except AppError as exc:
        raise AppError("invalid_oauth_state", "OAuth state token is invalid or expired", status_code=400) from exc
    if payload.get("purpose") != _STATE_PURPOSE:
        raise AppError("invalid_oauth_state", "OAuth state token has wrong purpose", status_code=400)


def _frontend_error_redirect(message: str) -> RedirectResponse:
    """Redirect the browser to the frontend login page with an error message."""
    params = urlencode({"error": message})
    return RedirectResponse(f"{settings.frontend_url}/login?{params}", status_code=302)


async def _oauth_rate_limit(request: Request, bucket: str) -> RedirectResponse | None:
    """Return a redirect response if the OAuth start endpoint is over limit.

    OAuth start routes return ``RedirectResponse``, so they cannot raise a
    standard JSON ``AppError``.  Instead, over-limit requests are bounced back
    to the login page with an error query parameter.

    Returns ``None`` if the request is within the allowed rate.
    """
    limiter = RateLimiter(get_limiter(), enabled=settings.rate_limit_enabled)
    client_id = get_client_id(request)
    try:
        await limiter.check(bucket, client_id, limit=20, window_seconds=60)
    except RateLimitError:
        return _frontend_error_redirect("Too many sign-in attempts — please wait a moment and try again.")
    return None


# --------------------------------------------------------------------------- #
# GitHub                                                                       #
# --------------------------------------------------------------------------- #

_GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
_GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
_GITHUB_USER_URL = "https://api.github.com/user"
_GITHUB_EMAILS_URL = "https://api.github.com/user/emails"


@router.get("/github")
async def github_oauth_start(request: Request) -> RedirectResponse:
    """Redirect the user to the GitHub OAuth consent screen."""
    if (rate_limit_response := await _oauth_rate_limit(request, "oauth_start_github")) is not None:
        return rate_limit_response
    if not settings.github_client_id:
        raise AppError("oauth_not_configured", "GitHub OAuth is not configured on this server", status_code=503)
    state = _make_state_token()
    params = urlencode(
        {
            "client_id": settings.github_client_id,
            "redirect_uri": f"{settings.app_url}/auth/oauth/github/callback",
            "scope": "user:email",
            "state": state,
        }
    )
    return RedirectResponse(f"{_GITHUB_AUTHORIZE_URL}?{params}", status_code=302)


@router.get("/github/callback")
async def github_oauth_callback(
    session: SessionDep,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    """Handle the GitHub OAuth callback, exchange the code, and issue a JWT."""
    if error:
        return _frontend_error_redirect(f"GitHub login was denied: {error}")

    if not code or not state:
        return _frontend_error_redirect("GitHub did not return the expected code or state.")

    try:
        _verify_state_token(state)
    except AppError:
        return _frontend_error_redirect("OAuth state mismatch — please try signing in again.")

    async with httpx.AsyncClient(timeout=10) as client:
        # Exchange authorisation code for access token.
        token_resp = await client.post(
            _GITHUB_TOKEN_URL,
            data={
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret,
                "code": code,
                "redirect_uri": f"{settings.app_url}/auth/oauth/github/callback",
            },
            headers={"Accept": "application/json"},
        )
        token_data = token_resp.json()
        github_token = token_data.get("access_token")
        if not github_token:
            return _frontend_error_redirect("GitHub did not return an access token. Please try again.")

        gh_headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github+json",
        }

        # Fetch the authenticated user's profile.
        user_resp = await client.get(_GITHUB_USER_URL, headers=gh_headers)
        if user_resp.status_code != 200:
            return _frontend_error_redirect("Could not retrieve your GitHub profile.")
        gh_user = user_resp.json()

        # GitHub hides emails when "Keep my email addresses private" is enabled.
        # Fall back to the verified primary email from the /user/emails API.
        email: str | None = gh_user.get("email")
        if not email:
            emails_resp = await client.get(_GITHUB_EMAILS_URL, headers=gh_headers)
            if emails_resp.status_code == 200:
                for entry in emails_resp.json():
                    if entry.get("primary") and entry.get("verified"):
                        email = entry["email"]
                        break

    try:
        user = await find_or_create_oauth_user(
            session,
            provider="github",
            provider_user_id=str(gh_user["id"]),
            email=email,
            display_name=gh_user.get("name") or gh_user.get("login"),
            username_hint=gh_user.get("login", "githubuser"),
        )
        await session.commit()
        await session.refresh(user)
    except Exception:
        return _frontend_error_redirect("Failed to create or retrieve your EvalLedger account.")

    token = create_access_token(str(user.id))
    return RedirectResponse(
        f"{settings.frontend_url}/auth/callback?token={token}",
        status_code=302,
    )


# --------------------------------------------------------------------------- #
# Google                                                                       #
# --------------------------------------------------------------------------- #

_GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


@router.get("/google")
async def google_oauth_start(request: Request) -> RedirectResponse:
    """Redirect the user to the Google OAuth consent screen."""
    if (rate_limit_response := await _oauth_rate_limit(request, "oauth_start_google")) is not None:
        return rate_limit_response
    if not settings.google_client_id:
        raise AppError("oauth_not_configured", "Google OAuth is not configured on this server", status_code=503)
    state = _make_state_token()
    params = urlencode(
        {
            "client_id": settings.google_client_id,
            "redirect_uri": f"{settings.app_url}/auth/oauth/google/callback",
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "online",
        }
    )
    return RedirectResponse(f"{_GOOGLE_AUTHORIZE_URL}?{params}", status_code=302)


@router.get("/google/callback")
async def google_oauth_callback(
    session: SessionDep,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    """Handle the Google OAuth callback, exchange the code, and issue a JWT."""
    if error:
        return _frontend_error_redirect(f"Google login was denied: {error}")

    if not code or not state:
        return _frontend_error_redirect("Google did not return the expected code or state.")

    try:
        _verify_state_token(state)
    except AppError:
        return _frontend_error_redirect("OAuth state mismatch — please try signing in again.")

    async with httpx.AsyncClient(timeout=10) as client:
        # Exchange authorisation code for tokens.
        token_resp = await client.post(
            _GOOGLE_TOKEN_URL,
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "code": code,
                "redirect_uri": f"{settings.app_url}/auth/oauth/google/callback",
                "grant_type": "authorization_code",
            },
        )
        if token_resp.status_code != 200:
            return _frontend_error_redirect("Google token exchange failed. Please try again.")
        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        if not access_token:
            return _frontend_error_redirect("Google did not return an access token.")

        # Fetch the user info with the access token.
        info_resp = await client.get(
            _GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if info_resp.status_code != 200:
            return _frontend_error_redirect("Could not retrieve your Google profile.")
        g_user = info_resp.json()

    email: str | None = g_user.get("email")
    # Only trust Google's verified emails.
    if not g_user.get("email_verified", False):
        email = None

    # Derive a username hint from name or email prefix.
    name: str = g_user.get("name") or ""
    username_hint = (email.split("@")[0] if email else name) or "googleuser"

    try:
        user = await find_or_create_oauth_user(
            session,
            provider="google",
            provider_user_id=str(g_user["sub"]),
            email=email,
            display_name=name or None,
            username_hint=username_hint,
        )
        await session.commit()
        await session.refresh(user)
    except Exception:
        return _frontend_error_redirect("Failed to create or retrieve your EvalLedger account.")

    token = create_access_token(str(user.id))
    return RedirectResponse(
        f"{settings.frontend_url}/auth/callback?token={token}",
        status_code=302,
    )
