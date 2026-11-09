# 제품 및 시스템 설계

## 설계 원칙

1.  프런트엔드 뷰어, 백엔드 API, 에셋 접근, 룩북/미리보기 기능의 책임을
    분리합니다.
2.  하나의 리소스 해제 실패가 나머지 cleanup을 중단시키지 않도록 합니다.
3.  리소스 생성·사용·교체·언마운트·폐기 단계를 구분합니다.
4.  모델 및 에셋 접근은 인증/권한 경계를 지킵니다.
5.  구조 검사, 단위/통합 테스트, 브라우저 capability 검사, 실제 E2E를
    별도 등급으로 기록합니다.
6.  유료 Provider, 운영 데이터, 게시, 권리, 배포는 승인 경계로
    유지합니다.

## 논리 아키텍처

``` text
AI CREATOR STUDIO
├── Client / Studio UI
│   ├── Character & Lookbook workflows
│   ├── Authenticated preview
│   └── 3D Viewer
│       ├── Model URL resolution
│       ├── Bounded GLTF download
│       ├── GLTF scene / materials / textures
│       ├── Animation mixer & controls
│       └── Renderer / GPU resource lifecycle
├── Backend API
│   ├── Authentication & authorization
│   ├── Project / asset endpoints
│   ├── Lookbook / preview endpoints
│   └── Request / response contracts
└── External / Operational boundaries
    ├── Object storage
    ├── AI Providers / credit charging
    ├── Publication / rights
    └── Deployment / production database
```

이 도식은 논리 구성입니다. 실제 패키지와 파일 경로는 소스 트리 확보 후
확인해야 합니다.

## 3D Viewer 수명주기

### 모델 교체

1.  기존 scene에서 모델 제거
2.  animation mixer 정지
3.  mixer action/clip 참조 해제
4.  GLTF geometry/material/texture 리소스 해제
5.  관련 참조 초기화
6.  새 모델 등록

각 단계는 독립적인 실패 경계를 가져야 합니다. 앞 단계가 실패해도 후속
단계는 실행하고 모든 실패를 수집합니다.

### Renderer teardown 관리 대상

-   animation frame 취소
-   ResizeObserver disconnect
-   controls dispose
-   mixer stop/uncache
-   GLTF 및 stage 리소스 disposal
-   shadow/render target disposal
-   renderer dispose
-   canvas 제거
-   refs 및 내부 참조 초기화

## 핵심 모듈 경계

  ---------------------------------------------------------------------------
  영역                    책임                        검증
  ----------------------- --------------------------- -----------------------
  GLTF URL resolution     상대/절대 모델 URL 결정     base path, 인증 경로

  Bounded download        응답 크기/버퍼 상한         Content-Length,
                                                      streaming, trim

  GLTF disposal           geometry/material/texture   공유 리소스, 중복 해제
                          해제                        

  Cleanup runner          단계별 실행/오류 수집       실패 후 후속 실행

  Viewer component        React와 Three.js 연결       mount/update/unmount

  Backend contracts       요청/응답/API 일치          route/schema/contract
  ---------------------------------------------------------------------------

외부 glTF buffer/image URI 및 multi-file GLTF import는 이전 기록상 제한
또는 미지원입니다.
