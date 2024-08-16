from fastapi import FastAPI
from app.routers import routing_api, location_api

# Create the FastAPI instance
app = FastAPI()

app.include_router(routing_api.router)
app.include_router(location_api.router)

@app.get("/")
async def root() -> str:
    return "Hello world"

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
