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

> **원래 요청**: "프론트엔드(Next.js)에 MCP 클라이언트 기능 추가. Streamable HTTP 기반 MCP 프로토콜로 서버와 통신."

**핵심 의도**:
- Next.js 프론트엔드가 **진짜 MCP 클라이언트** 역할 수행
- 기존 HTTP 폴링이 아닌 **Streamable HTTP transport**로 MCP 서버와 통신
- MCP 서버의 `ui://dashboard/agent-status` 리소스를 프론트엔드에서 렌더링
- 채팅과 대시보드가 같은 화면에서 동작

**배경**:
- MCP Apps 서버는 구현 완료 (CHA-74~78)
- 하지만 MCP Apps UI를 렌더링할 클라이언트가 없음
- Claude Desktop은 MCP Apps UI 렌더링 미지원 (자체 에이전트 사용)
- **Streamable HTTP는 MCP 최신 표준** (2025.05부터 SSE 대신 권장)
- 브라우저에서 직접 MCP 서버에 연결 가능

**이슈 타입**: Feature

---

## 이슈 현황

### 완료된 이슈 (MCP Apps 대시보드)
| ID | 제목 | 상태 | 담당 | 라벨 | 우선순위 |
|----|------|------|------|------|----------|
| CHA-74 | Migrate from LangGraph StateGraph to LangChain create_agent pattern | ✅ Done | - | Feature | High |
| CHA-75 | Add state publishing middleware using LangChain 1.0 | ✅ Done | - | Feature | High |
| CHA-76 | Implement MCP Apps server with dashboard UI | ✅ Done | - | Feature | High |
| CHA-77 | Local container integration testing for MCP Apps | ✅ Done | - | Feature | Medium |
| CHA-78 | Azure deployment for MCP Apps dashboard | ✅ Done | - | Feature | Medium |

### 완료된 이슈 (Streamable HTTP MCP 클라이언트) - 오케스트레이션 사이클 완료
| ID | 제목 | 상태 | 담당 | 라벨 | 우선순위 |
|----|------|------|------|------|----------|
| CHA-79 | Add Streamable HTTP transport endpoint to MCP server | ✅ Done | 개발팀장 | Feature | High |
| CHA-80 | Add MCP client library to frontend | ✅ Done | 개발팀장 | Feature | High |
| CHA-81 | Create MCPProvider React context for state management | ✅ Done | 개발팀장 | Feature | High |
| CHA-82 | Implement AgentDashboard component with MCP UI resource rendering | ✅ Done | 개발팀장 | Feature | Medium |
| CHA-83 | Integrate AgentDashboard into channel chat page | ✅ Done | 개발팀장 | Feature | Medium |

**상태 범례**: ⏳ Backlog | 🔄 In Progress | ✅ Done | ❌ Failed | 🚫 Blocked

---

## 의존성 그래프

**상태**: ✅ 오케스트레이션 사이클 완료

```
[Streamable HTTP MCP 클라이언트 - 순차 의존성]

CHA-79 (백엔드 Streamable HTTP 엔드포인트)
    │   └─ src/api/v1/mcp.py (신규), router.py
    ▼
CHA-80 (프론트엔드 MCP 클라이언트)
    │   └─ frontend/src/lib/mcp/*.ts (신규)
    ▼
CHA-81 (MCPProvider React Context)
    │   └─ frontend/src/contexts/MCPContext.tsx (신규)
    ▼
CHA-82 (AgentDashboard 컴포넌트)
    │   └─ frontend/src/components/dashboard/*.tsx (신규)
    ▼
CHA-83 (채널 페이지 통합)
        └─ frontend/src/app/channels/[id]/page.tsx
```

**실행 계획**: 순차 실행 (5단계, 각 단독 실행)

| 단계 | 이슈 | 예상 소요 |
|------|------|----------|
| 1 | CHA-79 | ~5분 |
| 2 | CHA-80 | ~5분 |
| 3 | CHA-81 | ~5분 |
| 4 | CHA-82 | ~5분 |
| 5 | CHA-83 | ~5분 |

