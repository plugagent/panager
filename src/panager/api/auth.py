from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from panager.google.auth import exchange_code, get_auth_url
from panager.google.repository import save_tokens

router = APIRouter()


@router.get("/google/login")
async def google_login(user_id: int):
    url = get_auth_url(user_id)
    return RedirectResponse(url)


@router.get("/google/callback")
async def google_callback(request: Request, code: str, state: str):
    try:
        user_id = int(state)
        tokens = await exchange_code(code, user_id)
        await save_tokens(user_id, tokens)

        bot = request.app.state.bot
        pending = bot.pending_messages.get(user_id)
        await bot.auth_complete_queue.put(
            {
                "user_id": user_id,
                "message": pending,
            }
        )

        return HTMLResponse(
            "<html><body><h2>✅ Google 연동이 완료됐습니다.</h2>"
            "<p>Discord로 돌아가세요. 잠시 후 요청하신 내용을 처리해드립니다.</p>"
            "</body></html>"
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
