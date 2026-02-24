# Feature Flag API

A production-ready REST API for managing feature flags, built with FastAPI, SQLAlchemy 2.0 (async), asyncpg, and Pydantic V2.

## Prerequisites

- Python 3.10+
- PostgreSQL running and accessible

## Quick Start

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure the database connection
cp .env.example .env
# Edit .env with your PostgreSQL credentials

# 4. Run the server (tables are auto-created on startup)
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## API Endpoints

All endpoints are prefixed with `/api/v1`.

| Method   | Path                          | Description              |
|----------|-------------------------------|--------------------------|
| `GET`    | `/health`                     | Health check             |
| `POST`   | `/api/v1/flags/`              | Create a feature flag    |
| `GET`    | `/api/v1/flags/`              | List all feature flags   |
| `GET`    | `/api/v1/flags/{flag_id}`     | Get a flag by ID         |
| `PATCH`  | `/api/v1/flags/{flag_id}`     | Update a flag            |
| `PATCH`  | `/api/v1/flags/{flag_id}/toggle` | Toggle a flag on/off  |
| `DELETE` | `/api/v1/flags/{flag_id}`     | Delete a flag            |

### Query Parameters (List)

- `skip` (int, default 0) — pagination offset
- `limit` (int, default 50, max 200) — page size
- `enabled_only` (bool, default false) — filter to enabled flags only

## Interactive Docs

Once running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Project Structure

Repo root is the project root. After cloning:

```
.
├── main.py          # App init, lifespan, exception handlers
├── config.py        # Pydantic settings (env-driven)
├── database.py      # Async engine, session factory, get_db dependency
├── models.py        # SQLAlchemy ORM models
├── schemas.py       # Pydantic V2 request/response schemas
├── routers/
│   └── flags.py     # Feature flag CRUD endpoints
├── requirements.txt
├── .env.example
└── README.md
```
