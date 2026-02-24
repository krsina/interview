import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client() -> TestClient:
    """FastAPI test client. Lifespan runs on context entry (creates DB tables)."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def api_prefix() -> str:
    return "/api/v1"
