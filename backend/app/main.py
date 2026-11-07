import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager, suppress

import psycopg2
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.ops_events import format_http_event
from app.routers import (
    algorithm_lab,
    car_api,
    chat_api,
    itinerary_api,
    location_api,
    planning_candidates,
    preference_profiles,
    route_preparation,
    routing_api,
    studio,
    studio_research,
    trip_car,
    trip_sharing,
)

logger = logging.getLogger(__name__)


def _configure_app_logging() -> None:
    """Expose application logs at the configured level."""
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
    from app.research import database as research_database

    replication = (
        asyncio.create_task(research_database.replicate()) if research_database.enabled() else None
    )
    yield
    if replication:
        replication.cancel()
        with suppress(asyncio.CancelledError):
            await replication
    await studio.jobs.shutdown()
    from app.crud import chat_crud

    if chat_crud._pool is not None and not chat_crud._pool.closed:
        chat_crud._pool.closeall()


# Create the FastAPI instance
app = FastAPI(lifespan=lifespan)


@app.middleware("http")
async def guard_neon_writes(request, call_next):
    if settings.NEON_READ_ONLY and request.method not in {"GET", "HEAD", "OPTIONS"}:
        return JSONResponse(
            status_code=503,
            content={"detail": "Neon write routes are disabled pending provider acceptance"},
        )
    return await call_next(request)


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
    expose_headers=["X-Trip-Revision"],
)


@app.middleware("http")
async def operational_http_event(request, call_next):
    started = time.monotonic()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        print(
            format_http_event(request.method, status, (time.monotonic() - started) * 1000),
            flush=True,
        )


app.include_router(routing_api.router)
app.include_router(planning_candidates.router)
app.include_router(route_preparation.router)
app.include_router(algorithm_lab.router)
app.include_router(studio.router)
app.include_router(studio_research.router)
app.include_router(location_api.router)
app.include_router(itinerary_api.router)
app.include_router(car_api.router)
app.include_router(chat_api.router)
app.include_router(preference_profiles.router)
app.include_router(trip_car.router)
app.include_router(trip_sharing.router)


@app.get("/")
async def root() -> str:
    return "Hello world"


@app.api_route("/health", methods=["GET", "HEAD"])
async def health():
    return {"status": "ok"}


_SHARING_COLUMN_TYPES = {
    ("trip_shares", "id"): "uuid",
    ("trip_shares", "owner_id"): "text",
    ("trip_shares", "chat_id"): "text",
    ("trip_shares", "token_digest"): "text",
    ("trip_shares", "link_expires_at"): "timestamp with time zone",
    ("trip_shares", "created_at"): "timestamp with time zone",
    ("trip_share_members", "id"): "uuid",
    ("trip_share_members", "share_id"): "uuid",
    ("trip_share_members", "account_id"): "text",
    ("trip_share_members", "display_name"): "text",
    ("trip_share_members", "connected_at"): "timestamp with time zone",
}


def _sharing_readiness(cur):
    """Read-only release prerequisite, not a migration/constraint/recovery audit."""
    try:
        cur.execute(
            "SELECT to_regclass('public.trip_shares'), to_regclass('public.trip_share_members')"
        )
        if not all(cur.fetchone()):
            return "sharing_schema"
        cur.execute(
            "SELECT c.relname, a.attname, pg_catalog.format_type(a.atttypid, a.atttypmod) "
            "FROM pg_catalog.pg_attribute a JOIN pg_catalog.pg_class c ON c.oid=a.attrelid "
            "WHERE c.relnamespace='public'::regnamespace AND c.relkind IN ('r','p') "
            "AND c.relname IN ('trip_shares','trip_share_members') "
            "AND a.attnum>0 AND NOT a.attisdropped"
        )
        actual = {(table, column): kind for table, column, kind in cur.fetchall()}
        if any(actual.get(key) != kind for key, kind in _SHARING_COLUMN_TYPES.items()):
            return "sharing_schema"
        # A comma-separated privilege argument tests ANY privilege, not ALL.
        cur.execute(
            "SELECT "
            + ", ".join(
                f"has_table_privilege(current_user, 'public.{table}', '{privilege}')"
                for table in ("trip_shares", "trip_share_members")
                for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE")
            )
        )
        if not all(cur.fetchone()):
            return "sharing_permissions"
        cur.execute(
            "SELECT id, owner_id, chat_id, token_digest, link_expires_at, created_at "
            "FROM public.trip_shares LIMIT 0"
        )
        cur.execute(
            "SELECT id, share_id, account_id, display_name, connected_at "
            "FROM public.trip_share_members LIMIT 0"
        )
    except Exception:
        return "sharing_schema"
    return None


@app.get("/ready")
def ready():
    """Database readiness is separate from process liveness at /health."""
    conn = None
    try:
        conn = psycopg2.connect(
            settings.DATABASE_URL or "",
            sslmode=settings.DATABASE_SSLMODE,
            connect_timeout=5,
        )
        with conn.cursor() as cur:
            # Transaction poolers reject PostgreSQL startup options. Set the
            # query deadline after connecting so the readiness check works
            # through the same pooled Neon URL used by normal requests.
            cur.execute("SET statement_timeout = 5000")
            cur.execute(
                "SELECT to_regclass('public.chats'), to_regclass('public.route_segments'), to_regclass('public.steps'), to_regclass('public.chat_memory'), to_regclass('public.algorithm_lab_runs'), to_regclass('public.places_catalog_imports'), to_regclass('public.places_catalog'), to_regclass('public.places_catalog_active')"
            )
            if not all(cur.fetchone()):
                return JSONResponse(
                    status_code=503,
                    content={"status": "not_ready", "dependency": "database_schema"},
                )
            cur.execute(
                "SELECT EXISTS (SELECT 1 FROM places_catalog_active a "
                "JOIN places_catalog_imports i ON i.generation=a.generation "
                "WHERE i.row_count > 0 AND EXISTS (SELECT 1 FROM places_catalog p "
                "WHERE p.generation=a.generation))"
            )
            if not cur.fetchone()[0]:
                return JSONResponse(
                    status_code=503,
                    content={"status": "not_ready", "dependency": "places_catalog"},
                )
            if dependency := _sharing_readiness(cur):
                return JSONResponse(
                    status_code=503, content={"status": "not_ready", "dependency": dependency}
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
