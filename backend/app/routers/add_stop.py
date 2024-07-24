'''
from fastapi import FastAPI, HTTPException
from app.models.routing_models import MapBox, Trip_Advisor_Location_Search, Trip_Advisor_Information
import requests
from dotenv import load_dotenv
import os

load_dotenv()
#Cooldown class
class Cooldown:
    def __init__(self, restaurant, geo, attraction, hotel):
        self.restaurant = restaurant
        self.geo = geo
        self.attraction = attraction
        self.hotel = hotel

#Initialize a mapbox_step class
Mapbox_step = MapBox.MapBox_Route.Mapbox_leg.Mapbox_step

#Function that will find a nearby stop and resturn it
async def find_stop(category: str, lat: float, lon: float, radius: float) -> list:
    url = f"https://api.content.tripadvisor.com/api/v1/location/nearby_search?latLong={lat}%2C{lon}&key={tripadvisor_access_token}&category={category}&radius={radius}&radiusUnit=mi&language=en"
    headers = {"accept": "application/json"}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise an exception for HTTP errors
        locations = Trip_Advisor_Location_Search.model_validate(response.json())
        if len(locations.data) > 0:
            location = locations.data[0]  # Get the first location from the response
            location_id = location.location_id
            coordinates = await get_details(location_id)
            if coordinates is not None:
                return coordinates
            else:
                raise HTTPException(status_code=500, detail="Location data is missing latitude or longitude")
        else:
            raise HTTPException(status_code=404, detail="No locations found")
    except requests.exceptions.RequestException as exception:
        raise HTTPException(status_code=500, detail=f"Tripadvisor request failed: {str(exception)}")
    


#Grab details about the chosen location
async def get_details(location_id:int) -> list[float]:
    url = f"https://api.content.tripadvisor.com/api/v1/location/{location_id}/details?key={tripadvisor_access_token}&language=en&currency=USD"
    headers = {"accept": "application/json"}

    response = requests.get(url, headers=headers)
    details = Trip_Advisor_Information.model_validate(response.json())

    lat = details.latitude
    lon = details.longitude
    return [lat,lon]



#Function that will calculate the current postion of user
def find_position(coordinates: list[list[float]], steps: list[Mapbox_step], elapsed_time: float) -> list[float]:
    accumulated_time = 0
    for step in steps:
        step_duration = step.duration
        if accumulated_time + step_duration >= elapsed_time:
            ratio = (elapsed_time - accumulated_time) / step_duration
            start_coord = step.geometry.coordinates[0]
            end_coord = step.geometry.coordinates[-1]
            lat = start_coord[1] + ratio * (end_coord[1] - start_coord[1])
            lon = start_coord[0] + ratio * (end_coord[0] - start_coord[0])
            return [lat, lon]
        accumulated_time += step_duration
    return coordinates[-1]



@app.post('/add-stop')
async def add_stop(steps: list[Mapbox_step], coordinates: list[list[float]], route_duration: float, departure_time: float = 36000) -> list[list[float]]:
    #Conversion rate: 3600 seconds -> 1 hour
    cooldown = Cooldown(10800, 7200, 7200, 43200)
    current_time = 0
    total_time = route_duration
    real_time = departure_time #Keep track of the real world time

    #Create stopping point list
    stopping_points = []

    #Add stopping places until the trip is over
    while current_time < total_time:

        #Only find attractions and parks after 2 hours (Between 8am-8pm)
        if current_time > 7200 and (total_time - current_time) > 3600 and real_time > 28800 and real_time < 72000:
            if cooldown.attraction <= 0:
                current_lat, current_lon = find_position(coordinates, steps, current_time)
                stopping_points.append(await find_stop('attraction',current_lat, current_lon, 30))  #Can tweak radius depending on preferences
            if cooldown.geo <= 0:
                current_lat, current_lon = find_position(coordinates, steps, current_time)
                stopping_points.append(await find_stop('geo', current_lat, current_lon, 30))   #Can tweak radius depending on preferences

        #Find a hotel if after 9 pm
        if real_time > 75600:  #Can tweak this number depending on how early/late people want to drive
            if cooldown.hotel <= 0:
                current_lat, current_lon = find_position(coordinates, steps, current_time)
                stopping_points.append(await find_stop('hotel', current_lat, current_lon, 50))

        #Find food at alloted eating times
        if real_time > 28800 and real_time < 36000 or real_time > 46800 and real_time < 54000 or real_time > 64800 and real_time < 72000: #Can tweak all of these if user wants to eat at specific times
            if cooldown.restaurant <= 0:
                current_lat, current_lon = find_position(coordinates, steps, current_time)
                stopping_points.append(await find_stop('restaurant', current_lat, current_lon, 10))

        #Increment time
        current_time += 900
        if real_time + 900 < 86400:
            real_time += 900
        else:
            real_time += 900 - 86400

        #Increment cooldowns
        cooldown.attraction -= 900
        cooldown.geo -= 900
        cooldown.hotel -= 900
        cooldown.restaurant -= 900

    return stopping_points
'''