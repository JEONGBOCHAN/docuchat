# 개발 스케줄 문서: Streamable HTTP MCP 클라이언트

## 개요

| 항목 | 내용 |
|------|------|
| 범위 | CHA-79 ~ CHA-83 (5개 이슈) |
| 목표 | Next.js 프론트엔드에 MCP 클라이언트 기능 추가 |
| 예상 소요 | 약 25분 (순차 실행) |

---

## 이슈 목록

| ID | 제목 | 우선순위 | 의존성 | 라벨 |
|----|------|----------|--------|------|
| CHA-79 | Add Streamable HTTP transport endpoint to MCP server | High | 없음 | Feature |
| CHA-80 | Add MCP client library to frontend | High | CHA-79 | Feature |
| CHA-81 | Create MCPProvider React context for state management | High | CHA-80 | Feature |
| CHA-82 | Implement AgentDashboard component with MCP UI resource rendering | Medium | CHA-81 | Feature |
| CHA-83 | Integrate AgentDashboard into channel chat page | Medium | CHA-82 | Feature |

---

## 의존성 그래프 (논리적 의존성)

```
[Streamable HTTP MCP 클라이언트 - 순차 의존성]

CHA-79 (백엔드: Streamable HTTP 엔드포인트)
    │
    │  MCP 프로토콜 메시지 처리 엔드포인트 제공
    │
    ▼
CHA-80 (프론트엔드: MCP 클라이언트 라이브러리)
    │
    │  @modelcontextprotocol/sdk 기반 클라이언트
    │
    ▼
CHA-81 (프론트엔드: MCPProvider Context)
    │
    │  React Context로 MCP 상태 관리
    │
    ▼
CHA-82 (프론트엔드: AgentDashboard 컴포넌트)
    │
    │  MCP UI 리소스 렌더링
    │
    ▼
CHA-83 (프론트엔드: 채널 페이지 통합)
    │
    └──▶ 완료
```

> **의존성 설명**:
> - CHA-80은 CHA-79의 `/mcp/message` 엔드포인트가 있어야 테스트 가능
> - CHA-81은 CHA-80의 MCP 클라이언트 클래스를 사용
> - CHA-82는 CHA-81의 `useMCP()` 훅을 사용
> - CHA-83은 CHA-82의 AgentDashboard 컴포넌트를 import

---

## 파일 충돌 분석

| 이슈 | 수정 예상 파일 | 충돌 그룹 |
|------|---------------|----------|
| CHA-79 | `src/api/v1/mcp.py` (신규), `src/api/v1/router.py` | A (백엔드) |
| CHA-80 | `frontend/src/lib/mcp/client.ts` (신규), `frontend/src/lib/mcp/types.ts` (신규), `frontend/package.json` | B (프론트엔드 lib) |
| CHA-81 | `frontend/src/contexts/MCPContext.tsx` (신규), `frontend/src/components/Providers.tsx` | C (프론트엔드 context) |
| CHA-82 | `frontend/src/components/dashboard/AgentDashboard.tsx` (신규), `frontend/src/components/dashboard/index.ts` (신규) | D (프론트엔드 dashboard) |
| CHA-83 | `frontend/src/app/channels/[id]/page.tsx` | E (프론트엔드 page) |

### 충돌 분석 결과

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  파일 충돌 없음 - 각 이슈가 서로 다른 파일을 수정               │
│                                                                 │
│  그러나 논리적 의존성 존재:                                     │
│  - CHA-80은 CHA-79 엔드포인트 필요 (E2E 테스트)                │
│  - CHA-81은 CHA-80 클라이언트 필요 (import)                    │
│  - CHA-82는 CHA-81 Context 필요 (useMCP hook)                  │
│  - CHA-83은 CHA-82 컴포넌트 필요 (import)                      │
│                                                                 │
│  ※ 파일 충돌은 없지만 import 의존성으로 인해 순차 실행 필수    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 병렬 실행 가능성 검토

