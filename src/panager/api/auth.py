from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

router = APIRouter()


@router.get("/google/login")
async def google_login(request: Request, user_id: int):
    bot = request.app.state.bot
    url = bot.google_service.get_auth_url(user_id)
    return RedirectResponse(url)


@router.get("/google/callback")
async def google_callback(request: Request, code: str, state: str):
    try:
        user_id = int(state)
        bot = request.app.state.bot
        await bot.google_service.exchange_code(code, user_id)

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


@router.get("/github/login")
async def github_login(request: Request, user_id: int):
    bot = request.app.state.bot
    url = bot.github_service.get_auth_url(user_id)
    return RedirectResponse(url)


@router.get("/github/callback")
async def github_callback(request: Request, code: str, state: str):
    try:
        user_id = int(state)
        bot = request.app.state.bot
        await bot.github_service.exchange_code(code, user_id)

        pending = bot.pending_messages.get(user_id)
        await bot.auth_complete_queue.put(
            {
                "user_id": user_id,
                "message": pending,
            }
        )

        return HTMLResponse(
            "<html><body><h2>✅ GitHub 연동이 완료됐습니다.</h2>"
            "<p>Discord로 돌아가세요. 잠시 후 요청하신 내용을 처리해드립니다.</p>"
            "</body></html>"
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/notion/login")
async def notion_login(request: Request, user_id: int):
    bot = request.app.state.bot
    url = bot.notion_service.get_auth_url(user_id)
    return RedirectResponse(url)


@router.get("/notion/callback")
async def notion_callback(request: Request, code: str, state: str):
    try:
        user_id = int(state)
        bot = request.app.state.bot
        await bot.notion_service.exchange_code(code, user_id)

        pending = bot.pending_messages.get(user_id)
        await bot.auth_complete_queue.put(
            {
                "user_id": user_id,
                "message": pending,
            }
        )

        return HTMLResponse(
            "<html><body><h2>✅ Notion 연동이 완료됐습니다.</h2>"
            "<p>Discord로 돌아가세요. 잠시 후 요청하신 내용을 처리해드립니다.</p>"
            "</body></html>"
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
