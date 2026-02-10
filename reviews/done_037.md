# Done 037

완료일: 2026-02-10
대상: review_037 — 모듈 경계 누수 제거 + 구성 루트 정렬 + 깨진 테스트 복구

---

## 완료 요약

review_037의 DoD를 모두 충족했다.

1. `workspace/public.py`에서 `ChannelMetadata` ORM 재노출 제거
2. conversation repositories의 불필요 cross-module import 제거
3. `main.py`에서 `src.application.use_cases.exceptions` 직접 import 제거
4. 오디오 executor shutdown이 knowledge/public.py 경유로 정렬
5. 신규 가드 2종 추가 (public.py ORM 노출 금지 + modules→infrastructure import 정책)
6. `tests/architecture`: 45 passed
7. `tests/services`: 124 passed
8. `tests/infrastructure`: 214 passed
9. `tests/api/v1`: 302 passed
10. `tests/integration`: 41 passed, 1 skipped

---

## 커밋 이력

| 커밋 | 내용 |
|------|------|
| `d20af55` | public.py ORM 모델 노출 제거 + conversation 불필요 import 제거 + 가드 테스트 |
| `cfd2396` | main.py UpstreamError import 정렬 + audio shutdown knowledge 모듈 경유화 |
| `b79e849` | modules→infrastructure import 정책 가드 추가 |
| `fe150ff` | scheduler job 테스트 patch 경로 정렬 + Gemini adapter lazy-init 테스트 정렬 |

---

## Phase별 상세

### Phase A: 모듈 경계 누수 제거

- `src/modules/workspace/public.py`: `ChannelMetadata` ORM import 및 `__all__` 항목 제거
- `src/modules/conversation/infrastructure/persistence/repositories.py`: 미사용 `from src.modules.workspace.public import ChannelMetadata` 제거
- `tests/architecture/test_module_public_contracts.py` 신규 생성
  - `test_public_py_no_orm_model_imports`: public.py에서 persistence.models import 금지
  - `test_public_py_all_no_orm_names`: `__all__`에 ORM 모델명(DB/Model/Metadata) 금지

### Phase B: Composition Root 정렬

- `src/main.py`: `UpstreamError` import를 `src.shared.kernel.contracts.errors.use_case_errors`로 변경
- `src/modules/knowledge/public.py`: `shutdown_audio_executor` 재노출 추가
- `src/main.py`: audio shutdown 호출을 `src.modules.knowledge.public`로 변경

### Phase C: modules→infrastructure 의존 확산 차단

- `tests/architecture/test_modules_infrastructure_import_policy.py` 신규 생성
- 정책: `src/modules/*/infrastructure/di.py`만 `src.infrastructure.*` import 허용
- allowlist: workspace/knowledge/conversation/ops 4개 DI 파일

### Phase D: 깨진 테스트 정렬

- `tests/services/test_scheduler_jobs.py` (5건 수정)
  - patch 대상을 `src.modules.ops.infrastructure.scheduler.scheduler_jobs`로 변경
  - `TrashRepository` 클래스 patch → `create_trash_repository_port` factory patch
  - 채널 목록을 `mock_trash_repo.get_expired_trashed_channels()`로 제공
- Gemini adapter 테스트 5건 수정
  - `adapter._get_client()` 호출 추가하여 lazy-init 트리거 후 assert

### Phase E: 가드 검증

- 기존 가드(module_boundaries, layer_boundaries, legacy_freeze, api_v1_shim_style 등)와 충돌 없음 확인
- 신규 가드가 기존 규칙을 보강하는 방향으로 작동

---

## 사이드이펙트 분석

- DB 모델 변경: 없음
- Port DTO 필드 변경: 없음
- HTTP API contract 변경: 없음
- 기존 테스트 회귀: 없음
- `knowledge/public.py`에 `shutdown_audio_executor` 추가: 기존 호출 경로 유지, main.py만 변경

---

## 검증 결과

```
tests/architecture: 45 passed
tests/services: 124 passed
tests/infrastructure: 214 passed
tests/api/v1: 302 passed
tests/integration: 41 passed, 1 skipped
Total: 726 passed, 1 skipped
```
