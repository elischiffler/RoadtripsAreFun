from pydantic import BaseModel, Field
from typing import Optional

class Car(BaseModel):
    city_mpg: int
    car_class: str = Field(alias='class') #Create an alias for class to be car_class
    combination_mpg: int
    cylinders: Optional[int] = None
    displacement: Optional[float] = None
    drive: str
    fuel_type: str
    highway_mpg: int
    make: str
    model: str
    transmission: str
    year: int

    class Config:
        allow_population_by_field_name = True  # Allow the use of aliases when creating instances