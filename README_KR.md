# Docuchat

**RAG + AI Agent 기반 문서 분석 도구**

문서를 업로드하고, 질문하고, 문서 내용에 기반한 정확한 답변을 받을 수 있는 지능형 문서 어시스턴트입니다. RAG(Retrieval-Augmented Generation)와 에이전틱 워크플로우로 구축되었습니다.

[![라이브 데모](https://img.shields.io/badge/라이브%20데모-Azure-blue)](https://chalssak-frontend-staging.graysmoke-543aab46.eastus.azurecontainerapps.io)
[![Python](https://img.shields.io/badge/Python-3.11+-green)](https://python.org)
[![Next.js](https://img.shields.io/badge/Next.js-15-black)](https://nextjs.org)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

## 라이브 데모

지금 바로 사용해보세요: **[https://chalssak-frontend-staging.graysmoke-543aab46.eastus.azurecontainerapps.io](https://chalssak-frontend-staging.graysmoke-543aab46.eastus.azurecontainerapps.io)**

## 주요 기능

### 핵심 기능
- **문서 업로드** - PDF, 텍스트 파일, 마크다운 등 다양한 형식 지원
- **URL 가져오기** - 웹 페이지를 크롤링하여 문서로 가져오기
- **AI 채팅** - 문서 내용에 기반한 질문과 답변
- **출처 인용** - 모든 답변에 소스 문서 참조 포함
- **채널 구성** - 문서를 별도의 채널로 구성

### AI 기능
- **RAG (Retrieval-Augmented Generation)** - 실제 문서에 기반한 답변 생성
- **에이전틱 워크플로우** - LangGraph 기반 복잡한 추론 워크플로우
- **Gemini File Search** - Google Gemini File Search API 활용
- **멀티턴 대화** - 대화 기록을 활용한 맥락 인식 채팅

### 추가 기능
- **문서 요약** - 간략하거나 상세한 요약 생성
- **오디오 오버뷰** - 문서를 팟캐스트 스타일 오디오로 변환 (TTS)
- **학습 가이드** - 문서에서 자동으로 학습 자료 생성
- **다크 모드** - 전체 다크 모드 지원

## 기술 스택

### 백엔드
| 기술 | 용도 |
|------|------|
| **FastAPI** | REST API 서버 |
| **LangGraph** | 에이전틱 워크플로우 오케스트레이션 |
| **Gemini 2.5 Flash** | 생성형 LLM |
| **Gemini File Search API** | 문서 검색 (RAG) |
| **SQLite + SQLAlchemy** | 로컬 메타데이터 저장 |
| **APScheduler** | 백그라운드 작업 스케줄링 |

### 프론트엔드
| 기술 | 용도 |
|------|------|
| **Next.js 15** | React 프레임워크 |
| **TypeScript** | 타입 안전 개발 |
| **Tailwind CSS** | 스타일링 |
| **React Query** | 서버 상태 관리 |

### 인프라
| 기술 | 용도 |
|------|------|
| **Docker** | 컨테이너화 |
| **Azure Container Apps** | 클라우드 배포 |
| **GitHub Actions** | CI/CD 파이프라인 |

## 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                         사용자 인터페이스                         │
│                      (Next.js 프론트엔드)                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI 백엔드                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │   채널      │  │    문서     │  │    채팅     │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   LangGraph 에이전틱 워크플로우                   │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐      │
│  │  입력   │ -> │  검색   │ -> │ 컨텍스트│ -> │  응답   │      │
│  │  처리   │    │  RAG    │    │  구성   │    │  생성   │      │
│  └─────────┘    └─────────┘    └─────────┘    └─────────┘      │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
┌─────────────────────────┐     ┌─────────────────────────┐
│   Gemini File Search    │     │     SQLite 데이터베이스   │
│     (문서 저장소)        │     │   (메타데이터 & 히스토리) │
└─────────────────────────┘     └─────────────────────────┘
```

## 빠른 시작

### 사전 요구사항
- Python 3.11+
- Node.js 18+
- Docker (선택사항)
- Google AI API 키 ([여기서 발급](https://aistudio.google.com/apikey))

### 옵션 1: Docker (권장)

```bash
# 저장소 클론
git clone https://github.com/JEONGBOCHAN/docuchat.git
cd docuchat

# 환경 파일 복사
cp .env.docker.example .env.docker

# .env.docker에 Gemini API 키 추가
# GEMINI_API_KEY=your_api_key_here

# Docker Compose로 시작
docker compose up -d

# 앱 접속
# 프론트엔드: http://localhost:3000
# 백엔드:    http://localhost:8000
```

### 옵션 2: 로컬 개발

```bash
# 저장소 클론
git clone https://github.com/JEONGBOCHAN/docuchat.git
cd docuchat

# 백엔드 설정
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# .env에 GEMINI_API_KEY 추가
uvicorn src.main:app --reload

# 프론트엔드 설정 (새 터미널)
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

## API 문서

실행 후 인터랙티브 API 문서 접속:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### 주요 엔드포인트

| 엔드포인트 | 메서드 | 설명 |
|----------|--------|------|
| `/api/v1/channels` | GET, POST | 채널 목록/생성 |
| `/api/v1/documents` | GET, POST | 문서 목록/업로드 |
| `/api/v1/chat` | POST | 채팅 메시지 전송 |
| `/api/v1/notes/summary` | POST | 문서 요약 생성 |

## 프로젝트 구조

```
docuchat/
├── src/                    # 백엔드 소스 코드
│   ├── api/v1/            # API 라우트
│   ├── core/              # 설정
│   ├── models/            # Pydantic 모델
│   ├── services/          # 비즈니스 로직
│   └── workflows/         # LangGraph 워크플로우
├── frontend/              # Next.js 프론트엔드
│   ├── src/app/          # App 라우터 페이지
│   ├── src/components/   # React 컴포넌트
│   └── src/lib/          # 유틸리티 & API 클라이언트
├── tests/                 # 테스트 스위트
├── docs/                  # 문서
└── docker-compose.yml     # Docker 설정
```

## 문서

자세한 문서는 [`docs/`](./docs) 폴더에서 확인할 수 있습니다:

- [아키텍처](./docs/architecture.md) - 시스템 설계 및 데이터 흐름
- [API 명세](./docs/api-spec.md) - 상세 API 문서
- [설정 가이드](./docs/setup.md) - 환경 설정 안내
- [개발 가이드](./docs/development.md) - 기여 가이드라인
- [배포 가이드](./docs/deployment.md) - Azure 배포 안내

## 환경 변수

### 백엔드 (.env)
```env
GEMINI_API_KEY=your_gemini_api_key
DATABASE_URL=sqlite:///./data/docuchat.db
CORS_ORIGINS=["http://localhost:3000"]
```

### 프론트엔드 (.env.local)
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## 기여하기

기여를 환영합니다! Pull Request를 자유롭게 제출해주세요.

1. 저장소 포크
2. 기능 브랜치 생성 (`git checkout -b feature/amazing-feature`)
3. 변경사항 커밋 (`git commit -m 'Add amazing feature'`)
4. 브랜치에 푸시 (`git push origin feature/amazing-feature`)
5. Pull Request 열기

## 라이선스

이 프로젝트는 MIT 라이선스 하에 있습니다 - 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하세요.

## 감사의 글

- [Google Gemini](https://ai.google.dev/) - AI/ML 기능
- [LangGraph](https://github.com/langchain-ai/langgraph) - 에이전틱 워크플로우 프레임워크
- [FastAPI](https://fastapi.tiangolo.com/) - 백엔드 프레임워크
- [Next.js](https://nextjs.org/) - 프론트엔드 프레임워크

---

**[English Version](./README.md)**
