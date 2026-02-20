from __future__ import annotations

from datetime import datetime, timezone

from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError

from panager.google.auth import refresh_access_token
from panager.google.repository import get_tokens, update_access_token


class GoogleAuthRequired(Exception):
    """Google 계정 미연동 또는 scope 부족 시 발생하는 예외."""


async def _get_valid_credentials(user_id: int) -> Credentials:
    tokens = await get_tokens(user_id)
    if not tokens:
        raise GoogleAuthRequired("Google 계정이 연동되지 않았습니다.")

    if tokens.expires_at <= datetime.now(timezone.utc):
        new_token, new_expires = await refresh_access_token(tokens.refresh_token)
        await update_access_token(user_id, new_token, new_expires)
        tokens.access_token = new_token

    return Credentials(token=tokens.access_token)


def _execute(request):
    """googleapiclient 요청을 실행하고 401/403은 GoogleAuthRequired로 변환합니다."""
    try:
        return request.execute()
    except HttpError as exc:
        if exc.status_code in (401, 403):
            raise GoogleAuthRequired("Google 권한이 부족합니다. 재연동이 필요합니다.")
        raise
