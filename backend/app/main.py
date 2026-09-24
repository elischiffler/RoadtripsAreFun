import logging
import os
from contextlib import asynccontextmanager

import psycopg2
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.routers import agent_api, car_api, chat_api, itinerary_api, location_api, routing_api

logger = logging.getLogger(__name__)


def _configure_app_logging() -> None:
    """Make ``app.*`` logs (including the AGENT_DEBUG turn trace) visible.

    Uvicorn only configures its own ``uvicorn*`` loggers plus the root logger at
    WARNING, so application ``logger.info(...)`` calls — notably the per-turn
    agent trace in ``app.agent.debug`` — are silently dropped. We attach a
    stream handler to the ``app`` logger namespace at INFO (overridable via
    ``LOG_LEVEL``) so the console shows the trace during local debugging. Scoped
    to ``app`` so uvicorn's access/error logging is left untouched.
    """
    level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
    app_logger = logging.getLogger("app")
    app_logger.setLevel(level)
    # Avoid stacking duplicate handlers across --reload cycles.
    if not any(getattr(h, "_roadtrip_app_handler", False) for h in app_logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s:%(name)s:%(message)s"))
        handler._roadtrip_app_handler = True  # type: ignore[attr-defined]
        app_logger.addHandler(handler)
    # Don't also bubble to the root logger (prevents double lines).
    app_logger.propagate = False


_configure_app_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm up the Neon database connection pool on startup so the first
    # user request doesn't pay the cold-start penalty.
    try:
        from app.crud.chat_crud import _get_pool

        pool = _get_pool()
        conn = pool.getconn()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        pool.putconn(conn)
        logger.info("Database connection pool warmed up.")
    except Exception as e:
        logger.warning(f"DB warm-up failed (non-fatal): {e}")
    yield
    from app.crud import chat_crud

    if chat_crud._pool is not None and not chat_crud._pool.closed:
        chat_crud._pool.closeall()


# Create the FastAPI instance
app = FastAPI(lifespan=lifespan)


@app.middleware("http")
async def isolate_incomplete_preview(request, call_next):
    # Until reviewed schema/provider fixtures exist, fail before any business
    # route can use hardcoded upstreams (some routes do not require API keys).
    if settings.LOCAL_PREVIEW and request.url.path not in {"/", "/health", "/ready", "/algorithms"}:
        return JSONResponse(
            status_code=503,
            content={
                "detail": "Local business flows require reviewed database and provider fixtures"
            },
        )
    return await call_next(request)


# Enables support of the front end on a different domain/port
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],  # Allows all HTTP methods
    allow_headers=["*"],  # Allows all headers
)

app.include_router(routing_api.router)
app.include_router(location_api.router)
app.include_router(itinerary_api.router)
app.include_router(car_api.router)
app.include_router(chat_api.router)
app.include_router(agent_api.router)


@app.get("/")
async def root() -> str:
    return "Hello world"


@app.api_route("/health", methods=["GET", "HEAD"])
async def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    """Database readiness is separate from process liveness at /health."""
    conn = None
    try:
        conn = psycopg2.connect(
            settings.DATABASE_URL or "",
            sslmode=settings.DATABASE_SSLMODE,
            connect_timeout=5,
            options="-c statement_timeout=5000",
        )
        with conn.cursor() as cur:
            cur.execute(
                "SELECT to_regclass('public.chats'), to_regclass('public.route_segments'), to_regclass('public.steps'), to_regclass('public.chat_memory')"
            )
            if not all(cur.fetchone()):
                return JSONResponse(
                    status_code=503,
                    content={"status": "not_ready", "dependency": "database_schema"},
                )
        return {"status": "ready"}
    except Exception:
        return JSONResponse(
            status_code=503, content={"status": "not_ready", "dependency": "database"}
        )
    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
