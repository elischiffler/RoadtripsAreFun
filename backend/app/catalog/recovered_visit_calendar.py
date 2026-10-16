"""Offline, source-bound calendars for previously withheld Kaggle additions.

This companion enrichment never rewrites a catalog row or its original provenance.
Every acquired body is immutable and hash checked. Literal image readings are
limited to their dated source grids; original conflicting restrictions are retained
and conservatively intersected. Published hours never establish ticket inventory.
"""

import argparse
import calendar
import csv
import hashlib
import io
import json
import re
import zipfile
from copy import deepcopy
from datetime import date, datetime, timedelta
from pathlib import Path

from lxml import html

from app.catalog import market_visit_calendar
from app.routing.visit_calendar import Calendar

SCHEMA = "roadtrips-recovered-visit-calendars/1"
TRANSFORMATION = "new11-official-literals-2026-10-15-v1"
MAX_SOURCE_BYTES = 12 * 1024 * 1024
MAX_TOTAL_BYTES = 20 * 1024 * 1024

_REVIEWED_ROWS_PATH = "candidate-11-as-reviewed.json"
_REVIEWED_ROWS_SHA256 = "1adf51f421940c1a04c5ef369f27e27b4b613f91a002fde3ae813b0919c78162"
_SOURCES = {
    "301297-operator": {
        "body_path": "raw/301297-operator.bin",
        "source_url": "https://www.cambriafarmersmarket.com/",
        "snapshot_sha256": "c05c2904f694b974a07aa60756cda53ddda4d46de902d13f85e4b7e518d8c4cf",
        "checked_at": "2026-10-15T19:54:02.806396+00:00",
        "status": 200,
    },
    "308659-operator": {
        "body_path": "raw/308659-operator.bin",
        "source_url": "https://www.northcoastgrowersassociation.org/fortuna.html",
        "snapshot_sha256": "6f171a685c8ee28b54e5077d3e1c69e8396fd4359c789c0cdd15325bb11605a6",
        "checked_at": "2026-10-15T19:54:02.807078+00:00",
        "status": 200,
    },
    "308735-city": {
        "body_path": "raw/308735-city.bin",
        "source_url": "https://www.cityoflancasterca.org/our-city/departments-services/parks-recreation-arts/special-events/the-blvd-market",
        "snapshot_sha256": "21d346e32e71b9c4ab5980db7e02e710337f3ea78699f2ce85dbbfb397bb6e31",
        "checked_at": "2026-10-15T19:54:03.357083+00:00",
        "status": 403,
    },
    "Q5160318-dated-hours": {
        "body_path": "raw/Q5160318-dated-hours.bin",
        "source_url": "https://www.confusionhill.com/blog/2026/3/22/current-hours-10am-5pm-7-days-a-week",
        "snapshot_sha256": "54c96a20db14aeddb94ce8d131225ebda8e0e23be45186431223fb236f207f29",
        "checked_at": "2026-10-15T19:54:03.698683+00:00",
        "status": 200,
    },
    "Q14709151-calendar": {
        "body_path": "raw/Q14709151-calendar.bin",
        "source_url": "https://www.oakspark.com/roller-rink-hours",
        "snapshot_sha256": "32e3ae7dd7f64824c02ae6d56afec1deb311f8a6e7def4c1b7c83b3d36872f5b",
        "checked_at": "2026-10-15T19:54:04.156790+00:00",
        "status": 200,
    },
    "Q26267473-tour-admission": {
        "body_path": "raw/Q26267473-tour-admission.bin",
        "source_url": "https://preciousmomentschapel.org/pages/tickets",
        "snapshot_sha256": "fe0161ecf0c8534986074c176125cd418f3bea76eb351e3ef764fb58341651d1",
        "checked_at": "2026-10-15T19:54:04.165505+00:00",
        "status": 200,
    },
    "Q23994725-visit-current": {
        "body_path": "raw/Q23994725-visit-current.bin",
        "source_url": "https://fun-spot.com/kissimmee/plan-your-visit/",
        "snapshot_sha256": "4453c465c59d3da78165897cf98c6e91cb06bd4cbb5f04ce7f0a9f51299c2d1e",
        "checked_at": "2026-10-15T19:54:04.368792+00:00",
        "status": 200,
    },
    "301226-operator-final": {
        "body_path": "raw/301226-operator-final.bin",
        "source_url": "https://ecologycenter.org/food-farming/berkeley-farmers-markets/",
        "snapshot_sha256": "0de3b798c4e1211fb5c0083a6ef9a94e85a81c255f1bec0bb75aee5a348ef8dc",
        "checked_at": "2026-10-15T19:54:40.742788+00:00",
        "status": 200,
    },
    "Q131759816-calendar-1": {
        "body_path": "raw/Q131759816-calendar-1.bin",
        "source_url": "https://www.nascarspeedpark.com/wp-content/uploads/2026/07/1782913841793-ac04d2f7-f80e-4032-a14c-83f8022a87b4_3.jpg",
        "snapshot_sha256": "0d8bda4168918d66349b02c355aee21759bb7fd9b64f7299191de5f445407dfc",
        "checked_at": "2026-10-15T19:54:40.743333+00:00",
        "status": 200,
    },
    "Q131759816-calendar-2": {
        "body_path": "raw/Q131759816-calendar-2.bin",
        "source_url": "https://www.nascarspeedpark.com/wp-content/uploads/2026/09/1788275616966-884772b1-475c-4015-8622-5faa9da0c3b5_1.jpg",
        "snapshot_sha256": "8084e5c0fc44b1d85471ce1a3be5ac2edae8e95ab2e67d4792d1d5061e8a7877",
        "checked_at": "2026-10-15T19:54:40.743739+00:00",
        "status": 200,
    },
    "Q131759816-calendar-3": {
        "body_path": "raw/Q131759816-calendar-3.bin",
        "source_url": "https://www.nascarspeedpark.com/wp-content/uploads/2026/09/1788275616966-884772b1-475c-4015-8622-5faa9da0c3b5_2.jpg",
        "snapshot_sha256": "f7f819a737f7aea66ae5b12c3c24bad9138996c2539490b727d2d548b7a15fa0",
        "checked_at": "2026-10-15T19:54:40.967673+00:00",
        "status": 200,
    },
    "Q6386811-visitor-current": {
        "body_path": "raw/Q6386811-visitor-current.bin",
        "source_url": "https://www.kemahboardwalk.com/visitor-info",
        "snapshot_sha256": "cb4cde0f44c36ca73d1338dff2dc896a9ce0d6ec5fdc8c2e34d290c2ae70d33b",
        "checked_at": "2026-10-15T19:54:40.968227+00:00",
        "status": 200,
    },
    "Q14709151-october-calendar": {
        "body_path": "raw/Q14709151-october-calendar.bin",
        "source_url": "https://www.oakspark.com/pub/photo/October-2026-Rink-Hours.png",
        "snapshot_sha256": "c21c4f78f2bca18fc59804085044a9f83a093d48e25f40293f50e795e8f9b5ff",
        "checked_at": "2026-10-15T19:55:05.426588+00:00",
        "status": 200,
    },
    "Q14709151-november-calendar": {
        "body_path": "raw/Q14709151-november-calendar.bin",
        "source_url": "https://www.oakspark.com/pub/photo/November-2026-Rink-Hours.png",
        "snapshot_sha256": "1b2e4ba1340ac092c6e43da1384e13481af4ad6c5348f0dccda310f83ad9f44d",
        "checked_at": "2026-10-15T19:55:05.427082+00:00",
        "status": 200,
    },
    "Q6386811-public-hours-embed-valid": {
        "body_path": "raw/Q6386811-public-hours-embed-valid.bin",
        "source_url": "https://knowledgetags.yextapis.com/embed?key=CJQ7xGfq6XMwvkN9zn5QfHA15ogpb981bDSY6krUGAdS37pMWT1-6n-pTaFFGEP6&account_id=me&entity_id=KBWK&locale=en&v=20210504",
        "snapshot_sha256": "1b73a7e32523a4d91d1e81b69a7b8b182430ec7867294e1f7df2311d5869d010",
        "checked_at": "2026-10-15T19:55:54.119999+00:00",
        "status": 200,
    },
    "Q23994725-calendar-display-script": {
        "body_path": "raw/Q23994725-calendar-display-script.bin",
        "source_url": "https://fun-spot.com/wp-content/plugins/calendar-anything-1/assets/js/codemine-calendar.js",
        "snapshot_sha256": "026061ff4b7c716b615e2d9162710fa3691c076753bf4b3da5b9a0742b9b6e95",
        "checked_at": "2026-10-15T19:56:24.364995+00:00",
        "status": 200,
    },
    "Q23994725-title-date-conflict": {
        "body_path": "raw/Q23994725-title-date-conflict.bin",
        "source_url": "https://fun-spot.com/cmcal_events/october-21-2027/",
        "snapshot_sha256": "26f2468e8c6a9fca6b2d95c4f2239943821d816ed5d536a266c83c8c44a5249b",
        "checked_at": "2026-10-15T19:56:24.366096+00:00",
        "status": 200,
    },
    "308993-operator": {
        "body_path": "raw/308993-operator.bin",
        "source_url": "https://weavervillefarmersmarket.org/",
        "snapshot_sha256": "a75efb2b8ec409bac4225e7ed2f24c19b72e9f36396ed0ca1e5f28cdd329db40",
        "checked_at": "2026-10-15T19:57:13.668816+00:00",
        "status": 200,
    },
    "Q5160318-attractions-current": {
        "body_path": "raw/Q5160318-attractions-current.bin",
        "source_url": "https://www.confusionhill.com/attractions",
        "snapshot_sha256": "de34ae58c9339dcdda273bea231311cb54b568b169c102af9be7f2766d499ae2",
        "checked_at": "2026-10-15T19:57:13.881243+00:00",
        "status": 200,
    },
    "Q26267473-visit-current": {
        "body_path": "raw/Q26267473-visit-current.bin",
        "source_url": "https://preciousmomentschapel.org/pages/visit",
        "snapshot_sha256": "1e7376092db74db141683e475d1f80ab274990140faf3da41e2e2e5a373a3cdd",
        "checked_at": "2026-10-15T19:57:14.291070+00:00",
        "status": 200,
    },
    "market-archive": {
        "body_path": "market/harvestlymarkets--us-farmers-markets-by-state-2026-v4.zip",
        "source_url": "https://www.kaggle.com/api/v1/datasets/download/harvestlymarkets/us-farmers-markets-by-state-2026?datasetVersionNumber=4",
        "snapshot_sha256": "dea363d2a400f008fa28c933dc6816af2bb7166bea5e5795adc9ec79989d30b1",
        "checked_at": "2026-10-15T17:47:24.598237+00:00",
        "status": 200,
    },
    "market-canonical": {
        "body_path": "market/canonical-us-farmers-markets-2026.csv",
        "source_url": "https://harvestlymarkets.com/data/us-farmers-markets-2026.csv",
        "snapshot_sha256": "76b5e9887643a7cb82d91c89682d52c5c531c88d74fc9e2bed3ef79146039514",
        "checked_at": "2026-10-15T17:48:41.803170+00:00",
        "status": 200,
    },
    "market-cdfa": {
        "body_path": "existing-review-evidence/CA-official-markets-pinned.pdf",
        "source_url": "https://www.cdfa.ca.gov/is/docs/CurrentMrktsCounty.pdf",
        "snapshot_sha256": "846d121f3e38ec1ee5f83c95c2260a6ae3857b11b3ad88d31ba9dc548fb06742",
        "checked_at": "2026-10-15T17:48:42.365412+00:00",
        "status": 200,
    },
    "market-cdfa_rows": {
        "body_path": "market/cdfa-official-rows.json",
        "source_url": "https://www.cdfa.ca.gov/is/docs/CurrentMrktsCounty.pdf",
        "snapshot_sha256": "59475ba6d047af8944d99a1c1aa8dcd8297ccfdc5e49dff27f1ff972edff8163",
        "checked_at": "2026-10-15T17:48:42.365412+00:00",
        "status": 200,
    },
    "confusion-faq": {
        "body_path": "existing-review-evidence/Confusion-Hill-FAQ.html",
        "source_url": "https://www.confusionhill.com/faqs",
        "snapshot_sha256": "c1f8a864f9942ab88a51e490d1b30b2250308d5ee3f787f671c9736f614e6f77",
        "checked_at": "2026-10-15T17:52:37.012213+00:00",
        "status": 200,
    },
    "nascar-footer": {
        "body_path": "existing-review-evidence/NASCAR-hours-footer.html",
        "source_url": "https://www.nascarspeedpark.com/",
        "snapshot_sha256": "e003cf8f48d19d4fdcedaed3ea7eb938c60005cf77173a2f2e875684be56163c",
        "checked_at": "2026-10-15T17:51:26.759531+00:00",
        "status": 200,
    },
    "nascar-calendar-links": {
        "body_path": "existing-review-evidence/NASCAR-dated-calendar-links.html",
        "source_url": "https://www.nascarspeedpark.com/hours-and-info/",
        "snapshot_sha256": "d1010031d55eaf6a1270650b2bee9dc071466a5e7e91b1cf7b867058fc38eb4e",
        "checked_at": "2026-10-15T17:52:38.538947+00:00",
        "status": 200,
    },
    "original-Q5160318-0": {
        "body_path": "operator/Q5160318-0.html",
        "source_url": "https://www.confusionhill.com/attractions",
        "snapshot_sha256": "de34ae58c9339dcdda273bea231311cb54b568b169c102af9be7f2766d499ae2",
        "checked_at": "2026-10-15T17:52:36.951515+00:00",
        "status": 200,
    },
    "original-Q5160318-1": {
        "body_path": "operator/Q5160318-1.html",
        "source_url": "https://www.confusionhill.com/contact",
        "snapshot_sha256": "7b3ec375a960c0a9d0b551c17924fb61b3a897117f82efb897a8f8a6167cfe85",
        "checked_at": "2026-10-15T17:52:36.754325+00:00",
        "status": 200,
    },
    "original-Q5160318-2": {
        "body_path": "operator/Q5160318-2.html",
        "source_url": "https://www.confusionhill.com/history",
        "snapshot_sha256": "68e5f4b3e1b9cd96072f78b23978f6469cc98fb3d56b10ce97f44c23f8b3fa93",
        "checked_at": "2026-10-15T17:52:36.813872+00:00",
        "status": 200,
    },
    "original-Q5160318-3": {
        "body_path": "operator/Q5160318-3.html",
        "source_url": "https://www.confusionhill.com/faqs",
        "snapshot_sha256": "c1f8a864f9942ab88a51e490d1b30b2250308d5ee3f787f671c9736f614e6f77",
        "checked_at": "2026-10-15T17:52:37.012213+00:00",
        "status": 200,
    },
    "original-Q5160318-4": {
        "body_path": "operator/Q5160318-4.html",
        "source_url": "https://www.confusionhill.com/blog",
        "snapshot_sha256": "3ae43bd6bfe12f064c8d5192eca3146fe455e9a26f897f088dedf58913f2daff",
        "checked_at": "2026-10-15T17:52:37.026738+00:00",
        "status": 200,
    },
    "original-Q23994725-0": {
        "body_path": "operator/Q23994725-0.html",
        "source_url": "https://fun-spot.com/kissimmee/plan-your-visit/",
        "snapshot_sha256": "aa861e71fd06b263ab89aff597fd90e90045f4c01d824228ac230dee6531df25",
        "checked_at": "2026-10-15T17:52:39.623501+00:00",
        "status": 200,
    },
    "original-Q23994725-1": {
        "body_path": "operator/Q23994725-1.html",
        "source_url": "https://fun-spot.com/policies-and-frequently-asked-questions/",
        "snapshot_sha256": "112386944bf832ae72f87a66de27e94315e77fce2cea18a767f58cb53fc4f8ab",
        "checked_at": "2026-10-15T17:52:37.813059+00:00",
        "status": 200,
    },
    "original-Q6386811-0": {
        "body_path": "operator/Q6386811-0.html",
        "source_url": "https://www.kemahboardwalk.com/visitor-info",
        "snapshot_sha256": "d5df06671823eab6f83c4e4c1b6d06c0829d59b99433ff9282b659800ef9bf7d",
        "checked_at": "2026-10-15T17:52:38.078793+00:00",
        "status": 200,
    },
    "original-Q6386811-1": {
        "body_path": "operator/Q6386811-1.html",
        "source_url": "https://www.kemahboardwalk.com",
        "snapshot_sha256": "98b0317c1daef5159457a85c6e98e0fe257a0bf8955e8b9d5e18691d957c87df",
        "checked_at": "2026-10-15T17:51:25.409171+00:00",
        "status": 200,
    },
    "original-Q131759816-0": {
        "body_path": "operator/Q131759816-0.html",
        "source_url": "https://www.nascarspeedpark.com/",
        "snapshot_sha256": "e003cf8f48d19d4fdcedaed3ea7eb938c60005cf77173a2f2e875684be56163c",
        "checked_at": "2026-10-15T17:51:26.759531+00:00",
        "status": 200,
    },
    "original-Q131759816-1": {
        "body_path": "operator/Q131759816-1.html",
        "source_url": "https://www.nascarspeedpark.com/hours-and-info/",
        "snapshot_sha256": "d1010031d55eaf6a1270650b2bee9dc071466a5e7e91b1cf7b867058fc38eb4e",
        "checked_at": "2026-10-15T17:52:38.538947+00:00",
        "status": 200,
    },
    "original-Q14709151-0": {
        "body_path": "operator/Q14709151-0.html",
        "source_url": "https://www.oakspark.com/",
        "snapshot_sha256": "5a20f67af8dd3c2673b6b9c5cb93f23b8b7ee348de6d9563aca73521bc25680c",
        "checked_at": "2026-10-15T17:51:26.895011+00:00",
        "status": 200,
    },
    "original-Q14709151-1": {
        "body_path": "operator/Q14709151-1.html",
        "source_url": "https://www.oakspark.com/roller-skating-rink",
        "snapshot_sha256": "e0ef67920cb3e64338595cf10a90f575d202a2fc70d8f9268760b434e4dd46a4",
        "checked_at": "2026-10-15T17:52:39.170240+00:00",
        "status": 200,
    },
    "original-Q14709151-2": {
        "body_path": "operator/Q14709151-2.html",
        "source_url": "https://www.oakspark.com/directions",
        "snapshot_sha256": "249e113fddd93c466e6f3ec7cec01a745da4da920bc0366d31b7cebad53298ce",
        "checked_at": "2026-10-15T17:52:39.312727+00:00",
        "status": 200,
    },
    "original-Q26267473-0": {
        "body_path": "operator/Q26267473-0.html",
        "source_url": "https://preciousmomentschapel.org/",
        "snapshot_sha256": "576b12f16dfc06f11c7da89612bb8715f12f6f9c1f0034bd292d0a977d8cc0f1",
        "checked_at": "2026-10-15T17:51:28.852700+00:00",
        "status": 200,
    },
    "original-Q26267473-1": {
        "body_path": "operator/Q26267473-1.html",
        "source_url": "https://preciousmomentschapel.org/pages/visit",
        "snapshot_sha256": "1bce3225f3163e4429c4ae0b3b1866fadab284f3cbadc98740957e77f8a9205a",
        "checked_at": "2026-10-15T17:52:40.481818+00:00",
        "status": 200,
    },
}


