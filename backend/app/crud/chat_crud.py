import boto3
from boto3.dynamodb.conditions import Key
from app.schemas import chat_schemas
from app.core.config import settings
from pydantic import BaseModel
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict

session = boto3.Session(profile_name=settings.AWS_NAME)
dynamodb = session.resource('dynamodb', region_name=settings.AWS_REGION)

table = dynamodb.Table(settings.DYNAMODB_TABLE_NAME)


def create_chat(auth_token: str,
                chat_id: str,
                chat_data: Dict[str, Any],
                chat_logs: Dict[str, Any]):
    """Create a new chat instance in the database"""

    coords = [chat_data['startCoords'], chat_data['endCoords']]
    if len(coords) > 0:
        for coord in coords:
            #print(coord)
            if coords[0]:
                coord[0] = Decimal(coord[0]).quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)
            if coords[1]:
                coord[1] = Decimal(coord[1]).quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)
    chat_data['startCoords'] = coords[0]
    chat_data['endCoords'] = coords[1]
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
    """Get an individual chat from the database"""
    response = table.get_item(
        Key={
            'UserId': auth_token,
            'ChatId': chat_id
        }
    )
    return response


def get_all_chats(auth_token: str):
    """Get all chats for a given authentication token."""
    # Query all chat items for a give authentication token
    response = table.query(
        KeyConditionExpression=Key('UserId').eq(auth_token)
    )
    print(response)
    items = response.get('Items', [])
    return items


def update_chat_component(auth_token: str, chat_id: str, chat_schema: BaseModel, prefix: str):
    """Update a component of a user's chat in the database"""

    # Convert the schema to a dictionary
    comp_dict = chat_schema.model_dump()

    # Initialize placeholders for attribute names and values
    expression_attribute_names = {}
    expression_attribute_values = {}

    # Prepare the update expression and attribute values
    update_expression = 'SET '
    update_clauses = []

    use_expression_attribute_names = False

    for key, value in comp_dict.items():
        if value is not None or value != []:
            # Handle reserved keywords by creating placeholders for attribute names
            if key == 'action':  # Example reserved keyword
                placeholder_name = '#action'
                expression_attribute_names[placeholder_name] = key
                use_expression_attribute_names = True
            else:
                placeholder_name = key

            # Convert floats to a rounded decimal to meet AWS requirements
            if isinstance(value, float):
                value = Decimal(round(value, 6))
            elif isinstance(value, list):
                for idx in range(len(value)):
                    value[idx] = Decimal(value[idx]).quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP) if isinstance(value[idx], float) else value[idx]

            update_clauses.append(f"{prefix}.{placeholder_name} = :{key}")
            expression_attribute_values[f":{key}"] = {'S': value}  # Adjust type if necessary

    # Join update clauses
    update_expression += ', '.join(update_clauses)

    # Update the items in the database
    kwargs = {
        'Key': {
            'UserId': auth_token,
            'ChatId': chat_id,
        },
        'UpdateExpression': update_expression,
        'ExpressionAttributeValues': expression_attribute_values,
        'ReturnValues': 'UPDATED_NEW'
    }

    if use_expression_attribute_names:
        kwargs['ExpressionAttributeNames'] = expression_attribute_names

    response = table.update_item(**kwargs)
    return response


def delete_chat(auth_token: str, chat_id: str) -> chat_schemas.ChatSchema:
    """Delete a desired chat from the database"""
    # Delete the desired chat
    response = table.delete_item(
        Key={
            'UserId': auth_token,
            'ChatId': chat_id
        }
    )
    return response
