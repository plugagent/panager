from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError

from panager.google.auth import (
    get_settings as _get_google_settings,
    refresh_access_token,
)
from panager.google.repository import get_tokens, update_access_token


class GoogleAuthRequired(Exception):
    """Google 계정 미연동 또는 scope 부족 시 발생하는 예외."""


async def _get_valid_credentials(user_id: int) -> Credentials:
    tokens = await get_tokens(user_id)
    if not tokens:
        raise GoogleAuthRequired("Google 계정이 연동되지 않았습니다.")

    expires_at = tokens.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= datetime.now(timezone.utc):
        new_token, new_expires = await refresh_access_token(tokens.refresh_token)
        await update_access_token(user_id, new_token, new_expires)
        tokens.access_token = new_token

    settings = _get_google_settings()
    return Credentials(
        token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
    )


async def _execute(request) -> dict | None:
    """googleapiclient 요청을 비동기로 실행하고 401/403은 GoogleAuthRequired로 변환합니다."""
    try:
        return await asyncio.to_thread(request.execute)
    except HttpError as exc:
        if exc.status_code in (401, 403):
            raise GoogleAuthRequired("Google 권한이 부족합니다. 재연동이 필요합니다.")
        raise
