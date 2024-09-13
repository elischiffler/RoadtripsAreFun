import boto3
from app.schemas import chat_schemas
from app.core.config import settings
from typing import Optional, Any

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


def delete_chat(auth_token: str, chat_id: str) -> chat_schemas.ChatSchema:
    response = table.delete_item(
        Key={
            'UserId': auth_token,
            'ChatId': chat_id
        }
    )
    return response


def update_chat(auth_token: str,
                chat_id: str,
                chat_data: Optional[chat_schemas.ChatDataSchema] = None,
                chat_logs: Optional[chat_schemas.ChatLogSchema] = None) -> Any:
    responses = []
    if chat_data:
        responses.append(update_chat_data(auth_token, chat_id, chat_data))
    if chat_logs:
        responses.append(update_chat_logs(auth_token, chat_id, chat_logs))
    if chat_data is None and chat_logs is None:
        raise ValueError("Chat data or logs data is required")
    return responses


def update_chat_data(auth_token: str, chat_id: str, chat_data: chat_schemas.ChatDataSchema):
    update_expression = 'SET ' + ', '.join(f"ChatData.{key} = :{key}" for key in chat_data.dict.keys())
    expression_attribute_values = {f":{key}": value for key, value in chat_data.dict.items()}
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


def update_chat_logs(auth_token: str, chat_id: str, chat_logs: chat_schemas.ChatLogSchema):
    update_expression = 'SET ' + ', '.join(f"ChatLog.{key} = :{key}" for key in chat_logs.dict.keys())
    expression_attribute = {f":{key}": value for key, value in chat_logs.dict.items()}
    response = table.update_item(
        Key={
            'UserId': auth_token,
            'ChatId': chat_id,
        },
        UpdateExpression=update_expression,
        ExpressionAttributeValues=expression_attribute,
        ReturnValues='UPDATED_NEW'
    )
    return response

