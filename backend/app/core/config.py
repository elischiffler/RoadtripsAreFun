import os
from pathlib import Path
from dotenv import load_dotenv

# Resolve .env from the monorepo root (two levels up from this file)
load_dotenv(Path(__file__).resolve().parents[3] / ".env")


class Settings:
    DATABASE_URL = os.getenv("DATABASE_URL")


settings = Settings()
