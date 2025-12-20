# API 명세

## Base URL

```
http://localhost:8000/api/v1
```

## 인증

현재 버전에서는 인증 없음 (추후 구현)

---

## 채널 API

### 채널 생성

```
POST /channels
```

**Request Body:**
```json
{
  "name": "프로젝트 문서",
  "description": "프로젝트 관련 기술 문서 모음"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| name | string | O | 채널 이름 (1-100자) |
| description | string | X | 채널 설명 (최대 500자) |

**Response (201 Created):**
```json
{
  "id": "fileSearchStores/abc123",
  "name": "프로젝트 문서",
  "description": "프로젝트 관련 기술 문서 모음",
  "created_at": "2025-12-20T12:00:00Z",
  "file_count": 0
}
```

### 채널 목록 조회

```
GET /channels?limit=10&offset=0
```

**Query Parameters:**
| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|----------|------|------|--------|------|
| limit | integer | X | 전체 | 최대 반환 개수 (1-100) |
| offset | integer | X | 0 | 건너뛸 개수 |

**Response (200 OK):**
```json
{
  "channels": [
    {
      "id": "fileSearchStores/abc123",
      "name": "프로젝트 문서",
      "description": "프로젝트 관련 기술 문서 모음",
      "created_at": "2025-12-20T12:00:00Z",
      "file_count": 5
    }
  ],
  "total": 1
}
```

### 채널 상세 조회

```
GET /channels/{channel_id}
```

**Response (200 OK):**
```json
{
  "id": "fileSearchStores/abc123",
  "name": "프로젝트 문서",
  "description": "프로젝트 관련 기술 문서 모음",
  "created_at": "2025-12-20T12:00:00Z",
  "file_count": 5
}
```

### 채널 삭제

```
DELETE /channels/{channel_id}
```

**Response (204 No Content)**

---

## 문서 API

### 문서 업로드

```
POST /documents?channel_id={channel_id}
```

**Request:** `multipart/form-data`
| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| file | file | O | 업로드할 파일 |

**Response (202 Accepted):**
```json
{
  "id": "operations/upload-123",
  "filename": "api-spec.pdf",
  "status": "processing",
  "message": "Upload initiated"
}
```

### URL에서 문서 업로드

```
POST /documents/url?channel_id={channel_id}
```

**Request Body:**
```json
{
  "url": "https://example.com/article"
}
```

**Response (202 Accepted):**
```json
{
  "id": "operations/upload-456",
  "filename": "Article Title.md",
  "status": "processing",
  "message": "URL content uploaded"
}
```

### 문서 목록 조회

```
GET /documents?channel_id={channel_id}
```

**Response (200 OK):**
```json
{
  "documents": [
    {
      "id": "files/file-123",
      "filename": "api-spec.pdf",
      "file_size": 1048576,
      "content_type": "application/octet-stream",
      "status": "completed",
      "channel_id": "fileSearchStores/abc123",
      "created_at": "2025-12-20T12:00:00Z"
    }
  ],
  "total": 1
}
```

### 문서 업로드 상태 조회

```
GET /documents/{document_id}/status
```

**Response (200 OK):**
```json
{
  "id": "operations/upload-123",
  "done": true,
  "error": null
}
```

### 문서 삭제

```
DELETE /documents/{document_id}
```

**Response (204 No Content)**

---

## 채팅 API

### 질문하기

```
POST /chat?channel_id={channel_id}
```

**Request Body:**
```json
{
  "query": "결제 취소 API의 재시도 로직은 어떻게 구현하기로 했지?"
}
```

**Response (200 OK):**
```json
{
  "query": "결제 취소 API의 재시도 로직은 어떻게 구현하기로 했지?",
  "response": "2024-10-15 기술 리뷰 미팅 노트에 따르면, 결제 취소 API는 최대 3회 재시도하며...",
  "sources": [
    {
      "source": "기술리뷰_20241015.pdf",
      "page": null,
      "content": "재시도 로직은 exponential backoff를 사용하여..."
    }
  ],
  "created_at": "2025-12-20T12:00:00Z"
}
```

### 채팅 히스토리 조회

```
GET /chat/history?channel_id={channel_id}&limit=100
```

**Query Parameters:**
| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|----------|------|------|--------|------|
| channel_id | string | O | - | 채널 ID |
| limit | integer | X | 100 | 최대 메시지 수 (1-500) |

**Response (200 OK):**
```json
{
  "channel_id": "fileSearchStores/abc123",
  "messages": [
    {
      "role": "user",
      "content": "결제 취소 API의 재시도 로직은?",
      "sources": [],
      "created_at": "2025-12-20T12:00:00Z"
    },
    {
      "role": "assistant",
      "content": "2024-10-15 기술 리뷰 미팅 노트에 따르면...",
      "sources": [
        {
          "source": "기술리뷰_20241015.pdf",
          "page": null,
          "content": "재시도 로직은..."
        }
      ],
      "created_at": "2025-12-20T12:00:01Z"
    }
  ],
  "total": 2
}
```

### 채팅 히스토리 삭제

```
DELETE /chat/history?channel_id={channel_id}
```

**Response (204 No Content)**

---

## FAQ API

### FAQ 자동 생성

```
POST /channels/{channel_id}/generate-faq
```

**Request Body:**
```json
{
  "count": 5
}
```

| 필드 | 타입 | 필수 | 기본값 | 설명 |
|------|------|------|--------|------|
| count | integer | X | 5 | 생성할 FAQ 개수 (1-20) |

**Response (200 OK):**
```json
{
  "channel_id": "fileSearchStores/abc123",
  "items": [
    {
      "question": "프로젝트의 주요 목표는 무엇인가요?",
      "answer": "이 프로젝트의 주요 목표는..."
    },
    {
      "question": "어떤 기술 스택을 사용하나요?",
      "answer": "FastAPI, LangGraph, Gemini API를 사용합니다..."
    }
  ],
  "generated_at": "2025-12-20T12:00:00Z"
}
```

**에러 응답:**
- 400: 채널에 문서가 없음
- 404: 채널을 찾을 수 없음
- 500: FAQ 생성 실패

---

## 용량 API

### 채널 용량 조회

```
GET /capacity?channel_id={channel_id}
```

**Response (200 OK):**
```json
{
  "channel_id": "fileSearchStores/abc123",
  "file_count": 5,
  "max_files": 50,
  "file_usage_percent": 10.0,
  "size_bytes": 5242880,
  "size_mb": 5.0,
  "max_size_bytes": 104857600,
  "max_size_mb": 100.0,
  "size_usage_percent": 5.0,
  "can_upload": true,
  "remaining_files": 45,
  "remaining_mb": 95.0
}
```

---

## 관리자 API

### 시스템 통계 조회

```
GET /admin/stats
```

**Response (200 OK):**
```json
{
  "channels": {
    "total": 10,
    "by_state": {
      "active": 8,
      "inactive": 2
    }
  },
  "storage": {
    "total_files": 50,
    "total_size_bytes": 52428800,
    "total_size_mb": 50.0,
    "avg_files_per_channel": 5.0,
    "avg_size_per_channel_mb": 5.0
  },
  "api": {
    "uptime_seconds": 3600,
    "total_calls": 1000,
    "gemini_calls": 200,
    "error_rate_percent": 0.5
  },
  "scheduler": {
    "running": true,
    "job_count": 1
  },
  "limits": {
    "max_files_per_channel": 50,
    "max_channel_size_mb": 100
  }
}
```

### 채널별 상세 분석

```
GET /admin/channels
```

**Response (200 OK):**
```json
{
  "channels": [
    {
      "gemini_store_id": "fileSearchStores/abc123",
      "name": "프로젝트 문서",
      "created_at": "2025-12-20T12:00:00Z",
      "last_accessed_at": "2025-12-20T14:00:00Z",
      "file_count": 5,
      "size_mb": 5.0,
      "state": "active",
      "action": "none",
      "days_since_access": 0,
      "usage_percent": 5.0
    }
  ],
  "total": 1
}
```

### API 메트릭 조회

```
GET /admin/api-metrics
```

**Response (200 OK):**
```json
{
  "uptime_seconds": 3600,
  "started_at": "2025-12-20T10:00:00Z",
  "total_api_calls": 1000,
  "total_errors": 5,
  "error_rate_percent": 0.5,
  "avg_latency_ms": 150.0,
  "gemini_api_calls": 200,
  "top_endpoints": [
    {
      "endpoint": "POST /chat",
      "calls": 500,
      "errors": 2,
      "avg_latency_ms": 200.0
    }
  ]
}
```

### API 메트릭 리셋

```
POST /admin/api-metrics/reset
```

**Response (200 OK):**
```json
{
  "message": "API metrics have been reset"
}
```

---

## 스케줄러 API

### 스케줄러 상태 조회

```
GET /scheduler/status
```

**Response (200 OK):**
```json
{
  "running": true,
  "job_count": 1,
  "jobs": [
    {
      "id": "cleanup_inactive_channels",
      "name": "Cleanup Inactive Channels",
      "next_run": "2025-12-21T00:00:00Z",
      "trigger": "cron[hour='0', minute='0']"
    }
  ]
}
```

### 작업 실행 히스토리

```
GET /scheduler/history?limit=20
```

**Response (200 OK):**
```json
{
  "entries": [
    {
      "job_id": "cleanup_inactive_channels",
      "run_time": "2025-12-20T00:00:00Z",
      "status": "success",
      "error": null
    }
  ],
  "total": 1
}
```

### 작업 수동 실행

```
POST /scheduler/jobs/{job_id}/run
```

**Response (202 Accepted):**
```json
{
  "message": "Job cleanup_inactive_channels triggered successfully"
}
```

---

## 헬스체크

```
GET /health
```

**Response (200 OK):**
```json
{
  "status": "healthy"
}
```

---

## 에러 응답

### 형식

```json
{
  "detail": "채널을 찾을 수 없습니다: fileSearchStores/xxx"
}
```

### HTTP 상태 코드

| HTTP 상태 | 설명 |
|----------|------|
| 400 | 잘못된 요청 (파일 형식, 크기 등) |
| 404 | 채널/문서 없음 |
| 413 | 용량 초과 |
| 422 | 유효성 검사 실패 |
| 500 | 서버 내부 오류 |

---

## 지원 파일 형식

| 카테고리 | 확장자 |
|---------|--------|
| 문서 | .pdf, .docx, .pptx, .xlsx |
| 텍스트 | .txt, .md, .html |
| 데이터 | .json, .csv, .xml |
| 코드 | .py, .js, .java, .cpp |

## 제한사항

| 항목 | 제한 |
|------|------|
| 파일 크기 | 최대 100MB |
| 채널당 파일 수 | 최대 50개 (설정 가능) |
| 채널당 용량 | 최대 100MB (설정 가능) |
