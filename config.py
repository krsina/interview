import logging
import os

from pydantic import field_validator
from pydantic_settings import BaseSettings

_log = logging.getLogger(__name__)


def _normalize_database_url(url: str) -> str:
    """Convert platform-provided DB URLs to postgresql+asyncpg://."""
    if not url or not url.strip():
        _log.warning("DATABASE_URL is empty — falling back to localhost default")
        return "postgresql+asyncpg://postgres:postgres@localhost:5432/feature_flags"

    url = url.strip()

    # DigitalOcean may inject ${db.DATABASE_URL} literally if binding failed
    if url.startswith("${") and url.endswith("}"):
        _log.error("DATABASE_URL is an unresolved reference: %s", url)
        raise ValueError(
            f"DATABASE_URL contains an unresolved variable reference: {url}. "
            "Check that the database component is bound correctly in App Platform."
        )

    # Strip wrapping quotes if someone pasted "postgresql://..." with quotes
    if (url.startswith('"') and url.endswith('"')) or (url.startswith("'") and url.endswith("'")):
        url = url[1:-1]

    # Normalize scheme
    if url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://") and "+asyncpg" not in url:
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]

    # Log the scheme (not the full URL, which has credentials)
    scheme = url.split("://")[0] if "://" in url else "UNKNOWN"
    _log.info("DATABASE_URL scheme after normalization: %s", scheme)

    return url


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/feature_flags"
    debug: bool = False
    db_pool_size: int = 5
    db_max_overflow: int = 10
    api_prefix: str = "/api/v1"
    cache_ttl_seconds: int = 60
    cache_max_size: int = 10_000

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, v: str | None) -> str:
        return _normalize_database_url(v or "")


# Log raw env var at import time so deploy logs show what the platform injected
_raw = os.environ.get("DATABASE_URL", "")
if _raw:
    _scheme = _raw.split("://")[0] if "://" in _raw else "NO_SCHEME"
    _log.info("Raw DATABASE_URL env var scheme: %s (length: %d)", _scheme, len(_raw))
else:
    _log.warning("DATABASE_URL env var is NOT SET — will use default")

settings = Settings()
