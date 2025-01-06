import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    AWS_REGION = os.getenv("AWS_REGION")  # Default to 'us-west-1' if not set
    DYNAMODB_TABLE_NAME = os.getenv("DYNAMODB_TABLE_NAME")  # Default to 'RoadtripAI' if not set
    AWS_NAME = os.getenv("AWS_USER")
    DYNAMODB_ROUTE_TABLE = os.getenv("DYNAMODB_ROUTE_TABLE")
    STEP_TABLE = os.getenv("STEP_TABLE")


settings = Settings()
