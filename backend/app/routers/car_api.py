import logging
import re
import xml.etree.ElementTree as ET
from typing import Optional

import requests
from fastapi import APIRouter, HTTPException
from requests import Response
from requests.exceptions import RequestException

# Grab app from APIRouter
router = APIRouter()
logger = logging.getLogger(__name__)

# Explicit (connect, read) timeouts in seconds for outbound FuelEconomy.gov calls so
# a slow or unresponsive upstream can't hang the request (and the event loop).
_HTTP_TIMEOUT = (5, 15)


def _normalize(text: str) -> str:
    """Normalize a model/make string for forgiving comparison.

    Lowercases and strips out hyphens, spaces, and other separators so that
    user input like ``CX3``, ``cx-3``, and ``CX 3`` all compare equal to the
    database's ``CX-3``.
    """
    return re.sub(r"[\s\-_]+", "", (text or "").strip().lower())


@router.get("/get-car-details")
async def get_car_details(model: str, make: str, year: int) -> dict[str, float]:
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
            - If there is an issue with the API request or response format (500/502).
    """

    api_url = "https://www.fueleconomy.gov/ws/rest/vehicle/menu/options"

    try:
        logger.info("get_car_details: request year=%s make=%r model=%r", year, make, model)

        full_model = _get_full_model_name(model, make, year)
        if full_model is None:
            logger.info(
                "get_car_details: no matching model for year=%s make=%r model=%r",
                year,
                make,
                model,
            )
            raise HTTPException(
                status_code=404,
                detail=f"Could not find a '{make} {model}' for {year}. "
                "Check the spelling, make, and year.",
            )
        logger.info("get_car_details: matched model %r -> %r", model, full_model)

        params = {
            "model": full_model,
            "make": make,
            "year": year,
        }

        # Send a request to the API. Explicit (connect, read) timeouts so a slow or
        # hung FuelEconomy.gov can't stall the request indefinitely.
        response = requests.get(api_url, params=params, timeout=_HTTP_TIMEOUT)
        if response.status_code != requests.codes.ok:
            logger.warning(
                "get_car_details: options lookup returned %s for %s %s %s",
                response.status_code,
                year,
                make,
                full_model,
            )
            raise HTTPException(
                status_code=502, detail="FuelEconomy.gov returned an unexpected response"
            )

        # Get the first available car ID for given model
        car_id = _handle_car_identifier(response)[0]

        # The URL to get statistics information on the car
        statistics_url = f"https://www.fueleconomy.gov/ws/rest/vehicle/{car_id}"

        # Get the car statistics xml response
        car_info_response = requests.get(statistics_url, timeout=_HTTP_TIMEOUT)
        if car_info_response.status_code != requests.codes.ok:
            logger.warning(
                "get_car_details: stats lookup returned %s for car_id=%s",
                car_info_response.status_code,
                car_id,
            )
            raise HTTPException(
                status_code=502, detail="FuelEconomy.gov returned an unexpected response"
            )

        # Get the combination miles per gallon from the response
        mpg = _handle_car_info(car_info_response)
        logger.info("get_car_details: success year=%s make=%r model=%r mpg=%s", year, make, model, mpg)
        return {"combination_mpg": float(mpg)}

    except HTTPException:
        # Already a well-formed API error (404/502/etc.) — let it through.
        raise
    except RequestException as exception:
        logger.error("get_car_details: FuelEconomy request failed: %s", exception)
        # 502: the upstream FuelEconomy.gov request failed. 500 is reserved for the
        # electric-vehicle contract raised in _handle_car_info (the frontend maps 500
        # to its "electric car" message), so it must not leak from transport failures.
        raise HTTPException(status_code=502, detail=f"Car data request failed: {str(exception)}")
    except ET.ParseError as exception:
        logger.error("get_car_details: could not parse FuelEconomy XML: %s", exception)
        raise HTTPException(status_code=502, detail="Could not parse FuelEconomy.gov response")
    except (AttributeError, ValueError) as exception:
        # Missing expected XML tags, or a non-numeric mpg value.
        logger.error("get_car_details: unexpected car data shape: %s", exception)
        raise HTTPException(
            status_code=502, detail="Unexpected car data from FuelEconomy.gov"
        )


def _handle_car_identifier(response: Response) -> list[str]:
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
    # Get the vehicle type (guard against a missing tag)
    atv_type = root.find("atvType")
    fuel_type = atv_type.text if atv_type is not None else None
    if fuel_type == "EV":
        # Raise exception if they searched for an electric car. Kept as 500 because
        # the frontend maps status 500 to its "electric car" message (CalcBudget.jsx).
        raise HTTPException(status_code=500, detail="We currently do not support electric vehicles")

    comb = root.find("comb08")
    if comb is None or comb.text is None:
        raise HTTPException(
            status_code=502, detail="Could not find miles per gallon info from response"
        )
    return comb.text


def _get_full_model_name(model: str, make: str, year: int) -> Optional[str]:
    """
    Get the full model name in the database from the given model name.

    Matching is forgiving: it ignores case, hyphens, and spaces, tries an exact
    normalized match first, then a substring match in either direction (so
    ``CX3`` matches ``CX-3`` and ``Wrangler`` matches ``Wrangler 4dr 4WD``).

    Args:
        model (str): The model of the car
        make (str): The manufacturer of the car
        year (int): The manufacturing year of the car

    Returns:
        Optional[str]: The full model name in the database, or None if no match.
    """
    models_url = "https://www.fueleconomy.gov/ws/rest/vehicle/menu/model"
    params = {
        "make": make,
        "year": year,
    }

    response = requests.get(
        models_url, params=params, timeout=_HTTP_TIMEOUT
    )  # Get the response from the API
    if response.status_code != requests.codes.ok:
        logger.warning(
            "_get_full_model_name: model list returned %s for make=%r year=%s",
            response.status_code,
            make,
            year,
        )
        # A non-200 upstream response is an upstream failure, not "no such model".
        # Raise 502 so it isn't confused with a successful empty result (None -> 404).
        raise HTTPException(
            status_code=502, detail="FuelEconomy.gov returned an unexpected response"
        )

    models = _handle_car_identifier(response)  # Get the list of models from xml response
    target = _normalize(model)
    if not target:
        return None

    # 1. Exact normalized match (e.g. "cx3" == normalized "CX-3").
    for full_model in models:
        if _normalize(full_model) == target:
            return full_model

    # 2. Substring match in either direction (user typed a prefix, or a
    #    superset of the DB name). Collect ALL matches: a single match is used,
    #    but multiple matches are ambiguous and must not silently resolve to the
    #    first one (that would query an arbitrary model).
    matches = [
        full_model
        for full_model in models
        if (norm := _normalize(full_model)) and (target in norm or norm in target)
    ]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        logger.info(
            "_get_full_model_name: %r ambiguous across %d models for %s %s: %s",
            model,
            len(matches),
            year,
            make,
            matches,
        )
        raise HTTPException(
            status_code=400,
            detail=f"'{make} {model}' is ambiguous for {year}. Matches: "
            f"{', '.join(matches)}. Please be more specific.",
        )

    logger.info(
        "_get_full_model_name: %r not among %d models for %s %s",
        model,
        len(models),
        year,
        make,
    )
    return None


@router.get("/get-gas-price")
async def get_gas_price() -> float:
    """
    Retrieves the current national average price for regular gas from FuelEconomy.gov.
    """
    api_url = "https://www.fueleconomy.gov/ws/rest/fuelprices"

    try:
        response = requests.get(api_url, timeout=_HTTP_TIMEOUT)
        if response.status_code == requests.codes.ok:
            root = ET.fromstring(response.content)
            regular_price = root.find("regular").text
            return float(regular_price)
        else:
            return 3.317  # Fallback to hardcoded average if the API fails
    except Exception as exception:
        logger.error(
            "get_gas_price: FuelEconomy.gov request failed, using fallback $3.317: %s", exception
        )
        return 3.317  # Fallback if an exception occurs
