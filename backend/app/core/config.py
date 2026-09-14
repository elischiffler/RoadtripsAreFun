import os
from pathlib import Path

from dotenv import load_dotenv

# Resolve .env from the monorepo root (two levels up from this file)
load_dotenv(Path(__file__).resolve().parents[3] / ".env")


class Settings:
    DATABASE_URL = os.getenv("DATABASE_URL")

    # Chat agent LLM provider — the self-hosted Mentro gateway
    # (POST {MENTRO_GATEWAY_URL}/api/chat/stream-full, SSE). The backend calls it
    # server-to-server, authenticating with a Supabase JWT minted from a service
    # account in the gateway's own Supabase project. See docs/chat-agent-design.md §6.
    MENTRO_GATEWAY_URL = os.getenv("MENTRO_GATEWAY_URL", "https://mentro-lucid-dust-3580.fly.dev")
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
