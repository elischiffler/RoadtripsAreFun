import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv

# Resolve .env from the monorepo root (two levels up from this file)
if os.getenv("LOCAL_PREVIEW") != "true":
    load_dotenv(Path(__file__).resolve().parents[3] / ".env")


def validate_local_environment(env) -> None:
    """Fail closed before an isolated preview can inherit hosted destinations."""
    if env.get("LOCAL_PREVIEW") != "true":
        return
    allowed = {
        "DATABASE_URL": {"postgres", "restore", "127.0.0.1", "localhost"},
        "MENTRO_GATEWAY_URL": {"mentro-server", "127.0.0.1", "localhost"},
        "SUPABASE_URL": {"fixture", "127.0.0.1", "localhost"},
    }
    for name, hosts in allowed.items():
        value = env.get(name, "")
        if not value or urlparse(value).hostname not in hosts:
            raise ValueError(f"{name} must explicitly select an isolated local service")
    if env.get("ROUTING_REMOTE_URL"):
        raise ValueError("ROUTING_REMOTE_URL must be unset for an isolated preview")
    for name in (
        "MAPBOX_API",
        "TRIPADVISOR_API",
        "GOOGLE_PLACES_API",
        "OPENCAGE_KEY",
        "CAR_DATA_API",
    ):
        if env.get(name):
            raise ValueError(f"{name} must be unset for an isolated preview")


validate_local_environment(os.environ)


def validate_neon_environment(env) -> None:
    """Reject an accidental non-Neon or unverified production database target."""
    if env.get("ROADTRIPS_DATABASE_TARGET") != "neon":
        return
    url = urlparse(env.get("DATABASE_URL", ""))
    if (
        url.scheme not in {"postgres", "postgresql"}
        or not url.hostname
        or not url.hostname.endswith(".neon.tech")
        or url.path != "/neondb"
        or any(
            name != "channel_binding" or values != ["require"]
            for name, values in parse_qs(url.query).items()
        )
    ):
        raise ValueError("Neon deployment requires a neondb connection on a Neon host")
    if env.get("DATABASE_SSLMODE") != "verify-full":
        raise ValueError("Neon deployment requires DATABASE_SSLMODE=verify-full")
    if env.get("PGSSLROOTCERT") != "/etc/ssl/certs/ca-certificates.crt":
        raise ValueError("Neon deployment requires the runtime CA bundle")
    if env.get("ROADTRIPS_NEON_WRITES_ENABLED") not in {"true", "false"}:
        raise ValueError("Neon deployment requires an explicit write gate")


validate_neon_environment(os.environ)


def _database_sslmode() -> str:
    mode = os.getenv("DATABASE_SSLMODE", "require").strip()
    if mode not in {"require", "verify-ca", "verify-full", "disable"}:
        raise ValueError("DATABASE_SSLMODE must be require, verify-ca, verify-full or disable")
    return mode


class Settings:
    LOCAL_PREVIEW = os.getenv("LOCAL_PREVIEW") == "true"
    NEON_READ_ONLY = (
        os.getenv("ROADTRIPS_DATABASE_TARGET") == "neon"
        and os.getenv("ROADTRIPS_NEON_WRITES_ENABLED") != "true"
    )
    CORS_ORIGINS = [
        value.strip()
        for value in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173,http://127.0.0.1:8082,https://roadtrips.elischiffler.dev,https://roadtripsarefun.vercel.app",
        ).split(",")
        if value.strip()
    ]
    DATABASE_URL = os.getenv("DATABASE_URL")
    # Explicit opt-out only for the dedicated same-host Docker network.
    DATABASE_SSLMODE = _database_sslmode()

    # Chat agent LLM provider — the self-hosted Mentro gateway
    # (POST {MENTRO_GATEWAY_URL}/api/chat/stream-full, SSE). The backend calls it
    # server-to-server, authenticating with a Supabase JWT minted from a service
    # account in the gateway's own Supabase project. See docs/chat-agent-design.md §6.
    MENTRO_GATEWAY_URL = os.getenv("MENTRO_GATEWAY_URL", "https://api.mentro.elischiffler.dev")
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
    MENTRO_SERVICE_EMAIL = os.getenv("MENTRO_SERVICE_EMAIL")
    MENTRO_SERVICE_PASSWORD = os.getenv("MENTRO_SERVICE_PASSWORD")

    # When set (local dev), the agent's routing tools proxy the IP-whitelisted
    # external calls (Mapbox/TripAdvisor/hotels) through the DEPLOYED roadtrip
    # backend at this URL, which has the whitelisted IP. Unset on the deployed
    # backend itself, so the same tools run the routing locally there. See
    # app/agent/routing_remote.py and docs/chat-agent-design.md.
    ROUTING_REMOTE_URL = os.getenv("ROUTING_REMOTE_URL")


settings = Settings()
