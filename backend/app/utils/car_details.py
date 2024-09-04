import requests
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()
#Grab the car data api key
car_data_key = os.getenv('CAR_DATA_API')

model = 'cx-3'
make = 'mazda'
year = 2018
api_url = 'https://api.api-ninjas.com/v1/cars'
headers = {
    'X-API-Key': car_data_key
}
params = {
    'model': model,
    'make': make,
    'year': year,
    'limit': 10
}
response = requests.get(api_url, headers = headers, params = params)
if response.status_code == requests.codes.ok:
    print(response.text)
else:
    print("Error:", response.status_code, response.text)
