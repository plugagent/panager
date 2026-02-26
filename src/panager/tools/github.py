from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from langchain_core.tools import tool
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool
    from panager.services.github import GithubService

log = logging.getLogger(__name__)


class ListReposInput(BaseModel):
    pass


class SetupWebhookInput(BaseModel):
    repo_full_name: str = Field(
        ..., description="Repository full name (e.g., 'owner/repo')"
    )
    webhook_url: str = Field(
        ..., description="The URL to which the payloads will be delivered"
    )


def make_github_tools(user_id: int, github_service: GithubService) -> list[BaseTool]:
    @tool(args_schema=ListReposInput, metadata={"domain": "github"})
    async def list_github_repositories() -> str:
        """GitHub 사용자의 저장소 목록을 조회합니다."""
        # ...
        async with await github_service.get_client(user_id) as client:
            # ... (rest of implementation)
            response = await client.get(
                "/user/repos", params={"sort": "updated", "per_page": 20}
            )
            response.raise_for_status()
            repos = response.json()

            result = [
                {
                    "full_name": r["full_name"],
                    "description": r["description"],
                    "html_url": r["html_url"],
                    "updated_at": r["updated_at"],
                }
                for r in repos
            ]
            return json.dumps(
                {"status": "success", "repositories": result}, ensure_ascii=False
            )

    @tool(args_schema=SetupWebhookInput, metadata={"domain": "github"})
    async def setup_github_webhook(repo_full_name: str, webhook_url: str) -> str:
        """GitHub 저장소에 Push 이벤트용 Webhook을 설정합니다.

        repo_full_name: 'owner/repo' 형식
        webhook_url: 이벤트를 수신할 서버의 URL
        """
        async with await github_service.get_client(user_id) as client:
            payload = {
                "name": "web",
                "active": True,
                "events": ["push"],
                "config": {
                    "url": webhook_url,
                    "content_type": "json",
                    "secret": github_service.settings.github_webhook_secret,
                },
            }
            response = await client.post(f"/repos/{repo_full_name}/hooks", json=payload)
            if response.status_code == 201:
                return json.dumps(
                    {"status": "success", "message": "Webhook created successfully"},
                    ensure_ascii=False,
                )
            else:
                return json.dumps(
                    {"status": "error", "message": response.text}, ensure_ascii=False
                )

    return [list_github_repositories, setup_github_webhook]
