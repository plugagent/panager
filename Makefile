.PHONY: dev db db-down test migrate-test up down dev-up dev-down dev-logs build-model

# 로컬 개발 (Native): dev DB 올리고 봇 핫리로드 실행
dev: db
	POSTGRES_HOST=localhost POSTGRES_PORT=5432 \
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
	docker compose -f docker-compose.dev.yml build model-init

# dev DB 시작 (healthy 대기)
db:
	docker compose -f docker-compose.dev.yml up -d db --wait

# dev DB 정리
db-down:
	docker compose -f docker-compose.dev.yml stop db

# DB 마이그레이션 (dev DB 사용)
migrate-test: db
	POSTGRES_HOST=localhost POSTGRES_PORT=5432 \
	POSTGRES_USER=panager POSTGRES_DB=panager \
	uv run alembic upgrade head

# 테스트 (dev DB 사용)
test: db
	POSTGRES_HOST=localhost POSTGRES_PORT=5432 \
	POSTGRES_USER=panager POSTGRES_DB=panager \
	uv run pytest -v

# 프로덕션 빌드+실행
up:
	MODEL_IMAGE_TAG=$(MODEL_IMAGE_TAG) IMAGE_TAG=$(IMAGE_TAG) docker compose up -d

# 프로덕션 정리
down:
	docker compose down
