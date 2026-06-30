# DocuQuery AI — Local Development Setup Guide

## Prerequisites

- **Docker** and **Docker Compose** (v2+)
- **Python 3.11+** (for local development without Docker)
- **Node.js 20+** (for frontend development)
- **OpenAI API Key** (for embedding and LLM features; optional for demo)

---

## Quick Start (Docker)

The fastest way to get everything running:

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/docuquery-ai.git
cd docuquery-ai

# 2. Copy environment variables
cp .env.example .env

# 3. Edit .env and add your OpenAI API key
# OPENAI_API_KEY=sk-your-key-here

# 4. Start all services
docker-compose up --build

# 5. Run database migrations
docker-compose exec backend alembic upgrade head

# 6. Seed demo data (choose one option):

# Option A — Real embeddings (requires OPENAI_API_KEY in .env):
docker-compose exec backend python -m scripts.seed

# Option B — Mock embeddings (no API key needed):
docker-compose exec backend python -m scripts.seed --mock-embeddings
```

The application will be available at:
- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

---

## Seed Script Options

The seed script (`backend/scripts/seed.py`) creates demo users and documents:

### Default Mode (Real Embeddings)
```bash
python -m scripts.seed
```
- Requires `OPENAI_API_KEY` to be set
- Generates real embeddings via OpenAI API
- Produces meaningful similarity search results
- Costs approximately $0.001 for the seed data

### Mock Mode (No API Key)
```bash
python -m scripts.seed --mock-embeddings
```
- No `OPENAI_API_KEY` required
- Generates random 1536-dimensional vectors
- All UI features work, but similarity search returns random results
- Perfect for UI demos, development, and testing

### What Gets Created

**Users:**
- `admin@docuquery.ai` / `password123` — Full admin access
- `manager@docuquery.ai` / `password123` — Manager-level access
- `employee@docuquery.ai` / `password123` — Employee-level access

**Documents (4 at each RBAC level):**
- "Company Overview 2024" — Public
- "Employee Onboarding Guide" — Internal
- "Engineering Promotion Criteria" — Confidential
- "Executive Compensation Policy" — Restricted

The script is **idempotent**: running it again will skip existing records.

---

## Running Without Docker (Development)

### 1. Start PostgreSQL with pgvector

```bash
# Using Docker for just the database
docker run -d \
  --name docuquery-pg \
  -e POSTGRES_DB=docuquery \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -p 5432:5432 \
  pgvector/pgvector:pg16
```

### 2. Start Redis

```bash
docker run -d \
  --name docuquery-redis \
  -p 6379:6379 \
  redis:7-alpine
```

### 3. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/docuquery
export REDIS_URL=redis://localhost:6379/0
export JWT_SECRET_KEY=dev-secret-key-change-in-production
export OPENAI_API_KEY=sk-your-key-here

# Run migrations
alembic upgrade head

# Seed demo data
python -m scripts.seed --mock-embeddings

# Start the server
uvicorn app.main:app --reload --port 8000
```

### 4. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start dev server (proxies /api to localhost:8000)
npm run dev
```

---

## Running Tests

```bash
cd backend

# Run all tests with coverage
pytest --cov=app --cov-report=term-missing -v

# Run specific test files
pytest tests/test_auth.py -v
pytest tests/test_rbac.py -v
pytest tests/test_prompt_guard.py -v

# Run with detailed output
pytest -v --tb=long
```

---

## Adding Test Documents

1. Log in as admin (`admin@docuquery.ai` / `password123`)
2. Navigate to the Documents page
3. Click "Upload Document"
4. Drag and drop or browse for a PDF or DOCX file
5. Enter a descriptive title
6. Select the access level (public, internal, confidential, restricted)
7. Click "Upload & Process"
8. Wait for processing to complete (status: pending → processing → completed)

---

## Frontend Development Notes

### Key Libraries
- **React Router v6** — Client-side routing with auth guards
- **Recharts** — Charts on the metrics dashboard
- **react-hot-toast** — Toast notifications for all mutating actions
- **lucide-react** — Consistent icon set

### Route Guards
The app uses three route guard components in `App.jsx`:
- `ProtectedRoute` — Redirects unauthenticated users to `/login`
- `AdminRoute` — Redirects non-admin users to `/chat`
- `PublicRoute` — Redirects authenticated users to `/chat`

### API Client
The API client (`src/api/client.js`) handles:
- JWT token storage in localStorage
- Automatic Bearer token attachment
- 401 response handling (auto-logout)
- FormData support for file uploads

---

## Docker Architecture

### Services
| Service | Image | Port | Health Check |
|---------|-------|------|-------------|
| db | pgvector/pgvector:pg16 | 5432 | pg_isready |
| redis | redis:7-alpine | 6379 | redis-cli ping |
| backend | Custom (Python 3.11 slim) | 8000 | curl /api/v1/health |
| frontend | Custom (Node build → Nginx) | 5173→80 | wget localhost:80 |

### Build Details
- **Backend**: Multi-stage build, non-root user, Python env optimizations
- **Frontend**: Multi-stage (Node 20 → Nginx Alpine), SPA routing, API proxy

---

## Troubleshooting

### Database connection errors
- Ensure PostgreSQL is running: `docker ps | grep docuquery-pg`
- Check the DATABASE_URL environment variable
- Verify pgvector extension: `docker exec docuquery-pg psql -U postgres -d docuquery -c "SELECT * FROM pg_extension WHERE extname = 'vector'"`

### Redis connection errors
- Ensure Redis is running: `docker ps | grep docuquery-redis`
- Test connection: `docker exec docuquery-redis redis-cli ping`

### Migration errors
- Check if the database exists: `docker exec docuquery-pg psql -U postgres -lqt | grep docuquery`
- Reset migrations: `alembic downgrade base && alembic upgrade head`

### OpenAI API errors
- Verify your API key is set correctly in `.env`
- Check your OpenAI account for billing/quota issues
- Use `--mock-embeddings` flag to bypass API calls during development
- The system uses `gpt-4o-mini` (cheapest option) to minimize costs

### Frontend build errors
- Clear node_modules: `rm -rf node_modules && npm install`
- Check Node.js version: `node --version` (requires 20+)
- Verify vite config: the dev proxy points to `http://localhost:8000`

### Docker build errors
- Ensure Docker has enough disk space
- Check `.dockerignore` isn't excluding required files
- Build individually for debugging: `docker build -t test ./backend`
