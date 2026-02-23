from __future__ import annotations

from typing import Dict, Protocol


class UserSessionProvider(Protocol):
    @property
    def pending_messages(self) -> Dict[int, str]: ...

    async def get_user_timezone(self, user_id: int) -> str: ...
