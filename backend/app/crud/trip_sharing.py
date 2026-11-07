"""Revocable capabilities and verified-account read membership, with no runtime DDL.

Shared reads use one read-only repeatable-read snapshot: authorization, trip JSON
and owner-scoped segments stay coherent while an owner edits/revokes/deletes.
Revocation prevents subsequent reads; already downloaded data cannot be recalled.
"""

import hashlib
import math
import re
import secrets
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from psycopg2.extras import RealDictCursor

from app.crud import chat_crud

MAX_MEMBERS = 32
LINK_DAYS = 30


class ShareUnavailable(Exception):
    pass


class ShareConflict(Exception):
    pass


@contextmanager
def transaction(*, readonly=False):
    conn = chat_crud._get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if readonly:
                cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        chat_crud._put_conn(conn)


def token_digest(token: str):
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        raise ShareUnavailable
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def _owner_trip(cur, owner_id, chat_id):
    cur.execute(
        "SELECT chat_data FROM chats WHERE user_id=%s AND chat_id=%s FOR UPDATE",
        (owner_id, str(chat_id)),
    )
    row = cur.fetchone()
    if not row:
        raise ShareUnavailable
    return row["chat_data"]


def owner_status(owner_id: str, chat_id: int):
    with transaction() as cur:
        _owner_trip(cur, owner_id, chat_id)
        return _status(cur, owner_id, chat_id)


def _status(cur, owner_id, chat_id):
    cur.execute(
        "SELECT id, token_digest IS NOT NULL AND link_expires_at>now() AS link_enabled, "
        "link_expires_at FROM trip_shares WHERE owner_id=%s AND chat_id=%s",
        (owner_id, str(chat_id)),
    )
    share = cur.fetchone()
    if not share:
        return {"share_id": None, "link_enabled": False, "link_expires_at": None, "members": []}
    cur.execute(
        "SELECT id, display_name, connected_at FROM trip_share_members WHERE share_id=%s "
        "ORDER BY connected_at, id",
        (share["id"],),
    )
    return {
        "share_id": share["id"],
        **{k: share[k] for k in ("link_enabled", "link_expires_at")},
        "members": cur.fetchall(),
    }


def create_link(owner_id: str, chat_id: int, revision: str):
    token = secrets.token_urlsafe(32)
    with transaction() as cur:
        trip = _owner_trip(cur, owner_id, chat_id)
        if chat_crud.chat_data_revision(trip) != revision:
            raise ShareConflict("Saved trip changed; reload before sharing")
        if not trip.get("route") or not trip.get("itinerary"):
            raise ShareConflict("Save a route and itinerary before sharing")
        cur.execute(
            "INSERT INTO trip_shares (id,owner_id,chat_id,token_digest,link_expires_at) "
            "VALUES (%s,%s,%s,%s,%s) ON CONFLICT (owner_id,chat_id) DO UPDATE "
            "SET token_digest=EXCLUDED.token_digest,link_expires_at=EXCLUDED.link_expires_at",
            (
                str(uuid4()),
                owner_id,
                str(chat_id),
                token_digest(token),
                datetime.now(UTC) + timedelta(days=LINK_DAYS),
            ),
        )
        return {**_status(cur, owner_id, chat_id), "token": token}


def revoke(
    owner_id: str, chat_id: int, *, share_id: UUID, link_only=False, member_id: UUID | None = None
):
    with transaction() as cur:
        _owner_trip(cur, owner_id, chat_id)
        cur.execute(
            "SELECT id FROM trip_shares WHERE owner_id=%s AND chat_id=%s FOR UPDATE",
            (owner_id, str(chat_id)),
        )
        current = cur.fetchone()
        if not current or str(current["id"]) != str(share_id):
            raise ShareConflict("Sharing changed; reload before changing access")
        if member_id:
            cur.execute(
                "DELETE FROM trip_share_members m USING trip_shares s WHERE m.share_id=s.id "
                "AND s.owner_id=%s AND s.chat_id=%s AND s.id=%s AND m.id=%s RETURNING m.id",
                (owner_id, str(chat_id), str(share_id), str(member_id)),
            )
            # A removed connection may already know the link. Stop it as well;
            # other connected accounts retain their independent membership.
            if not cur.fetchone():
                raise ShareConflict("Connection changed; reload before removing access")
            cur.execute(
                "UPDATE trip_shares SET token_digest=NULL,link_expires_at=NULL WHERE id=%s",
                (str(share_id),),
            )
        elif link_only:
            cur.execute(
                "UPDATE trip_shares SET token_digest=NULL,link_expires_at=NULL "
                "WHERE owner_id=%s AND chat_id=%s AND id=%s",
                (owner_id, str(chat_id), str(share_id)),
            )
        else:
            cur.execute(
                "DELETE FROM trip_shares WHERE owner_id=%s AND chat_id=%s AND id=%s",
                (owner_id, str(chat_id), str(share_id)),
            )
        return _status(cur, owner_id, chat_id)


