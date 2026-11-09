# AI CREATOR STUDIO v0.59 개발 진행 기록

- `job_repository.py`에서 더 이상 사용하지 않는 Job/Event SQL helper와 관련 import를 제거했습니다.
- 레거시 모듈은 Aggregate Repository를 호출하는 호환 facade로 축소했습니다.
- 기존 테스트·도구가 사용하는 최소 연결/시간 helper만 유지했습니다.
- Storage Port 문서의 오래된 SQL 소유 설명을 수정했습니다.
- Legacy facade에 SQL statement가 남지 않았는지 정적 테스트를 추가했습니다.

검증: Backend pytest 186 passed, compileall passed, Viewer 19/19.
