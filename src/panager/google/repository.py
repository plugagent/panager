from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from panager.db.connection import get_pool


@dataclass
class GoogleTokens:
    user_id: int
    access_token: str
    refresh_token: str
    expires_at: datetime


async def save_tokens(user_id: int, tokens: dict) -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO google_tokens (user_id, access_token, refresh_token, expires_at)
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


async def get_tokens(user_id: int) -> GoogleTokens | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM google_tokens WHERE user_id = $1", user_id
        )
    if not row:
        return None
    return GoogleTokens(
        user_id=row["user_id"],
        access_token=row["access_token"],
        refresh_token=row["refresh_token"],
        expires_at=row["expires_at"],
    )


async def update_access_token(
    user_id: int, access_token: str, expires_at: datetime
) -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE google_tokens
            SET access_token = $2, expires_at = $3, updated_at = NOW()
            WHERE user_id = $1
            """,
            user_id,
            access_token,
            expires_at,
        )
