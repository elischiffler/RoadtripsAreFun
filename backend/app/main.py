from fastapi import FastAPI
import routingpy as rp
from pprint import pprint


app = FastAPI()
client = rp.Valhalla()


@app.get("/")
async def root() -> str:
    return "Hello world"


# Route GET request
@app.get("/get-route")
async def get_route(*, start_lat: float, start_lon: float, end_lat: float,  end_lon: float):
    print(start_lat, end_lat, start_lon, end_lon)
    coords = [[start_lat, start_lon], [end_lat, end_lon]]
    route = client.directions(locations= coords, profile='auto', dry_run=True)
    pprint((route.geometry, route.duration, route.distance, route.raw))
    return {"duration":route.duration, "distance":route.distance, 'geometry': route.geometry}
