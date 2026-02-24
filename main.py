import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from config import settings
from database import engine
from models import Base
from routers import flags

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up — creating database tables if they don't exist")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables ready")
    yield
    logger.info("Shutting down — disposing engine")
    await engine.dispose()


app = FastAPI(
    title="Feature Flag API",
    description="A production-ready REST API for managing feature flags.",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(flags.router, prefix=settings.api_prefix)


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(
    request: Request,
    exc: SQLAlchemyError,
) -> JSONResponse:
    logger.error("Unhandled database error: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal database error occurred."},
    )


@app.exception_handler(Exception)
async def general_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    logger.error("Unhandled error: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred."},
    )


@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    return {"status": "healthy"}
