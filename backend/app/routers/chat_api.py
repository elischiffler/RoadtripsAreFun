import logging

import psycopg2
from fastapi import APIRouter, Header, HTTPException, Response
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.crud.chat_crud import (
    ChatGeometryInvalid,
    ChatGeometryUnavailable,
    ChatIdentityConflict,
    ChatSnapshotConflict,
    chat_data_revision,
    create_chat,
    delete_chat,
    get_all_chats,
    restore_geometry,
    restore_legs,
    update_chat_component,
)
from app.schemas.chat_schemas import ChatSchema
from app.utils.auth import bearer_token, get_user_id_from_token

router = APIRouter()
logger = logging.getLogger(__name__)


def _require_consistent_trip_ids(chat_id, chat_data, chat_log):
    if str(chat_data.chatId) != str(chat_id) or chat_log.id != chat_data.chatId:
        raise HTTPException(status_code=422, detail="Trip IDs must match the request path")


@router.get("/chats")
async def initialize_chats(authorization: str | None = Header(default=None)):
    """Initialize all the previously stored chats in the database."""
    # Decode the permanent user ID from the temporary access token
    user_id = get_user_id_from_token(bearer_token(authorization))
    try:
        # Get all stored items for a users unique partition key
        items = get_all_chats(user_id)
        # Initialize list to hold all chat items
        chats = []
        if items and len(items) > 0:
            # Iterate through all the items returned
            for item in items:
                # Hash raw persisted JSON; coordinate hydration changes its shape.
                item["ChatData"]["savedRevision"] = chat_data_revision(item["ChatData"])
                initial = item["ChatData"].get("initial")
                if initial is not None and not isinstance(initial, dict):
                    raise ChatGeometryInvalid()
                if initial:
                    if "geometry" in initial:
                        initial["geometry"] = restore_geometry(
                            user_id, item["ChatId"], initial["geometry"], allow_absent=True
                        )
                    if "legs" in initial:
                        initial["legs"] = restore_legs(
                            user_id=user_id,
                            chat_id=item["ChatId"],
                            legs=initial["legs"],
                        )
                route = item["ChatData"].get("route")
                if route is not None and not isinstance(route, dict):
                    raise ChatGeometryInvalid()
                if route:
                    route["geometry"] = restore_geometry(
                        user_id=user_id,
                        chat_id=item["ChatId"],
                        geometry=route.get("geometry"),
                    )
                # Add a complete chat entry tuple with a chat log and chat data to chats
                chats.append((item["ChatData"], item["ChatLog"]))
        # Return a response indicating a successful query and a list of found chats
        return chats

    except ChatGeometryUnavailable:
        raise HTTPException(
            status_code=503, detail="Saved trip geometry is temporarily unavailable"
        ) from None
    except ChatGeometryInvalid:
        raise HTTPException(status_code=500, detail="Saved trip geometry is invalid") from None
    except psycopg2.Error as exception:
        logger.warning("Chat read unavailable: %s", type(exception).__name__)
        raise HTTPException(
            status_code=503, detail="Chat storage is temporarily unavailable"
        ) from None
    except KeyError as exception:
        raise HTTPException(status_code=500, detail=f"Stored data was missing a value: {exception}")
    except ValidationError as exception:
        raise HTTPException(status_code=500, detail=f"Error validating request: {exception}")


@router.post("/chats/create/{chat_id}")
async def chat_add(chat_id: str, request: ChatSchema, response: Response):
    """Add a new chat to the database."""
    # Get pertinent data from the request payload
    chat_data = request.ChatData
    chat_log = request.ChatLog
    user_id = get_user_id_from_token(request.PartitionKey)
    _require_consistent_trip_ids(chat_id, chat_data, chat_log)
    logger.info("CREATE chat_id=%s user_id=%s", chat_id, user_id)
    try:
        # Create a new item in the database for the given chat data and log
        stored = create_chat(
            user_id, chat_id, chat_data.model_dump(mode="json"), chat_log.model_dump(mode="json")
        )
        if stored is None:
            raise ChatIdentityConflict("Trip ID belongs to a different planning request")
        else:
            logger.info("CREATE success chat_id=%s", chat_id)
        stored_data = stored["chat_data"] if isinstance(stored, dict) else stored[2]
        stored_log = stored["chat_log"] if isinstance(stored, dict) else stored[3]
        if chat_data.agentChatId is not None and (
            stored_data != chat_data.model_dump(mode="json")
            or stored_log != chat_log.model_dump(mode="json")
        ):
            raise HTTPException(
                status_code=409, detail="Trip already saved; reload before continuing"
            )
        response.headers["X-Trip-Revision"] = chat_data_revision(stored_data)
        return stored
    except ChatIdentityConflict:
        raise HTTPException(
            status_code=409, detail="Trip ID belongs to a different planning request"
        ) from None
    except ValidationError as exception:
        logger.error("CREATE validation error chat_id=%s: %s", chat_id, exception)
        raise HTTPException(status_code=500, detail=f"Error validating request: {exception}")
    except psycopg2.Error:
        raise HTTPException(
            status_code=503, detail="Chat storage is temporarily unavailable"
        ) from None


