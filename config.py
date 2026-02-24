from pydantic import field_validator
from pydantic_settings import BaseSettings


def _normalize_database_url(url: str) -> str:
    """Ensure URL uses postgresql+asyncpg for async driver (e.g. when platform gives postgresql://)."""
    if not url or not url.strip():
        return "postgresql+asyncpg://postgres:postgres@localhost:5432/feature_flags"
    url = url.strip()
    if url.startswith("postgresql://") and "+asyncpg" not in url:
        return "postgresql+asyncpg://" + url[len("postgresql://") :]
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url[len("postgres://") :]
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


settings = Settings()