| 조합 | 병렬 가능? | 이유 |
|------|-----------|------|
| CHA-79 + CHA-80 | **불가** | CHA-80은 CHA-79 엔드포인트로 테스트해야 함 |
| CHA-80 + CHA-81 | **불가** | CHA-81은 CHA-80 클라이언트를 import |
| CHA-81 + CHA-82 | **불가** | CHA-82는 CHA-81의 useMCP() 훅 사용 |
| CHA-82 + CHA-83 | **불가** | CHA-83은 CHA-82 컴포넌트를 import |

**결론**: 모든 이슈가 순차 의존성을 가지므로 **순차 실행 필수**

---

## 실행 계획

| 단계 | 이슈 | 실행 방식 | 예상 소요 | 주요 작업 |
|------|------|----------|----------|----------|
| 1 | CHA-79 | 단독 | ~5분 | FastAPI `/mcp/message` 엔드포인트, 세션 관리, 스트리밍 응답 |
| 2 | CHA-80 | 단독 | ~5분 | `@modelcontextprotocol/sdk` 설치, MCP 클라이언트 클래스 |
| 3 | CHA-81 | 단독 | ~5분 | MCPContext.tsx, useMCP() 훅, Providers.tsx 수정 |
| 4 | CHA-82 | 단독 | ~5분 | AgentDashboard 컴포넌트, UI 리소스 렌더링 |
| 5 | CHA-83 | 단독 | ~5분 | 채널 페이지에 대시보드 패널 추가, 반응형 레이아웃 |

---

## 각 이슈별 상세 작업 내용

### CHA-79: Add Streamable HTTP transport endpoint to MCP server

**백엔드 작업** (Python/FastAPI)

| 파일 | 변경 유형 | 내용 |
|------|----------|------|
| `src/api/v1/mcp.py` | 신규 | `/mcp/message` POST 엔드포인트 |
| `src/api/v1/router.py` | 수정 | MCP 라우터 등록 |

**구현 포인트**:
- MCP 프로토콜 메시지 파싱 (initialize, resources/read, tools/call)
- Session ID 기반 연결 관리
- StreamingResponse로 스트리밍 응답
- 기존 `mcp_server` 인스턴스와 연동

**참고 파일**:
- `src/mcp_server/server.py` - 기존 MCP 서버 인스턴스
- `src/api/v1/dashboard.py` - 유사한 API 패턴

---

### CHA-80: Add MCP client library to frontend

**프론트엔드 작업** (TypeScript/Next.js)

| 파일 | 변경 유형 | 내용 |
|------|----------|------|
| `frontend/package.json` | 수정 | `@modelcontextprotocol/sdk` 의존성 추가 |
| `frontend/src/lib/mcp/client.ts` | 신규 | MCP 클라이언트 클래스 |
| `frontend/src/lib/mcp/types.ts` | 신규 | MCP 관련 타입 정의 |
| `frontend/src/lib/mcp/index.ts` | 신규 | 모듈 export |

**구현 포인트**:
- Streamable HTTP transport 설정
- 연결/재연결 로직
- `initialize()`, `readResource()`, `callTool()` 메서드
- 환경변수로 MCP 서버 URL 설정

**참고 파일**:
- `frontend/src/lib/api/client.ts` - 기존 API 클라이언트 패턴

---

### CHA-81: Create MCPProvider React context for state management

**프론트엔드 작업** (TypeScript/React)

| 파일 | 변경 유형 | 내용 |
|------|----------|------|
| `frontend/src/contexts/MCPContext.tsx` | 신규 | MCP Provider + Context |
| `frontend/src/components/Providers.tsx` | 수정 | MCPProvider 추가 |

**구현 포인트**:
- 연결 상태 관리 (connecting, connected, disconnected, error)
- 자동 재연결 로직
- 리소스/도구 캐싱
- `useMCP()` 훅 export

**참고 파일**:
- `frontend/src/components/Providers.tsx` - 기존 Provider 구조

---

### CHA-82: Implement AgentDashboard component with MCP UI resource rendering

**프론트엔드 작업** (TypeScript/React)