def _read(root, relative, expected):
    if not isinstance(relative, str) or not re.fullmatch(r"[A-Za-z0-9_./-]+", relative):
        raise ValueError("Invalid recovery source path")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("Recovery source is missing or escapes source root")
    if not 0 < path.stat().st_size <= MAX_SOURCE_BYTES:
        raise ValueError("Recovery source exceeds byte bound")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("Recovery source checksum mismatch: " + relative)
    return raw


def _load(root, reviewed_on):
    if type(reviewed_on) is not date:
        raise ValueError("An explicit review date is required")
    bodies, total = {}, 0
    for key, receipt in _SOURCES.items():
        checked = datetime.fromisoformat(receipt["checked_at"])
        if checked.utcoffset() is None or not 0 <= (reviewed_on - checked.date()).days <= 30:
            raise ValueError("Recovery source acquisition is future dated or stale")
        body = _read(root, receipt["body_path"], receipt["snapshot_sha256"])
        total += len(body)
        if total > MAX_TOTAL_BYTES:
            raise ValueError("Recovery aggregate source byte bound exceeded")
        bodies[key] = body
    rows = json.loads(_read(root, _REVIEWED_ROWS_PATH, _REVIEWED_ROWS_SHA256))
    if len(rows) != 11 or len({row["source_id"] for row in rows}) != 11:
        raise ValueError("Reviewed recovery identities differ")
    return bodies, {row["source_id"].split(":")[-1]: row for row in rows}, total


