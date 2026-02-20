from __future__ import annotations

from datetime import datetime, timezone, timedelta
from functools import lru_cache

from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

from panager.config import Settings

SCOPES = [
    "https://www.googleapis.com/auth/tasks",
    "https://www.googleapis.com/auth/calendar",
]


@lru_cache
def get_settings() -> Settings:
    return Settings()


def _make_flow(settings: Settings) -> Flow:
    return Flow.from_client_config(
        {
            "web": {
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [settings.google_redirect_uri],
            }
        },
        scopes=SCOPES,
        redirect_uri=settings.google_redirect_uri,
    )


def get_auth_url(user_id: int) -> str:
    settings = get_settings()
    flow = _make_flow(settings)
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        state=str(user_id),
        prompt="consent",
    )
    return auth_url


async def exchange_code(code: str, user_id: int) -> dict:
    settings = get_settings()
    flow = _make_flow(settings)
    flow.fetch_token(code=code)
    creds = flow.credentials
    return {
        "access_token": creds.token,
        "refresh_token": creds.refresh_token,
        "expires_at": datetime.now(timezone.utc) + timedelta(seconds=3600),
    }


async def refresh_access_token(refresh_token: str) -> tuple[str, datetime]:
    settings = get_settings()
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
    )
    creds.refresh(Request())
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=3600)
    return creds.token, expires_at
