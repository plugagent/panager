from __future__ import annotations

from datetime import datetime, timezone

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from langchain_core.tools import tool
from pydantic import BaseModel

from panager.google.auth import refresh_access_token
from panager.google.repository import get_tokens, update_access_token


async def _get_valid_credentials(user_id: int) -> Credentials:
    tokens = await get_tokens(user_id)
    if not tokens:
        raise ValueError(
            "Google 계정이 연동되지 않았습니다. /auth 명령으로 연동해주세요."
        )

    if tokens.expires_at <= datetime.now(timezone.utc):
        new_token, new_expires = await refresh_access_token(tokens.refresh_token)
        await update_access_token(user_id, new_token, new_expires)
        tokens.access_token = new_token

    return Credentials(token=tokens.access_token)


def _build_service(creds: Credentials):
    return build("tasks", "v1", credentials=creds)


# ---------------------------------------------------------------------------
# Tool factories – user_id is captured via closure, not exposed to the LLM
# ---------------------------------------------------------------------------


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
        result = service.tasks().list(tasklist="@default").execute()
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
        service.tasks().insert(tasklist="@default", body=body).execute()
        return f"할 일이 추가되었습니다: {title}"

    return task_create


def make_task_complete(user_id: int):
    @tool(args_schema=TaskCompleteInput)
    async def task_complete(task_id: str) -> str:
        """Google Tasks의 할 일을 완료 처리합니다."""
        creds = await _get_valid_credentials(user_id)
        service = _build_service(creds)
        service.tasks().patch(
            tasklist="@default", task=task_id, body={"status": "completed"}
        ).execute()
        return f"할 일이 완료 처리되었습니다: {task_id}"

    return task_complete


# ---------------------------------------------------------------------------
# Standalone tool objects kept for backward compatibility (e.g. slash commands)
# These still require user_id as an argument.
# ---------------------------------------------------------------------------


class _TaskListInputLegacy(BaseModel):
    user_id: int


class _TaskCreateInputLegacy(BaseModel):
    title: str
    user_id: int
    due_at: str | None = None


class _TaskCompleteInputLegacy(BaseModel):
    task_id: str
    user_id: int


@tool(args_schema=_TaskListInputLegacy)
async def task_list(user_id: int) -> str:
    """Google Tasks의 할 일 목록을 조회합니다."""
    creds = await _get_valid_credentials(user_id)
    service = _build_service(creds)
    result = service.tasks().list(tasklist="@default").execute()
    items = result.get("items", [])
    if not items:
        return "할 일이 없습니다."
    return "\n".join(
        f"- [{item['id']}] {item['title']}"
        for item in items
        if item.get("status") == "needsAction"
    )


@tool(args_schema=_TaskCreateInputLegacy)
async def task_create(title: str, user_id: int, due_at: str | None = None) -> str:
    """Google Tasks에 새 할 일을 추가합니다."""
    creds = await _get_valid_credentials(user_id)
    service = _build_service(creds)
    body: dict = {"title": title}
    if due_at:
        body["due"] = due_at
    service.tasks().insert(tasklist="@default", body=body).execute()
    return f"할 일이 추가되었습니다: {title}"


@tool(args_schema=_TaskCompleteInputLegacy)
async def task_complete(task_id: str, user_id: int) -> str:
    """Google Tasks의 할 일을 완료 처리합니다."""
    creds = await _get_valid_credentials(user_id)
    service = _build_service(creds)
    service.tasks().patch(
        tasklist="@default", task=task_id, body={"status": "completed"}
    ).execute()
    return f"할 일이 완료 처리되었습니다: {task_id}"
