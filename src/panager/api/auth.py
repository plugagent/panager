from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

from panager.google.auth import exchange_code, get_auth_url
from panager.google.repository import save_tokens

router = APIRouter()


@router.get("/google/login")
async def google_login(user_id: int):
    url = get_auth_url(user_id)
    return RedirectResponse(url)


@router.get("/google/callback")
async def google_callback(code: str, state: str):
    try:
        user_id = int(state)
        tokens = await exchange_code(code, user_id)
        await save_tokens(user_id, tokens)
        return {"message": "Google 계정 연동이 완료되었습니다. Discord로 돌아가세요."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
