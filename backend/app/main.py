from fastapi import FastAPI
from app.routers import routing_api, location_api, itinerary_api, car_api, chat_api
from fastapi.middleware.cors import CORSMiddleware

# Create the FastAPI instance
app = FastAPI()

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
