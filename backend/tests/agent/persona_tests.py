import json
import math

import pytest
from pydantic import ValidationError

from app.agent.persona import (
    ATTRIBUTE_KEYS,
    AccountPersona,
    PersonaWeightUpdate,
    default_weights,
    effective_weights,
    merge_weights,
)
from app.agent.trip_profile import TripProfile, TripProfileUpdate
from app.crud import memory_crud


def test_equal_default_and_example_normalizes():
    default = AccountPersona.default().weights
    assert set(default) == set(ATTRIBUTE_KEYS)
    assert math.isclose(sum(default.values()), 1)
    example = {key: 0.075 for key in ATTRIBUTE_KEYS}  # user's 1.05 example
    assert math.isclose(sum(example.values()), 1.05)
    assert AccountPersona(weights=example).weights == pytest.approx(default)


def test_partial_update_and_trip_override_precedence():
    account = AccountPersona.default().merged_with(PersonaWeightUpdate(weights={"food": 0.7}))
    assert account.weights["food"] > default_weights()["food"]
    trip = TripProfile().merged_with(TripProfileUpdate(persona_weights={"nature": 0.8}))
    assert (
        effective_weights(account.weights, trip.persona_weights)["nature"]
        > account.weights["nature"]
    )
    assert trip.to_json() and TripProfile.from_json(trip.to_json()) == trip
    assert effective_weights(account.weights) == account.weights
    assert math.isclose(sum(merge_weights(account.weights, {"food": 0.4}).values()), 1)


@pytest.mark.parametrize(
    "bad",
    [
        {"food": -1},
        {"food": float("nan")},
        {"food": float("inf")},
        {"food": 0},
        {"unknown": 1},
        {"food": True},
        {},
    ],
)
def test_invalid_supplied_weights_rejected(bad):
    with pytest.raises(ValidationError):
        PersonaWeightUpdate(weights=bad)
    with pytest.raises(ValidationError):
        TripProfileUpdate(persona_weights=bad)


class _FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.row = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def execute(self, sql, params):
        if "SELECT mem_value" in sql:
            user = params[0]
            self.row = {"mem_value": self.rows[user]} if user in self.rows else None
        elif "INSERT INTO chat_memory" in sql:
            self.rows[params[0]] = json.loads(params[3])

    def fetchone(self):
        return self.row


class _FakeConn:
    def __init__(self, rows):
        self.rows = rows

    def cursor(self, **_):
        return _FakeCursor(self.rows)

    def commit(self):
        pass

    def rollback(self):
        pass


def test_cross_chat_persona_isolated_by_user(monkeypatch):
    rows = {}
    monkeypatch.setattr(memory_crud, "ensure_memory_table", lambda: None)
    monkeypatch.setattr(memory_crud, "_get_conn", lambda: _FakeConn(rows))
    monkeypatch.setattr(memory_crud, "_put_conn", lambda _conn: None)
    store = memory_crud.MemoryCrudStore()
    assert store.load_account_persona("alice") == AccountPersona.default()
    updated = store.update_account_persona("alice", PersonaWeightUpdate(weights={"scenery": 0.9}))
    assert store.load_account_persona("alice") == updated
    assert store.load_account_persona("bob") == AccountPersona.default()
    store.update_account_persona("bob", PersonaWeightUpdate(weights={"food": 0.6}))
    assert store.load_account_persona("alice") == updated
    with pytest.raises(ValueError, match="user_id"):
        store.load_account_persona("")
