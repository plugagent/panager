from __future__ import annotations

import asyncio
import logging
from typing import Any

from googleapiclient.errors import HttpError

from panager.core.exceptions import GoogleAuthRequired

log = logging.getLogger(__name__)


class GoogleClient:
    """Google API 호출을 위한 클라이언트."""

    async def execute(self, request: Any) -> Any:
        """API 요청을 비동기로 실행하고 공통 에러 처리를 수행합니다."""
        try:
            return await asyncio.to_thread(request.execute)
        except HttpError as exc:
            if exc.status_code in (401, 403):
                log.warning("Google API 인증 오류 발생: %s", exc)
                raise GoogleAuthRequired(
                    "Google 권한이 부족합니다. 재연동이 필요합니다."
                ) from exc
            log.error("Google API 호출 오류: %s", exc)
            raise

    async def execute_list(
        self, collection: Any, request: Any, list_key: str
    ) -> list[dict[str, Any]]:
        """페이지네이션을 처리하여 모든 항목을 가져옵니다."""
        items = []
        while request is not None:
            result = await self.execute(request)
            items.extend(result.get(list_key, []))
            request = collection.list_next(request, result)
        return items
