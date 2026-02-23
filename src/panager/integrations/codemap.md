# src/panager/integrations/

외부 서비스 API와의 저수준 통신 및 연동 로직 관리.

## Responsibility

외부 시스템(Google 등)과의 연동 추상화 및 공통 작업(비동기 실행, 에러 핸들링) 수행.

## Design

- **비동기 래핑**: `asyncio.to_thread`를 통한 비동기 실행 지원.
- **예외 추상화**: HTTP 상태 코드를 도메인 예외(`GoogleAuthRequired`)로 변환.

## Flow

1. 상위 모듈에서 API 요청 객체 생성.
2. `GoogleClient`에 요청 전달.
3. `GoogleClient`가 실행 후 결과 반환.

## Integration

- **panager.core.exceptions**: `GoogleAuthRequired` 사용.
- **Google API Libraries**: `google-api-python-client` 사용.
