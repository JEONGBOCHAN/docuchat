# Done 036

완료일: 2026-02-10
대상: review_036 — 레거시 persistence 의존 정리 + shim 정책 고정

---

## 완료 요약

review_036의 DoD를 모두 충족했다.

1. `src/modules/*`에서 `src.infrastructure.persistence` import: **0건**
2. 신규 strict gate 테스트 green
3. 기존 strict gate 4종 계속 green
4. `tests/architecture`: 42 passed, `tests/api/v1`: 302 passed, `tests/integration`: 41 passed, 1 skipped
5. 레거시 persistence 파일은 호환 목적(재수출/shim)만 담당
6. audio `update_script` 시그니처 불일치 해소 완료

---

## 커밋 이력

| 커밋 | Linear | 내용 |
|------|--------|------|
| `db07cb6` | CHA-272 | workspace document summary cache module 내부화 + workspace/knowledge DI 전환 + audio update_script 계약 정렬 |
| `e16a054` | CHA-273 | conversation persistence repositories 신설 + conversation DI 전환 + legacy adapters shim화 |
| `a0cb10a` | CHA-274 | ops scheduler jobs legacy repository 의존 제거 |
| `9c4cab9` | CHA-275 | strict architecture gate 추가 + legacy persistence shim 정리 |

---

## Phase별 상세

### Phase A: Workspace/Knowledge 레거시 persistence 의존 제거

- `src/modules/workspace/infrastructure/persistence/document_summary_repository.py` 신규 생성
- workspace DI: `create_document_summary_cache_port`를 module-local path로 교체
- workspace DI: `create_audio_repository_port` 팩토리 추가, workspace public.py에 노출
- knowledge DI: `AudioRepositoryAdapter` import를 workspace public API로 교체
- `AudioRepositoryPort.update_script`에 `title: str | None = None` 파라미터 추가
- workspace repositories의 `update_script` 구현체도 `title` 지원 추가

### Phase B: Conversation persistence adapter 모듈 내부화

- `src/modules/conversation/infrastructure/persistence/repositories.py` 신규 생성
  - `ChatHistoryRepositoryAdapter`: 자체 SQLAlchemy 쿼리 구현 (legacy repo 위임 제거)
  - `ChatSessionRepositoryAdapter`: 자체 구현 (session timeout 로직 포함)
  - `ChatSessionMemoryRepositoryAdapter`: 자체 구현 (session PK 해석 포함)
- conversation DI: 3개 repository factory import를 module-local path로 교체
- `src/infrastructure/persistence/adapters.py`: 순수 re-export shim으로 전환
- workspace public.py에 `ChannelMetadata` ORM 모델 노출 (cross-module join용)

### Phase C: Ops scheduler legacy repository 의존 제거

- `scheduler_jobs.py`에서 `ChannelRepository` → `create_channel_repository_port`
- `scheduler_jobs.py`에서 `TrashRepository` → `create_trash_repository_port`
- `TrashRepositoryPort`에 `cleanup_specific_channels`, `cleanup_expired_notes` 메서드 추가
- `TrashRepositoryAdapter`에 해당 메서드 구현
- 반환 딕셔너리 키/로그 포맷 변경 없음

### Phase D: Strict architecture gate 추가

- `tests/architecture/test_modules_no_legacy_persistence_imports.py` 신규 생성
- AST 파싱으로 `src/modules/**/*.py`에서 `src.infrastructure.persistence` import 탐지
- 위반 시 파일명:라인번호와 함께 실패 메시지 출력

### Phase E: 레거시 persistence shim/freeze 정리

- `src/infrastructure/persistence/document_summary_repository.py`: 구현 제거, re-export only
- `src/infrastructure/persistence/adapters.py`: 모든 구현 제거, workspace/conversation re-export only
- 두 파일 모두 "compatibility shim" docstring 명시

---

## 사이드이펙트 분석

- DB 모델 변경: 없음
- Port DTO 필드 변경: 없음
- HTTP API contract 변경: 없음
- 기존 테스트 회귀: 없음 (385 passed, 1 skipped)
- `TrashRepositoryPort`에 2개 메서드 추가: 기존 추상 메서드/구현에 영향 없음 (모든 구현체 동시 업데이트)

---

## 검증 결과

```
tests/architecture: 42 passed
tests/api/v1: 302 passed
tests/integration: 41 passed, 1 skipped
Total: 385 passed, 1 skipped

src/modules → src.infrastructure.persistence imports: 0
src/modules → src.application imports: 0
```
