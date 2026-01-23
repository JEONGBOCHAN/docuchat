# 이슈 생성 보고서: MCP Apps 대시보드 구현

## 요청 내용

MCP Apps 대시보드 구현. LangGraph 1.0 업그레이드 + 미들웨어 선행. 로컬 컨테이너 테스트 후 Azure 배포. 에이전트 V2 구조는 이번 스코프 아님.

**핵심 의도**: MCP Apps 프로토콜(2025.11)로 에이전트 실행 상태 실시간 시각화

**개발 순서**:
1. LangGraph 1.0 업그레이드 (선행) → **이미 완료됨** (`langgraph>=1.0.0` in requirements.txt)
2. 미들웨어 추가 (상태 발행)
3. MCP Apps 서버 + UI
4. 로컬 컨테이너 테스트
5. Azure 배포

**스코프 아닌 것**: 에이전트 V2 구조 (Retrieve → Rerank → ... → Revise)

---

## 대화 요약

- 이슈메이커에게 1회 질의
- 제안된 이슈: 6개
- 승인: 4개 (3개 통합으로 실제 4개)
- 거절: 0개
- 통합: 3개 → 1개

---

## 승인된 이슈

| # | 제목 | 우선순위 | 라벨 | 설명 |
|---|------|----------|------|------|
| 1 | Add state publishing middleware for agent execution | High | Feature | LangGraph 워크플로우에 상태 발행 미들웨어 추가. think/act/observe 노드 실행 시 상태 이벤트 발행 |
| 2 | Implement MCP Apps server with dashboard UI | High | Feature | MCP Server 구조 + Tools + UI Resources + HTML 대시보드 통합 구현 **(원래 #2, #3, #4 통합)** |
| 3 | Local container testing for MCP Apps integration | Medium | Feature | Docker Compose로 MCP Server 실행, Claude Desktop 연동 검증 |
| 4 | Deploy MCP Apps to Azure Container Apps | Medium | Feature | Azure Container Apps 배포, 환경변수 설정, 헬스체크 |

---

## 통합된 이슈 (#2)

원래 이슈메이커가 3개로 나눈 것을 1개로 통합:

| 원래 이슈 | 통합 사유 |
|-----------|-----------|
| #2 MCP Server 기본 구조 | 함께 구현해야 테스트 가능 |
| #3 MCP Tools + UI Resources | 서버와 분리 불가 |
| #4 대시보드 HTML 템플릿 | UI 리소스의 일부 |

**통합 이슈 상세**:
```
Title: Implement MCP Apps server with dashboard UI
Description:
MCP Apps 서버 전체를 구현합니다:
1. 폴더 구조: src/mcp_server/
   - server.py: MCP Server 메인
   - tools.py: MCP Tools 정의 (get_agent_status, run_rag_query)
   - state.py: 상태 관리 (state_store)
   - templates/dashboard.html: 대시보드 HTML

2. UI 리소스:
   - ui://dashboard/agent-status
   - 도구 메타데이터에서 _meta.ui/resourceUri로 참조

3. 대시보드 기능:
   - Status indicator (idle/running/complete/error)
   - Pipeline 노드 시각화 (think → act → observe)
   - 현재 노드, 스텝 카운트, 쿼리 정보 표시
   - MCP postMessage로 상태 수신

Priority: High
Label: Feature
```

---

## 거절된 이슈

| 제목 | 거절 사유 |
|------|----------|
| (없음) | - |

---

## 의존성 그래프 (권장)

```
#1 미들웨어 ──▶ #2 MCP Apps 서버 ──▶ #3 로컬 테스트 ──▶ #4 Azure 배포
   (선행)           (핵심)              (검증)             (최종)
```

**실행 계획**:
| 단계 | 이슈 | 실행 방식 |
|------|------|----------|
| 1 | #1 (미들웨어) | 단독 |
| 2 | #2 (MCP Apps 서버) | 단독 (#1 완료 후) |
| 3 | #3 (로컬 테스트) | 단독 (#2 완료 후) |
| 4 | #4 (Azure 배포) | 단독 (#3 완료 후) |

> 순차 실행 필요 - 각 단계가 이전 단계에 의존

---

## 참고 사항

### LangGraph 1.0 업그레이드 불필요

이슈메이커가 확인한 결과:
- `requirements.txt`에 `langgraph>=1.0.0` 이미 명시
- `src/workflows/rag.py`가 LangGraph 기반으로 동작 중
- 별도 업그레이드 이슈 불필요

### 구현 참고 문서

- `docs/mcp-apps-dashboard-implementation.md`: Phase 1 구현 상세
- `docs/agent-pattern-analysis.md`: 미들웨어 훅 매핑

---

## 권장 사항

위 4개 이슈로 진행을 권장합니다.

- 총 4개 이슈 (6개 → 3개 통합 → 4개)
- 순차 실행 (의존성 체인)
- Phase 1 범위 내 (에이전트 V2 미포함)

---

**작성자**: 이슈팀장
**작성일**: 2025-01-23
