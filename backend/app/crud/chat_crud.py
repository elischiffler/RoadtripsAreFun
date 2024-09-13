import boto3
from app.schemas import chat_schemas
from app.core.config import settings

dynamodb = boto3.resource('dynamodb', region_name=settings.AWS_REGION)
table = dynamodb.Table(settings.DYNAMODB_TABLE_NAME)

def create_chat(auth_token: str, chat_id: str, chat_data, chat_logs):
    response = table.put_item(
        Item={
            'UserId': auth_token,

        }
    )