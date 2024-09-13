import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    AWS_REGION = os.getenv("AWS_REGION")  # Default to 'us-west-1' if not set
    DYNAMODB_TABLE_NAME = os.getenv("DYNAMODB_TABLE_NAME")  # Default to 'RoadtripAI' if not set
    AWS_NAME = os.getenv("AWS_USER")


settings = Settings()
