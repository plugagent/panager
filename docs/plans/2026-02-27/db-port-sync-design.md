# Design Doc: 환경별 DB 포트 동기화 및 충돌 방지

배포 서버에서 `dev`와 `prod` 환경이 동일한 DB 포트(5432)를 사용함에 따른 충돌 문제를 해결하기 위해, `POSTGRES_PORT` 환경 변수를 기반으로 컨테이너 내부 및 외부 포트를 동기화하는 설계를 적용합니다.

## 1. 개요
단일 서버 내에서 여러 환경(`dev`, `prod`)을 호스팅할 때, 기본값인 5432 포트가 충돌하는 문제를 방지해야 합니다. 이를 위해 `POSTGRES_PORT` 변수 하나로 애플리케이션 접속, DB 컨테이너 리스닝, 호스트 포트 노출을 모두 제어합니다.

## 2. 변경 사항

### 2.1 인프라 설정 (Docker Compose)
`docker-compose.yml` (Prod) 및 `docker-compose.dev.yml` (Dev)의 `db` 서비스 설정을 다음과 같이 수정합니다.
- `environment`: `PGPORT=${POSTGRES_PORT:-5432}` 추가. 이는 PostgreSQL 컨테이너 내부의 리스닝 포트를 변경합니다.
- `ports`: `"${POSTGRES_PORT:-5432}:${POSTGRES_PORT:-5432}"`로 수정하여 내/외부 포트를 일치시킵니다.
- `healthcheck`: `pg_isready` 호출 시 `-p ${POSTGRES_PORT:-5432}` 옵션을 추가하여 변경된 포트를 체크하도록 합니다.

### 2.2 빌드 도구 (Makefile)
- 로컬 개발 및 테스트 시에도 `POSTGRES_PORT` 환경 변수가 유동적으로 반영되도록 타겟들을 점검합니다.

### 2.3 환경 설정 (.env.example)
- `POSTGRES_PORT` 항목에 대한 설명을 보완하여, 배포 서버 환경별로 포트를 다르게 설정해야 함을 명시합니다.

## 3. 기대 효과
- **완전한 격리**: 서버의 `.env`에서 `POSTGRES_PORT`를 바꾸는 것만으로 모든 포트 설정이 자동으로 변경되어 충돌을 방지합니다.
- **기존 호환성 유지**: 기존 환경 변수(`POSTGRES_USER` 등)를 건드리지 않으며, 기본값(5432)을 유지하여 로컬 개발 환경의 변화를 최소화합니다.
