"""Exact native-linked visitor directions; synthetic facts, no provider requests."""

import copy

import pytest

from app.catalog.automated_nps import Hold
from app.catalog.automated_nps_arrivals import match

URL = "https://www.nps.gov/test/planyourvisit/directions.htm"
CAR = "Take exit 4 from Interstate 80. Turn onto Museum Road. Continue to the visitor parking lot."


def inputs():
    facility = {
        "name": "Example Museum Visitor Center",
        "description": "Example Museum Headquarters and Visitor Center is located in a public building.",
        "physical_address": {
            "line_1": "10 Museum Road",
            "city": "Example City",
            "state_code": "CA",
            "postal_code": "12345",
        },
        "siteURL": "https://www.nps.gov/test/visitor.htm",
    }
    data = {"directionsURL": URL}
    html = (
        "<h4>Example Museum Headquarters and Visitor Center</h4><p>10 Museum Road, Example City, CA 12345.</p><h3>Getting here by:</h3><h4><button>Car</button></h4><p>"
        + CAR
        + "</p><h4>Plane</h4><p>See the nearby airport.</p>"
    )
    return data, facility, html.encode()


def test_exact_published_formal_title_and_complete_address_join_typed_car_approach():
    data, facility, raw = inputs()
    original = copy.deepcopy(facility)
    value = match(data, facility, raw, URL)
    assert value["car_section"] == CAR
    assert value["facility_title"] == "Example Museum Headquarters and Visitor Center"
    assert value["native_address"] == facility["physical_address"]
    assert facility == original
    assert "hours" not in value and "coordinates" not in value


@pytest.mark.parametrize(
    "change",
    [
        "different_street",
        "different_city",
        "different_postal",
        "wrong_title",
        "wrong_section",
        "other_facility",
        "unlinked_url",
        "redirect_query",
    ],
)
def test_nearby_name_or_partial_address_never_supplies_facility_access(change):
    data, facility, raw = inputs()
    text, url = raw.decode(), URL
    if change == "different_street":
        text = text.replace("10 Museum Road", "210 Museum Road")
    if change == "different_city":
        text = text.replace("Example City", "Another City")
    if change == "different_postal":
        text = text.replace("12345", "912345")
    if change == "wrong_title":
        text = text.replace("Example Museum Headquarters", "Another Museum Headquarters")
    if change == "wrong_section":
        text = text.replace(">Car<", ">Bike<")
    if change == "other_facility":
        text = text.replace(
            "<h3>Getting here by:", "<h2>Other Visitor Center</h2><h3>Getting here by:"
        )
    if change == "unlinked_url":
        url = URL.replace("/test/", "/else/")
    if change == "redirect_query":
        url += "?redirect=somewhere"
    with pytest.raises(Hold):
        match(data, facility, text.encode(), url)


@pytest.mark.parametrize(
    "warning",
    [
        "Parking is closed.",
        "No public parking.",
        "Employee-only parking.",
        "Parking lot for buses only.",
        "Permit required.",
        "Parking is available 9:00am to 3:00pm.",
        "Private access.",
    ],
)
def test_negative_or_timed_car_qualifications_are_never_lost(warning):
    data, facility, raw = inputs()
    with pytest.raises(Hold):
        match(data, facility, raw.replace(CAR.encode(), (CAR + " " + warning).encode()), URL)


@pytest.mark.parametrize(
    "warning",
    [
        "The parking lot is closed.",
        "Permits are required.",
        "Parking hours are 9:00am to 3:00pm.",
        "Access restrictions apply.",
    ],
)
def test_global_footnotes_and_identity_section_restrictions_are_not_dropped(warning):
    data, facility, raw = inputs()
    with pytest.raises(Hold):
        match(
            data,
            facility,
            raw + ("<h3>Visitor information</h3><p>" + warning + "</p>").encode(),
            URL,
        )


def test_oversized_vehicle_qualifications_remain_exact_source_facts():
    data, facility, raw = inputs()
    warning = "The parking lot does not have designated parking for RV's or buses. Nearby city lots may be used when visitor center lot is full."
    value = match(data, facility, raw.replace(CAR.encode(), (CAR + " " + warning).encode()), URL)
    assert warning in value["car_section"]
    assert value["vehicle_scope"].startswith("Ordinary passenger-car")


@pytest.mark.parametrize(
    "warning", ["Parking is closed.", "Open 6am-9pm.", "Parking is open 06:00-21:00."]
)
@pytest.mark.parametrize("position", ["prefix", "suffix"])
def test_visible_alerts_before_first_heading_and_all_literal_clock_formats_are_retained(
    warning, position
):
    data, facility, raw = inputs()
    alert = ('<div class="alert">' + warning + "</div>").encode()
    with pytest.raises(Hold):
        match(data, facility, alert + raw if position == "prefix" else raw + alert, URL)


@pytest.mark.parametrize("heading", ["Parking Closed", "Parking hours 6am-9pm"])
def test_heading_only_access_qualifications_cannot_disappear(heading):
    data, facility, raw = inputs()
    with pytest.raises(Hold):
        match(data, facility, raw + ("<h3>" + heading + "</h3>").encode(), URL)
