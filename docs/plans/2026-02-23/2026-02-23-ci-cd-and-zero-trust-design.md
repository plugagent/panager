# Design: CI/CD Pipeline & Zero Trust Security

## 1. 개요
`panager` 프로젝트의 코드 품질 유지와 안정적인 배포를 위해 GitHub Actions 기반의 CI/CD 파이프라인을 구축하고, 보안 강화를 위한 Zero Trust 원칙을 적용합니다.

## 2. CI (Continuous Integration) 설계
GitHub Actions를 사용하여 푸시 및 풀 리퀘스트 시점에 다음 작업을 자동 수행합니다.

### 2.1 주요 워크플로 (`.github/workflows/ci.yml`)
- **Lint & Format**: `astral-sh/setup-uv`를 사용하여 Python 3.13 환경에서 `ruff check` 및 `ruff format` 실행.
- **Testing**: `pgvector/pgvector:pg16` 서비스를 컨테이너로 띄워 실제 DB 환경에서 `pytest` 수행.
- **Build Verification**: `docker compose build`를 통해 도커 이미지 빌드 가능 여부 검증.

## 3. CD (Continuous Deployment) 설계
`main` 브랜치에 코드가 병합될 때 자동으로 배포를 수행합니다.

### 3.1 배포 프로세스 (`.github/workflows/cd.yml`)
- **Build & Push**: GitHub Container Registry (GHCR)로 `latest` 태그 이미지를 빌드하여 푸시합니다.
- **Zero-Trust SSH Transport**: Cloudflare Tunnel(`cloudflared`)을 사용하여 포트 개방 없이 서버에 SSH로 접속합니다.
- **Environment Management**: 전체 `.env` 파일 내용을 GitHub Secret(`ENV_FILE`)으로 관리하며, 배포 시점에 서버에 동적으로 생성합니다.
- **Deployment**: `docker compose pull` 및 `docker compose up -d`를 통해 최신 이미지를 반영합니다.

## 4. Zero Trust 보안 설계
- **No Inbound Ports**: 서버의 모든 인바운드 포트를 닫고 Cloudflare Tunnel을 통해서만 접근을 허용합니다.
- **Service Token & SSH Key**: Cloudflare Access 서비스 토큰(설정 시)과 SSH Private Key를 결합한 다중 인증을 적용합니다.
- **Least Privilege**: GitHub Actions 워크플로에 최소한의 권한(`packages: write` 등)만 부여합니다.

## 5. 관련 파일 및 경로
- CI 설정: `.github/workflows/ci.yml`
- CD 설정: `.github/workflows/cd.yml`
- 프로덕션 구성: `docker-compose.yml` (GHCR 이미지 사용)
- 환경 설정: GitHub Secrets (`ENV_FILE`, `SSH_PRIVATE_KEY` 등)

