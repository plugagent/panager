from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from langchain_core.tools import tool
from pydantic import BaseModel

if TYPE_CHECKING:
    from panager.services.google import GoogleService


class TaskListInput(BaseModel):
    pass


class TaskCreateInput(BaseModel):
    title: str
    due_at: str | None = None


class TaskCompleteInput(BaseModel):
    task_id: str


def make_task_list(user_id: int, google_service: GoogleService):
    @tool(args_schema=TaskListInput)
    async def task_list() -> str:
        """Google Tasks의 할 일 목록을 조회합니다."""
        service = await google_service.get_tasks_service(user_id)
        result = await asyncio.to_thread(
            service.tasks().list(tasklist="@default").execute
        )
        items = result.get("items", [])
        if not items:
            return "할 일이 없습니다."
        pending = [
            f"- [{item['id']}] {item['title']}"
            for item in items
            if item.get("status") == "needsAction"
        ]
        if not pending:
            return "완료되지 않은 할 일이 없습니다."
        return "\n".join(pending)

    return task_list


def make_task_create(user_id: int, google_service: GoogleService):
    @tool(args_schema=TaskCreateInput)
    async def task_create(title: str, due_at: str | None = None) -> str:
        """Google Tasks에 새 할 일을 추가합니다."""
        service = await google_service.get_tasks_service(user_id)
        body: dict = {"title": title}
        if due_at:
            body["due"] = due_at
        await asyncio.to_thread(
            service.tasks().insert(tasklist="@default", body=body).execute
        )
        return f"할 일이 추가되었습니다: {title}"

    return task_create


def make_task_complete(user_id: int, google_service: GoogleService):
    @tool(args_schema=TaskCompleteInput)
    async def task_complete(task_id: str) -> str:
        """Google Tasks의 할 일을 완료 처리합니다."""
        service = await google_service.get_tasks_service(user_id)
        await asyncio.to_thread(
            service.tasks()
            .patch(tasklist="@default", task=task_id, body={"status": "completed"})
            .execute
        )
        return f"할 일이 완료 처리되었습니다: {task_id}"

    return task_complete
