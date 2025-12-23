# 개발 스케줄 문서: CHA-73

## 이슈 정보

| 항목 | 내용 |
|------|------|
| ID | CHA-73 |
| 제목 | Upgrade Gemini model from 2.5 Flash to 3 Flash |
| 라벨 | Feature |
| 의존성 | 없음 |

## 의존성 분석

### 이슈 목록

| ID | 제목 | 의존성 | 충돌 그룹 |
|----|------|--------|----------|
| CHA-73 | Upgrade Gemini model from 2.5 Flash to 3 Flash | 없음 | A (gemini.py) |

### 의존성 그래프

```
CHA-73 (단독 이슈)
   │
   └── 없음 (선행 작업 없음)
```

## 파일 충돌 분석

| 이슈 | 수정 예상 파일 | 충돌 그룹 |
|------|---------------|----------|
| CHA-73 | src/services/gemini.py | A |

→ 단일 이슈이므로 충돌 없음

## 작업 범위

### 수정 대상 (14개 함수)

| # | 함수명 | 라인 |
|---|--------|------|
| 1 | search_and_answer_stream | 255 |
| 2 | search_and_answer | 341 |
| 3 | multi_store_search | 413 |
| 4 | multi_store_search_stream | 497 |
| 5 | generate_faq | 596 |
| 6 | search_with_citations | 797 |
| 7 | search_with_citations_stream | 856 |
| 8 | summarize_channel | 928 |
| 9 | summarize_document | 984 |
| 10 | generate_timeline | 1043 |
| 11 | generate_briefing | 1129 |
| 12 | generate_study_guide | 1237 |
| 13 | generate_quiz | 1356 |
| 14 | generate_podcast_script | 1487 |

### 변경 내용

```python
# Before
model: str = "gemini-2.5-flash"

# After
model: str = "gemini-3-flash-preview"
```

## 실행 계획

| 단계 | 작업 | 실행 방식 |
|------|------|----------|
| 1 | CHA-73: 모델명 변경 (14개 함수) | 단독 |
| 2 | 테스트 실행 | pytest -v |

## 예상 소요 시간

- 1단계 (모델명 변경): ~2분
- 2단계 (테스트): ~3분
- 총 예상: ~5분

## 리스크

1. **API 호환성**: gemini-3-flash-preview 모델이 기존 API와 호환되지 않을 수 있음
   - 대응: 기존 테스트로 호환성 검증, 필요시 E2E 테스트 수행

2. **Preview 모델 불안정성**: preview 버전은 production에서 불안정할 수 있음
   - 대응: 테스트 결과 확인 후 진행

## 권장 사항

이 작업은 단순한 문자열 변경이므로 즉시 실행 가능합니다.
테스트 통과 확인 후 완료 처리하면 됩니다.
