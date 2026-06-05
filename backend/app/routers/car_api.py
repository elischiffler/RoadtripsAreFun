from typing import Dict, List
import requests
from requests import Response
from requests.exceptions import RequestException
from fastapi import HTTPException, APIRouter
from pydantic import ValidationError
import xml.etree.ElementTree as ET

# Grab app from APIRouter
router = APIRouter()


@router.get("/get-car-details")
async def get_car_details(model: str, make: str, year: int) -> Dict[str, float]:
    """
    Retrieves car details from FuelEconomy on a given car's model, make, and year.

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

    api_url = "https://www.fueleconomy.gov/ws/rest/vehicle/menu/options"

    try:
        model = _get_full_model_name(model, make, year)
        params = {
            "model": model,
            "make": make,
            "year": year,
        }

        # Send a request to the API
        response = requests.get(api_url, params=params)

        #  If not a empty list but response exists, validate and return the data
        if response.status_code == requests.codes.ok:
            # Get the first available car ID for given model
            car_id = _handle_car_identifier(response)[0]

            # The URL to get statistics information on the car
            statistics_url = f"https://www.fueleconomy.gov/ws/rest/vehicle/{car_id}"

            # Get the car statistics xml response
            car_info_response = requests.get(statistics_url)
            if car_info_response.status_code == requests.codes.ok:
                # Get the combination miles per gallon from the response
                mpg = _handle_car_info(car_info_response)
                if isinstance(mpg, str):
                    return {"combination_mpg": float(mpg)}
                else:
                    raise HTTPException(
                        status_code=500, detail="Could not find miles per gallon info from response"
                    )

    except RequestException as exception:
        raise HTTPException(status_code=500, detail=f"Car data request failed: {str(exception)}")


def _handle_car_identifier(response: Response) -> List[str]:
    """
    Get a certain car identifier (vehicle makes or database id's) from a xml response

    Args:
        - response (Response): Response from Fueleconomy API

    Returns:
        - List[str]: List of car identifiers
    """
    # Convert the response content to an element tree for parsing
    root = ET.fromstring(response.content)
    # Get ids list from the response
    details = [child.text for child in root.findall(".//menuItem/value")]
    # Check if details were found
    if len(details) == 0:
        raise HTTPException(status_code=404, detail="No cars found")
    return details


def _handle_car_info(response: Response) -> str:
    """
    Get the miles per gallon from information from an xml response

    Args:
        - response (Response): Response from FuelEconomy API

    Returns:
        - The miles per gallon from information from a xml response
    """
    root = ET.fromstring(response.content)
    # Get the vehicle type
    fuel_type = root.find("atvType").text
    if fuel_type != "EV":  # Check to be sure not an electric vehicle
        mpg = root.find("comb08").text  # Get the combination mpg
        return mpg
    else:
        # Raise exception if they searched for an electric car
        raise HTTPException(status_code=500, detail="We currently do not support electric vehicles")


def _get_full_model_name(model: str, make: str, year: int) -> str:
    """
    Get the full model name in the database from the given model name

    Args:
        model (str): The model of the car
        make (str): The manufacturer of the car
        year (int): The manufacturing year of the car

    Returns:
        str: The full model name in the database

    """
    models_url = f"https://www.fueleconomy.gov/ws/rest/vehicle/menu/model"
    params = {
        "make": make,
        "year": year,
    }

    response = requests.get(models_url, params=params)  # Get the response from the API
    if response.status_code == requests.codes.ok:  # Ensure an OK response
        models = _handle_car_identifier(response)  # Get the list of models from xml response
        for full_model in models:  # Loop through all model names
            # Check if the provided model name is in the full_model
            if model.lower() in full_model.lower():  # Ensure they have the same capitalization
                return full_model


@router.get("/get-gas-price")
async def get_gas_price() -> float:
    """
    Retrieves the current national average price for regular gas from FuelEconomy.gov.
    """
    api_url = "https://www.fueleconomy.gov/ws/rest/fuelprices"

    try:
        response = requests.get(api_url)
        if response.status_code == requests.codes.ok:
            root = ET.fromstring(response.content)
            regular_price = root.find("regular").text
            return float(regular_price)
        else:
            return 3.317  # Fallback to hardcoded average if the API fails
    except Exception as exception:
        return 3.317  # Fallback if an exception occurs
