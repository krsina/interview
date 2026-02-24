# Feature Flag API

A production-ready REST API for managing feature flags with per-user overrides and cached evaluation, built with **FastAPI**, **SQLAlchemy 2.0 (async)**, **asyncpg**, and **Pydantic V2**.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Requirements Fulfillment](#requirements-fulfillment)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [API Reference](#api-reference)
- [Evaluation Logic](#evaluation-logic)
- [Caching Strategy](#caching-strategy)
- [Testing](#testing)
- [Validation and Error Handling](#validation-and-error-handling)
- [Deployment](#deployment)

---

## Architecture Overview

The service is organized around two core database tables and a layered resolution model:

```
                           ┌──────────────────┐
                           │   Client / curl   │
                           └────────┬─────────┘
                                    │ HTTP
                           ┌────────▼─────────┐
                           │  FastAPI Router   │
                           │  (routers/flags)  │
                           └──┬─────────────┬──┘
                              │             │
                    ┌─────────▼──┐    ┌─────▼─────────┐
                    │  In-Memory │    │  PostgreSQL    │
                    │  TTL Cache │    │  (asyncpg)     │
                    │  (cache.py)│    │                │
                    └────────────┘    │ feature_flags  │
                                     │ flag_user_     │
                                     │   overrides    │
                                     └────────────────┘
```

**Evaluation flow:** When a client asks "is feature X enabled for user Y?", the API checks the cache first. On a miss, it queries the `flag_user_overrides` table for a per-user override. If one exists, it wins. Otherwise, the global default from `feature_flags.is_enabled` is used. The result is cached for subsequent requests and invalidated whenever the underlying data changes.

---

## Requirements Fulfillment

### Functional Requirements

| Requirement | How It's Fulfilled | Key Files |
|---|---|---|
| **Store feature flags** | `feature_flags` table with UUID PK, unique `name`, optional `description`, boolean `is_enabled`, and timestamps. Full CRUD via REST endpoints. | `models.py`, `routers/flags.py` |
| **Create flags (name, description, default state)** | `POST /api/v1/flags/` accepts `name`, `description`, and `is_enabled` (defaults to `false`). Validated by Pydantic. Returns 201. | `schemas.py` (`FeatureFlagCreate`), `routers/flags.py` |
| **Enable/disable for all users (global default)** | `PATCH /api/v1/flags/{id}` or `PATCH /api/v1/flags/{id}/toggle` update `FeatureFlag.is_enabled`, which is the global default for all users without an override. | `routers/flags.py` |
| **Enable/disable for a specific user** | `PUT /api/v1/flags/{id}/users/{user_id}` creates or updates a row in `flag_user_overrides` with `is_enabled` for that user. `DELETE` removes the override. | `models.py` (`FlagUserOverride`), `routers/flags.py` |
| **Evaluate whether a feature is enabled for a user** | `GET /api/v1/flags/evaluate?flag_name=...&user_id=...` checks for a per-user override first; if none exists, falls back to the global default. Response includes a `source` field ("override" or "default") for transparency. | `routers/flags.py` (`evaluate_flag`) |
| **Persistent storage** | PostgreSQL via async SQLAlchemy + asyncpg. Tables are auto-created on startup via `Base.metadata.create_all` in the lifespan handler. All writes go through transactional sessions (commit on success, rollback on error). | `database.py`, `main.py` |
| **Cache evaluations** | In-memory TTL cache keyed by `(flag_id, user_id)`. Configurable TTL (default 60s) and max size (default 10,000). Invalidated on flag update/toggle/delete and on override set/delete. | `cache.py`, `config.py` |
| **Appropriate HTTP status codes** | 200 (success), 201 (created), 204 (deleted override), 404 (not found), 409 (conflict/duplicate), 422 (validation error), 500 (server error). | `routers/flags.py`, `main.py` |

### Engineering Requirements

| Requirement | How It's Fulfilled |
|---|---|
| **Code pushed to GitHub** | Repository at [github.com/krsina/interview](https://github.com/krsina/interview) |
| **Documentation** | This README covers architecture, requirements mapping, API reference, testing, and deployment |
| **Tests that demonstrate correctness** | 20+ pytest tests in `tests/test_flags.py` covering all endpoints, status codes, and edge cases |
| **Sensible validation and error handling** | Pydantic V2 schemas enforce field constraints; global exception handlers catch unhandled DB and server errors; specific 404/409/422 responses for known error cases |
| **Thoughtful organization of code** | Separated into `main.py`, `config.py`, `database.py`, `models.py`, `schemas.py`, `cache.py`, and `routers/flags.py` — each with a single responsibility |

---

## Tech Stack

| Component | Technology |
|---|---|
| Web framework | FastAPI |
| ORM | SQLAlchemy 2.0 (async) |
| Database driver | asyncpg |
| Database | PostgreSQL |
| Validation | Pydantic V2 |
| Configuration | pydantic-settings (env-driven) |
| Caching | Custom in-memory TTL cache |
| Testing | pytest + FastAPI TestClient |
| Deployment | DigitalOcean App Platform (buildpack) |

---

## Project Structure

```
.
├── main.py              # FastAPI app, lifespan (auto-create tables), exception handlers
├── config.py            # Pydantic settings loaded from environment / .env
├── database.py          # Async engine, session factory, get_db dependency
├── models.py            # SQLAlchemy ORM models (FeatureFlag, FlagUserOverride)
├── schemas.py           # Pydantic V2 request/response schemas
├── cache.py             # In-memory TTL cache with invalidation
├── routers/
│   ├── __init__.py
│   └── flags.py         # All API endpoints (CRUD, overrides, evaluate)
├── tests/
│   ├── __init__.py
│   └── test_flags.py    # Pytest endpoint tests
├── conftest.py          # Pytest fixtures (TestClient, api_prefix)
├── Procfile             # Process definition for platform deployment
├── .python-version      # Pins Python 3.12 for buildpack
├── requirements.txt     # Python dependencies
├── .env.example         # Example environment variables
├── .gitignore
└── README.md
```

---

## Getting Started

### Prerequisites

- Python 3.10+
- PostgreSQL running and accessible

### Setup

```bash
# Clone the repository
git clone https://github.com/krsina/interview.git
cd interview

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure the database connection
cp .env.example .env
# Edit .env with your PostgreSQL credentials

# Run the server (tables are auto-created on startup)
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/feature_flags` | Async PostgreSQL connection string |
| `DEBUG` | `false` | Enable SQLAlchemy query logging |
| `DB_POOL_SIZE` | `5` | Connection pool size |
| `DB_MAX_OVERFLOW` | `10` | Max overflow connections |
| `API_PREFIX` | `/api/v1` | API route prefix |
| `CACHE_TTL_SECONDS` | `60` | Cache entry time-to-live |
| `CACHE_MAX_SIZE` | `10000` | Max cached entries |

### Interactive Docs

Once running, visit:
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

---

## API Reference

All endpoints are prefixed with `/api/v1`.

### Feature Flags (CRUD)

| Method | Path | Description | Status Codes |
|---|---|---|---|
| `POST` | `/flags/` | Create a feature flag | 201, 409, 422 |
| `GET` | `/flags/` | List flags (paginated, filterable) | 200 |
| `GET` | `/flags/{flag_id}` | Get a flag by ID | 200, 404 |
| `PATCH` | `/flags/{flag_id}` | Partially update a flag | 200, 404, 409, 422 |
| `PATCH` | `/flags/{flag_id}/toggle` | Toggle global default on/off | 200, 404 |
| `DELETE` | `/flags/{flag_id}` | Delete a flag | 200, 404 |

#### Create flag request body

```json
{
  "name": "dark_mode",
  "description": "Enable dark mode UI",
  "is_enabled": false
}
```

#### List query parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `skip` | int | 0 | Pagination offset |
| `limit` | int | 50 | Page size (max 200) |
| `enabled_only` | bool | false | Filter to enabled flags only |

### Per-User Overrides

| Method | Path | Description | Status Codes |
|---|---|---|---|
| `PUT` | `/flags/{flag_id}/users/{user_id}` | Set override (create or update) | 200, 201, 404 |
| `DELETE` | `/flags/{flag_id}/users/{user_id}` | Remove override | 204, 404 |
| `GET` | `/flags/{flag_id}/users` | List overrides for a flag | 200, 404 |

#### Set override request body

```json
{
  "is_enabled": true
}
```

### Evaluation

| Method | Path | Description | Status Codes |
|---|---|---|---|
| `GET` | `/flags/evaluate?flag_name=...&user_id=...` | Evaluate flag for user | 200, 404 |

#### Evaluate response

```json
{
  "enabled": true,
  "flag_id": "550e8400-e29b-41d4-a716-446655440000",
  "flag_name": "dark_mode",
  "user_id": "user_1",
  "source": "override"
}
```

The `source` field indicates whether the result came from a per-user `"override"` or the global `"default"`.

### Health and Root

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | API info and links |
| `GET` | `/health` | Health check |

---

## Evaluation Logic

The evaluate endpoint implements a two-tier resolution model:

```
1. Look up flag by name       → 404 if not found
2. Check in-memory cache      → return cached result on hit
3. Query flag_user_overrides   → if override exists: enabled = override.is_enabled, source = "override"
                               → if no override:     enabled = flag.is_enabled,     source = "default"
4. Store result in cache
5. Return response
```

This design allows:
- A global default that applies to all users.
- Per-user overrides that take priority when present.
- Removing an override causes the user to fall back to the global default.

---

## Caching Strategy

The cache (`cache.py`) is an in-memory dictionary with TTL-based expiration:

- **Key:** `(flag_id, user_id)` tuple
- **Value:** The full evaluate response dict
- **TTL:** Configurable via `CACHE_TTL_SECONDS` (default 60s)
- **Max size:** Configurable via `CACHE_MAX_SIZE` (default 10,000 entries)
- **Thread-safe:** Protected by `threading.Lock`
- **Eviction:** Expired entries are evicted on read; when at capacity, expired entries are evicted first, then the oldest entry

### Cache Invalidation

Cache consistency is maintained through targeted invalidation:

| Action | Invalidation |
|---|---|
| Update or toggle a flag | `invalidate_flag(flag_id)` — removes all cached entries for that flag |
| Delete a flag | `invalidate_flag(flag_id)` — removes all cached entries for that flag |
| Set a user override | `invalidate_override(flag_id, user_id)` — removes that specific entry |
| Delete a user override | `invalidate_override(flag_id, user_id)` — removes that specific entry |

---

## Testing

Tests are in `tests/test_flags.py` and use FastAPI's `TestClient` with pytest. They cover:

| Test Class | What It Verifies |
|---|---|
| `TestHealth` | Health endpoint returns 200 |
| `TestCreateFlag` | Flag creation (201), duplicate name rejection (409) |
| `TestListFlags` | List with pagination, `enabled_only` filter |
| `TestGetFlag` | Get by ID (200), not found (404) |
| `TestUpdateFlag` | Partial update (200), empty body (422) |
| `TestToggleFlag` | Toggle global default (200) |
| `TestDeleteFlag` | Delete and confirm gone (200 then 404) |
| `TestEvaluate` | Default resolution (200), override resolution (200), missing flag (404) |
| `TestUserOverrides` | Create (201), update (200), delete (204), not found (404), list (200) |

### Running Tests

```bash
# Requires PostgreSQL running and DATABASE_URL configured
pip install -r requirements.txt
pytest tests/ -v
```

Tests use unique flag names (UUID suffixes) so they can run in any order against a shared database.

---

## Validation and Error Handling

### Request Validation (Pydantic V2)

- `FeatureFlagCreate`: `name` required (1-255 chars), `description` optional, `is_enabled` defaults to `false`
- `FeatureFlagUpdate`: All fields optional; rejects empty body with 422
- `FlagUserOverrideSet`: `is_enabled` required (boolean)
- Query params: `skip` (>= 0), `limit` (1-200), `flag_name` and `user_id` required for evaluate
- UUID path parameters validated automatically by FastAPI

### Error Responses

All errors return JSON with a `detail` field:

| Status | When |
|---|---|
| 404 | Flag ID not found, flag name not found, override not found |
| 409 | Duplicate flag name on create or update |
| 422 | Invalid input (Pydantic validation), empty PATCH body |
| 500 | Unhandled database or server errors (global exception handlers in `main.py` log the error and return a safe message) |

### Database Safety

- The `get_db` dependency commits on success and rolls back on any exception
- `IntegrityError` is caught explicitly for unique constraint violations (409)
- `SQLAlchemyError` has a global handler that returns 500 without leaking internals
- Foreign keys use `CASCADE` delete so overrides are cleaned up when a flag is deleted

---

## Deployment

### DigitalOcean App Platform

The app is configured for deployment via DigitalOcean App Platform using the Heroku Python buildpack:

- **`Procfile`** defines the web process: `uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}`
- **`.python-version`** pins Python 3.12
- **`config.py`** normalizes `DATABASE_URL` from various formats (`postgres://`, `postgresql://`) to `postgresql+asyncpg://`

#### Steps

1. Connect the GitHub repository in App Platform
2. Add a managed PostgreSQL database (or set `DATABASE_URL` manually)
3. Set the `DATABASE_URL` environment variable to the full connection string with `postgresql+asyncpg://` scheme and `?sslmode=require`
4. Deploy — tables are created automatically on first startup

### Local Development

```bash
cp .env.example .env
# Edit .env with your local PostgreSQL credentials
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