def _visible(raw):
    document = html.fromstring(raw)
    for element in document.xpath("//script|//style|//noscript"):
        element.drop_tree()
    return " ".join(document.text_content().split())


def _require(bodies, key, *literals):
    text = _visible(bodies[key])
    if any(literal not in text for literal in literals):
        raise ValueError("Required recovery literal missing: " + key)


def _constraint(key, locator, facts, *, interpretation=None):
    result = {
        **{k: v for k, v in _SOURCES[key].items() if k != "status"},
        "extraction_locator": locator,
        "literal_facts": facts,
    }
    if interpretation:
        result["interpretation"] = interpretation
    return result


def _window(opens, closes, weekdays=None, *, end_day_offset=0):
    result = {"opens": opens, "closes": closes, "end_day_offset": end_day_offset}
    if weekdays is not None:
        result["weekdays"] = weekdays
    return result


def _calendar(weekly=(), seasons=(), overrides=()):
    return {
        "schema_version": "roadtrips-source-visit-calendar/1",
        "weekly_windows": list(weekly),
        "seasons": list(seasons),
        "date_overrides": list(overrides),
        "fixed_starts": [],
        "unknown_reasons": [],
    }


def _entry(ident, calendar_value, constraints, scope, **details):
    calendar_value["source_receipts"] = deepcopy(constraints)
    Calendar.model_validate(calendar_value)
    return {
        "source_id": ident,
        "source_visit_calendar": calendar_value,
        "source_constraints": constraints,
        "transformation": {
            "adapter": TRANSFORMATION,
            "scope": scope,
            "rule": "Conservative intersection of separately attributed source restrictions",
            "ticket_availability": "unknown",
            "original_catalog_row_and_provenance_modified": False,
            **details,
        },
    }


