# Design Doc: DB 통합 및 테스트 환경 최적화

`docker-compose.test.yml`을 제거하고, `dev` 환경의 데이터베이스 컨테이너를 테스트에서도 공유하도록 설정을 통합합니다.

## 1. 개요
현재 `dev` 환경과 `test` 환경이 별도의 DB 컨테이너와 포트를 사용하고 있어 관리가 복잡합니다. `dev` DB 자체가 테스트용으로 사용되어도 무방하므로, 이를 하나로 통합하여 개발 경험을 개선합니다.

## 2. 변경 사항

### 2.1 인프라 및 설정 (Infrastructure & Config)
- `docker-compose.test.yml` 삭제
- `docker-compose.dev.yml`의 `db` 서비스(5432 포트)를 공용으로 사용

### 2.2 빌드 도구 (Makefile)
- `db` 타겟: `docker-compose.dev.yml`의 `db` 서비스만 실행하도록 수정
- `test` 타겟: `POSTGRES_PORT=5432`, `POSTGRES_DB=panager`를 사용하도록 수정
- `migrate-test` 타겟: `test`와 동일하게 설정 수정

### 2.3 테스트 코드 (Test Code)
- `tests/test_db_connection.py` 및 기타 테스트 파일에서 하드코딩된 `5432` 포트와 `panager` DB 명칭을 `5432` 및 `panager`로 변경

### 2.4 CI/CD (GitHub Workflows)
- `.github/workflows/dev.yml` 및 `prod-ci.yml`에서 테스트용 PostgreSQL 서비스의 DB 이름을 `panager`로 통일

## 3. 기대 효과
- 로컬 개발 환경 구성 단순화
- 컨테이너 리소스 절약
- 개발 및 테스트 환경 간의 설정 일관성 확보
