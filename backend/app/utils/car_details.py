import requests
from requests import Response
import xml.etree.ElementTree as et
from pathlib import Path
import json
from timeit import default_timer as timer


def generate_car_dict(year: int):
    start_time = timer()
    print(year)
    year_dict = {}
    makes_url = f"https://www.fueleconomy.gov/ws/rest/vehicle/menu/make?year={year}"
    makes_response = requests.get(makes_url)
    makes = _handle_car_details(makes_response)
    for make in makes:
        print(make)
        make_dict = {}
        models_url = f"https://www.fueleconomy.gov/ws/rest/vehicle/menu/model?year={year}&make={make}"
        models_response = requests.get(models_url)
        models = _handle_car_details(models_response)
        for model in models:
            ids_url = f"https://www.fueleconomy.gov/ws/rest/vehicle/menu/options?year={year}&make={make}&model={model}"
            ids_response = requests.get(ids_url)
            ids = _handle_car_details(ids_response)
            if len(ids) > 0:
                car_id = ids[0]
                mpg_url = f"https://www.fueleconomy.gov/ws/rest/vehicle/{car_id}"
                mpg_response = requests.get(mpg_url)
                if mpg_response.status_code == 200:
                    root = et.fromstring(mpg_response.content)
                    fuel_type = root.find('atvType').text
                    if fuel_type != "EV":  # Check to be sure not an electric vehicle
                        mpg = root.find('highway08U').text
                        make_dict[model] = mpg
        year_dict[make] = make_dict
    end_time = timer()
    print(end_time - start_time)
    return year_dict


def _handle_car_details(response: Response):
    if response.status_code == 200:
        root = et.fromstring(response.content)
        details = [child.text for child in root.findall(".//menuItem/value")]
        return details


if __name__ == '__main__':
    cars_dict = generate_car_dict(2025)
    main_folder_path = Path(__file__).parents[1]
    save_path = main_folder_path / 'crud' / 'car_details.json'
    with open(save_path, 'w') as json_file:
        json.dump(cars_dict, json_file, indent=4)
