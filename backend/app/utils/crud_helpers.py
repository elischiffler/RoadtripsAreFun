from typing import Any
from decimal import Decimal, ROUND_HALF_UP
import boto3
import boto3.dynamodb
import boto3.dynamodb.table

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
        if data%1 == 0:
            return int(data)
        else:
            return float(data)
    return data

def segment_route(geometry: list[float], seg_size: int = 10000) -> list[list[float]]:
    segments = []
    for i in range(0, len(geometry), seg_size):
        segments.append(geometry[i : i + seg_size])
    return segments

def store_legs(auth_token: str, legs: list[Any], s_table: boto3.dynamodb.table) -> list[Any]:
    """Stores coordinates of a leg's steps under a unique step"""
    legs_mod = []
    for i, leg in enumerate(legs):
        leg['geometry'] = None
        leg_id = f'{auth_token}-leg{i}' # unique id for each leg
        with s_table.batch_writer() as batch:
            for step_id, step in enumerate(leg['steps']):
                batch.put_item({
                    'step_id': str(step_id),
                    'leg_id': leg_id,
                    'coordinates': step['geometry']['coordinates']
                })
                step['geometry']['coordinates'] = leg_id
                step['intersections'], step['exits'], step['destinations'], step['maneuver'], step['weight'] = None, None, None, None, None
                leg['notifications'], leg['via_waypoints'], leg['admins'] = [], [], []
                leg['steps'][step_id] = step
        legs_mod.append(leg)
    return legs_mod