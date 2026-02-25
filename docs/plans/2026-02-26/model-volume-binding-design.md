# Design: Embedding Model Volume Binding via Init Container

## 1. 개요 (Overview)
현재 `panager`는 Docker 이미지 빌드 시점에 임베딩 모델을 포함하고 있습니다. 이는 이미지 크기를 비대하게 만들고, CI/CD 효율을 저하시키며, 모델 교체 시 전체 이미지를 다시 빌드해야 하는 불편함이 있습니다. 이를 해결하기 위해 **모델 전용 이미지**와 **Init 컨테이너**를 활용하여 모델을 볼륨으로 바인딩하는 구조로 개선합니다.

## 2. 목표 (Goals)
- **이미지 최적화:** 메인 앱 이미지에서 수 GB의 모델 데이터를 분리하여 크기 축소.
- **콜드 스타트 방지:** 런타임 다운로드 없이, 서비스 시작 시점에 이미 모델이 볼륨에 준비되도록 설계.
- **CI/CD 유연성:** 앱 코드와 모델의 빌드/배포 주기를 분리.
- **유지보수성:** 호스트 환경 또는 외부 스토리지와 모델 데이터를 쉽게 공유.

## 3. 설계 (Architecture)

### 3.1. 컴포넌트 구조
1.  **Model Image (`Dockerfile.model`):**
    *   빌드 시점에 HuggingFace에서 모델을 다운로드하여 내부에 저장.
    *   최종 단계에서 `alpine` 등 최소한의 OS 이미지를 사용하여 파일만 보관.
    *   실행 시 지정된 볼륨 경로로 모델 파일을 복사하는 스크립트 포함.
2.  **Init Container (`model-init` service):**
    *   메인 앱 실행 전 동작하는 일회성 컨테이너.
    *   모델 이미지의 데이터를 공유 볼륨(`hf_cache`)으로 복사.
3.  **Main App (`panager` service):**
    *   공유 볼륨을 `/app/.cache/huggingface`에 마운트하여 사용.
    *   `depends_on` 설정을 통해 `model-init` 완료 후 실행 보장.

### 3.2. 데이터 흐름
1.  CI/CD에서 `panager-model` 이미지 빌드 및 푸시.
2.  배포 환경에서 `docker-compose up` 실행.
3.  `model-init`이 실행되어 볼륨에 모델 파일 복사.
4.  복사 완료 후 `panager` 앱이 실행되며 볼륨의 모델을 즉시 로드.

## 4. 변경 사항 (Changes)

### 4.1. Docker 설정
- `Dockerfile.model` 신규 생성.
- `Dockerfile` 내 모델 다운로드 스테이지 및 복사 로직 제거.
- `docker-compose.yml` (및 `.dev.yml`, `.test.yml`)에 `model-init` 서비스 추가 및 `panager` 의존성 수정.

### 4.2. 애플리케이션 코드
- `src/panager/services/memory.py`: 모델 경로를 환경 변수(`HF_HOME`)를 통해 유연하게 참조하도록 보장 (현재 이미 `HF_HOME` 사용 중).

## 5. 테스트 및 검증 (Testing & Verification)
1.  **빌드 테스트:** `Dockerfile.model`이 정상적으로 모델을 다운로드하고 이미지를 생성하는지 확인.
2.  **실행 테스트:** `docker-compose up` 시 `model-init`이 종료된 후 앱이 즉시 모델을 로드하는지 로그 확인.
3.  **볼륨 확인:** 컨테이너 내부 및 호스트(필요시)에서 모델 파일이 정상적으로 복사되었는지 확인.

## 6. 결론 (Conclusion)
이 설계는 Docker의 레이어 캐싱과 Init 컨테이너 패턴을 활용하여 ML 모델 관리의 고질적인 문제인 이미지 크기와 배포 속도를 획기적으로 개선합니다.
