import boto3
import boto3.dynamodb
from boto3.dynamodb.conditions import Key
import boto3.dynamodb.types
from app.schemas import chat_schemas
from app.core.config import settings
from pydantic import BaseModel
from typing import Any, Dict
from ..utils.crud_helpers import convert_floats_to_decimal, deserialize_response,segment_route,store_legs

session = boto3.Session(profile_name=settings.AWS_NAME)
dynamodb = session.resource('dynamodb', region_name=settings.AWS_REGION)

table = dynamodb.Table(settings.DYNAMODB_TABLE_NAME)
route_table = dynamodb.Table(settings.DYNAMODB_ROUTE_TABLE)
step_table = dynamodb.Table(settings.STEP_TABLE)


            
def create_chat(auth_token: str,
                chat_id: str,
                chat_data: Dict[str, Any],
                chat_logs: Dict[str, Any]):
    """Create a new chat instance in the database"""

    coords = [chat_data['startCoords'], chat_data['endCoords']]
    if len(coords) > 0:
        for coord in coords:
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
    for i in range(len(items)):
        items[i] = deserialize_response(items[i])
    return items

def get_segments(route_id: str):
    """Get all the segments associated with a single route_id"""
    # Query for all segments for a given route id
    response = route_table.query(
        KeyConditionExpression=Key('route_id').eq(route_id)
    )
    segments = response.get('Items')
    sorted_segs = sorted(segments, key=lambda x: x['segment_id'])
    segs = []
    for seg in sorted_segs:
        seg = deserialize_response(seg)
        segs.extend(seg['coords'])
    return segs


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

    route_id = f'{auth_token}-{chat_id}'

    for key, value in comp_dict.items():
        route = None
        if value not in empty_vals:

            # Ensure that all values are converted to their correct data types for storage
            if isinstance(value, (float, list, dict)):
                value = convert_floats_to_decimal(value)

            # Handle reserved keywords by creating placeholders for attribute names
            if key == 'initial':
                route = value['geometry']['coordinates']
                value['geometry'] = route_id
                value['legs'] = store_legs(auth_token=auth_token,
                                           legs=value['legs'],
                                           s_table=step_table)

            if key == 'route':
                route = value['coordinates']
            if key == 'action':
                placeholder_name = '#action'
                expression_attribute_names[placeholder_name] = key
                use_expression_attribute_names = True
            else:
                placeholder_name = key
            if route:
                segments = segment_route(route)
                with route_table.batch_writer() as batch:
                    for seg_id, segment in enumerate(segments):
                        batch.put_item({
                            'route_id': route_id,
                            'segment_id': str(seg_id),
                            'coords': segment
                        })
                print('Modified route:', value)

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

def restore_legs(legs: list[Any]):
    """Restore the coordinates of all the steps to their proper values"""
    rest_legs = []
    for leg in legs:
        leg_id = leg['steps'][0]['geometry']['coordinates']
        response = step_table.query(
            KeyConditionExpression = Key('leg_id').eq(leg_id)
        )
        steps_coords = response.get('Items')
        print(steps_coords)
        steps_coords = sorted(steps_coords, key=lambda x: x['step_id'])
        for i in range(len(steps_coords)):
            leg['steps'][i]['geometry']['coordinates'] = deserialize_response(steps_coords[i]['coordinates'])
        rest_legs.append(leg)
    return rest_legs
        