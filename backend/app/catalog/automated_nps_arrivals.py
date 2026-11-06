"""Exact facility/address joins to typed Car sections on native-linked NPS pages.

This supplies approach evidence only. It never creates coordinates, hours,
parking capacity or a claim that an oversized vehicle can use ordinary parking.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from urllib.parse import urlsplit


def words(value):
    return " ".join(re.findall(r"[a-z0-9]+", str(value).casefold()))


class Sections(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.sections, self.heading, self.parts, self.ignore = [], None, [], 0
        self.prefix = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.ignore += 1
        if self.ignore:
            return
        if re.fullmatch("h[1-6]", tag):
            self.heading = tag
            self.parts = []
        elif self.heading is None and self.sections:
            self.sections[-1]["content"].append(" ")

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self.ignore:
            self.ignore -= 1
            return
        if self.ignore:
            return
        if tag == self.heading:
            self.sections.append({"heading": " ".join("".join(self.parts).split()), "content": []})
            self.heading = None
        elif self.heading is None and self.sections:
            self.sections[-1]["content"].append(" ")

    def handle_data(self, data):
        if self.ignore:
            return
        if self.heading is not None:
            self.parts.append(data)
        elif self.sections:
            self.sections[-1]["content"].append(data)
        else:
            self.prefix.append(data)


def match(data, facility, body, url):
    """Return an exact native identity/Car section, or fail with no guessed join."""
    from app.catalog.automated_nps import Hold, _prose_guard

    parsed = urlsplit(url)
    native_urls = [urlsplit(data.get("directionsURL", "")), urlsplit(facility.get("siteURL", ""))]
    if (
        parsed.scheme != "https"
        or parsed.hostname not in {"www.nps.gov", "nps.gov"}
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or not any(
            native.hostname in {"www.nps.gov", "nps.gov"}
            and parsed.path == native.path
            and native.scheme in {"http", "https"}
            and not native.query
            and not native.fragment
            for native in native_urls
        )
    ):
        raise Hold("arrival_page_not_linked_by_exact_native_facility_or_unit")
    if not 0 < len(body) <= 2 * 1024 * 1024:
        raise Hold("arrival_page_body_exceeds_ceiling")
    parser = Sections()
    parser.feed(body.decode("utf-8-sig"))
    titles = {words(facility.get("name", ""))}
    # Some native facility descriptions state an expanded formal title. It is
    # still an exact publisher-native identity, not a fuzzy name substitution.
    formal = re.match(r"^(.{8,180}?)\s+is located\b", facility.get("description", ""), re.I)
    if formal and set(words(facility["name"]).split()) <= set(words(formal[1]).split()):
        titles.add(words(formal[1]))
    address = facility.get("physical_address", {})
    address_parts = [
        words(address.get(key, "")) for key in ("line_1", "city", "state_code", "postal_code")
    ]
    if any(not value for value in address_parts):
        raise Hold("arrival_page_requires_complete_native_street_city_state_postal_identity")
    identities = [
        section
        for section in parser.sections
        if words(section["heading"]) in titles
        and all(
            re.search(
                r"(?:^| )" + re.escape(part) + r"(?: |$)", words(" ".join(section["content"]))
            )
            for part in address_parts
        )
    ]
    cars = [section for section in parser.sections if words(section["heading"]) == "car"]
    if (
        len(identities) != 1
        or len(cars) != 1
        or parser.sections.index(identities[0]) >= parser.sections.index(cars[0])
    ):
        raise Hold("arrival_page_facility_address_or_typed_car_section_ambiguous")
    between = parser.sections[
        parser.sections.index(identities[0]) + 1 : parser.sections.index(cars[0])
    ]
    if any(
        words(section["heading"])
        not in {"getting here by", "getting here", "directions", "transportation"}
        for section in between
    ):
        raise Hold("arrival_page_intervening_facility_scope_ambiguous")
    text = " ".join(" ".join(cars[0]["content"]).split())
    other_text = (
        " ".join(parser.prefix)
        + " "
        + " ".join(
            section["heading"] + " " + " ".join(section["content"])
            for section in parser.sections
            if section is not cars[0]
        )
    )
    if re.search(
        r"\bclos(?:ed|ures?)\b|no (?:car |public |visitor )?parking\b|no (?:public )?vehic|not accessible by car|parking (?:is )?(?:not available|prohibited)|\bprivate\b|employee.only|staff.only|reservation|\bpermits?\b|sunrise|sunset|\bdawn\b|\bdusk\b|open only|parking hours|entrance gate|access restriction|\b\d{1,2}:\d{2}\b|\b\d{1,2}(?::\d{2})?\s*[ap]\.?m\b",
        other_text,
        re.I,
    ):
        raise Hold("arrival_page_global_access_or_clock_qualification_requires_review")
    if (
        not 1 <= len(text) <= 4096
        or not re.search(r"\bparking lot\b", text, re.I)
        or len(re.findall(r"\b(?:take|turn|continue|exit)\b", text, re.I)) < 2
    ):
        raise Hold("arrival_page_lacks_literal_driving_approach_and_visitor_parking")
    _prose_guard(text)
    if re.search(
        r"\bprivate\b|employee|staff.only|permit|reservation|\bonly\b|not (?:for|accessible to) (?:cars|visitors)|\bhours?\b|\b\d{1,2}:\d{2}\b|\b\d{1,2}\s*[ap]\.?m\b",
        text,
        re.I,
    ):
        raise Hold("arrival_page_has_unresolved_access_or_clock_qualification")
    return {
        "facility_title": identities[0]["heading"],
        "native_address": {
            key: address[key] for key in ("line_1", "city", "state_code", "postal_code")
        },
        "car_section": text,
        "vehicle_scope": "Ordinary passenger-car approach only; all published RV, bus, oversized-vehicle and capacity qualifications remain source facts",
    }
