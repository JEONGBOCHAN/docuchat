# 이슈 생성 보고서: Gemini 3 Flash 업그레이드

## 요청 내용

오케스트레이터 요청: Gemini 2.5 Flash에서 Gemini 3 Flash로 업그레이드

**배경:**
- Gemini 3 Flash는 3배 향상된 성능 (reasoning, coding, multimodal)
- 가격 인상은 20-67%로 합리적
- 모델 이름이 하드코딩되어 있음: `model: str = 'gemini-2.5-flash'`

## 사전 조사 결과

### API 호환성 분석

| 항목 | Gemini 2.5 Flash | Gemini 3 Flash |
|------|------------------|----------------|
| Model ID | `gemini-2.5-flash` | `gemini-3-flash-preview` |
| Input Token Limit | 1,048,576 | 1,048,576 (동일) |
| Output Token Limit | 65,536 | 65,536 (동일) |
| File Search API | ✅ 지원 | ✅ 지원 |
| Thinking 파라미터 | thinking_budget | thinking_level |

### 영향받는 코드

`src/services/gemini.py` - 14개 함수의 기본 파라미터:
- `search_and_answer_stream` (line 255)
- `search_and_answer` (line 341)
- `multi_store_search` (line 413)
- `multi_store_search_stream` (line 497)
- `generate_faq` (line 596)
- `search_with_citations` (line 797)
- `search_with_citations_stream` (line 856)
- `summarize_channel` (line 928)
- `summarize_document` (line 983)
- `generate_timeline` (line 1043)
- `generate_briefing` (line 1128)
- `generate_study_guide` (line 1237)
- `generate_quiz` (line 1356)
- `generate_podcast_script` (line 1487)

### Breaking Changes 분석

현재 프로젝트에 영향 없음:
- ❌ Image segmentation (사용하지 않음)
- ❌ Maps grounding (사용하지 않음)
- ❌ Computer use tools (사용하지 않음)

## 대화 요약

- 이슈메이커에게 1회 질의
- 제안된 이슈: 1개
- 승인: 1개, 거절: 0개

## 승인된 이슈

| ID | 제목 | 우선순위 | 라벨 | 설명 |
|----|------|----------|------|------|
| 1 | Upgrade Gemini model from 2.5 Flash to 3 Flash | High | Improvement | 모델 업그레이드 및 선택적 thinking_level 지원 |

### 상세 설명

**변경 사항:**
1. 모델 파라미터 변경: `gemini-2.5-flash` → `gemini-3-flash-preview`
2. (선택) 모델 이름을 상수로 추출하여 향후 업데이트 용이하게
3. (선택) `thinking_level` 파라미터 지원 추가

**테스트 요구사항:**
- 기존 Gemini 통합 테스트 실행
- 실제 Gemini 3 Flash API로 E2E 테스트
- File Search API 정상 작동 확인

## 거절된 이슈

없음

## 1차 검수 근거

- 단일 이슈로 통합한 것이 적절함 (14개 함수가 모두 같은 파일에 있고, 같은 패턴의 변경)
- "모델명 변경", "테스트", "thinking_level 추가"를 별도 이슈로 분리하는 것은 인위적 분할
- 개발자가 한 번에 처리하는 것이 효율적

## 권장 사항

위 1개 이슈로 진행을 권장합니다.

---

**참고 자료:**
- [Gemini 3 Developer Guide](https://ai.google.dev/gemini-api/docs/gemini-3)
- [Gemini Models Documentation](https://ai.google.dev/gemini-api/docs/models)
