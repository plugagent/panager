.PHONY: dev db db-down test migrate-test up down

# 로컬 개발: test DB 올리고 봇 핫리로드 실행
dev: db
	POSTGRES_HOST=localhost POSTGRES_PORT=5433 \
	uv run watchfiles "python -m panager.bot.client" src

# test DB 시작 (healthy 대기)
db:
	docker compose -f docker-compose.test.yml up -d --wait

# test DB 정리
db-down:
	docker compose -f docker-compose.test.yml down

# test DB 마이그레이션
migrate-test: db
	POSTGRES_HOST=localhost POSTGRES_PORT=5433 \
	uv run alembic upgrade head

# 테스트 (test DB 사용)
test: db
	POSTGRES_HOST=localhost POSTGRES_PORT=5433 \
	uv run pytest -v

# 프로덕션 빌드+실행
up:
	docker compose up -d --build

# 프로덕션 정리
down:
	docker compose down