@router.put("/chats/update/{chat_id}")
async def chat_update(chat_id: int, request: ChatSchema):
    """Update the chat components from the database."""
    # Retrieve pertinent data from the request payload
    chat_data = request.ChatData
    chat_log = request.ChatLog
    user_id = get_user_id_from_token(request.PartitionKey)
    _require_consistent_trip_ids(chat_id, chat_data, chat_log)
    logger.info(
        "UPDATE chat_id=%s user_id=%s has_data=%s has_log=%s",
        chat_id,
        user_id,
        chat_data is not None,
        chat_log is not None,
    )
    if request.ExpectedRevision is None and (
        {"ExpectedRevision", "UpdateScope"} & request.model_fields_set
    ):
        raise HTTPException(
            status_code=422, detail="Conditional updates require a saved trip revision"
        )
    if (
        request.ExpectedRevision is not None
        and request.UpdateScope == "presentation"
        and "presentation" not in chat_data.model_fields_set
    ):
        raise HTTPException(
            status_code=422, detail="Presentation updates require presentation data"
        )
    responses = []
    try:
        # Ensure there is data to add
        if chat_data is None and chat_log is None:
            raise ValueError("Chat data or logs data is required")
        if request.ExpectedRevision is not None:
            result = update_chat_component(
                user_id,
                str(chat_id),
                chat_data,
                "ChatData",
                expected_revision=request.ExpectedRevision,
                update_scope=request.UpdateScope,
            )
            if result is None:
                raise HTTPException(status_code=404, detail="Chat not found")
            return {"savedRevision": chat_data_revision(result[0]["chat_data"])}
        # Check if chat data was sent to be updated in the database
        if chat_data:
            result = update_chat_component(user_id, str(chat_id), chat_data, "ChatData")
            if result is None:
                raise HTTPException(status_code=404, detail="Chat not found")
            else:
                logger.info("UPDATE chat_data success chat_id=%s", chat_id)
            responses.append(result)
        # Check if a chat log was sent to be updated in the database
        if chat_log:
            result = update_chat_component(user_id, str(chat_id), chat_log, "ChatLog")
            if result is None:
                raise HTTPException(status_code=404, detail="Chat not found")
            else:
                logger.info("UPDATE chat_log success chat_id=%s", chat_id)
            responses.append(result)
        return responses
    except ChatSnapshotConflict:
        raise HTTPException(
            status_code=409, detail="Saved trip changed; reload before editing"
        ) from None
    except HTTPException:
        raise
    except psycopg2.Error:
        raise HTTPException(
            status_code=503, detail="Chat storage is temporarily unavailable"
        ) from None
    except Exception as exception:
        logger.error("UPDATE failed chat_id=%s: %s", chat_id, exception)
        raise HTTPException(status_code=500, detail=f"Error updating chat: {exception}")


@router.delete("/chats/delete/{chat_id}")
async def delete_chat_component(chat_id: int, authorization: str | None = Header(default=None)):
    """Delete a particular chat component from the database."""
    user_id = get_user_id_from_token(bearer_token(authorization))
    try:
        # Delete the chat and send a success response if no errors are raised
        if not delete_chat(user_id, str(chat_id)):
            raise HTTPException(status_code=404, detail="Chat not found")
        return JSONResponse(
            status_code=200,
            content={"status": "success", "message": f"Chat {chat_id} deleted successfully"},
        )
    except psycopg2.Error:
        raise HTTPException(
            status_code=503, detail="Chat storage is temporarily unavailable"
        ) from None
    except ValidationError as exception:
        raise HTTPException(status_code=500, detail=f"Error validating request: {exception}")
