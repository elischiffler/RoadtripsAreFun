import json
import boto3
import boto3.dynamodb
from boto3.dynamodb.conditions import Key
import boto3.dynamodb.types
from app.schemas import chat_schemas
from app.core.config import settings
from pydantic import BaseModel
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict

session = boto3.Session(profile_name=settings.AWS_NAME)
dynamodb = session.resource('dynamodb', region_name=settings.AWS_REGION)

table = dynamodb.Table(settings.DYNAMODB_TABLE_NAME)

type_set = set(['S', 'D', 'N', 'M'])

def convert_floats_to_decimal(data: Any):
    """Converts various datatypes to replace any float values with decimal variants"""
    if isinstance(data, float):
        return Decimal(data).quantize(Decimal('0.00001'), rounding=ROUND_HALF_UP)
    elif isinstance(data, list):
        return [convert_floats_to_decimal(item) for item in data]
    elif isinstance(data, dict):
        return {k: convert_floats_to_decimal(v) for k,v in data.items()}
    else:
        return data
    
def deserialize_response(data: Any):
    """
    Recursively deserialize a dynamodb response and convert to valid python types
    """
    deserializer = boto3.dynamodb.types.TypeDeserializer()
    if isinstance(data, dict):
        if set(data.keys()).intersection(type_set):
            deserialized = deserializer.deserialize(data)
            return deserialize_response(deserialized)
        else:
            return {k: deserialize_response(v) for k,v in data.items()}
    elif isinstance(data, list):
        return [deserialize_response(v) for v in data]
    elif isinstance(data, Decimal):
        print('found decimal: ', data)
        if data%1 == 0:
            return int(data)
        else:
            return float(data)
    return data
            
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
                coord[0] = convert_floats_to_decimal(coords[0])
            if coords[1]:
                coord[1] = convert_floats_to_decimal(coords[1])
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
    items = response.get('Items', [])
    print('premodified items', items)
    for i in range(len(items)):
        items[i] = deserialize_response(items[i])
        print(f'deserialized item {i}\n{items}\n\n\n\n')
    print('deserialized items', items)
    return 


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
    empty_vals = [[], {}, None, False, '']

    for key, value in comp_dict.items():
        if value not in empty_vals:

            # Ensure that all values are converted to their correct data types for storage
            if isinstance(value, (float, list, dict)):
                value = convert_floats_to_decimal(value)

            # Handle reserved keywords by creating placeholders for attribute names
            if key == 'initial':
                print(value)
            if key == 'action':
                placeholder_name = '#action'
                expression_attribute_names[placeholder_name] = key
                use_expression_attribute_names = True
            else:
                placeholder_name = key

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
