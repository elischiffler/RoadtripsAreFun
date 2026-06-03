from fastapi import FastAPI
from app.routers import routing_api, location_api, itinerary_api, car_api, chat_api
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

logger = logging.getLogger(__name__)


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


# Create the FastAPI instance
app = FastAPI(lifespan=lifespan)

# Enables support of the front end on a different domain/port
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins; replace with specific origins for production
    allow_credentials=True,
    allow_methods=["*"],  # Allows all HTTP methods
    allow_headers=["*"],  # Allows all headers
)

app.include_router(routing_api.router)
app.include_router(location_api.router)
app.include_router(itinerary_api.router)
app.include_router(car_api.router)
app.include_router(chat_api.router)

@app.get("/")
async def root() -> str:
    return "Hello world"

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