def _csv(raw):
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
    if len(rows) > 10000 or len({row["listing_id"] for row in rows}) != len(rows):
        raise ValueError("Invalid bounded market identity feed")
    return {row["listing_id"]: row for row in rows}


def _market_sources(bodies, reviewed):
    with zipfile.ZipFile(io.BytesIO(bodies["market-archive"])) as archive:
        member = archive.getinfo("us-farmers-markets-2026.csv")
        if member.file_size > 5 * 1024 * 1024:
            raise ValueError("Native market CSV exceeds byte bound")
        native = _csv(archive.read(member))
    canonical = _csv(bodies["market-canonical"])
    agency = json.loads(bodies["market-cdfa_rows"])
    if agency["sha256"] != _SOURCES["market-cdfa"]["snapshot_sha256"] or agency["anomalies"]:
        raise ValueError("Agency extraction is not bound to source PDF")
    verified = {}
    for ident in ("301226", "301297", "308659", "308735", "308993"):
        groups = reviewed[ident]["provenance"][0]["published_access_facts"]
        if len(groups) != 3:
            raise ValueError("Original market feed constraints missing")
        for group, source, key in zip(
            groups[:2], (native[ident], canonical[ident]), ("market-archive", "market-canonical")
        ):
            if (
                group["snapshot_sha256"] != _SOURCES[key]["snapshot_sha256"]
                or group["fields"]["season"] != source["season"]
                or group["fields"]["city"] != source["city"]
                or group["fields"]["location"] != source["street"]
            ):
                raise ValueError("Original market restriction differs from raw feed")
        fact = groups[2]
        matched = [
            row
            for row in agency["rows"]
            if all(row[k] == fact[k] for k in ("pdf_page", "table_index", "row_index"))
        ]
        if len(matched) != 1 or any(
            matched[0][k] != fact["fields"][k] for k in ("days", "hours", "months", "location")
        ):
            raise ValueError("Original agency market restriction differs from pinned extraction")
        verified[ident] = deepcopy(groups)
    return verified


def _market_constraints(ident, facts):
    result = []
    for group, key in zip(facts, ("market-archive", "market-canonical", "market-cdfa")):
        locator = {"kind": "csv-record", "listing_id": ident}
        if key == "market-archive":
            locator["archive_member"] = "us-farmers-markets-2026.csv"
        elif key == "market-cdfa":
            locator = {
                "kind": "pdf-table-cell",
                **{k: group[k] for k in ("pdf_page", "table_index", "row_index")},
                "pinned_extraction_path": _SOURCES["market-cdfa_rows"]["body_path"],
                "pinned_extraction_sha256": _SOURCES["market-cdfa_rows"]["snapshot_sha256"],
            }
        result.append(_constraint(key, locator, group["fields"]))
    return result


