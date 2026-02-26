from __future__ import annotations

import os
from unittest.mock import MagicMock, patch
from uuid import UUID

import numpy as np
import pytest

from panager.db.connection import init_pool, close_pool, get_pool
from panager.services.memory import MemoryService


@pytest.fixture(autouse=True)
async def setup_db():
    dsn = os.environ.get(
        "TEST_DATABASE_URL", "postgresql://panager:panager@localhost:5432/panager"
    )
    await init_pool(dsn)

    async with get_pool().acquire() as conn:
        # 테스트용 유저 생성
        await conn.execute(
            "INSERT INTO users (user_id, username) VALUES ($1, $2) ON CONFLICT DO NOTHING",
            999999,
            "test_user",
        )
    yield
    async with get_pool().acquire() as conn:
        await conn.execute("DELETE FROM memories WHERE user_id = $1", 999999)
        await conn.execute("DELETE FROM users WHERE user_id = $1", 999999)
    await close_pool()


@pytest.mark.asyncio
async def test_memory_service_save_and_search():
    # SentenceTransformer를 모킹하여 실제 모델 로딩 및 인코딩 방지
    with patch("panager.services.memory.SentenceTransformer") as mock_transformer_cls:
        mock_model = MagicMock()
        # 임베딩 결과 모킹 (768차원 리스트 반환하도록 설정)
        mock_model.encode.return_value = np.array([0.1] * 768)
        mock_transformer_cls.return_value = mock_model

        service = MemoryService(get_pool())

        # 1. 저장 테스트
        content = "인공지능 공부하기"
        memory_id = await service.save_memory(999999, content)

        assert isinstance(memory_id, UUID)
        mock_model.encode.assert_called_with(content)

        # 2. 검색 테스트
        results = await service.search_memories(999999, "AI")
        assert len(results) >= 1
        assert content in results
        mock_model.encode.assert_called_with("AI")


@pytest.mark.asyncio
async def test_memory_service_delete():
    with patch("panager.services.memory.SentenceTransformer") as mock_transformer_cls:
        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([0.1] * 768)
        mock_transformer_cls.return_value = mock_model

        service = MemoryService(get_pool())

        content = "지울 메모리"
        memory_id = await service.save_memory(999999, content)

        # 삭제 전 확인 (검색 결과에 포함되어야 함)
        results = await service.search_memories(999999, content)
        assert content in results

        # 삭제 실행
        await service.delete_memory(999999, memory_id)

        # 삭제 후 확인 (검색 결과에 없어야 함)
        results = await service.search_memories(999999, content)
        assert content not in results
