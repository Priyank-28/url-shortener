# URL Shortener

A production-style URL shortening service built with FastAPI, PostgreSQL, and Redis — containerised with Docker Compose.

---

## Architecture

```
                        Docker Compose (urlnet bridge)
┌──────────────────────────────────────────────────────────┐
│                                                          │
│   ┌─────────────────┐        ┌─────────────────┐        │
│   │   API Service   │──────▶ │  Cache Service  │        │
│   │                 │        │                 │        │
│   │  FastAPI 0.111  │        │    Redis 7      │        │
│   │  Uvicorn        │        │    Port 6379    │        │
│   │  Port 8000      │        │  (internal only)│        │
│   └────────┬────────┘        └─────────────────┘        │
│            │                                             │
│            ▼                                             │
│   ┌─────────────────┐                                    │
│   │  DB Service     │                                    │
│   │                 │                                    │
│   │  PostgreSQL 16  │                                    │
│   │  Port 5432      │                                    │
│   │  (internal only)│                                    │
│   └─────────────────┘                                    │
│                                                          │
└──────────────────────────────────────────────────────────┘
          ▲
          │  Port 8000 exposed to host
          │
     Your Browser / curl
```

---

## Request Flow

```
POST /shorten
─────────────
Client ──▶ FastAPI ──▶ Check DB for duplicate ──▶ Generate 6-char code
                                                        │
                                              Save to PostgreSQL
                                                        │
                                              Warm Redis cache
                                                        │
                                              Return short URL ──▶ Client

GET /{code}
───────────
Client ──▶ FastAPI ──▶ Check Redis
                           │
                  ┌────────┴────────┐
               HIT (fast)        MISS (fallback)
                  │                  │
                  │            Query PostgreSQL
                  │                  │
                  │            Populate Redis
                  │                  │
                  └────────┬─────────┘
                           │
                    Increment clicks
                           │
                    307 Redirect ──▶ Client ──▶ Original URL
```

---

## Features

- **URL shortening** — `POST /shorten` accepts any valid URL, returns a 6-character code
- **Idempotent** — submitting the same URL twice returns the same short code
- **Redirect** — `GET /{code}` redirects to the original URL via HTTP 307
- **Click tracking** — every redirect increments a click counter in PostgreSQL
- **Cache-aside** — Redis checked on every redirect before touching the database
- **Stats endpoint** — `GET /stats/{code}` returns click count and creation timestamp
- **Health endpoint** — `GET /health` for load balancer / orchestration probes
- **Input validation** — Pydantic rejects invalid URLs with a 422 before any DB call
- **7 unit tests** — Redis mocked, SQLite in-memory DB, no containers needed to test

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| API framework | FastAPI 0.111 | Async, auto-docs, Pydantic built-in |
| Web server | Uvicorn | ASGI, hot-reload in dev |
| Database | PostgreSQL 16 Alpine | Reliable, ACID, industry standard |
| Cache | Redis 7 Alpine | Sub-millisecond key lookup |
| ORM | SQLAlchemy 2.0 | Type-safe mapped columns |
| Validation | Pydantic v2 | Schema validation at the edge |
| Config | pydantic-settings | Typed env vars, fails fast on missing config |
| Containers | Docker Compose | Reproducible multi-service local environment |
| Tests | Pytest + unittest.mock | Fast, no containers required |

---

## Project Structure

```
url-shortener/
├── app/
│   ├── main.py          # FastAPI app, route handlers
│   ├── models.py        # SQLAlchemy ORM model (URL table)
│   ├── schemas.py       # Pydantic request/response schemas
│   ├── database.py      # Engine, session, Base, get_db dependency
│   ├── cache.py         # Redis client, get/set/increment helpers
│   └── config.py        # pydantic-settings config from .env
├── tests/
│   ├── __init__.py
│   └── test_api.py      # 7 tests, Redis mocked, SQLite DB
├── docker-compose.yml   # 3-service stack with healthchecks
├── Dockerfile           # Multi-stage Python 3.12-slim image
├── Makefile             # Developer shortcuts (up, down, logs, shell)
├── requirements.txt     # Pinned dependencies
├── pytest.ini           # Pytest config
├── .env.example         # Safe env template (committed)
├── .env                 # Real secrets (gitignored)
└── README.md
```

---

## Quick Start

### Prerequisites

