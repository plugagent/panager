# Design: CI/CD Pipeline & Zero Trust Security

## 1. 개요
`panager` 프로젝트의 코드 품질 유지와 안정적인 배포를 위해 GitHub Actions 기반의 CI/CD 파이프라인을 구축하고, 보안 강화를 위한 Zero Trust 원칙을 적용합니다.

## 2. CI (Continuous Integration) 설계
GitHub Actions를 사용하여 푸시 및 풀 리퀘스트 시점에 다음 작업을 자동 수행합니다.

### 2.1 주요 워크플로 (`.github/workflows/ci.yml`)
- **Lint & Format**: `astral-sh/setup-uv`를 사용하여 Python 3.13 환경에서 `ruff check` 및 `ruff format` 실행.
- **Testing**: `pgvector/pgvector:pg16` 서비스를 컨테이너로 띄워 실제 DB 환경에서 `pytest` 수행.
  - 서비스 포트: 5433:5432
  - 환경 변수: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` 설정.
- **Build Verification**: `docker compose build`를 통해 도커 이미지 빌드 가능 여부 검증.

## 3. CD (Continuous Deployment) 설계 (통합 예정)
자동화된 배포 프로세스를 위해 다음 단계를 추가 설계합니다.

- **Docker Registry**: GitHub Container Registry (GHCR) 또는 Docker Hub에 이미지 푸시.
- **Continuous Deployment**: 배포 서버에서 Webhook 또는 GitHub Actions Runner를 통해 `docker compose pull && docker compose up -d` 자동 수행.
- **Environment Management**: `.env` 파일 대신 GitHub Secrets를 사용하여 민감 정보 주입.

## 4. Zero Trust 보안 설계
- **Least Privilege**: GitHub Actions 워크플로에 최소한의 권한(`contents: read` 등)만 부여.
- **Secret Management**: 모든 API 키(Discord, Google, OpenAI 등)는 GitHub Secrets에서 관리하며, 로그에 노출되지 않도록 처리.
- **Infrastructure as Code**: 모든 인프라 구성(Docker, Actions)을 코드로 관리하여 변경 이력을 추적하고 검증되지 않은 변경 차단.

## 5. 관련 파일 및 경로
- CI 설정: `.github/workflows/ci.yml`
- 의존성 관리: `pyproject.toml`, `uv.lock`
- 환경 설정: `.env.example`, `src/panager/core/config.py`
