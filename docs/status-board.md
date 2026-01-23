# Status Board

## 이 문서의 목적

1. **상태 공유**: 모든 역할(오케스트레이터, 팀장, 실무자)이 현재 진행 상황을 한눈에 파악
2. **컨텍스트 보존**: 하위 Claude가 "왜 이 작업을 하는지" 원래 의도를 잃지 않도록 함

> 사무실 화이트보드처럼, 누구나 보고 / 누구나 업데이트

## 갱신 규칙

- **Linear 작업 후 즉시 이 문서도 갱신** (Linear → Status Board 순서)
- 이슈 상태 변경, 담당자 배정, 완료 처리 등 모든 Linear 작업 후 반영
- 결정 사항은 결정자가 직접 기록

---

## 현재 미션

> **원래 요청**: "MCP Apps 대시보드 구현. LangGraph 1.0 업그레이드 + 미들웨어 선행. 로컬 컨테이너 테스트 후 Azure 배포. 에이전트 V2 구조는 이번 스코프 아님."

**핵심 의도**:
- MCP Apps 대시보드로 에이전트 실행 상태 실시간 시각화
- 선행 작업: LangGraph 1.0 업그레이드, 미들웨어 추가
- 로컬 컨테이너 테스트 → Azure 배포

**개발 순서**:
1. LangGraph 1.0 업그레이드
2. 미들웨어 추가 (상태 발행)
3. MCP Apps (대시보드 UI)
4. 로컬 컨테이너 테스트
5. Azure 배포

**스코프 아닌 것**: 에이전트 V2 구조 (Retrieve → Rerank → ... → Revise)

**이슈 타입**: Feature

---

## 이슈 현황

| ID | 제목 | 상태 | 담당 | 라벨 | 우선순위 |
|----|------|------|------|------|----------|
| CHA-74 | Migrate from LangGraph StateGraph to LangChain create_agent pattern | ✅ Done | - | Feature | High |
| CHA-75 | Add state publishing middleware using LangChain 1.0 | ✅ Done | - | Feature | High |
| CHA-76 | Implement MCP Apps server with dashboard UI | ✅ Done | - | Feature | High |
| CHA-77 | Local container integration testing for MCP Apps | ✅ Done | - | Feature | Medium |
| CHA-78 | Azure deployment for MCP Apps dashboard | ✅ Done | - | Feature | Medium |

**상태 범례**: ⏳ Backlog | 🔄 In Progress | ✅ Done | ❌ Failed | 🚫 Blocked

---

## 의존성 그래프

**상태**: ✅ 승인됨

```
[MCP Apps Dashboard - 순차 의존성]
CHA-74 (LangChain 1.0 migration)
    │
    ▼
CHA-75 (State publishing middleware)
    │
    ▼
CHA-76 (MCP Apps server + dashboard UI)
    │
    ▼
CHA-77 (Local container testing)
    │
    ▼
CHA-78 (Azure deployment)
```

**실행 계획**:
| 단계 | 이슈 | 실행 방식 | 설명 |
|------|------|----------|------|
| 1 | CHA-74 | 단독 | LangChain 1.0 create_agent 마이그레이션 |
| 2 | CHA-75 | 단독 | 상태 발행 미들웨어 구현 |
| 3 | CHA-76 | 단독 | MCP Apps 서버 + 대시보드 UI |
| 4 | CHA-77 | 단독 | 로컬 컨테이너 통합 테스트 |
| 5 | CHA-78 | 단독 | Azure 배포 |

> ※ 대화는 `docs/messages/`에서 진행 → 승인 후 여기에 반영

---

## 블로커 & 질문

### 블로커
- (없음)

### 미해결 질문
- (없음)

---

## 결정 로그

