from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from app.crud.chat_crud import update_chat_component, create_chat, delete_chat, get_all_chats, get_segments, restore_legs
from app.schemas.chat_schemas import ChatSchema

router = APIRouter()

@router.get('/chats')
async def initialize_chats(partition_key: str):
    """Initialize all the previously stored chats in the database."""
    try:
        # Get all stored items for a users unique partition key
        items = get_all_chats(partition_key)
        # Initialize list to hold all chat items
        chats = []
        if items and len(items) > 0:
            # Iterate through all the items returned
            for item in items:
                if item['ChatData']['initial']:
                    sorted_segments = get_segments(route_id=item['ChatData']['initial']['geometry'])
                    item['ChatData']['initial']['geometry'] = {}
                    item['ChatData']['initial']['geometry']['coordinates'] = sorted_segments
                    item['ChatData']['initial']['legs'] = restore_legs(legs=item['ChatData']['initial']['legs'])
                if item['ChatData']['route']:
                    item['ChatData']['route']['geometry']
                    item['ChatData']['route']['geometry']['coordinates'] = sorted_segments
                # Add a complete chat entry tuple with a chat log and chat data to chats
                chats.append((item['ChatData'], item['ChatLog']))
        # Return a response indicating a successful query and a list of found chats
        return chats

    except KeyError as exception:
        raise HTTPException(status_code=500, detail=f'Stored data was missing a value: {exception}')
    except ValidationError as exception:
        raise HTTPException(status_code=500, detail=f"Error validating request: {exception}")


@router.post('/chats/create/{chat_id}')
async def chat_add(chat_id: str, request: ChatSchema):
    """Add a new chat to the database."""
    # Get pertinent data from the request payload
    chat_data = request.ChatData
    chat_log = request.ChatLog
    try:
        # Create a new item in the database for the given chat data and log
        response = create_chat(request.PartitionKey, chat_id, chat_data.model_dump(), chat_log.model_dump())
        return response
    except ValidationError as exception:
        raise HTTPException(status_code=500, detail=f"Error validating request: {exception}")


@router.put('/chats/update/{chat_id}')
async def chat_update(chat_id: int, request: ChatSchema):
    """Update the chat components from the database."""
    # Retrieve pertinent data from the request payload
    chat_data = request.ChatData
    chat_log = request.ChatLog
    responses = []
    try:
        # Ensure there is data to add
        if chat_data is None and chat_log is None:
            raise ValueError("Chat data or logs data is required")
        # Check if chat data was sent to be updated in the database
        if chat_data:
            responses.append(update_chat_component(request.PartitionKey, str(chat_id), chat_data, 'ChatData'))
        # Check if a chat log was sent to be updated in the database
        if chat_log:
            responses.append(update_chat_component(request.PartitionKey, str(chat_id), chat_log, 'ChatLog'))
        return responses
    except Exception as exception:
        raise HTTPException(status_code=500, detail=f"Error updating chat: {exception}")


@router.delete("/chats/delete/{chat_id}")
async def delete_chat_component(chat_id: int, partition_key: str):
    """Delete a particular chat component from the database."""
    try:
        # Delete the chat and send a success response if no errors are raised
        delete_chat(partition_key, str(chat_id))
        return JSONResponse(status_code=200,
                            content={'status': 'success', 'message': f'Chat {chat_id} deleted successfully'})
    except ValidationError as exception:
        raise HTTPException(status_code=500, detail=f"Error validating request: {exception}")