def _market(ident, bodies, facts):
    facts = deepcopy(facts)
    originals = deepcopy(facts)
    constraints = _market_constraints(ident, originals)
    if ident == "301226":
        key = "301226-operator-final"
        literal = "South Berkeley Tuesday: 2:00 PM - 6:30 PM"
        _require(bodies, key, literal)
        expected = "Year-round · Tuesdays 2:00–6:30 PM"
        if facts[1]["fields"]["season"] != expected:
            raise ValueError("Unsupported South Berkeley canonical restriction")
        facts[1]["fields"]["season"] = "Year-round Tuesdays 2:00pm - 6:30pm"
        # Both literal endpoints are independently explicit in the operator and CDFA.
        explanation = "Canonical shared PM matches explicit operator 2:00 PM and CDFA 2pm."
    elif ident == "308659":
        key = "308659-operator"
        literal = "Tuesdays: 3-6pm, May - End of October"
        _require(bodies, key, literal, "10th St between Main and L St")
        for fact in facts[:2]:
            if fact["fields"]["season"] != "Tuesdays 3:00–6:00pm":
                raise ValueError("Unsupported Fortuna native/canonical restriction")
            fact["fields"]["season"] = "Tuesdays 3:00pm - 6:00pm"
        explanation = "Native/canonical shared PM matches explicit CDFA 3pm - 6pm."
    elif ident == "301297":
        key = "301297-operator"
        literal = "Friday afternoons"
        _require(
            bodies,
            key,
            literal,
            "Summer hours are 2:30 – 5:30 pm (May - September)",
            "close at 5:00 pm during the winter (October - April)",
        )
        if facts[2]["fields"]["hours"] != "2:30 -\n5:30pm,\n5pm\nwinter":
            raise ValueError("Unsupported Cambria agency restriction")
        # The operator explicitly says afternoons. Intersect both closing variants
        # for every date rather than inventing a source-neutral winter boundary.
        facts[2]["fields"]["hours"] = "2:30pm - 5:00pm"
        explanation = "Explicit Friday afternoons sets PM; intersect summer 17:30 and winter 17:00."
        constraints.append(
            _constraint(
                key,
                {"kind": "visible-text", "contains": "Summer hours"},
                {
                    "summer": "2:30 – 5:30 pm (May - September)",
                    "winter": "close at 5:00 pm during the winter (October - April)",
                    "weekday_context": literal,
                },
                interpretation="Conservative common window 14:30–17:00; no seasonal variant discarded.",
            )
        )
    elif ident == "308993":
        key = "308993-operator"
        literal = "2026 Market Season May 20th – Oct 14th Wednesdays 4pm – 7pm"
        _require(bodies, key, literal)
        if facts[2]["fields"]["hours"] != "4 - 7pm":
            raise ValueError("Unsupported Weaverville agency restriction")
        facts[2]["fields"]["hours"] = "4pm - 7pm"
        facts.append(
            {
                "feed": "official_visitor_facts",
                **{
                    "source_url": _SOURCES[key]["source_url"],
                    "snapshot_sha256": _SOURCES[key]["snapshot_sha256"],
                    "checked_at": _SOURCES[key]["checked_at"],
                },
                "fields": {
                    "days": "Wednesdays",
                    "hours": "4pm - 7pm",
                    "start_date": "2026-05-20",
                    "end_date": "2026-10-14",
                },
            }
        )
        explanation = "Intersect native/canonical May–October, CDFA May20–Oct21 and dated operator May20–Oct14."
    else:
        raise ValueError("Market has no admitted recovery")
    constraints.append(
        _constraint(
            key,
            {"kind": "visible-text", "contains": literal},
            {"literal": literal},
            interpretation=explanation,
        )
    )
    cal = market_visit_calendar.build(facts)
    if cal["unknown_reasons"]:
        raise ValueError("Market source intersection unresolved: " + ident)
    return _entry(
        "usda-market:" + ident,
        cal,
        constraints,
        "Published recurring market only; all original feed seasons participate",
        literal_normalization=explanation,
        derived_restrictions=[fact["fields"] for fact in facts],
    )


def _original_park_constraints(ident, rows, bodies):
    facts = next(p["source_facts"] for p in rows[ident]["provenance"] if "source_facts" in p)
    result = []
    for index, fact in enumerate(facts):
        key = f"original-{ident}-{index}"
        if fact["snapshot_sha256"] != _SOURCES[key]["snapshot_sha256"]:
            raise ValueError("Original operator source binding differs")
        result.append(
            _constraint(
                key,
                {"kind": "retained-operator-page", "prior_review": "PR47"},
                {"restrictions": fact["restrictions"]},
                interpretation="Original restriction retained; newly verified clocks resolve the earlier missing-calendar hold only.",
            )
        )
    return result


def _confusion(bodies, rows):
    ident = "Q5160318"
    constraints = _original_park_constraints(ident, rows, bodies)
    key = "Q5160318-attractions-current"
    literal = "HOURSWE OPEN 7 days a week, 10am-5pmWORLD-FAMOUS GRAVITY HOUSE IS OPEN!"
    _require(bodies, key, literal, "Train Ride is closed for the season")
    _require(bodies, "confusion-faq", "The GIFT SHOP and GRAVITY HOUSE are OPEN ALL YEAR!")
    _require(bodies, "Q5160318-dated-hours", "March 22, 2026", "10am till 5pm,7 days a week")
    constraints.extend(
        [
            _constraint(
                key,
                {"kind": "visible-text", "section": "HOURS / GRAVITY HOUSE"},
                {"hours": literal, "train": "Train Ride is closed for the season"},
                interpretation="Gravity House/general attraction hours only; do not transfer seasonal train or Snack Bar access.",
            ),
            _constraint(
                "confusion-faq",
                {"kind": "visible-text", "question": 11},
                {"season": "The GIFT SHOP and GRAVITY HOUSE are OPEN ALL YEAR!"},
            ),
            _constraint(
                "Q5160318-dated-hours",
                {"kind": "dated-announcement", "publication_date": "2026-03-22"},
                {"hours": "10am till 5pm,7 days a week"},
            ),
        ]
    )
    return _entry(
        "wikidata-park:" + ident,
        _calendar([_window("10:00", "17:00", list(range(7)))]),
        constraints,
        "Gravity House self-guided visit; Mountain Train excluded",
    )


def _precious(bodies, rows):
    ident, key = "Q26267473", "Q26267473-visit-current"
    constraints = _original_park_constraints(ident, rows, bodies)
    _require(
        bodies,
        key,
        "Open 9am-5pm Daily",
        "Guided or Self Tours, allow 1-3 hours",
        "Admission tickets available on-site",
        "the last Chapel tour is at 4 PM.",
    )
    constraints.append(
        _constraint(
            key,
            {"kind": "visible-text", "sections": ["Know Hours & Admission", "Tours & Admission"]},
            {
                "hours": "Open 9am-5pm Daily",
                "visit_modes": "Guided or Self Tours, allow 1-3 hours",
                "last_chapel_tour": "the last Chapel tour is at 4 PM.",
            },
            interpretation="General/self-guided cultural access only. Full two-hour dwell ends by17:00 and starts by15:00; no guided departure or ticket inventory promised.",
        )
    )
    return _entry(
        "wikidata-park:" + ident,
        _calendar([_window("09:00", "17:00", list(range(7)))]),
        constraints,
        "General admission and self-guided Chapel, museum and gardens; guided tour availability unknown",
    )


