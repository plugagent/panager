# Design: Advanced Build & Deploy Optimization

## 1. Goal
Achieve zero-downtime deployment and automated rollback while maintaining high build efficiency.

## 2. Architecture Changes

### 2.1. Health Check Endpoint
- **File**: `src/panager/api/app.py` (or main API entrypoint)
- **Change**: Add a GET `/health` endpoint that returns `{"status": "ok"}`.
- **Purpose**: Provide a reliable signal for Docker and GHA to verify service readiness.

### 2.2. Zero-Downtime Deployment (Docker Compose)
- **File**: `docker-compose.yml`
- **Configuration**:
  - Add `healthcheck` to `panager` service using `curl` against the new `/health` endpoint.
  - Set `deploy.update_config.order: start-first` to ensure the new container is healthy before stopping the old one.
  - Use `--wait` flag in `docker compose up -d` during deployment.

### 2.3. Automated Rollback (GitHub Actions)
- **File**: `.github/workflows/dev.yml`
- **Workflow Logic**:
  1. Capture `PREVIOUS_SHA` before starting deployment.
  2. Attempt `docker compose up -d --wait`.
  3. If failed, trigger a rollback job that reverts `.env`'s `IMAGE_TAG` to `PREVIOUS_SHA` and redeploys.
  4. Post-deployment cleanup (`prune`) only runs on success.

### 2.4. Build Optimization (Buildx)
- **Change**: Consolidate multiple image tagging and pushing into a single build session where possible.
- **Caching**: Ensure inline cache is used for faster layer comparison with GHCR.

## 3. Success Criteria
- Zero bot downtime during deployment.
- Deployment automatically reverts to previous version if health checks fail.
- Build & Push time remains efficient despite added complexity.

## 4. Risks & Mitigations
- **Port Conflicts**: Since we use `start-first`, two containers will briefly attempt to bind to the same host port.
  - *Mitigation*: Since the bot primarily uses outbound connections (Discord) and the API is behind a proxy, we will use internal port mapping or ensure the proxy can handle temporary double-routing. For local port bindings, we may need to adjust to random ports or use Docker's internal networking.
