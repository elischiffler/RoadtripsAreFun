from fastapi import FastAPI
import requests

app = FastAPI()



@app.get("/")
async def root() -> str:
    return "Hello world"


@app.get("/get-route")
async def get_route(*, start_lat: float, start_lon: float, end_lat: float, end_lon: float) -> dict:
    distance, duration = 0,0
    # Creating the get request for matbox
    response = requests.get('https://api.mapbox.com/directions/v5/mapbox/driving/' +
                            str(start_lon) +
                            '%2C' +
                            str(start_lat) +
                            '%3B' +
                            str(end_lon) +
                            '%2C' +
                            str(end_lat) +
                            '?alternatives=false&geometries=geojson&language=en&overview=full&steps=true&access_token=pk.eyJ1IjoiYWlkYW4xMzgiLCJhIjoiY2x5cDdzODVkMDFyYjJrcHd3Z3puY2o1eSJ9.FMN-O1YsLaTjFsL4VfnufA')
    # Need to get the distance,duration, steps
    steps = []
    json_data = response.json() if response and response.status_code == 200 else None
    if json_data and 'routes' in json_data:
        for route in json_data['routes']:
            distance, duration = route['distance'], route['duration']
            for leg in route['legs']:
                for step in leg['steps']:
                    # Each step has a distance, duration, instruction, and location for future use
                    temp_dis = step['distance']
                    temp_dur = step['duration']
                    temp_instruction = step['maneuver']['instruction']
                    temp_location = step['maneuver']['location']
                    steps.append({'distance': temp_dis, 'duration': temp_dur, 'instruction': temp_instruction, 'location': temp_location})
    return{'distance': distance, 'duration': duration, 'route': steps}