# Literal readings of the pinned source-native grids. Values are closing hours;
# every positive grid cell literally opens11AM. None is an explicit CLOSED cell.
_NASCAR_CLOSES = {
    "2026-10": "19 20 22 20 20 20 20 20 22 22 22 21 20 20 20 21 22 20 19 19 19 19 20 22 20 19 19 X X 20 21",
    "2026-11": "20 19 19 X X 20 21 20 19 19 X X 20 21 20 X X X X 20 21 20 20 20 20 X 21 21 20 X",
    "2026-12": "X X X 19 20 19 X X X X 19 20 19 X X X X 19 20 20 20 20 20 X X 22 21 21 21 21 21",
}
_FOOTER = [
    ("Monday 11:00 AM – 9:00 PM", "21:00"),
    ("Tuesday 11:00 AM – 8:00 PM", "20:00"),
    ("Wednesday 11:00 AM – 8:00 PM", "20:00"),
    ("Thursday 11:00 AM – 8:00 PM", "20:00"),
    ("Friday 11:00 AM – 9:00 PM", "21:00"),
    ("Saturday 11:00 AM – 10:00 PM", "22:00"),
    ("Sunday 11:00 AM – 10:00 PM", "22:00"),
]


def _nascar(bodies, rows):
    ident = "Q131759816"
    constraints = _original_park_constraints(ident, rows, bodies)
    _require(bodies, "nascar-footer", *(literal for literal, _ in _FOOTER))
    page = html.fromstring(bodies["nascar-calendar-links"])
    overrides = []
    for index, (month, encoded) in enumerate(_NASCAR_CLOSES.items(), 1):
        key = f"Q131759816-calendar-{index}"
        linked = page.xpath("//img[@src=$url]", url=_SOURCES[key]["source_url"])
        if len(linked) != 1 or linked[0].get("alt") not in {"OCT26", "NOV. 26", "DEC. 26"}:
            raise ValueError("Dated image calendar link/year binding missing")
        year, number = map(int, month.split("-"))
        closes = encoded.split()
        if len(closes) != calendar.monthrange(year, number)[1]:
            raise ValueError("Image transcription day count differs")
        cells = []
        offset = (date(year, number, 1).weekday() + 1) % 7
        for day, end in enumerate(closes, 1):
            date_value = date(year, number, day)
            grid_index = offset + day - 1
            cells.append(
                {
                    "date": date_value.isoformat(),
                    "grid_row": grid_index // 7,
                    "grid_column_sunday_zero": grid_index % 7,
                    "literal": "CLOSED" if end == "X" else f"11AM-{int(end) - 12}PM",
                }
            )
            # Monthly and weekly variants remain distinct. Take the restrictive
            # closing clock, never silently replace the source footer with an image.
            windows = []
            if end != "X":
                close = min(end + ":00", _FOOTER[date_value.weekday()][1])
                windows = [_window("11:00", close)]
            overrides.append({"date": date_value.isoformat(), "windows": windows})
        constraints.append(
            _constraint(
                key,
                {
                    "kind": "manually-read-image-calendar",
                    "literal_month_heading": calendar.month_name[number] + " ’26",
                    "columns": "Sunday through Saturday",
                    "grid_upper_left_pixels": [34, 291],
                    "grid_cell_pitch_pixels": [104, 104],
                    "gateway_body_path": _SOURCES["nascar-calendar-links"]["body_path"],
                    "gateway_snapshot_sha256": _SOURCES["nascar-calendar-links"]["snapshot_sha256"],
                    "image_alt": linked[0].get("alt"),
                },
                {
                    "dated_grid_cells": cells,
                    "hours_qualification": "subject to change without notice",
                },
                interpretation="Manual literal grid reading pinned to exact image hash; effective clocks intersect the prior weekly footer.",
            )
        )
    constraints.append(
        _constraint(
            "nascar-footer",
            {"kind": "visible-text", "section": "weekly opening hours"},
            {"weekly_hours": [literal for literal, _ in _FOOTER]},
        )
    )
    return _entry(
        "wikidata-park:" + ident,
        _calendar(overrides=overrides),
        constraints,
        "General SpeedPark hours; only explicitly dated October–December2026 cells",
        transcription="Pinned original images, exact month/year,92 indexed cells; source and effective closes retained separately",
    )


_OAKS_GENERAL = {
    0: [],
    1: [("15:00", "17:00")],
    2: [("15:00", "17:00"), ("19:00", "21:30")],
    3: [("15:00", "17:00"), ("19:00", "21:30")],
    4: [("13:00", "17:00"), ("19:00", "22:30")],
    5: [("13:00", "17:00"), ("19:00", "22:30")],
    6: [("13:00", "17:00"), ("19:00", "21:30")],
}
_OAKS_EXCEPTIONS = {
    "2026-11-11": [("13:00", "17:00"), ("19:00", "21:30")],
    "2026-11-23": [("13:00", "17:00")],
    "2026-11-24": [("13:00", "17:00")],
    "2026-11-25": [("13:00", "17:00"), ("19:00", "21:30")],
    "2026-11-26": [("19:00", "21:30")],
    "2026-11-27": [("13:00", "17:00"), ("19:00", "22:30")],
}