- Docker Desktop with WSL2 backend
- Git

### Run locally

```bash
# Clone the repo
git clone git@github.com:priyankmistry1999/url-shortener.git
cd url-shortener

# Copy env template
cp .env.example .env

# Build and start all 3 containers
make up

# Check everything is healthy
make ps
```

Open **http://localhost:8000/docs** for the interactive Swagger UI.

---

## API Reference

### `POST /shorten`

Shorten a URL.

**Request**
```json
{
  "url": "https://www.example.com/some/very/long/path"
}
```

**Response** `201 Created`
```json
{
  "short_code": "f8ulWC",
  "short_url": "http://localhost:8000/f8ulWC",
  "original_url": "https://www.example.com/some/very/long/path"
}
```

---

### `GET /{code}`

Redirect to the original URL.

**Response** `307 Temporary Redirect` → original URL

---

### `GET /stats/{code}`

Get click stats for a short code.

**Response** `200 OK`
```json
{
  "short_code": "f8ulWC",
  "original_url": "https://www.example.com/some/very/long/path",
  "clicks": 42,
  "created_at": "2026-05-15T16:14:34.329637Z"
}
```

---

### `GET /health`

Liveness probe.

**Response** `200 OK`
```json
{ "status": "ok" }
```

---

## Make Commands

```bash
make up          # Build images and start all containers (detached)
make down        # Stop and remove containers
make logs        # Tail API container logs (Ctrl+C to exit)
make ps          # Show container status and health
make build       # Rebuild images without starting
make shell-api   # Open bash shell inside the API container
make shell-db    # Open psql shell inside the PostgreSQL container
```

---

## Running Tests

Tests use SQLite (no containers needed) and mock Redis entirely.

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run tests
PYTHONPATH=. pytest tests/ -v
```

Expected output:
```
tests/test_api.py::test_health                 PASSED
tests/test_api.py::test_shorten_url            PASSED
tests/test_api.py::test_shorten_same_url_twice PASSED
tests/test_api.py::test_redirect               PASSED
tests/test_api.py::test_stats                  PASSED
tests/test_api.py::test_invalid_url            PASSED
tests/test_api.py::test_unknown_code           PASSED

7 passed in 1.18s
```

---

## Design Decisions

**Cache-aside pattern**
Redis is never written directly by the client. The database is always the source of truth. On a cache miss, the app queries PostgreSQL and populates Redis for subsequent requests with a 1-hour TTL.

**`depends_on` with healthchecks**
The API container uses `condition: service_healthy` instead of plain `depends_on`. This ensures PostgreSQL has finished initialising before the API attempts its first connection — plain `depends_on` only waits for the container to start, not for the database inside it to be ready.

**`pool_pre_ping=True`**
SQLAlchemy tests each connection before using it from the pool. Prevents cryptic errors from stale connections that dropped silently.

**Route ordering**
`GET /stats/{code}` is defined before `GET /{code}` in main.py. FastAPI matches routes in order — if the wildcard came first, `/stats/abc` would be treated as a redirect instead of a stats lookup.

**Collision-safe code generation**
The short code generator retries up to 5 times to find a unique code. With 62^6 (~56 billion) possible codes this is practically unnecessary, but the defensive loop demonstrates awareness of edge cases.

---

## What I Learned

- Docker Compose networking — containers communicate by service name (`db`, `cache`), not `localhost`. The custom bridge network provides automatic DNS resolution.
- Cache-aside pattern — Redis as a read layer in front of PostgreSQL, database always source of truth
- FastAPI dependency injection — `get_db` uses `yield` to act as a context manager, ensuring the session closes after every request regardless of outcome
- SQLAlchemy 2.0 `Mapped` columns — fully type-safe ORM models, IDE-friendly
- Mocking external services in tests — `unittest.mock.patch` replaces the Redis client so tests run in under 2 seconds without any infrastructure
- Pydantic `HttpUrl` — validates URL format at the schema level before any business logic runs

---

## Next Steps (Project 2)

- Deploy to Kubernetes with Minikube (Deployments, Services, Ingress, HPA)
- Add Prometheus metrics endpoint and Grafana dashboard
- GitHub Actions CI/CD pipeline

---

*Part of a cloud engineering portfolio — built to demonstrate containerisation, caching patterns, and production-grade Python service design.*
