from typing import Dict
import requests
from requests import Response
from requests.exceptions import RequestException
from fastapi import HTTPException, APIRouter
from pydantic import ValidationError
import xml.etree.ElementTree as ET

# Grab app from APIRouter
router = APIRouter()


@router.get('/get-car-details')
async def get_car_details(model: str, make: str, year: int) -> Dict[str, float]:
    """
    Retrieves car details from the fuel gov on a given car's model, make, and year.
    
    Args:
        model (str): The model of the car
        make (str): The manufacturer of the car
        year (int): The manufacturing year of the car

    Returns:
        Dict[str, float]: Dictionary containing relevant car details for calculating budget

    Raises:
        HTTPException: 
            - If no cars are found with the given parameters (404).
            - If there is an issue with the API request or response format (500).
            - If the car data validation fails (502).
    """

    api_url = 'https://www.fueleconomy.gov/ws/rest/vehicle/menu/options'

    try:

        model = _get_full_model_name(model , make, year)
        params = {
            'model': model,
            'make': make,
            'year': year,
        }

        # Send a request to the API
        response = requests.get(api_url, params=params)

        #  If not a empty list but response exists, validate and return the data
        if response.status_code == requests.codes.ok:

            # Get the first available car ID for given model
            car_id = _handle_car_identifier(response)[0]

            # The URL to get MPG information
            mpg_url = f"https://www.fueleconomy.gov/ws/rest/vehicle/{car_id}"

            # Get the car info using the id
            car_info_response = requests.get(mpg_url)
            if car_info_response.status_code == requests.codes.ok:
                mpg = _handle_car_info(car_info_response)
                if isinstance(mpg, str):
                    return {'combination_mpg': float(mpg)}
                else:
                    raise HTTPException(status_code=500, detail='Could not find miles per gallon info from response')

    except RequestException as exception:
        raise HTTPException(status_code=500, detail=f"Car data request failed: {str(exception)}")
    except ValidationError as exception:
        raise HTTPException(status_code=502, detail=f'Improper car data response: {str(exception)}')


def _handle_car_identifier(response: Response):
    """Get a certain car identifier (makes or database id) from a xml response"""
    print("finding id...")
    # Convert the response content to an element tree for parsing
    root = ET.fromstring(response.content)
    # Get ids list from the response
    details = [child.text for child in root.findall(".//menuItem/value")]
    print(details)
    if len(details) == 0:
        raise HTTPException(status_code=404, detail="No cars found")
    return details


def _handle_car_info(response: Response):
    """Get the miles per gallon from information from an xml response"""
    root = ET.fromstring(response.content)
    # Get the vehicle type
    fuel_type = root.find('atvType').text
    if fuel_type != "EV":  # Check to be sure not an electric vehicle
        mpg = root.find('comb08').text  # Get the combination mpg
        return mpg
    else:
        raise HTTPException(status_code=500, detail="We currently do not support electric vehicles")

def _get_full_model_name(model: str, make: str, year: int) -> str:
    """Get the full model name in the database from the given model name"""
    models_url = f"https://www.fueleconomy.gov/ws/rest/vehicle/menu/model"
    params = {
        'make': make,
        'year': year,
    }

    response = requests.get(models_url, params=params)
    if response.status_code == requests.codes.ok:
        models = _handle_car_identifier(response)
        for full_model in models:
            # Check if the the provided model name is in the full_model provided
            if model.lower() in full_model.lower():
                return full_model
