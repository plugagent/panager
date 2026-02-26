# 인증 플로우 설계 문서

**날짜:** 2026-02-21  
**상태:** 확정

---

## 목표

사용자가 처음 패니저와 대화를 시작했을 때부터 Google 계정 연동까지의 UX를 개선한다.
Google 기능 요청 시 미연동 상태면 인증 안내 → 인증 완료 후 원래 요청을 자동 재실행한다.

---

## 결정사항

| 항목 | 결정 |
|---|---|
| Google 연동 필수 여부 | 선택 (미연동 상태에서도 대화 가능) |
| OAuth URL 노출 시점 | Google 기능 요청 시에만 |
| 콜백 후 알림 방식 | 웹페이지 성공 메시지만 |
| 인증 완료 후 동작 | 원래 요청 자동 재실행 → DM으로 결과 전송 |
| 봇+API 통합 | 단일 프로세스 (같은 asyncio 이벤트 루프) |
| 브리지 방식 | `asyncio.Queue` |
| pending 메시지 저장 | 메모리 dict `{user_id: str}` |

---

## 아키텍처

### 현재 구조

```
[panager 컨테이너] discord.py 봇
[api 컨테이너]     FastAPI OAuth 서버 (별도 프로세스)
```

### 변경 후 구조

```
[panager 컨테이너]
  ├── discord.py 봇 (asyncio 이벤트 루프)
  └── uvicorn FastAPI (같은 이벤트 루프, 포트 8000)

asyncio.Queue — 두 레이어 간 브리지
```

---

## 플로우

### 신규 사용자 첫 메시지

```
1. 사용자가 첫 DM 전송
2. DB에 사용자 등록
3. 에이전트 실행 (Google 연동 없이 대화 가능)
```

### Google 기능 요청 (미연동 상태)

```
1. 사용자: "이번 주 일정 보여줘"
2. 에이전트 → event_list 툴 호출
3. _get_valid_credentials() → 토큰 없음 → ValueError 발생
4. _tool_node에서 ValueError 캐치:
   - bot.pending_messages[user_id] = "이번 주 일정 보여줘"
   - ToolMessage: "Google 연동이 필요해요: https://..."
5. 에이전트가 사용자에게 인증 URL 안내
```

### OAuth 인증 완료

```
6. 사용자가 URL 클릭 → 구글 로그인
7. OAuth 콜백: 토큰 DB 저장
8. auth_complete_queue.put({"user_id": ..., "message": "이번 주 일정 보여줘"})
9. 웹페이지: "연동이 완료됐습니다. Discord로 돌아가세요."

10. _process_auth_queue() 백그라운드 태스크:
    - 큐에서 꺼냄
    - pending_messages에서 원래 메시지 제거
    - 에이전트 재실행
    - DM: "이번 주 일정입니다: ..."
```

---

## 변경 파일 목록

| 파일 | 변경 내용 |
|---|---|
| `bot/client.py` | uvicorn 내장 실행, `auth_complete_queue`, `pending_messages`, `_process_auth_queue()` |
| `api/main.py` | lifespan DB 초기화 제거, `app.state.bot` 주입 방식으로 변경 |
| `api/auth.py` | 콜백에서 `app.state.bot.auth_complete_queue.put()` 호출 |
| `agent/graph.py` | `_tool_node`에서 Google 미연동 에러 캐치, pending 저장, 인증 URL 반환 |
| `bot/handlers.py` | 신규 사용자 등록 후 에이전트 바로 실행 (WELCOME_MESSAGE 제거) |
| `docker-compose.yml` | `api` 서비스 제거, `panager`에 `ports: 8000:8000` 추가 |
| `docker-compose.dev.yml` | 삭제 |
| `Makefile` | 신규 생성 |

---

## 로컬 개발 환경

```bash
make dev    # test DB 올리고 봇 실행 (watchfiles 핫리로드)
make test   # test DB 올리고 pytest 실행
make up     # 프로덕션 Docker Compose 빌드+실행
make down   # 프로덕션 정리
```

`make dev`는 `POSTGRES_HOST=localhost POSTGRES_PORT=5432`을 환경변수로 주입하여
`.env`의 Docker 내부 호스트명(`db`)을 오버라이드한다.
