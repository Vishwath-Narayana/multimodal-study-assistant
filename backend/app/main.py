from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.documents import router as documents_router
from app.api.health import router as health_router
from app.api.retrieval import router as retrieval_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.ingestion.repository import get_connection, init_db


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    Path(settings.sqlite_path).parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection(settings.sqlite_path)
    try:
        init_db(conn)
    finally:
        conn.close()

    app = FastAPI(
        title="Multimodal Study Assistant API",
        version="0.1.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_allowed_origins.split(",")],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router)
    app.include_router(documents_router)
    app.include_router(retrieval_router)
    return app


app = create_app()
