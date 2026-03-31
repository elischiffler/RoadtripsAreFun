from supabase import create_client, Client
from app.schemas import chat_schemas
from app.core.config import settings
from pydantic import BaseModel
from typing import Any, Dict
from ..utils.crud_helpers import segment_route

supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

def _store_legs_supabase(auth_token: str, chat_id: str, route_id: str, legs: list):
    """Helper to store steps inside Supabase"""
    for i, leg in enumerate(legs):
        leg_id = f"{route_id}-leg-{i}"
        steps = leg.get('steps', [])
        
        step_inserts = []
        for step_idx, step in enumerate(steps):
            coords = step['geometry']['coordinates']
            step_inserts.append({
                'user_id': auth_token,
                'chat_id': chat_id,
                'leg_id': leg_id,
                'step_id': step_idx,
                'coordinates': coords
            })
            step['geometry']['coordinates'] = leg_id
            
        if step_inserts:
            supabase.table('steps').upsert(step_inserts).execute()
    return legs
            
def create_chat(auth_token: str,
                chat_id: str,
                chat_data: Dict[str, Any],
                chat_logs: Dict[str, Any]):
    """Create a new chat instance in the database"""
    response = supabase.table('chats').upsert({
        'user_id': auth_token,
        'chat_id': chat_id,
        'chat_data': chat_data,
        'chat_log': chat_logs
    }).execute()
    return response.data


def get_chat(auth_token: str, chat_id: str) -> chat_schemas.ChatSchema:
    """Get an individual chat from the database"""
    response = supabase.table('chats').select('*').eq('user_id', auth_token).eq('chat_id', chat_id).execute()
    return response.data[0] if response.data else None


def get_all_chats(auth_token: str):
    """Get all chats for a given authentication token."""
    response = supabase.table('chats').select('*').eq('user_id', auth_token).execute()
    # Format the data into the exact Capitalized structure your API endpoints expect
    items = []
    for row in response.data:
        items.append({
            'UserId': row['user_id'],
            'ChatId': row['chat_id'],
            'ChatData': row['chat_data'],
            'ChatLog': row['chat_log']
        })
    return items

def get_segments(route_id: str):
    """Get all the segments associated with a single route_id"""
    response = supabase.table('route_segments').select('*').eq('route_id', route_id).execute()
    sorted_segs = sorted(response.data, key=lambda x: int(x['segment_id']))
    segs = []
    for seg in sorted_segs:
        segs.extend(seg['coords'])
    return segs


def update_chat_component(auth_token: str, chat_id: str, chat_schema: BaseModel, prefix: str):
    """Update a component of a user's chat in the database"""
    # Convert the schema to a dictionary
    comp_dict = chat_schema.model_dump()
    
    # Fetch existing data from Supabase
    col_name = 'chat_data' if prefix == 'ChatData' else 'chat_log'
    existing_resp = supabase.table('chats').select(col_name).eq('user_id', auth_token).eq('chat_id', chat_id).execute()
    if not existing_resp.data:
        return None
        
    current_val = existing_resp.data[0].get(col_name) or {}
    empty_vals = [[], {}, None, False, '']
    route_id = f'{auth_token}-{chat_id}'

    for key, value in comp_dict.items():
        route = None
        if value not in empty_vals:
            if key == 'initial':
                route = value['geometry']['coordinates']
                value['geometry'] = route_id
                value['legs'] = _store_legs_supabase(auth_token, chat_id, route_id, value['legs'])

            if key == 'route':
                route = value['geometry']['coordinates']
                value['geometry']['coordinates'] = route_id
            if route:
                segments = segment_route(route)
                seg_inserts = [{'user_id': auth_token, 'chat_id': chat_id, 'route_id': route_id, 'segment_id': str(seg_id), 'coords': segment} for seg_id, segment in enumerate(segments)]
                if seg_inserts:
                    supabase.table('route_segments').upsert(seg_inserts).execute()

            # Apply the update to our dictionary mapping
            current_val[key] = value

    # Upload the modified JSON back to Supabase
    response = supabase.table('chats').update({col_name: current_val}).eq('user_id', auth_token).eq('chat_id', chat_id).execute()
    return response.data


def delete_chat(auth_token: str, chat_id: str) -> chat_schemas.ChatSchema:
    """Delete a desired chat from the database"""
    response = supabase.table('chats').delete().eq('user_id', auth_token).eq('chat_id', chat_id).execute()
    return response.data

def restore_legs(legs: list[Any]):
    """Restore the coordinates of all the steps to their proper values"""
    rest_legs = []
    for leg in legs:
        leg_id = leg['steps'][0]['geometry']['coordinates']
        response = supabase.table('steps').select('*').eq('leg_id', leg_id).execute()
        steps_coords = response.data
        steps_coords = sorted(steps_coords, key=lambda x: x['step_id'])
        for i in range(len(steps_coords)):
            leg['steps'][i]['geometry']['coordinates'] = steps_coords[i]['coordinates']
        rest_legs.append(leg)
    return rest_legs
