# CI/CD and Zero Trust Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** GitHub Actions 기반 배포(CD) 파이프라인 구축 및 Cloudflare Tunnel + SSH 기반의 Zero Trust 서버 배포 환경 설정

**Architecture:** 
1. `docker-compose.yml`을 프로덕션용으로 구성하여 GitHub Container Registry(GHCR)에서 이미지를 받아와 실행하도록 설정합니다.
2. 배포 대상 서버는 모든 인바운드 포트를 닫고, `cloudflared`를 통해서만 SSH 접속을 허용합니다 (Zero Trust).
3. GitHub Actions는 빌드 후 `cloudflared` ProxyCommand를 사용해 서버에 안전하게 접속합니다.
4. 전체 `.env` 파일 내용은 GitHub Secret(`ENV_FILE`)으로 관리하며 배포 시점에 서버에 동적으로 생성합니다.

**Tech Stack:** GitHub Actions, Docker Compose, Cloudflare Tunnel (cloudflared), SSH, bash

---

### Task 1: GitHub Secrets 및 서버 보안 설정

**Step 1: GitHub Secrets 등록**
레포지토리의 `Settings > Secrets and variables > Actions`에 다음 항목들을 등록합니다.

- `SERVER_HOST`: 배포 서버의 호스트명 (Cloudflare Tunnel을 통해 라우팅되는 도메인)
- `SERVER_USER`: 배포 서버 SSH 사용자 (예: `ubuntu`)
- `SSH_PRIVATE_KEY`: 배포용 Private SSH Key
- `ENV_FILE`: 서버에서 사용할 전체 `.env` 파일 내용 (API 키, DB 암호 등 포함)
- `CF_ID`: Cloudflare Access Service Token Client ID (선택 사항)
- `CF_SECRET`: Cloudflare Access Service Token Client Secret (선택 사항)

**Step 2: 서버 측 Zero Trust & SSH 설정 절차**

1. **`authorized_keys` 등록**
   ```bash
   # GitHub Actions용 Public Key를 서버에 등록
   echo "ssh-ed25519 AAAAC3..." >> ~/.ssh/authorized_keys
   chmod 600 ~/.ssh/authorized_keys
   ```

2. **`sshd_config` 수정 (보안 강화)**
   ```text
   ListenAddress 127.0.0.1  # 터널링을 통해서만 접속 허용 시 권장
   PasswordAuthentication no
   PubkeyAuthentication yes
   ```

3. **Cloudflare Tunnel (cloudflared) 설정**
   - 서버에 `cloudflared` 데몬 설치 및 `ingress` 규칙에 `ssh://localhost:22` 추가.

---

### Task 2: 프로덕션용 Docker Compose 및 CD 워크플로 구축

**Step 1: `docker-compose.yml` 수정**
- `build: .` 섹션을 삭제하고 `image: ghcr.io/${GITHUB_REPOSITORY_OWNER}/panager:latest`를 사용합니다.

**Step 2: `.github/workflows/cd.yml` 작성**
- **Build Job**: GHCR로 이미지 빌드 및 푸시.
- **Deploy Job**:
  - `cloudflared` 설치 및 SSH ProxyCommand 설정.
  - 서버 접속 후 `ENV_FILE` 시크릿을 `.env` 파일로 주입.
  - `docker compose pull && docker compose up -d` 실행.

**Step 3: 커밋 및 푸시**
```bash
git add docker-compose.yml .github/workflows/cd.yml
git commit -m "feat: 프로덕션용 docker-compose 및 Zero-Trust CD 워크플로 구축"
git push origin dev
```
