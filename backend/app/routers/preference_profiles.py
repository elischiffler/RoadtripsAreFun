"""Settings APIs use verified subjects and return no inferred account persona."""

from uuid import UUID

import psycopg2
from fastapi import APIRouter, Depends, HTTPException, Response

from app.crud import preference_profiles as store
from app.schemas.preference_profiles import PreferenceProfile, PreferenceProfileInput
from app.utils.auth import require_authenticated_user

router = APIRouter(prefix="/preference-profiles", tags=["settings"])


def unavailable():
    return HTTPException(status_code=503, detail="Preference profiles are temporarily unavailable")


@router.get("", response_model=list[PreferenceProfile])
def list_profiles(response: Response, user_id: str = Depends(require_authenticated_user)):
    response.headers["Cache-Control"] = "no-store"
    try:
        return store.list_profiles(user_id)
    except psycopg2.Error:
        raise unavailable() from None


@router.put("/{profile_id}", response_model=PreferenceProfile)
def save_profile(
    profile_id: UUID,
    value: PreferenceProfileInput,
    response: Response,
    user_id: str = Depends(require_authenticated_user),
):
    response.headers["Cache-Control"] = "no-store"
    try:
        return store.save_profile(user_id, profile_id, value)
    except store.ProfileLimitReached:
        raise HTTPException(
            status_code=409, detail="Delete a saved profile before adding another"
        ) from None
    except psycopg2.Error:
        raise unavailable() from None


@router.delete("/{profile_id}", status_code=204)
def delete_profile(profile_id: UUID, user_id: str = Depends(require_authenticated_user)):
    try:
        store.delete_profile(user_id, profile_id)
    except psycopg2.Error:
        raise unavailable() from None
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