**병렬 실행 불가 사유**: 파일 충돌은 없으나, import 의존성으로 순차 실행 필수

**스케줄 문서**: `docs/schedules/schedule_CHA-79-83.md`

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
| 2026-01-23 | 오케스트레이터 | CHA-79~83 2차 검수 승인 - Streamable HTTP MCP 클라이언트 오케스트레이션 사이클 완료 |
| 2026-01-23 | 개발팀장 | CHA-79~83 개발 완료 - 57개 프론트엔드 테스트 통과, 1차 검수 완료, 2차 검수 대기 |
| 2026-01-23 | 오케스트레이터 | Streamable HTTP MCP 클라이언트 이슈 등록 (CHA-79~83) - 2차 검수 승인 |
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
| 오케스트레이터 | MCP 클라이언트 기능 추가 오케스트레이션 | 2026-01-23 |

---

## 변경된 파일

| 파일 | 이슈 | 변경 유형 |
|------|------|----------|
| src/api/v1/mcp.py | CHA-79 | 신규 (MCP Streamable HTTP endpoint) |
| src/api/v1/router.py | CHA-79 | 수정 (MCP router 등록) |
| tests/api/v1/test_mcp.py | CHA-79 | 신규 (20 tests) |
| frontend/src/lib/mcp/*.ts | CHA-80 | 신규 (MCP client library) |
| frontend/src/__tests__/mcp-client.test.ts | CHA-80 | 신규 (17 tests) |
| frontend/src/contexts/MCPContext.tsx | CHA-81 | 신규 (React Context) |
| frontend/src/__tests__/mcp-context.test.tsx | CHA-81 | 신규 (18 tests) |
| frontend/src/components/Providers.tsx | CHA-81 | 수정 (MCPProvider 추가) |
| frontend/src/components/dashboard/*.tsx | CHA-82 | 신규 (AgentDashboard) |
| frontend/src/__tests__/agent-dashboard.test.tsx | CHA-82 | 신규 (13 tests) |
| frontend/src/app/channels/[id]/page.tsx | CHA-83 | 수정 (대시보드 통합) |
| docs/results/result_CHA-79-83.txt | CHA-79~83 | 신규 |
| docker-compose.yml | CHA-77 | 수정 (MCP 서버 서비스 추가) |
| .github/workflows/deploy.yml | CHA-78 | 수정 (MCP 테스트 단계 추가) |
| docs/results/result_CHA-77.txt | CHA-77 | 신규 |
| docs/results/result_CHA-78.txt | CHA-78 | 신규 |
| src/services/gemini.py | CHA-73 | 수정 |

---

## 테스트 상태

```
마지막 실행: 2026-01-23 (CHA-79~83)
Frontend MCP 테스트: 57 passed
  - mcp-client.test.ts: 17 passed
  - mcp-context.test.tsx: 18 passed
  - agent-dashboard.test.tsx: 13 passed
  - dark-mode.test.tsx: 9 passed
Backend MCP 테스트: 20 passed (test_mcp.py)
TypeScript 컴파일: No errors
```

---

## 최근 업데이트

| 시간 | 내용 |
|------|------|
| 2026-01-23 | 오케스트레이터: CHA-79~83 2차 검수 승인, 오케스트레이션 사이클 완료 |
| 2026-01-23 | 개발팀장: CHA-79~83 개발 완료, 57개 프론트엔드 테스트 통과, 1차 검수 완료, 2차 검수 대기 |
| 2026-01-23 | 개발팀장: CHA-79~83 의존성 분석 완료, 스케줄 문서 작성, 오케스트레이터 승인 대기 |
| 2026-01-23 | Streamable HTTP MCP 클라이언트 이슈 등록 (CHA-79~83) - 개발팀장 분석 완료 |
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
