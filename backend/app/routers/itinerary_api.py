from fastapi import APIRouter, HTTPException, Request
from app.models.routing_models import Route

# Initialize FastAPI
router = APIRouter()

@router.post("/generate-itinerary")
async def generate_itinerary(route: Request):
    try:
        # Convert json payload back to route
        json_data = await route.json()
        data = Route.model_validate(json_data)
        pass
    except Exception as e:
        pass