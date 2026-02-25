from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import asyncpg
import httpx

from panager.core.config import Settings
from panager.core.exceptions import GithubAuthRequired

log = logging.getLogger(__name__)

SCOPES = ["repo", "admin:repo_hook"]


@dataclass
class GithubTokens:
    """사용자의 GitHub OAuth 토큰 정보."""

    user_id: int
    access_token: str
    refresh_token: str | None
    expires_at: datetime | None


class GithubService:
    """GitHub 서비스 관리를 위한 중앙 서비스."""

    def __init__(self, settings: Settings, pool: asyncpg.Pool) -> None:
        self.settings = settings
        self.pool = pool

    def get_auth_url(self, user_id: int) -> str:
        """사용자 인증을 위한 URL을 생성합니다."""
        params = {
            "client_id": self.settings.github_client_id,
            "redirect_uri": self.settings.github_redirect_uri,
            "scope": " ".join(SCOPES),
            "state": str(user_id),
        }
        query_string = "&".join(f"{k}={v}" for k, v in params.items())
        return f"https://github.com/login/oauth/authorize?{query_string}"

    async def exchange_code(self, code: str, user_id: int) -> dict:
        """OAuth 인증 코드를 토큰으로 교환합니다."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://github.com/login/oauth/access_token",
                data={
                    "client_id": self.settings.github_client_id,
                    "client_secret": self.settings.github_client_secret,
                    "code": code,
                    "redirect_uri": self.settings.github_redirect_uri,
                },
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            data = response.json()

        if "error" in data:
            raise ValueError(
                f"GitHub OAuth error: {data.get('error_description', data['error'])}"
            )

        tokens = {
            "access_token": data["access_token"],
            "refresh_token": data.get("refresh_token"),
            "expires_at": None,  # GitHub personal OAuth tokens don't always expire unless configured
        }
        # If expires_in is present, calculate expires_at
        if "expires_in" in data:
            from datetime import timedelta

            tokens["expires_at"] = datetime.now(timezone.utc) + timedelta(
                seconds=data["expires_in"]
            )

        await self.save_tokens(user_id, tokens)
        return tokens

    async def save_tokens(self, user_id: int, tokens: dict) -> None:
        """토큰을 데이터베이스에 저장합니다."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO github_tokens (user_id, access_token, refresh_token, expires_at)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (user_id) DO UPDATE
                SET access_token = $2, refresh_token = $3,
                    expires_at = $4, updated_at = NOW()
                """,
                user_id,
                tokens["access_token"],
                tokens["refresh_token"],
                tokens["expires_at"],
            )

    async def get_tokens(self, user_id: int) -> GithubTokens | None:
        """사용자의 토큰을 조회합니다."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM github_tokens WHERE user_id = $1", user_id
            )
        if not row:
            return None
        return GithubTokens(
            user_id=row["user_id"],
            access_token=row["access_token"],
            refresh_token=row["refresh_token"],
            expires_at=row["expires_at"],
        )

    async def get_client(self, user_id: int) -> httpx.AsyncClient:
        """GitHub API 호출을 위한 인증된 클라이언트를 반환합니다."""
        tokens = await self.get_tokens(user_id)
        if not tokens:
            raise GithubAuthRequired("GitHub 계정이 연동되지 않았습니다.")

        # GitHub 토큰 갱신 로직은 필요한 경우 추가 (현재는 생략)
        return httpx.AsyncClient(
            base_url="https://api.github.com",
            headers={
                "Authorization": f"Bearer {tokens.access_token}",
                "Accept": "application/vnd.github.v3+json",
            },
        )
