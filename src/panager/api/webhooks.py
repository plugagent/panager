from __future__ import annotations

import hashlib
import hmac
import json
import logging


from fastapi import APIRouter, Header, HTTPException, Request

from panager.core.config import Settings
from panager.db.connection import get_pool

log = logging.getLogger(__name__)
router = APIRouter()


def _get_settings() -> Settings:
    return Settings()  # type: ignore


async def verify_signature(request: Request, signature: str | None) -> bytes:
    """GitHub Webhook 시그니처 검증."""
    if not signature:
        log.warning("X-Hub-Signature-256 헤더가 누락되었습니다.")
        raise HTTPException(status_code=401, detail="X-Hub-Signature-256 missing")

    body = await request.body()
    settings = _get_settings()

    if not settings.github_webhook_secret:
        log.error("GITHUB_WEBHOOK_SECRET 설정이 누락되었습니다.")
        raise HTTPException(status_code=500, detail="Webhook secret not configured")

    secret = settings.github_webhook_secret.encode()
    hash_object = hmac.new(secret, body, hashlib.sha256)
    expected_signature = "sha256=" + hash_object.hexdigest()

    if not hmac.compare_digest(signature, expected_signature):
        log.warning("GitHub Webhook 시그니처 검증 실패")
        raise HTTPException(status_code=401, detail="Invalid signature")

    return body


@router.post("/github")
async def github_webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(None),
):
    """GitHub Push 이벤트를 수신하여 에이전트 작업을 트리거합니다."""
    body = await verify_signature(request, x_hub_signature_256)

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # repository.full_name, ref, commits 추출
    repository = payload.get("repository", {})
    repo_full_name = repository.get("full_name")
    ref = payload.get("ref")
    commits = payload.get("commits", [])

    if not repo_full_name or not ref:
        return {"status": "ignored", "reason": "Missing repository or ref info"}

    # 커밋 메시지 및 타임스탬프 추출
    extracted_commits = [
        {
            "message": c.get("message"),
            "timestamp": c.get("timestamp"),
        }
        for c in commits
    ]

    # github_tokens 테이블에서 user_id 조회
    # 개인용 봇이므로 토큰 소유자를 해당 푸시의 대상 사용자로 간주
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id FROM github_tokens")
        if not rows:
            log.info("github_tokens에 등록된 사용자가 없어 무시합니다.")
            return {"status": "ignored", "reason": "No registered users"}

        user_ids = [row["user_id"] for row in rows]

    bot = request.app.state.bot
    context = {
        "repository": repo_full_name,
        "ref": ref,
        "commits": extracted_commits,
    }

    # 각 사용자별로 에이전트 트리거
    for user_id in user_ids:
        # 에이전트에게 전달할 명령 메시지 구성
        command = (
            f"GitHub Push 알림: {repo_full_name} 저장소의 {ref} 브랜치에 "
            f"{len(extracted_commits)}개의 새로운 커밋이 푸시되었습니다. "
            f"변경 내용을 확인하고 회고를 작성할까요?\n\n"
            f"컨텍스트: {json.dumps(context, ensure_ascii=False)}"
        )
        # trigger_task(user_id, command, payload)
        # 현재 bot.py의 trigger_task는 payload를 직접 사용하지 않으므로 command에 context를 포함하여 전달
        await bot.trigger_task(
            user_id, command, payload={"pending_reflections": [context]}
        )

    log.info(
        "GitHub Webhook 처리 완료: %s (ref: %s, commits: %d)",
        repo_full_name,
        ref,
        len(commits),
    )
    return {"status": "success", "triggered_count": len(user_ids)}
