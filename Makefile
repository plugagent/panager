.PHONY: dev db db-down test migrate-test up down dev-up dev-down dev-logs build-model

# 로컬 개발 (Native): test DB 올리고 봇 핫리로드 실행
dev: db
	POSTGRES_HOST=localhost POSTGRES_PORT=5433 \
	uv run watchfiles "python -m panager.main" src

# 로컬 개발 (Docker): 도커 컨테이너에서 봇 실행 (핫리로드 지원)
dev-up:
	MODEL_IMAGE_TAG=$(MODEL_IMAGE_TAG) docker compose -f docker-compose.dev.yml up -d --build

dev-down:
	docker compose -f docker-compose.dev.yml down

dev-logs:
	docker compose -f docker-compose.dev.yml logs -f

# 모델 이미지 빌드 (로컬)
build-model:
	docker compose build model-init

# test DB 시작 (healthy 대기)
db:
	docker compose -f docker-compose.test.yml up -d --wait

# test DB 정리
db-down:
	docker compose -f docker-compose.test.yml down

# test DB 마이그레이션
migrate-test: db
	POSTGRES_HOST=localhost POSTGRES_PORT=5433 \
	POSTGRES_USER=panager POSTGRES_PASSWORD=panager POSTGRES_DB=panager_test \
	uv run alembic upgrade head

# 테스트 (test DB 사용)
test: db
	POSTGRES_HOST=localhost POSTGRES_PORT=5433 \
	POSTGRES_USER=panager POSTGRES_PASSWORD=panager POSTGRES_DB=panager_test \
	uv run pytest -v

# 프로덕션 빌드+실행
up:
	MODEL_IMAGE_TAG=$(MODEL_IMAGE_TAG) docker compose up -d --build

# 프로덕션 정리
down:
	docker compose down
