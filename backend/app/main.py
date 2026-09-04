import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.chat import _ERROR_STATUS as _GENERATION_ERROR_STATUS
from app.api.chat import router as chat_router
from app.api.documents import artifacts_router, chunks_router
from app.api.documents import router as documents_router
from app.api.health import router as health_router
from app.api.retrieval import _ERROR_STATUS as _RETRIEVAL_ERROR_STATUS
from app.api.retrieval import router as retrieval_router
from app.api.study import _ERROR_STATUS as _STUDY_ERROR_STATUS
from app.api.study import router as study_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.generation.errors import GenerationError
from app.ingestion.repository import get_connection, init_db
from app.retrieval.errors import RetrievalError
from app.study.errors import StudyError

logger = logging.getLogger(__name__)

# Security headers applied to every response (spec section 8S). This is a
# local-first, single-origin JSON API with no cookie-based session and no
# server-rendered HTML, so a full Content-Security-Policy is not
# applicable here (see docs/security/SECURITY_CONFIGURATION.md); these
# three headers are still meaningful for the endpoints that serve
# uploaded/extracted files (`/artifacts/{id}/file`) and cost nothing for
# the JSON endpoints.
_SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
}


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
    app.include_router(chunks_router)
    app.include_router(artifacts_router)
    app.include_router(retrieval_router)
    app.include_router(chat_router)
    app.include_router(study_router)

    @app.middleware("http")
    async def _add_security_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        for name, value in _SECURITY_HEADERS.items():
            response.headers[name] = value
        return response

    # Spec section 8H: a domain error (empty index, unreachable model
    # provider, malformed structured output, ...) can be raised from a
    # FastAPI dependency provider (e.g. `get_bm25_retriever` building an
    # index) rather than from inside an endpoint's own try/except — such an
    # error would otherwise fall through to the generic 500 handler below
    # with no domain-specific status code. Registering a handler per error
    # hierarchy, reusing each router's own `_ERROR_STATUS` mapping, closes
    # that gap without duplicating the mapping.
    def _domain_error_response(exc: Exception, status_map: dict) -> JSONResponse:
        status_code = next(
            (code for error_type, code in status_map.items() if isinstance(exc, error_type)),
            500,
        )
        return JSONResponse(status_code=status_code, content={"detail": exc.message})  # type: ignore[attr-defined]

    @app.exception_handler(RetrievalError)
    async def _retrieval_error_handler(request: Request, exc: RetrievalError) -> JSONResponse:
        return _domain_error_response(exc, _RETRIEVAL_ERROR_STATUS)

    @app.exception_handler(GenerationError)
    async def _generation_error_handler(request: Request, exc: GenerationError) -> JSONResponse:
        return _domain_error_response(exc, _GENERATION_ERROR_STATUS)

    @app.exception_handler(StudyError)
    async def _study_error_handler(request: Request, exc: StudyError) -> JSONResponse:
        return _domain_error_response(exc, _STUDY_ERROR_STATUS)

    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Spec section 8H.1: never expose filesystem paths, stack traces,
        or internal exception details in an API response. The full
        exception (with traceback) is logged server-side only; the client
        always gets the same generic, safe message."""
        logger.exception(
            "unhandled_exception method=%s path=%s", request.method, request.url.path
        )
        return JSONResponse(status_code=500, content={"detail": "Internal server error."})

    return app


app = create_app()
