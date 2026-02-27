from __future__ import annotations

import logging
from dataclasses import dataclass

import asyncpg
import httpx
from notion_client import AsyncClient

from panager.core.config import Settings
from panager.core.exceptions import NotionAuthRequired

log = logging.getLogger(__name__)


@dataclass
class NotionTokens:
    """사용자의 Notion OAuth 토큰 정보."""

    user_id: int
    access_token: str
    workspace_id: str | None
    workspace_name: str | None
    bot_id: str | None


from urllib.parse import urlencode


class NotionService:
    """Notion 서비스 관리를 위한 중앙 서비스."""

    def __init__(self, settings: Settings, pool: asyncpg.Pool) -> None:
        self.settings = settings
        self.pool = pool

    def get_auth_url(self, user_id: int) -> str:
        """사용자 인증을 위한 URL을 생성합니다."""
        params = {
            "client_id": self.settings.notion_client_id,
            "redirect_uri": self.settings.notion_redirect_uri,
            "response_type": "code",
            "owner": "user",
            "state": str(user_id),
        }
        return f"https://api.notion.com/v1/oauth/authorize?{urlencode(params)}"

    async def exchange_code(self, code: str, user_id: int) -> dict:
        """OAuth 인증 코드를 토큰으로 교환합니다."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.notion.com/v1/oauth/token",
                json={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": self.settings.notion_redirect_uri,
                },
                auth=(
                    self.settings.notion_client_id,
                    self.settings.notion_client_secret,
                ),
            )
            response.raise_for_status()
            data = response.json()

        if "error" in data:
            raise ValueError(
                f"Notion OAuth error: {data.get('error_description', data['error'])}"
            )

        tokens = {
            "access_token": data["access_token"],
            "workspace_id": data.get("workspace_id"),
            "workspace_name": data.get("workspace_name"),
            "bot_id": data.get("bot_id"),
        }
        await self.save_tokens(user_id, tokens)
        return tokens

    async def save_tokens(self, user_id: int, tokens: dict) -> None:
        """토큰을 데이터베이스에 저장합니다."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO notion_tokens (user_id, access_token, workspace_id, updated_at)
                VALUES ($1, $2, $3, NOW())
                ON CONFLICT (user_id) DO UPDATE
                SET access_token = $2, workspace_id = $3, updated_at = NOW()
                """,
                user_id,
                tokens["access_token"],
                tokens["workspace_id"],
            )

    async def get_tokens(self, user_id: int) -> NotionTokens | None:
        """사용자의 토큰을 조회합니다."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM notion_tokens WHERE user_id = $1", user_id
            )
        if not row:
            return None
        return NotionTokens(
            user_id=row["user_id"],
            access_token=row["access_token"],
            workspace_id=row["workspace_id"],
            workspace_name=None,  # DB에 저장하지 않은 필드들
            bot_id=None,
        )

    async def get_client(self, user_id: int) -> AsyncClient:
        """Notion API 호출을 위한 인증된 클라이언트를 반환합니다."""
        tokens = await self.get_tokens(user_id)
        if not tokens:
            raise NotionAuthRequired("Notion 계정이 연동되지 않았습니다.")

        return AsyncClient(auth=tokens.access_token)
