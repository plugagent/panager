from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any

import asyncpg
from langchain_core.tools import BaseTool
from sentence_transformers import SentenceTransformer

if TYPE_CHECKING:
    from panager.core.config import Settings

log = logging.getLogger(__name__)


class ToolRegistry:
    """도구 등록 및 시멘틱 검색을 담당하는 레지스트리."""

    def __init__(self, pool: asyncpg.Pool, settings: Settings) -> None:
        self._pool = pool
        self._settings = settings
        self._tools: dict[str, BaseTool] = {}
        self._tool_factories: dict[str, Any] = {}
        self._model: SentenceTransformer | None = None
        self._lock = asyncio.Lock()

    async def _get_model(self) -> SentenceTransformer:
        if self._model is None:
            async with self._lock:
                if self._model is None:
                    log.info("ToolRegistry: SentenceTransformer 모델 로딩 시작...")
                    self._model = await asyncio.to_thread(
                        SentenceTransformer, "paraphrase-multilingual-mpnet-base-v2"
                    )
                    log.info("ToolRegistry: SentenceTransformer 모델 로딩 완료.")
        return self._model

    async def _get_embedding(self, text: str) -> list[float]:
        model = await self._get_model()
        embedding = await asyncio.to_thread(model.encode, text)
        if hasattr(embedding, "tolist"):
            return embedding.tolist()
        return list(embedding)

    def register_tools(self, tools: list[BaseTool]) -> None:
        """도구를 메모리 레지스트리에 등록합니다."""
        for tool in tools:
            self._tools[tool.name] = tool
            log.debug("Tool registered: %s", tool.name)

    async def sync_to_db(self) -> None:
        """메모리에 등록된 도구들을 데이터베이스와 동기화(인덱싱)합니다."""
        await self.sync_tools_by_prototypes(list(self._tools.values()))

    async def sync_tools_by_prototypes(self, prototypes: list[BaseTool]) -> None:
        """도구 프로토타입(설명용)을 기반으로 DB와 동기화합니다."""
        log.info("ToolRegistry: 도구 프로토타입 동기화 시작 (총 %d개)", len(prototypes))
        async with self._pool.acquire() as conn:
            for tool in prototypes:
                name = tool.name
                description = tool.description
                domain = tool.metadata.get("domain") if tool.metadata else "unknown"

                tool_schema = {}
                if (
                    hasattr(tool, "args_schema")
                    and tool.args_schema
                    and hasattr(tool.args_schema, "schema")
                ):
                    tool_schema = tool.args_schema.schema()

                embedding = await self._get_embedding(f"{name}: {description}")

                await conn.execute(
                    """
                    INSERT INTO tool_registry (name, domain, description, schema, embedding)
                    VALUES ($1, $2, $3, $4, $5::vector)
                    ON CONFLICT (name) DO UPDATE SET
                        description = EXCLUDED.description,
                        schema = EXCLUDED.schema,
                        embedding = EXCLUDED.embedding,
                        domain = EXCLUDED.domain
                    """,
                    name,
                    domain,
                    description,
                    json.dumps(tool_schema),
                    str(embedding),
                )
        log.info("ToolRegistry: 도구 동기화 완료.")

    async def get_tools_for_user(self, user_id: int, **services: Any) -> list[BaseTool]:
        """특정 사용자에 대해 모든 등록된 도구 인스턴스를 생성하여 반환합니다."""
        all_tools = []

        # 1. Google Tools
        if "google_service" in services:
            from panager.tools.google import (
                make_manage_google_calendar,
                make_manage_google_tasks,
            )

            all_tools.append(
                make_manage_google_calendar(user_id, services["google_service"])
            )
            all_tools.append(
                make_manage_google_tasks(user_id, services["google_service"])
            )

        # 2. GitHub Tools
        if "github_service" in services:
            from panager.tools.github import make_github_tools

            all_tools.extend(make_github_tools(user_id, services["github_service"]))

        # 3. Notion Tools
        if "notion_service" in services:
            from panager.tools.notion import make_notion_tools

            all_tools.extend(make_notion_tools(user_id, services["notion_service"]))

        # 4. Memory Tools
        from panager.tools.memory import make_memory_tools

        all_tools.extend(make_memory_tools())

        # 5. Scheduler Tools
        from panager.tools.scheduler import make_scheduler_tools

        all_tools.extend(make_scheduler_tools())

        return all_tools

    async def search_tools(self, query: str, limit: int = 10) -> list[BaseTool]:
        """쿼리와 유사한 도구를 검색하여 반환합니다."""
        embedding = await self._get_embedding(query)

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT name
                FROM tool_registry
                ORDER BY embedding <=> $1::vector
                LIMIT $2
                """,
                str(embedding),
                limit,
            )

            results = []
            for row in rows:
                name = row["name"]
                if name in self._tools:
                    results.append(self._tools[name])
                else:
                    log.warning("Tool found in DB but not in memory registry: %s", name)

            return results

    def get_tool(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def get_all_tools(self) -> list[BaseTool]:
        return list(self._tools.values())