| 시간 | 결정자 | 내용 |
|------|--------|------|
| 2026-01-23 | 오케스트레이터 | 2차 검수 승인 - MCP Apps 대시보드 오케스트레이션 사이클 완료 (CHA-74~78 모두 Done) |
| 2026-01-23 | 개발팀장 | CHA-77, CHA-78 완료 - 로컬 컨테이너 테스트 설정 및 Azure 배포 CI/CD 업데이트 |
| 2025-12-24 | 오케스트레이터 | CHA-74 완료 - 다크모드 구현, Playwright 검증, Azure 배포 (GitHub Actions #64) |
| 2025-12-23 | 오케스트레이터 | CHA-73 2차 검수 승인 - 오케스트레이션 사이클 완료, 푸시 완료 |
| 2025-12-23 | 개발팀장 | CHA-73 개발 완료 - 14개 함수 모델 업그레이드, 테스트 통과 |
| 2025-12-23 | 오케스트레이터 | CHA-71 2차 검수 승인 - 오케스트레이션 사이클 완료 |
| 2025-12-23 | 개발팀장 | CHA-71 개발 완료 - 1차 검수 통과 (Side Effects Analysis 포함) |
| 2025-12-21 17:55 | 오케스트레이터 | 오케스트레이션 사이클 완료 - 모든 이슈 Done, E2E 테스트 통과 |
| 2025-12-21 17:49 | 오케스트레이터 | 개발 결과 2차 검수 승인 |
| 2025-12-21 15:35 | 오케스트레이터 | 이슈 검토 완료 - CHA-65~70 유지, 추가/수정/삭제 없음 |

---

## 활성 인스턴스

| 역할 | 작업 | 시작 시간 |
|------|------|----------|
| (없음) | - | - |

---

## 변경된 파일

| 파일 | 이슈 | 변경 유형 |
|------|------|----------|
| docker-compose.yml | CHA-77 | 수정 (MCP 서버 서비스 추가) |
| .github/workflows/deploy.yml | CHA-78 | 수정 (MCP 테스트 단계 추가) |
| docs/results/result_CHA-77.txt | CHA-77 | 신규 |
| docs/results/result_CHA-78.txt | CHA-78 | 신규 |
| src/services/gemini.py | CHA-73 | 수정 |

---

## 테스트 상태

```
마지막 실행: 2026-01-23 (CHA-77, CHA-78)
MCP 서버 유닛 테스트: 69 passed
MCP 통합 테스트: 30 passed
총 MCP 관련 테스트: 99 passed
```

---

## 최근 업데이트

| 시간 | 내용 |
|------|------|
| 2026-01-23 | CHA-77, CHA-78 완료 - Docker Compose MCP 서비스 추가, CI/CD MCP 테스트 단계 추가 |
| 2026-01-23 | CHA-76 완료 - MCP Apps 서버 + 대시보드 UI 구현, 69개 테스트 통과 |
| 2026-01-23 | CHA-75 완료 - DashboardMiddleware 구현, 34개 테스트 통과 |
| 2026-01-23 | CHA-74 완료 - LangChain create_agent 패턴 마이그레이션, 17개 테스트 통과 |
| 2026-01-23 | MCP Apps 이슈 등록 완료 - CHA-74~78 (5개 이슈, 순차 의존성) |
| 2025-12-24 | CHA-74 완료 - 다크모드 구현 (next-themes + Tailwind v4 @custom-variant) |
| 2025-12-23 | CHA-73 완료 - Gemini 모델 업그레이드 (2.5 Flash → 3 Flash) |
| 2025-12-23 | CHA-71 완료 - 고아 리소스 버그 수정 (8가지 사이드이펙트 분석) |
| 2025-12-21 17:55 | 오케스트레이션 사이클 완료 - 프론트엔드 빌드 수정 포함 |
| 2025-12-21 17:49 | 모든 이슈 완료 (CHA-65~70) - 개발팀장 |
| 2025-12-21 17:41 | Step 3 완료 (CHA-70) |
| 2025-12-21 17:41 | Step 2 완료 (CHA-66, CHA-69) |
| 2025-12-21 17:28 | Step 1 완료 (CHA-65, CHA-67, CHA-68) |
| 2025-12-21 17:09 | 개발 시작 - 개발팀장 |
| 2025-12-21 15:35 | 이슈 검토 완료 - 기존 이슈 유지 결정 |
| 2025-12-21 | Status Board 초안 생성 |