def _oaks(bodies, rows):
    ident = "Q14709151"
    constraints = _original_park_constraints(ident, rows, bodies)
    page = html.fromstring(bodies["Q14709151-calendar"])
    overrides = []
    for month, key, filename in (
        (10, "Q14709151-october-calendar", "/pub/photo/October-2026-Rink-Hours.png"),
        (11, "Q14709151-november-calendar", "/pub/photo/November-2026-Rink-Hours.png"),
    ):
        if not page.xpath("//img[@src=$src]", src=filename):
            raise ValueError("Dated Oaks image link missing")
        for day in range(1, calendar.monthrange(2026, month)[1] + 1):
            date_value = date(2026, month, day)
            slots = _OAKS_EXCEPTIONS.get(
                date_value.isoformat(), _OAKS_GENERAL[date_value.weekday()]
            )
            # Absence is no verified public session, never whole-park closure.
            if slots:
                overrides.append(
                    {
                        "date": date_value.isoformat(),
                        "windows": [_window(start, end) for start, end in slots],
                    }
                )
        constraints.append(
            _constraint(
                key,
                {
                    "kind": "manually-read-image-calendar",
                    "literal_month_heading": calendar.month_name[month] + " 2026",
                    "section": "Roller Rink General Hours; orange Open Skate sessions only",
                    "columns": "Sunday through Saturday",
                    "exception_sidebar_sections": ["Veterans Day Hours", "Thanksgiving Break Hours"]
                    if month == 11
                    else ["Special Events"],
                },
                {
                    "public_open_skate_weekdays": _OAKS_GENERAL,
                    "dated_exceptions": _OAKS_EXCEPTIONS if month == 11 else {},
                    "thanksgiving_qualification": "The rink is closed until 7 PM on Thanksgiving Day"
                    if month == 11
                    else None,
                    "excluded_sessions": "All age-restricted/specialty sessions, classes, private rentals, and October24 11PM–2AM adult event",
                },
                interpretation="Only the explicitly named month applies. Replace regular sessions with holiday exceptions; no inferred Fall/Winter season boundary.",
            )
        )
    _require(bodies, "Q14709151-calendar", "Quantities are limited", "guaranteed admission")
    return _entry(
        "wikidata-park:" + ident,
        _calendar(overrides=overrides),
        constraints,
        "General-public Open Skate component only; October–November2026; limited-ticket policy retained",
        transcription="Two exact dated monthly images; specialties excluded; Thanksgiving afternoon canceled",
    )


def _embedded_json(raw, marker):
    """Decode a source JSON value without executing its surrounding JavaScript."""
    text = raw.decode("utf-8")
    index = text.find(marker)
    if index < 0:
        raise ValueError("Required embedded source JSON missing")
    value, _ = json.JSONDecoder().raw_decode(text[index + len(marker) :].lstrip())
    return value


def _funspot_dates(events):
    overrides, facts, held, seen = [], [], [], set()
    for event in sorted(events, key=lambda e: e["start"]):
        if not "2026-10-01" <= event["start"] < "2027-01-03":
            continue
        start, end = datetime.fromisoformat(event["start"]), datetime.fromisoformat(event["end"])
        if start.utcoffset() != timedelta() or end.utcoffset() != timedelta():
            raise ValueError("Unsupported source display-clock offset")
        if start.date() in seen:
            raise ValueError("Conflicting duplicate Fun Spot calendar date")
        seen.add(start.date())
        title = event["title"].split(" (")[0]
        try:
            titled = datetime.strptime(title, "%B %d, %Y").date()
        except ValueError as exc:
            raise ValueError("Unsupported literal Fun Spot date title") from exc
        if titled != start.date() or start.date() != end.date():
            held.append(
                {
                    "source_id": "wikidata-park:Q23994725",
                    "scope": "date",
                    "date": start.date().isoformat(),
                    "reason": "Published event title conflicts with machine date; neither year inferred",
                    "event": deepcopy(event),
                }
            )
            continue
        content = _visible(event["post_content"].encode())
        if content == "CLOSED – ALL DAY":
            if start.hour or start.minute or end.hour or end.minute:
                raise ValueError("Conflicting Fun Spot closure clocks")
            windows = []
        elif content == "Midnight" and end.hour == end.minute == 0 and end < start:
            windows = [_window(start.strftime("%H:%M"), "00:00", end_day_offset=1)]
        else:
            raise ValueError("Unsupported literal Fun Spot clock content")
        overrides.append({"date": start.date().isoformat(), "windows": windows})
        facts.append(deepcopy(event))
    return overrides, facts, held


def _funspot(bodies, rows):
    ident, key = "Q23994725", "Q23994725-visit-current"
    constraints = _original_park_constraints(ident, rows, bodies)
    document = html.fromstring(bodies[key])
    scripts = document.xpath('//script[@id="codemine-calendar-js-js-extra"]/text()')
    if len(scripts) != 1:
        raise ValueError("Kissimmee calendar container missing")
    config = _embedded_json(scripts[0].encode(), "var CMCAL_vars_164 = ")
    if len(config["all_events"]) != 674:
        raise ValueError("Kissimmee source event count differs")
    original = html.fromstring(bodies["original-Q23994725-0"])
    original_scripts = original.xpath('//script[@id="codemine-calendar-js-js-extra"]/text()')
    if len(original_scripts) != 1:
        raise ValueError("Original Kissimmee calendar feed is missing")
    original_config = _embedded_json(original_scripts[0].encode(), "var CMCAL_vars_164 = ")
    if original_config["all_events"] != config["all_events"]:
        raise ValueError("Old and new Kissimmee source calendars require conflict review")
    # The source displays UTC-encoded clock fields using moment.utc. They are
    # display wall clocks, never verified UTC visit instants or fixed starts.
    before = document.xpath('//script[@id="codemine-calendar-js-js-before"]/text()')
    if (
        len(before) != 1
        or "moment.utc(event.start)" not in before[0]
        or "moment.utc(event.end)" not in before[0]
        or b"timeZone: false" not in bodies["Q23994725-calendar-display-script"]
    ):
        raise ValueError("Fun Spot source display-clock semantics not verified")
    overrides, literal_events, held = _funspot_dates(config["all_events"])
    if len(overrides) != 93 or len(held) != 1 or held[0]["date"] != "2026-10-21":
        raise ValueError("Dated Fun Spot calendar differs from reviewed conflict set")
    _require(bodies, "Q23994725-title-date-conflict", "October 21, 2027")
    for hold in held:
        hold["source_constraints"] = [
            _constraint(
                key,
                {
                    "kind": "script-json",
                    "json_variable": "CMCAL_vars_164",
                    "event_id": hold["event"]["id"],
                },
                {"conflicting_event": hold["event"]},
            ),
            _constraint(
                "Q23994725-title-date-conflict",
                {"kind": "visible-text", "title": "October 21, 2027"},
                {"conflicting_title": "October 21, 2027"},
            ),
        ]
    constraints.extend(
        [
            _constraint(
                key,
                {
                    "kind": "script-json",
                    "script_id": "codemine-calendar-js-js-extra",
                    "json_variable": "CMCAL_vars_164",
                    "json_pointer": "/all_events",
                    "component": "Kissimmee calendar164",
                },
                {"dated_events": literal_events, "conflicting_dates": held},
                interpretation="Match title and machine date; source Midnight means next-day00:00. Omitted conflicting date is unknown, not closed.",
            ),
            _constraint(
                "Q23994725-calendar-display-script",
                {"kind": "javascript-text", "contains": "timeZone: false"},
                {"calendar_time_zone_setting": "timeZone: false"},
            ),
            _constraint(
                key,
                {"kind": "script-text", "script_id": "codemine-calendar-js-js-before"},
                {"clock_rendering": ["moment.utc(event.start)", "moment.utc(event.end)"]},
                interpretation="Keep rendered wall clocks and resolve actual visitor IANA timezone at runtime; no fixed UTC starts.",
            ),
            _constraint(
                "Q23994725-title-date-conflict",
                {"kind": "visible-text", "title": "October 21, 2027"},
                {"conflicting_title": "October 21, 2027"},
            ),
        ]
    )
    return (
        _entry(
            "wikidata-park:" + ident,
            _calendar(overrides=overrides),
            constraints,
            "Kissimmee only; October2026 through January2,2027; conflicting October21 omitted",
            held_dates=[item["date"] for item in held],
        ),
        held,
    )


