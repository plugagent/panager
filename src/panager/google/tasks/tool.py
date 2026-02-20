from __future__ import annotations

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from langchain_core.tools import tool
from pydantic import BaseModel

from panager.google.credentials import _execute, _get_valid_credentials


def _build_service(creds: Credentials):
    return build("tasks", "v1", credentials=creds)


class TaskListInput(BaseModel):
    pass


class TaskCreateInput(BaseModel):
    title: str
    due_at: str | None = None


class TaskCompleteInput(BaseModel):
    task_id: str


def make_task_list(user_id: int):
    @tool(args_schema=TaskListInput)
    async def task_list() -> str:
        """Google Tasks의 할 일 목록을 조회합니다."""
        creds = await _get_valid_credentials(user_id)
        service = _build_service(creds)
        result = _execute(service.tasks().list(tasklist="@default"))
        items = result.get("items", [])
        if not items:
            return "할 일이 없습니다."
        return "\n".join(
            f"- [{item['id']}] {item['title']}"
            for item in items
            if item.get("status") == "needsAction"
        )

    return task_list


def make_task_create(user_id: int):
    @tool(args_schema=TaskCreateInput)
    async def task_create(title: str, due_at: str | None = None) -> str:
        """Google Tasks에 새 할 일을 추가합니다."""
        creds = await _get_valid_credentials(user_id)
        service = _build_service(creds)
        body: dict = {"title": title}
        if due_at:
            body["due"] = due_at
        _execute(service.tasks().insert(tasklist="@default", body=body))
        return f"할 일이 추가되었습니다: {title}"

    return task_create


def make_task_complete(user_id: int):
    @tool(args_schema=TaskCompleteInput)
    async def task_complete(task_id: str) -> str:
        """Google Tasks의 할 일을 완료 처리합니다."""
        creds = await _get_valid_credentials(user_id)
        service = _build_service(creds)
        _execute(
            service.tasks().patch(
                tasklist="@default", task=task_id, body={"status": "completed"}
            )
        )
        return f"할 일이 완료 처리되었습니다: {task_id}"

    return task_complete