| 파일 | 변경 유형 | 내용 |
|------|----------|------|
| `frontend/src/components/dashboard/AgentDashboard.tsx` | 신규 | 대시보드 컴포넌트 |
| `frontend/src/components/dashboard/index.ts` | 신규 | 모듈 export |

**구현 포인트**:
- `useMCP()` 훅으로 MCP 클라이언트 사용
- `ui://dashboard/agent-status` 리소스 읽기
- HTML 콘텐츠 렌더링 (iframe 또는 dangerouslySetInnerHTML)
- 실시간 상태 업데이트 (폴링)

**참고 파일**:
- `src/mcp_server/templates/dashboard.html` - 렌더링할 HTML 형식

---

### CHA-83: Integrate AgentDashboard into channel chat page

**프론트엔드 작업** (TypeScript/React)

| 파일 | 변경 유형 | 내용 |
|------|----------|------|
| `frontend/src/app/channels/[id]/page.tsx` | 수정 | AgentDashboard 통합 |

**구현 포인트**:
- 채팅 영역 옆에 대시보드 사이드 패널 추가
- 토글 버튼으로 패널 접기/펼치기
- 반응형 레이아웃 (모바일: 탭 전환)
- 채팅 시작 시 대시보드 자동 표시

**참고 파일**:
- `frontend/src/app/channels/[id]/page.tsx` - 현재 페이지 구조 (531줄)

---

## 테스트 전략

| 이슈 | 테스트 유형 | 테스트 범위 |
|------|-----------|-----------|
| CHA-79 | pytest 단위 테스트 | MCP 메시지 처리, 세션 관리 |
| CHA-80 | Vitest 단위 테스트 | MCP 클라이언트 메서드 |
| CHA-81 | Vitest + React Testing Library | Context 상태 변화, 훅 동작 |
| CHA-82 | Vitest + React Testing Library | 컴포넌트 렌더링, UI 리소스 표시 |
| CHA-83 | Vitest + 수동 테스트 | 레이아웃 통합, 반응형 동작 |

**E2E 테스트 (전체 통합)**:
- CHA-83 완료 후 전체 흐름 E2E 테스트
- 채팅 → MCP 클라이언트 → 백엔드 MCP 서버 → 대시보드 렌더링

---

## 예상 소요 시간

| 단계 | 이슈 | 예상 시간 |
|------|------|----------|
| Step 1 | CHA-79 | ~5분 |
| Step 2 | CHA-80 | ~5분 |
| Step 3 | CHA-81 | ~5분 |
| Step 4 | CHA-82 | ~5분 |
| Step 5 | CHA-83 | ~5분 |
| **총합** | | **~25분** |

---

## 위험 요소 및 대응

| 위험 | 가능성 | 영향 | 대응 방안 |
|------|-------|------|----------|
| MCP SDK 브라우저 호환성 | 중 | 높 | Streamable HTTP는 브라우저 fetch API 사용 가능, 필요시 polyfill |
| CORS 이슈 | 중 | 중 | FastAPI CORS 미들웨어 설정 확인/수정 |
| 세션 관리 복잡도 | 낮 | 중 | 단순한 in-memory 세션으로 시작, 필요시 확장 |
| HTML 렌더링 보안 | 낮 | 중 | 신뢰할 수 있는 MCP 서버 응답만 렌더링 (자체 서버) |

---

## 권장 사항

1. **순차 실행 필수**: 모든 이슈가 선형 의존성을 가지므로 병렬 실행 불가
2. **커밋 단위**: 각 이슈 완료 시 즉시 커밋
3. **테스트 우선**: 각 단계에서 테스트 통과 확인 후 다음 단계 진행
4. **E2E 테스트**: CHA-83 완료 후 전체 흐름 E2E 테스트 수행

---

## 체크리스트

- [x] 의존성 분석 완료
- [x] 파일 충돌 분석 완료
- [x] 실행 계획 수립 완료
- [ ] 오케스트레이터 승인 대기

---

**작성일**: 2026-01-23
**작성자**: 개발팀장
