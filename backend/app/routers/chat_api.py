from fastapi import APIRouter, HTTPException
from pydantic import ValidationError
from app.crud.chat_crud import update_chat_component, create_chat, delete_chat, get_all_chats
from app.schemas.chat_schemas import ChatSchema
from botocore.exceptions import ClientError, DataNotFoundError, ConnectionError

router = APIRouter()

@router.get('/chats/{chat_id}')
async def initialize_chats(partition_key: int):
    try:
        items = get_all_chats(str(partition_key))
        chats = []
        if len(items) > 0:
            for item in items:
                chats.append((item['ChatData'], item['ChatLog']))
            return chats
        else:
            raise HTTPException(status_code=404, detail='No Chats found')
    except ConnectionError as exception:
        raise HTTPException(status_code=500, detail=f"Error connecting to the database: {exception}")
    except ClientError as exception:
        raise HTTPException(status_code=500, detail=f"Client error processing request: {exception}")
    except ValidationError as exception:
        raise HTTPException(status_code=500, detail=f"Error validating request: {exception}")

@router.post('/chats/{chat_id}')
async def chat_add(chat_id: int, partition_key: int, chat: ChatSchema):
    chat_data = chat.ChatData
    chat_log = chat.ChatLog
    try:
        response = create_chat(str(partition_key), str(chat_id), chat_data, chat_log)
        return {'status': '200 SUCCESS', 'response': response}
    except ConnectionError as exception:
        raise HTTPException(status_code=500, detail=f"Error connecting to the database: {exception}")
    except ClientError as exception:
        raise HTTPException(status_code=500, detail=f"Client error processing request: {exception}")
    except ValidationError as exception:
        raise HTTPException(status_code=500, detail=f"Error validating request: {exception}")


@router.put('/chats/{chat_id}')
async def chat_update(chat_id: int, partition_key: int, chat: ChatSchema):
    chat_data = chat.ChatData
    chat_log = chat.ChatLog
    responses = []
    try:
        if chat_data:
            responses.append(update_chat_component(str(partition_key), str(chat_id), chat_data, 'ChatData'))
        # Check if chat logs were set and then update the database
        if chat_log:
            responses.append(update_chat_component(str(partition_key), str(chat_id), chat_log, 'ChatLog'))
        # Check to be sure some data was sent else raise an error
        if chat_data is None and chat_log is None:
            raise ValueError("Chat data or logs data is required")
        return {'status': '200 SUCCESS', 'response': responses}
    except DataNotFoundError as exception:
        raise HTTPException(status_code=404, detail=f"Chat was not found: {exception}")
    except ConnectionError as exception:
        raise HTTPException(status_code=500, detail=f"Error connecting to the database: {exception}")
    except ClientError as exception:
        raise HTTPException(status_code=500, detail=f"Client error processing request: {exception}")


@router.delete("/chats/{chat_id}")
async def delete_chat_component(chat_id: int, partition_key: int):
    try:
        response = delete_chat(str(chat_id), str(partition_key))
        return {"status": "success", "response": response}
    except ConnectionError as exception:
        raise HTTPException(status_code=500, detail=f"Error connecting to the database: {exception}")
    except ClientError as exception:
        raise HTTPException(status_code=500, detail=f"Client error processing request: {exception}")
    except ValidationError as exception:
        raise HTTPException(status_code=500, detail=f"Error validating request: {exception}")
