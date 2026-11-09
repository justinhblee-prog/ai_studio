# 개발 진행 기록 v0.41

## 구현
- `app/repositories/poll.py`에 PollTask worker port 및 SQLite adapter 추가.
- `worker_repositories.py`는 이전 public class name을 호환 계층으로 유지.
- Output persistence는 OutputRepository를 통해 위임하고, Job lifecycle은 Job/Event UoW 기반 service를 유지.
- 미구현 PostgreSQL은 fail-closed.

## 검증
- Backend pytest: 160 passed
- compileall: passed
- Viewer: 19/19 structural checks passed

## 한계
Poll Task SQL의 완전한 이동은 아직 아닙니다. Adapter boundary를 추출한 상태이며, legacy transactional SQL을 위임합니다.
