"""Read-only capability views and authenticated account connections, never edits."""

from contextlib import contextmanager
from uuid import UUID

import psycopg2
from fastapi import APIRouter, Depends, HTTPException, Path, Response

from app.crud import trip_sharing as store
from app.schemas.trip_sharing import ConnectTripInput, ShareLinkInput, ShareTokenInput
from app.utils.auth import require_authenticated_user

router = APIRouter(tags=["trip sharing"])


@contextmanager
def sharing_response(response):
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Referrer-Policy"] = "no-referrer"
    try:
        yield
    except store.ShareUnavailable:
        raise HTTPException(
            status_code=404,
            detail="Shared trip is unavailable",
            headers={"Cache-Control": "no-store, private"},
        ) from None
    except store.ShareConflict as exc:
        raise HTTPException(
            status_code=409, detail=str(exc), headers={"Cache-Control": "no-store, private"}
        ) from None
    except psycopg2.Error:
        # Missing migration fails sharing alone; no startup DDL or global readiness change.
        raise HTTPException(
            status_code=503,
            detail="Trip sharing is temporarily unavailable",
            headers={"Cache-Control": "no-store, private"},
        ) from None


@router.get("/chats/{chat_id}/sharing")
def sharing_status(
    response: Response,
    chat_id: int = Path(gt=0, le=9007199254740991),
    user_id: str = Depends(require_authenticated_user),
):
    with sharing_response(response):
        return store.owner_status(user_id, chat_id)


@router.post("/chats/{chat_id}/sharing/link")
def create_link(
    value: ShareLinkInput,
    response: Response,
    chat_id: int = Path(gt=0, le=9007199254740991),
    user_id: str = Depends(require_authenticated_user),
):
    with sharing_response(response):
        return store.create_link(user_id, chat_id, value.expected_revision)


@router.delete("/chats/{chat_id}/sharing/link")
def stop_link(
    share_id: UUID,
    response: Response,
    chat_id: int = Path(gt=0, le=9007199254740991),
    user_id: str = Depends(require_authenticated_user),
):
    with sharing_response(response):
        return store.revoke(user_id, chat_id, share_id=share_id, link_only=True)


@router.delete("/chats/{chat_id}/sharing/members/{member_id}")
def remove_member(
    member_id: UUID,
    share_id: UUID,
    response: Response,
    chat_id: int = Path(gt=0, le=9007199254740991),
    user_id: str = Depends(require_authenticated_user),
):
    with sharing_response(response):
        return store.revoke(user_id, chat_id, share_id=share_id, member_id=member_id)


@router.delete("/chats/{chat_id}/sharing")
def stop_sharing(
    share_id: UUID,
    response: Response,
    chat_id: int = Path(gt=0, le=9007199254740991),
    user_id: str = Depends(require_authenticated_user),
):
    with sharing_response(response):
        return store.revoke(user_id, chat_id, share_id=share_id)


@router.post("/trip-sharing/view")
def view_link(value: ShareTokenInput, response: Response):
    with sharing_response(response):
        return store.view(token=value.token.get_secret_value())


@router.post("/trip-sharing/connect")
def connect_account(
    value: ConnectTripInput, response: Response, user_id: str = Depends(require_authenticated_user)
):
    with sharing_response(response):
        return store.connect(user_id, value.token.get_secret_value(), value.display_name)


@router.get("/shared-trips")
def list_connected(response: Response, user_id: str = Depends(require_authenticated_user)):
    with sharing_response(response):
        return store.list_connected(user_id)


@router.get("/shared-trips/{share_id}")
def view_connected(
    share_id: UUID, response: Response, user_id: str = Depends(require_authenticated_user)
):
    with sharing_response(response):
        return store.view(user_id=user_id, share_id=share_id)


@router.delete("/shared-trips/{share_id}/membership", status_code=204)
def leave_trip(
    share_id: UUID, response: Response, user_id: str = Depends(require_authenticated_user)
):
    with sharing_response(response):
        store.leave(user_id, share_id)
    return Response(status_code=204, headers={"Cache-Control": "no-store, private"})
