import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional
from uuid import uuid4, UUID
from routingpy import Valhalla



app = FastAPI()


@app.get("/")
async def root():
    return "Hello world"

