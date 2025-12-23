# Docuchat

<div align="center">

![Python](https://img.shields.io/badge/Python-3.11+-green.svg)
![Next.js](https://img.shields.io/badge/Next.js-15-black.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

![LangGraph](https://img.shields.io/badge/LangGraph-Agentic-purple.svg)
![Gemini](https://img.shields.io/badge/Gemini-Powered-blue.svg)
![Azure](https://img.shields.io/badge/Azure-Deployed-0078D4.svg)

**Document Analysis Tool powered by RAG + AI Agent**

[Features](#features) • [Tech Stack](#tech-stack) • [Architecture](#architecture) • [Quick Start](#quick-start)

[한국어](README_KR.md)

</div>

---

## Overview

**Docuchat** is an intelligent document assistant that lets you upload documents, ask questions, and get accurate answers grounded in your content. Built with Retrieval-Augmented Generation (RAG) and LangGraph-powered agentic workflows.

**Try it now**: [Live Demo](https://docuchat-frontend-staging.wonderfulsky-2a5ed695.eastus.azurecontainerapps.io)

```
┌─────────────────────────────────────────────────────────────┐
│                        Docuchat                              │
│                                                              │
│   Documents ──▶ RAG Agent ──▶ Analysis ──▶ Answers          │
│                     │                                        │
│              ┌──────┴──────┐                                 │
│              ▼             ▼                                 │
│        Gemini API    File Search                             │
│        (LLM)         (RAG)                                   │
└─────────────────────────────────────────────────────────────┘
```

## Features

### Core Capabilities

- **Document Upload** - Upload PDFs, text files, markdown, and more
- **URL Import** - Crawl web pages and import content as documents
- **AI Chat** - Ask questions and get answers grounded in your documents
- **Source Citations** - Every answer includes references to source documents
- **Channel Organization** - Organize documents into separate channels

### AI Capabilities

- **RAG (Retrieval-Augmented Generation)** - Answers grounded in actual documents
- **Agentic Workflows** - LangGraph-powered ReAct loop for complex reasoning
- **Gemini File Search** - Powered by Google's Gemini File Search API
- **Multi-turn Conversations** - Context-aware chat with conversation history

### Additional Features

- **Document Summaries** - Generate concise or detailed summaries
- **Audio Overview** - Convert documents to podcast-style audio (TTS)
- **Study Guide** - Auto-generate study materials from documents
- **Dark Mode** - Full dark mode support

## Tech Stack

### Backend
| Technology | Purpose |
|------------|---------|
| **FastAPI** | REST API server |
| **LangGraph** | Agentic workflow orchestration |
| **Gemini Flash** | LLM for generation |
| **Gemini File Search API** | Document retrieval (RAG) |
| **SQLite + SQLAlchemy** | Local metadata storage |
| **APScheduler** | Background job scheduling |

### Frontend
| Technology | Purpose |
|------------|---------|
| **Next.js 15** | React framework |
| **TypeScript** | Type-safe development |
| **Tailwind CSS** | Styling |
| **React Query** | Server state management |

### Infrastructure
| Technology | Purpose |
|------------|---------|
| **Docker** | Containerization |
| **Azure Container Apps** | Cloud deployment |
| **GitHub Actions** | CI/CD pipeline |

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Interface                          │
│                      (Next.js Frontend)                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI Backend                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │  Channels   │  │  Documents  │  │    Chat     │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              LangGraph Agentic Workflow (ReAct Loop)            │
│                                                                 │
│    ┌─────────┐      ┌─────────┐      ┌─────────┐               │
│    │  THINK  │ ──▶  │   ACT   │ ──▶  │ OBSERVE │               │
│    │         │      │         │      │         │               │
│    │ Decide  │      │ Execute │      │ Record  │               │
│    │ action  │      │  tool   │      │ result  │               │
│    └─────────┘      └─────────┘      └────┬────┘               │
│         ▲                                 │                     │
│         │         ┌──────────────┐        │                     │
│         └─────────│   Continue?  │◀───────┘                     │
│                   │  (max 3x)    │                              │
│                   └──────┬───────┘                              │
│                          │ Done                                 │
│                          ▼                                      │
│                   ┌─────────────┐                               │
│                   │   FINISH    │                               │
│                   │ Final answer│                               │
│                   └─────────────┘                               │
│                                                                 │
│    Tools: [search_documents] [finish]                           │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
┌─────────────────────────┐     ┌─────────────────────────┐
│   Gemini File Search    │     │     SQLite Database     │
│  (Document Storage)     │     │   (Metadata & History)  │
└─────────────────────────┘     └─────────────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker (optional)
- Google AI API Key ([Get one here](https://aistudio.google.com/apikey))

### Option 1: Docker (Recommended)

```bash
# Clone the repository
git clone https://github.com/JEONGBOCHAN/docuchat.git
cd docuchat

# Copy environment file
cp .env.docker.example .env.docker

# Add your Gemini API key to .env.docker
# GEMINI_API_KEY=your_api_key_here

# Start with Docker Compose
docker compose up -d

# Access the app
# Frontend: http://localhost:3000
# Backend:  http://localhost:8000
```

### Option 2: Local Development

```bash
# Clone the repository
git clone https://github.com/JEONGBOCHAN/docuchat.git
cd docuchat

# Backend setup
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Add your GEMINI_API_KEY to .env
uvicorn src.main:app --reload

# Frontend setup (new terminal)
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

## API Documentation

Once running, access the interactive API docs:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/channels` | GET, POST | List/create channels |
| `/api/v1/documents` | GET, POST | List/upload documents |
| `/api/v1/chat` | POST | Send chat message |
| `/api/v1/notes/summary` | POST | Generate document summary |

## Project Structure

```
docuchat/
├── src/                    # Backend source code
│   ├── api/v1/            # API routes
│   ├── core/              # Configuration
│   ├── models/            # Pydantic models
│   ├── services/          # Business logic
│   └── workflows/         # LangGraph workflows
├── frontend/              # Next.js frontend
│   ├── src/app/          # App router pages
│   ├── src/components/   # React components
│   └── src/lib/          # Utilities & API client
├── tests/                 # Test suites
├── docs/                  # Documentation
└── docker-compose.yml     # Docker configuration
```

## Documentation

Detailed documentation is available in the [`docs/`](./docs) folder:

- [API Specification](./docs/api-spec.md) - Detailed API documentation
- [Deployment Guide](./docs/deployment.md) - Azure deployment instructions
- [Azure ACR Setup](./docs/azure-acr-setup.md) - Container Registry setup
- [Azure Container Apps](./docs/azure-container-apps-setup.md) - Container Apps deployment

## Environment Variables

### Backend (.env)
```env
GEMINI_API_KEY=your_gemini_api_key
DATABASE_URL=sqlite:///./data/docuchat.db
CORS_ORIGINS=["http://localhost:3000"]
```

### Frontend (.env.local)
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

MIT License - see [LICENSE](LICENSE) for details.

---

<div align="center">

**Built with LangGraph and Gemini**

[Report Bug](https://github.com/JEONGBOCHAN/docuchat/issues) • [Request Feature](https://github.com/JEONGBOCHAN/docuchat/issues)

</div>
