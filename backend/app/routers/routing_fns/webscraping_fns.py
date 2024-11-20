from typing import List, Tuple, Dict, Any, Optional
from fastapi import HTTPException
import random
import requests
from lxml import html
from app.utils.geolocation_helpers import get_location


def find_google_hotels(query: str, price_range: Tuple[float, float], coords: Tuple[float, float], radius: int, geolocator: Any) -> Dict[
                                                                                                                      str, Any] | None:
    """
    Handles the parsing of a Google hotels for the best hotel given the users preferences

    Args:
        - query: The search parameter for google
        - price_range: a tuple containing max and min pricing

    Returns:
        - Dict[str, Any]: Relevant hotel information

    Raises:
        - HTTPException: When no hotel information is found
    """
    url = 'https://www.google.com/travel/search'  # Link to google hotels
    response = _get_html_response(query=query, url=url)
    if response.status_code == 200:
        listings = _parse_google_response(response.text)  # Convert the response to a string to parse
        if len(listings) > 0:  # Ensure listings were found
            # Filter hotels out of budget
            valid_hotels = list(filter(lambda listing: price_range[0] <= listing['price'] <= price_range[1], listings))
            # Check only the top 20% of hotels found
            attempts = round(len(valid_hotels) * .2)
            while attempts > 0:  # Search through all hotel offerings
                print("advanced search...", valid_hotels)

                # Get detailed information on the highest rated hotel
                ideal_hotel = _get_advanced_listing(valid_hotels.pop())

                # Ensure advanced information was found and its within the search radius
                if ideal_hotel is not None and geodesic((ideal_hotel['coordinates'][0], ideal_hotel['coordinates'][1]),
                                                        coords).miles <= radius:
                    return ideal_hotel
                attempts -= 1  # Remove an attempt
        raise HTTPException(status_code=404,
                            detail="No valid hotels found for the given parameters")  # To handle research



def _get_html_response(url: str, query: Optional[str] = None) -> requests.Response:
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:85.0) Gecko/20100101 Firefox/85.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.96 Safari/537.36',
    ]  # A small list containing reliable user agents
    if query:
        params = {
            'q': query,
        }
    else:
        params = None

    headers = {
        'user-agent': random.choice(user_agents),  # select a random reliable user-agent
        'authority': 'www.google.com',
        'method': 'GET',
        'scheme': 'https',
        'accept-language': 'en-US,en;q=0.9',
        'cache-control': 'max-age=0',
        'upgrade-insecure-requests': '1',
        'DNT': "1"  # Do not track the request header
    }

    print("search query:", query)
    response = requests.get(url, params=params, headers=headers)
    return response


def _parse_google_response(response: str) -> List[Dict[str, Any]]:
    """
    Parses an HTML response for hotel information
    Parameters
        - response: The HTML response in string format

    Returns
        - List[Dict[str, Any]]: List of hotel information sorted by rating

    """
    parser = html.fromstring(response)
    hotels_list = parser.xpath("//div[@jsname='mutHjb']")  # Get a list of divs which contain the specified jsname
    listings = []
    for hotel in hotels_list:
        name = hotel.xpath(".//h2[@class='BgYkof ogfYpf ykx2he']/text()")  # Get this classes text value
        google_url = hotel.xpath(".//a[@class='PVOOXe']/@href")  # Get the google listing link for later scraping
        rank_details = hotel.xpath(".//span[@class='ta47le ']/@aria-label")
        pricing_details = hotel.xpath(  # List includes extraneous information unreliably
            ".//span[@jsaction='mouseenter:JttVIc;mouseleave:VqIRre;']//text()"
        )
        if len(pricing_details) == 4:  # Ensure all pricing info is being returned
            price = int(''.join(filter(str.isdigit, pricing_details[0])))  # Convert representation to an integer representation of price
            stars, review_count = _str_to_rating(rank_details[0])  # Extract rank information
            listings.append({  # Add a hotel with all its relevant information
                "name": name[0],
                "url": f"https://www.google.com{google_url[0]}",
                "price": price,
                "stars": stars,
                "review_count": review_count,
            })
    if len(listings) > 0:
        listings.sort(key=lambda listing: listing["stars"])  # Sort hotels lowest rated to highest
    return listings


def _get_advanced_listing(hotel: Dict[str, Any], geolocator) -> Dict[str, Any] | None:
    """
    Scrapes a given hotel listing for an accurate website url and location info
    Args:
        hotel(Dict[str, Any]): The hotel information that will be updated

    Returns:
        Dict[str, Any]: The updated hotel listing

    """
    response = _get_html_response(url=hotel['url'])  # Use the already found direct google url
    if response.status_code == 200:
        parser = html.fromstring(response.text)  # Format the data for parsing
        details = parser.xpath("//div[@class='iInyCf QqZUDd Zuc8V BLvVUb HoSN7e']")  # Div with relevant info
        if len(details) > 0:  # Ensure details were found
            details = details[0]  # set the details to be the first instance
            hotel_location_path = details.xpath(".//div[@class='K4nuhf']")[
                0]  # Exact container that will always have location
            address = hotel_location_path.xpath(".//span[@class='CFH2De']/text()")[
                0]  # Get the full address from the website page
            print('made it here')
            location = get_location(geocoder=geolocator, address=address)  # Geolocate for additional area info
            coordinates = [location.latitude, location.longitude]  # Get the coordinates of the hotel
            # Add new values to the dictionary
            print("finna return")
            hotel['coordinates'], hotel['address'] = coordinates, address
            return hotel  # Return the updated data
        return None


def _str_to_rating(rating: str) -> Tuple[float, int]:
    """
    Parses scraped rating information for relevant number

    Args:
        rating(str): Scraped unprocessed data for ratings

    Returns:
        Tuple[float, int]: The number of stars (0-5) and user review count

    """
    details = rating.split()
    stars = float(details[0])  # Get the star rating
    review_count = int(details[6].replace(',', ''))  # Remove commas to get review count as an integer
    return stars, review_count