def _kemah(bodies, rows):
    ident, key = "Q6386811", "Q6386811-public-hours-embed-valid"
    constraints = _original_park_constraints(ident, rows, bodies)
    page_key = "Q6386811-visitor-current"
    _require(bodies, page_key, "Hours shown are current month.", "seasonal.")
    document = html.fromstring(bodies[page_key])
    if not any(
        _SOURCES[key]["source_url"] == src.strip('\\"') for src in document.xpath("//script/@src")
    ):
        raise ValueError("Kemah public embed is not selected by operator page")
    raw = bodies[key].decode()
    payload = None
    for match in re.finditer(r'\{"', raw):
        try:
            value, _ = json.JSONDecoder().raw_decode(raw[match.start() :])
        except ValueError:
            continue
        if isinstance(value, dict) and "entityIdToUid" in value:
            payload = value
            break
    if payload is None:
        raise ValueError("Kemah structured public source payload missing")
    entities = [e for e in payload["entities"] if e["entityId"] == "KBWK"]
    if len(entities) != 1:
        raise ValueError("Kemah source identity not unique")
    entity = entities[0]
    names = list(calendar.day_name)
    weekly, facts = [], {}
    for day, name in enumerate(names):
        key_name = f"hours.{name.lower()}.openIntervals"
        intervals = entity["attributes"][key_name]
        literal = entity["attributes"]["hours-" + name.lower()]
        schemas = [
            s for s in entity["schema"]["openingHoursSpecification"] if s["dayOfWeek"] == name
        ]
        if len(intervals) != 1 or len(schemas) != 1:
            raise ValueError("Kemah structured clock variants unsupported")
        opened, closed = intervals[0]["start"], intervals[0]["end"]
        if schemas[0]["opens"] != opened or schemas[0]["closes"] != closed:
            raise ValueError("Kemah structured schema conflicts with operator clocks")
        weekly.append(_window(opened, closed, [day]))
        facts[name] = {"literal": literal, "structured_intervals": intervals}
    checked = datetime.fromisoformat(_SOURCES[page_key]["checked_at"]).date()
    first = checked.replace(day=1)
    last = checked.replace(day=calendar.monthrange(checked.year, checked.month)[1])
    constraints.extend(
        [
            _constraint(
                page_key,
                {"kind": "visible-text", "section": "current-month hours"},
                {
                    "month_scope": "Hours shown are current month.",
                    "restrictions": "Hours are seasonal; some rides may close for maintenance, high winds or lightning; dining and Boardwalk Beast schedules differ.",
                },
                interpretation="Only the acquisition month applies; no November or annual extrapolation.",
            ),
            _constraint(
                key,
                {
                    "kind": "public-embed-json",
                    "entity_id": "KBWK",
                    "json_pointers": [
                        "/entities/0/attributes/hours.*.openIntervals",
                        "/entities/0/schema/openingHoursSpecification",
                    ],
                },
                {
                    "weekly_clocks": facts,
                    "holidayHoursFormatted": entity["attributes"]["holidayHoursFormatted"],
                },
                interpretation="Structured operator-selected facts only; generatedFaq prose excluded. Null holiday field does not verify future holiday access.",
            ),
        ]
    )
    return _entry(
        "wikidata-park:" + ident,
        _calendar(weekly, [{"kind": "dated", "start": first.isoformat(), "end": last.isoformat()}]),
        constraints,
        "Published current-month general ride hours; separate dining/speedboat and weather closures retained",
    )


def build_enrichments(source_root, *, reviewed_on):
    """Return reproducible companion entries and holds, without mutating raw rows.

    Inputs are offline originals, not an editable calendar proposal. All source
    hashes, acquisition dates, source scopes and original market restrictions are
    checked before any output is returned. Corruption fails the whole batch.
    """
    bodies, rows, size = _load(Path(source_root), reviewed_on)
    market_facts = _market_sources(bodies, rows)
    entries = [
        _market(ident, bodies, market_facts[ident])
        for ident in ("301226", "301297", "308659", "308993")
    ]
    entries.extend(
        [
            _confusion(bodies, rows),
            _precious(bodies, rows),
            _nascar(bodies, rows),
            _oaks(bodies, rows),
            _kemah(bodies, rows),
        ]
    )
    funspot, date_holds = _funspot(bodies, rows)
    entries.append(funspot)
    holds = [
        {
            "source_id": "usda-market:308735",
            "scope": "record",
            "reason": "Strict opening meridiem remains unresolved; city acquisition403; no bypass or inferred PM",
            "source_constraints": _market_constraints("308735", market_facts["308735"])
            + [
                _constraint(
                    "308735-city",
                    {"kind": "http-response", "status": 403},
                    {"status": 403},
                )
            ],
        },
        *date_holds,
    ]
    return {
        "schema_version": SCHEMA,
        "reviewed_on": reviewed_on.isoformat(),
        "entries": sorted(entries, key=lambda entry: entry["source_id"]),
        "holds": holds,
        "summary": {
            "reviewed_records": 11,
            "companion_entries": len(entries),
            "positive_calendar_recoveries": 9,
            "expired_2026_season_corrections": 1,
            "record_holds": 1,
            "date_holds": len(date_holds),
            "pinned_input_files": len(bodies) + 1,
            "pinned_source_bytes": size,
            "reviewed_rows_artifact_sha256": _REVIEWED_ROWS_SHA256,
            "original_catalog_rows_modified": 0,
            "ticket_availability": "unknown",
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--reviewed-on", required=True, type=date.fromisoformat)
    args = parser.parse_args()
    result = build_enrichments(args.source_root, reviewed_on=args.reviewed_on)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