def connect(user_id: str, token: str, display_name: str):
    digest = token_digest(token)
    with transaction() as cur:
        cur.execute(
            "SELECT id,owner_id FROM trip_shares WHERE token_digest=%s AND link_expires_at>now() "
            "FOR UPDATE",
            (digest,),
        )
        share = cur.fetchone()
        if not share:
            raise ShareUnavailable
        if share["owner_id"] == user_id:
            raise ShareConflict("You already own this trip")
        cur.execute(
            "SELECT count(*) AS total FROM trip_share_members WHERE share_id=%s", (share["id"],)
        )
        count = cur.fetchone()["total"]
        cur.execute(
            "SELECT id FROM trip_share_members WHERE share_id=%s AND account_id=%s",
            (share["id"], user_id),
        )
        existing = cur.fetchone()
        if not existing and count >= MAX_MEMBERS:
            raise ShareConflict("This trip has reached its connected account limit")
        cur.execute(
            "INSERT INTO trip_share_members (id,share_id,account_id,display_name) VALUES (%s,%s,%s,%s) "
            "ON CONFLICT (share_id,account_id) DO UPDATE SET display_name=EXCLUDED.display_name",
            (str(uuid4()), share["id"], user_id, display_name),
        )
        return {"share_id": share["id"]}


def leave(user_id: str, share_id: UUID):
    with transaction() as cur:
        cur.execute(
            "DELETE FROM trip_share_members WHERE share_id=%s AND account_id=%s",
            (str(share_id), user_id),
        )


def _text(value, limit=300):
    return value[:limit] if isinstance(value, str) else None


def _number(value):
    return value if type(value) in (int, float) and math.isfinite(value) else None


def _point(value):
    return (
        isinstance(value, list)
        and len(value) == 2
        and all(_number(v) is not None for v in value)
        and -180 <= value[0] <= 180
        and -90 <= value[1] <= 90
    )


def _mapping(value):
    return value if isinstance(value, dict) else {}


def _items(value):
    return value if isinstance(value, list) else []


def _project(cur, row):
    """Allowlist every output field; never return ChatData/ChatLog or source blobs."""
    data = _mapping(row["chat_data"])
    route = _mapping(data.get("route"))
    geometry = _mapping(route.get("geometry")).get("coordinates", [])
    if isinstance(geometry, str):
        cur.execute(
            "SELECT coords FROM route_segments WHERE user_id=%s AND chat_id=%s AND route_id=%s "
            "ORDER BY segment_id::int",
            (row["owner_id"], row["chat_id"], geometry),
        )
        geometry = [p for segment in cur.fetchall() for p in _items(segment["coords"])]
    points = [p for p in geometry if _point(p)] if isinstance(geometry, list) else []
    if len(points) > 4096:
        final_point = points[-1]
        points = points[:: math.ceil((len(points) - 1) / 4095)]
        if points[-1] != final_point:
            points.append(final_point)
    days = []
    for day in _items(data.get("itinerary"))[:100]:
        if not isinstance(day, dict):
            continue
        stops = []
        for stop in _items(day.get("stops"))[:300]:
            if not isinstance(stop, dict):
                continue
            stops.append(
                {
                    key: _text(stop.get(key))
                    for key in (
                        "name",
                        "time",
                        "type",
                        "kind",
                        "arrival_time",
                        "departure_time",
                        "timezone",
                        "meal_type",
                        "window_start",
                        "window_end",
                    )
                }
            )
        days.append({"date": _text(day.get("date")), "stops": stops})
    start = _text(_mapping(data.get("startConfirmed")).get("address"))
    end = _text(_mapping(data.get("endConfirmed")).get("address"))
    result = {
        "share_id": str(row["id"]),
        # A saved plan label, never evidence of eligibility or a trusted proof.
        "trip_mode": route.get("trip_mode")
        if route.get("trip_mode") in ("one_day", "overnight")
        else None,
        "start": start,
        "destination": end,
        "title": f"{start} → {end}" if start and end else "Shared trip",
        "route": {
            "coordinates": points,
            "distance": _number(route.get("distance")),
            "duration": _number(route.get("duration")),
        },
        "itinerary": days,
    }
    # A public content revision exposes no digest of hidden account/profile fields.
    return {**result, "revision": chat_crud.chat_data_revision(result)}


def view(*, token: str | None = None, user_id: str | None = None, share_id: UUID | None = None):
    with transaction(readonly=True) as cur:
        if token is not None:
            clause, args = "s.token_digest=%s AND s.link_expires_at>now()", (token_digest(token),)
        else:
            clause, args = (
                (
                    "s.id=%s AND EXISTS (SELECT 1 FROM trip_share_members m "
                    "WHERE m.share_id=s.id AND m.account_id=%s)"
                ),
                (str(share_id), user_id),
            )
        cur.execute(
            "SELECT s.id,s.owner_id,s.chat_id,c.chat_data FROM trip_shares s JOIN chats c "
            "ON c.user_id=s.owner_id AND c.chat_id=s.chat_id WHERE " + clause,
            args,
        )
        row = cur.fetchone()
        if not row:
            raise ShareUnavailable
        return _project(cur, row)


def list_connected(user_id: str):
    with transaction(readonly=True) as cur:
        cur.execute(
            "SELECT s.id,c.chat_data FROM trip_share_members m JOIN trip_shares s ON s.id=m.share_id "
            "JOIN chats c ON c.user_id=s.owner_id AND c.chat_id=s.chat_id WHERE m.account_id=%s "
            "ORDER BY m.connected_at DESC LIMIT 100",
            (user_id,),
        )
        result = []
        for row in cur.fetchall():
            data = _mapping(row["chat_data"])
            start = _text(_mapping(data.get("startConfirmed")).get("address"))
            end = _text(_mapping(data.get("endConfirmed")).get("address"))
            result.append(
                {
                    "share_id": row["id"],
                    "title": f"{start} → {end}" if start and end else "Shared trip",
                }
            )
        return result
