from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from panager.core.config import Settings
from panager.google.repository import get_tokens, update_access_token
from panager.integrations.google_client import GoogleAuthRequired

if TYPE_CHECKING:
    from googleapiclient.discovery import Resource

log = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/tasks",
    "https://www.googleapis.com/auth/calendar",
]


class GoogleService:
    """Google 서비스 관리를 위한 중앙 서비스."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _make_flow(self) -> Flow:
        """OAuth Flow 객체를 생성합니다."""
        return Flow.from_client_config(
            {
                "web": {
                    "client_id": self.settings.google_client_id,
                    "client_secret": self.settings.google_client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [self.settings.google_redirect_uri],
                }
            },
            scopes=SCOPES,
            redirect_uri=self.settings.google_redirect_uri,
        )

    def get_auth_url(self, user_id: int) -> str:
        """사용자 인증을 위한 URL을 생성합니다."""
        flow = self._make_flow()
        auth_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            state=str(user_id),
            prompt="consent",
        )
        return auth_url

    async def exchange_code(self, code: str, user_id: int) -> dict:
        """OAuth 인증 코드를 토큰으로 교환합니다."""
        flow = self._make_flow()
        await asyncio.to_thread(flow.fetch_token, code=code)
        creds = flow.credentials
        if creds.refresh_token is None:
            raise ValueError(
                "Google OAuth가 refresh_token을 반환하지 않았습니다. "
                "prompt=consent로 재시도하세요."
            )
        return {
            "access_token": creds.token,
            "refresh_token": creds.refresh_token,
            "expires_at": datetime.now(timezone.utc) + timedelta(seconds=3600),
        }

    async def _get_valid_credentials(self, user_id: int) -> Credentials:
        """DB에서 토큰을 가져오고 필요시 갱신하여 유효한 Credentials를 반환합니다."""
        tokens = await get_tokens(user_id)
        if not tokens:
            raise GoogleAuthRequired("Google 계정이 연동되지 않았습니다.")

        expires_at = tokens.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if expires_at <= datetime.now(timezone.utc):
            log.info("Google access token 만료됨. 갱신 시도 (user_id=%d)", user_id)
            creds = Credentials(
                token=None,
                refresh_token=tokens.refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=self.settings.google_client_id,
                client_secret=self.settings.google_client_secret,
            )
            await asyncio.to_thread(creds.refresh, Request())
            if creds.token is None:
                raise RuntimeError("토큰 갱신 실패: 새 access token을 받지 못했습니다.")

            new_expires = datetime.now(timezone.utc) + timedelta(seconds=3600)
            await update_access_token(user_id, creds.token, new_expires)
            tokens.access_token = creds.token

        return Credentials(
            token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self.settings.google_client_id,
            client_secret=self.settings.google_client_secret,
        )

    async def get_calendar_service(self, user_id: int) -> Resource:
        """Google Calendar API 서비스 객체를 생성합니다."""
        creds = await self._get_valid_credentials(user_id)
        return build("calendar", "v3", credentials=creds)

    async def get_tasks_service(self, user_id: int) -> Resource:
        """Google Tasks API 서비스 객체를 생성합니다."""
        creds = await self._get_valid_credentials(user_id)
        return build("tasks", "v1", credentials=creds)
