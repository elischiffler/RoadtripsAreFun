"""Car model matching should distinguish similar Mazda model numbers."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.routers import car_api


def _models(*names):
    items = "".join(f"<menuItem><value>{name}</value></menuItem>" for name in names)
    return SimpleNamespace(status_code=200, content=f"<menuItems>{items}</menuItems>".encode())


def test_cx5_does_not_match_cx50(monkeypatch):
    monkeypatch.setattr(
        car_api.requests,
        "get",
        lambda *args, **kwargs: _models("CX-5 4WD", "CX-50 4WD"),
    )
    assert car_api._get_full_model_name("CX-5", "Mazda", 2024) == "CX-5 4WD"
    assert car_api._get_full_model_name("cx5", "Mazda", 2024) == "CX-5 4WD"
    assert car_api._get_full_model_name("CX-50", "Mazda", 2024) == "CX-50 4WD"


def test_multiple_cx5_drivetrains_still_need_clarification(monkeypatch):
    monkeypatch.setattr(
        car_api.requests,
        "get",
        lambda *args, **kwargs: _models("CX-5 2WD", "CX-5 4WD", "CX-50 4WD"),
    )
    with pytest.raises(HTTPException) as exc:
        car_api._get_full_model_name("CX-5", "Mazda", 2024)
    assert exc.value.status_code == 400
    assert "CX-50" not in exc.value.detail


async def test_2024_mazda_cx5_details_are_verified(monkeypatch):
    calls = []

    def get(url, *, params=None, timeout=None):
        calls.append((url, params))
        if url.endswith("/menu/model"):
            return _models("CX-5 4WD", "CX-50 4WD")
        if url.endswith("/menu/options"):
            return _models("12345")
        return SimpleNamespace(status_code=200, content=b"<vehicle><comb08>28</comb08></vehicle>")

    monkeypatch.setattr(car_api.requests, "get", get)
    assert await car_api.get_car_details("CX-5", "Mazda", 2024) == {"combination_mpg": 28.0}
    assert calls[1][1] == {"model": "CX-5 4WD", "make": "Mazda", "year": 2024}
