# 이슈 생성 보고서: Streamable HTTP 기반 MCP 클라이언트

## 요청 내용

**Original Request**: 프론트엔드(Next.js)에 MCP 클라이언트 기능 추가. Streamable HTTP 기반 MCP 프로토콜로 서버와 통신.

**핵심 의도**:
- Next.js 프론트엔드가 **진짜 MCP 클라이언트** 역할 수행
- 기존 HTTP 폴링이 아닌 **Streamable HTTP transport**로 MCP 서버와 통신
- MCP 서버의 `ui://dashboard/agent-status` 리소스를 프론트엔드에서 렌더링

**배경**:
1. MCP Apps 서버 구현 완료 (CHA-74~78), 현재 stdio transport
2. 프론트엔드에서 MCP UI 리소스를 렌더링하려면 MCP 클라이언트가 필요
3. **Streamable HTTP는 MCP 최신 표준** (2025.05부터 권장)
4. 브라우저에서 직접 MCP 서버에 연결 가능

**이전 보고서와의 차이**:
- 이전: HTTP 폴링 방식 (단순 REST API 호출)
- 이번: **Streamable HTTP MCP 프로토콜** (진짜 MCP 클라이언트)

---

## 기술 배경: Streamable HTTP Transport

### Streamable HTTP란?
- MCP 최신 표준 (2025.05부터 SSE 대신 권장)
- **단일 엔드포인트** (`/mcp/message`)로 양방향 통신
- 브라우저에서 fetch API로 요청, 응답은 스트리밍
- Session ID로 재연결 지원
- 참고: https://modelcontextprotocol.io/specification/2025-03-26/basic/transports

### 기존 방식 vs Streamable HTTP

| 항목 | HTTP 폴링 | Streamable HTTP |
|------|-----------|-----------------|
| 프로토콜 | REST API | MCP 프로토콜 |
| 엔드포인트 | 여러 개 (/state, /reset 등) | 단일 (/mcp/message) |
| 클라이언트 | 단순 fetch | MCP SDK Client |
| 확장성 | 제한적 | MCP 표준 호환 |
| 양방향 통신 | 불가 | 가능 |

---

## 대화 요약

- 이슈메이커에게 2회 질의
- 제안된 이슈: 5개
- 승인: 5개, 거절: 0개

---

## 승인된 이슈

| ID | 제목 | 우선순위 | 라벨 | 설명 |
|----|------|----------|------|------|
| 1 | Add Streamable HTTP transport endpoint to MCP server | High | Feature | 백엔드 MCP 서버에 `/mcp/message` 엔드포인트 추가 |
| 2 | Add MCP client library to frontend | High | Feature | @modelcontextprotocol/sdk 기반 MCP 클라이언트 구현 |
| 3 | Create MCPProvider React context for state management | High | Feature | MCP 클라이언트 상태 관리 React Context Provider |
| 4 | Implement AgentDashboard component with MCP UI resource rendering | Medium | Feature | MCP UI 리소스 렌더링 대시보드 컴포넌트 |
| 5 | Integrate AgentDashboard into channel chat page | Medium | Feature | 채널 채팅 페이지에 대시보드 통합 |

---

## 상세 이슈 내용

### Issue 1: Add Streamable HTTP transport endpoint to MCP server

**TYPE**: Feature
**PRIORITY**: High
**LABEL**: Feature

**설명**:
백엔드 MCP 서버에 Streamable HTTP transport 엔드포인트 추가.

**현재 상태**: stdio transport만 지원 (`mcp_server.run_stdio_async()`)

**구현 내용**:
- FastAPI 라우터에 `/mcp/message` POST 엔드포인트 추가
- MCP 프로토콜 메시지 처리 (initialize, resources/read, tools/call 등)
- Session ID 기반 연결 관리
- 스트리밍 응답 지원 (StreamingResponse)
- MCP 메시지 직렬화/역직렬화

**완료 조건**:
- `/mcp/message` 엔드포인트가 MCP 프로토콜 메시지를 처리함
- 기존 stdio transport와 동일한 결과 반환
- 단위 테스트 통과

---

### Issue 2: Add MCP client library to frontend

**TYPE**: Feature
**PRIORITY**: High
**LABEL**: Feature

**설명**:
Next.js 프론트엔드에 @modelcontextprotocol/sdk 기반 MCP 클라이언트 추가.

**구현 내용**:
- `@modelcontextprotocol/sdk` 패키지 설치
- `src/lib/mcp/client.ts` - MCP 클라이언트 클래스 구현
  - Streamable HTTP transport 설정
  - 연결/재연결 로직
  - 리소스 읽기, 도구 호출 메서드
- `src/lib/mcp/types.ts` - MCP 관련 타입 정의

**완료 조건**:
- MCP 클라이언트가 백엔드 `/mcp/message` 엔드포인트와 통신 가능
- initialize, resources/read, tools/call 메서드 동작
- Vitest 단위 테스트 통과

---

### Issue 3: Create MCPProvider React context for state management

**TYPE**: Feature
**PRIORITY**: High
**LABEL**: Feature

**설명**:
MCP 클라이언트 상태를 관리하는 React Context Provider 구현.

**구현 내용**:
- `src/contexts/MCPContext.tsx` - MCP Provider 컴포넌트
  - 연결 상태 관리 (connecting, connected, disconnected, error)
  - 자동 재연결 로직
  - 리소스/도구 캐싱
