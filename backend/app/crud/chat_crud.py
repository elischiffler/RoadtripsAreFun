import boto3
from boto3.dynamodb.conditions import Key
from app.schemas import chat_schemas
from app.core.config import settings
from pydantic import BaseModel
from fastapi import HTTPException

session = boto3.Session(profile_name=settings.AWS_NAME)
dynamodb = session.resource('dynamodb', region_name=settings.AWS_REGION)

table = dynamodb.Table(settings.DYNAMODB_TABLE_NAME)


def create_chat(auth_token: str,
                chat_id: str,
                chat_data: chat_schemas.ChatDataSchema,
                chat_logs: chat_schemas.ChatLogSchema):
    response = table.put_item(
        Item={
            'UserId': auth_token,
            'ChatId': chat_id,
            'ChatData': chat_data,
            'ChatLog': chat_logs,
        }
    )
    return response


def get_chat(auth_token: str, chat_id: str) -> chat_schemas.ChatSchema:
    response = table.get_item(
        Key={
            'UserId': auth_token,
            'ChatId': chat_id
        }
    )
    return response


def get_all_chats(auth_token: str):
    response = table.query(
        KeyConditionExpression=Key('UserId').eq(auth_token)
    )
    items = response.get('Items', [])
    if len(items) == 0:
        raise HTTPException(status_code=404, detail="No items found for the user")
    return items

def update_chat_component(auth_token: str, chat_id: str, chat_schema: BaseModel, prefix: str):
    # Iterate through all the values that are going to be set
    update_expression = 'SET ' + ', '.join(f"{prefix}.{key} = :{key}" for key in chat_schema.dict().keys())
    # Iterate through the attributes you want to change the value of
    expression_attribute_values = {f":{key}": value for key, value in chat_schema.dict().items() if value is not None}

    # Update the items in the database
    response = table.update_item(
        Key={
            'UserId': auth_token,
            'ChatId': chat_id,
        },
        UpdateExpression=update_expression,
        ExpressionAttributeValues=expression_attribute_values,
        ReturnValues='UPDATED_NEW'
    )
    return response


def delete_chat(auth_token: str, chat_id: str) -> chat_schemas.ChatSchema:
    response = table.delete_item(
        Key={
            'UserId': auth_token,
            'ChatId': chat_id
        }
    )
    return response






