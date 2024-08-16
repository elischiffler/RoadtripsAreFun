from fastapi import FastAPI
from .routers import routing_api

# Create the FastAPI instance
app = FastAPI()

# Add the FastAPI instance to a router for routing_api to access
app.include_router(routing_api.router)

