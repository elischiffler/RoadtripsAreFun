import requests
from requests.exceptions import RequestException
from dotenv import load_dotenv
from fastapi import HTTPException, APIRouter
import os
from pydantic import ValidationError
from app.models.car_data_models import Car

# Grab app from APIRouter
router = APIRouter()

# Load environment variables
load_dotenv()
#Grab the car data api key
car_data_key = os.getenv('CAR_DATA_API')

@router.get('/get-car-details')
async def get_car_details(model: str, make: str, year: int) -> Car:
    """
    Retrieves car details from the API Ninjas service given a car's model, make, and year.
    
    Args:
        model (str): The model of the car
        make (str): The manufacturer of the car
        year (int): The manufacturing year of the car

    Returns:
        Car: A Pydantic `Car` model instance containing validated car data.

    Raises:
        HTTPException: 
            - If no cars are found with the given parameters (404).
            - If there is an issue with the API request or response format (500).
            - If the car data validation fails (502).
    """

    api_url = 'https://api.api-ninjas.com/v1/cars'
    headers = {
        'X-API-Key': car_data_key
    }
    params = {
        'model': model,
        'make': make,
        'year': year,
        'limit': 1
    }
    try:
        response = requests.get(api_url, headers = headers, params = params)
        #Check to see if response.text is an empty list
        if response.text == '[]':
            raise HTTPException(status_code=404, detail="No cars found")
        
        #If not a empty list but response exists, validate and return the data
        elif response.status_code == requests.codes.ok:
            # Convert the response JSON to a list of dicts
            car_list_json_data = response.json()

            # Access the first item in the list. List only has 1 item because limit = 1
            car_json_data = car_list_json_data[0]
            
            # Validate the car data using the Pydantic model
            car_data = Car.model_validate(car_json_data)
            
            # Successfully validated car
            return car_data
        
    except RequestException as exception:
        raise HTTPException(status_code=500, detail=f"Car data request failed: {str(exception)}")
    except ValidationError as exception:
        raise HTTPException(status_code=502, detail=f'Improper car data response: {str(exception)}')