- `useMCP()` 훅 제공
- `Providers.tsx`에 MCPProvider 추가

**완료 조건**:
- `useMCP()` 훅으로 MCP 클라이언트 접근 가능
- 연결 상태 변경 시 UI 업데이트
- 테스트 통과

---

### Issue 4: Implement AgentDashboard component with MCP UI resource rendering

**TYPE**: Feature
**PRIORITY**: Medium
**LABEL**: Feature

**설명**:
MCP UI 리소스(`ui://dashboard/agent-status`)를 렌더링하는 대시보드 컴포넌트 구현.

**구현 내용**:
- `src/components/dashboard/AgentDashboard.tsx`
  - `useMCP()` 훅으로 MCP 클라이언트 사용
  - `ui://dashboard/agent-status` 리소스 읽기
  - HTML 콘텐츠를 iframe 또는 dangerouslySetInnerHTML로 렌더링
  - 실시간 상태 업데이트 (폴링 또는 재연결)
- `src/components/dashboard/index.ts` - export

**완료 조건**:
- 대시보드 UI가 MCP 리소스에서 가져온 HTML로 렌더링됨
- 에이전트 상태 변경 시 UI 업데이트
- 테스트 통과

---

### Issue 5: Integrate AgentDashboard into channel chat page

**TYPE**: Feature
**PRIORITY**: Medium
**LABEL**: Feature

**설명**:
채널 채팅 페이지에 AgentDashboard 컴포넌트 통합.

**구현 내용**:
- `src/app/channels/[id]/page.tsx` 수정
  - 채팅 영역 옆에 대시보드 패널 추가 (접을 수 있는 사이드 패널)
  - 채팅 시작 시 대시보드 자동 표시
  - 반응형 레이아웃 (모바일에서는 탭으로 전환)

**완료 조건**:
- 채팅 중 에이전트 실행 상태가 실시간으로 표시됨
- 대시보드 패널 토글 가능
- 반응형 동작 확인

---

## 거절된 이슈

| 제목 | 거절 사유 |
|------|----------|
| (없음) | - |

---

## 1차 검수 결과

### 검수 기준 평가

| 기준 | Issue 1 | Issue 2 | Issue 3 | Issue 4 | Issue 5 |
|------|---------|---------|---------|---------|---------|
| 필요성 | O (필수) | O (필수) | O (필수) | O (필수) | O (필수) |
| 강제성 | X | X | X | X | X |
| 중복 | X | X | X | X | X |
| 명확성 | O | O | O | O | O |
| 범위 | 적절 | 적절 | 적절 | 적절 | 적절 |

### 검수 판단

1. **Issue 1 (Streamable HTTP endpoint)**: 백엔드가 Streamable HTTP를 지원해야 프론트엔드 MCP 클라이언트가 연결 가능. **필수**.

2. **Issue 2 (MCP client library)**: MCP SDK 기반 클라이언트 구현으로, 단순 HTTP 폴링 대신 **진짜 MCP 프로토콜** 통신. **필수**.

3. **Issue 3 (MCPProvider)**: React에서 MCP 상태 관리를 위한 Context Provider. **필수**.

4. **Issue 4 (AgentDashboard)**: UI 리소스 렌더링이 원래 요청의 핵심 목표. **필수**.

5. **Issue 5 (Channel page integration)**: "채팅과 대시보드가 같은 화면에서 동작"이라는 최종 요구사항 구현. **필수**.

---

## 의존성 그래프 (권장)

```
[Streamable HTTP MCP 클라이언트 - 순차 의존성]

Issue 1 (백엔드 Streamable HTTP 엔드포인트)
    │
    ▼
Issue 2 (프론트엔드 MCP 클라이언트)
    │
    ▼
Issue 3 (MCPProvider React Context)
    │
    ▼
Issue 4 (AgentDashboard 컴포넌트)
    │
    ▼
Issue 5 (채널 페이지 통합)
```

**권장 실행 순서**:
| 단계 | 이슈 | 설명 |
|------|------|------|
| 1 | Issue 1 | 백엔드 Streamable HTTP 지원 |
| 2 | Issue 2 | 프론트엔드 MCP 클라이언트 |
| 3 | Issue 3 | React Context Provider |
| 4 | Issue 4 | 대시보드 컴포넌트 |
| 5 | Issue 5 | 최종 통합 |

---

## 권장 사항

위 5개 이슈로 진행을 권장합니다.

**이유**:
1. **모든 이슈가 필수**: 각 이슈는 최종 목표(프론트엔드에서 MCP UI 렌더링) 달성에 필요한 단계
2. **명확한 순차 의존성**: Issue 1 없이 Issue 2 불가, Issue 2 없이 Issue 3 불가 등
3. **적절한 범위**: 각 이슈가 독립적으로 테스트 가능한 단위
4. **강제로 짜낸 이슈 없음**: 모든 이슈가 핵심 기능 구현에 직접 필요
5. **MCP 표준 준수**: Streamable HTTP는 MCP 최신 표준으로, 향후 확장성 확보

---

## 검수 완료

- **1차 검수**: 이슈팀장 완료 (5개 이슈 모두 승인)
- **2차 검수**: 오케스트레이터 대기
- **Linear 등록**: 2차 검수 승인 후 진행

---

*작성자: 이슈팀장*
*작성일: 2026-01-23*
