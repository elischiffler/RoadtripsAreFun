from fastapi import FastAPI
import requests


app = FastAPI()


@app.get("/")
async def root() -> str:
    return "Hello world"


@app.get("/get-route")
async def get_route(start_lat: float, start_lon: float, end_lat: float, end_lon: float) -> dict:
    # Creating the get request for matbox
    url = f'https://api.mapbox.com/directions/v5/mapbox/driving/{start_lon},{start_lat};{end_lon},{end_lat}'
    params = {
        'alternatives': 'false',
        'geometries': 'geojson',
        'language': 'en',
        'overview': 'full',
        'steps': 'true',
        'access_token': 'pk.eyJ1IjoiYWlkYW4xMzgiLCJhIjoiY2x5cDdzODVkMDFyYjJrcHd3Z3puY2o1eSJ9.FMN-O1YsLaTjFsL4VfnufA'
    }
    response = requests.get(url, params = params)

    # Need to get the distance(meters), duration(seconds), steps for the route
    json_data = response.json() if response and response.status_code == 200 else None
    if json_data and 'routes' in json_data:
        distance, duration = 0,0
        steps = []
        for route in json_data['routes']:
            distance, duration = route['distance'], route['duration']
            for leg in route['legs']:
                for step in leg['steps']:
                    # Each step has a distance, duration, instruction, and location for future use
                    steps.append({'distance': step['distance'],
                                  'duration': step['duration'],
                                  'instruction': step['maneuver']['instruction'],
                                  'location': step['maneuver']['location']})
        return {'coordinates': [[start_lat, start_lon], [end_lat, end_lon]],
                'distance': distance,
                'duration': duration,
                'route': steps}
    else:
        return {"Error": "Unable to get route"}
