from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from langchain_core.tools import tool
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool
    from panager.services.notion import NotionService

log = logging.getLogger(__name__)


class CreateNotionPageInput(BaseModel):
    database_id: str = Field(
        ..., description="The ID of the database to create the page in"
    )
    properties: dict[str, Any] = Field(
        ..., description="The properties of the new page (Notion API format)"
    )
    children: list[dict[str, Any]] | None = Field(
        None, description="The content of the new page (Notion API format)"
    )


class SearchNotionInput(BaseModel):
    query: str | None = Field(None, description="The text to search for")
    filter_type: str | None = Field(
        None, description="The type of objects to search for (e.g., 'database', 'page')"
    )


def make_notion_tools(user_id: int, notion_service: NotionService) -> list[BaseTool]:
    @tool(args_schema=SearchNotionInput)
    async def search_notion(
        query: str | None = None, filter_type: str | None = None
    ) -> str:
        """Notion에서 데이터베이스나 페이지를 검색합니다. database_id를 찾을 때 유용합니다."""
        client = await notion_service.get_client(user_id)
        params: dict[str, Any] = {}
        if query:
            params["query"] = query
        if filter_type:
            params["filter"] = {"value": filter_type, "property": "object"}

        response = await client.search(**params)
        results = []
        for res in response.get("results", []):
            item = {"id": res["id"], "object": res["object"], "title": ""}
            if res["object"] == "database":
                item["title"] = res.get("title", [{}])[0].get("plain_text", "Untitled")
            elif res["object"] == "page":
                # 페이지 제목 추출은 속성에 따라 다를 수 있음 (보통 'title' 또는 'Name')
                props = res.get("properties", {})
                for p in props.values():
                    if p.get("type") == "title":
                        item["title"] = p.get("title", [{}])[0].get(
                            "plain_text", "Untitled"
                        )
                        break
            results.append(item)

        return json.dumps({"status": "success", "results": results}, ensure_ascii=False)

    @tool(args_schema=CreateNotionPageInput)
    async def create_notion_page(
        database_id: str,
        properties: dict[str, Any],
        children: list[dict[str, Any]] | None = None,
    ) -> str:
        """Notion 데이터베이스에 새로운 페이지를 생성합니다."""
        client = await notion_service.get_client(user_id)
        params: dict[str, Any] = {
            "parent": {"database_id": database_id},
            "properties": properties,
        }
        if children:
            params["children"] = children

        response = await client.pages.create(**params)
        return json.dumps(
            {
                "status": "success",
                "page_id": response["id"],
                "url": response.get("url"),
            },
            ensure_ascii=False,
        )

    return [search_notion, create_notion_page]
