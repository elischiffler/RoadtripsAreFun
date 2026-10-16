"""Replay reviewed NPS facility hours without extrapolating annual availability.

The review pins authentic structured bodies, not a hand-entered hours table. Every
clock and exception is read again from those bodies. Output is a finite set of
dated windows in the acquisition year; this is an extraction scope, not an NPS
promise of validity through December. Dates with unresolved negative facts have
no positive override. Source rows, coordinates and original provenance are never
rewritten by this supplement producer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path

SCHEMA = "roadtrips-source-visit-calendar/1"
TRANSFORMATION = "roadtrips-reviewed-nps-facility-calendar/1"

# Filled with reviewed native body hashes, facility IDs and schedule scopes below.
PROFILES = {
    "nps:bisc": {
        "sha256": "fe8fa1d2de5a56cfdc094bc7efbe6c189255563cb988767bd32de7fac7e34a99",
        "checked_at": "2026-10-15T00:11:53.767708+00:00",
        "facility_id": 2552,
        "schedule_id": 20573,
        "full": [3417, 3416],
        "exceptions": [],
    },
    "nps-heritage:arpo": {
        "sha256": "7742fcefd2f50631b696e32e206a6dbf108c5bd09105c6ea76781629cbfb01d8",
        "checked_at": "2026-10-15T02:31:32.274776+00:00",
        "facility_id": 5712,
        "schedule_id": 17972,
        "full": [],
        "exceptions": [3250],
    },
    "nps-heritage:liho": {
        "sha256": "ff6753f46b46999a195df339b6706368ada49303988f1bb5fa8c97565c724a08",
        "checked_at": "2026-10-15T02:31:33.168860+00:00",
        "facility_id": 5860,
        "schedule_id": 20507,
        "full": [3258],
        "exceptions": [],
    },
    "nps-heritage:cari": {
        "sha256": "7bc9d80048458946ca4a9a0c1fc76b1f2a3943c57c26e8554295f2dc9026225e",
        "checked_at": "2026-10-15T02:31:33.360892+00:00",
        "facility_id": 3649,
        "schedule_id": 19346,
        "full": [3508],
        "exceptions": [],
    },
    "nps-heritage:gwca": {
        "sha256": "53617b442d6ce6add205ec7b64b1a437ce65b81a679d24e4ac2021bd643630af",
        "checked_at": "2026-10-15T02:31:33.952571+00:00",
        "facility_id": 1226,
        "schedule_id": 1475,
        "full": [1469],
        "exceptions": [],
    },
    "nps-heritage:waba": {
        "sha256": "5739a427498c9235808823a17348a50ced5e1655b096de4697042763f8e98755",
        "checked_at": "2026-10-15T02:31:34.654436+00:00",
        "facility_id": 175,
        "schedule_id": 372,
        "full": [],
        "exceptions": [],
    },
    "nps-heritage:rowi": {
        "sha256": "b26cad2b17c0e2e1cd84d749f832de415281363e3e4f691fc0327619c87fdf65",
        "checked_at": "2026-10-15T02:31:34.900697+00:00",
        "facility_id": 189,
        "schedule_id": 390,
        "full": [],
        "exceptions": [389],
    },
    "nps-heritage:azru": {
        "sha256": "098a6c6343f3d9971220b599aad8e6bcba87c8bb5b94266cb1cc57bdcee5b841",
        "checked_at": "2026-10-15T03:15:52.954315+00:00",
        "facility_id": 2377,
        "schedule_id": 21411,
        "full": [17938],
        "exceptions": [],
    },
    "nps-heritage:cavo": {
        "sha256": "5994ff880646228a2d3982067f03f878380d122bf6f2c09795c44ed0e2196e0a",
        "checked_at": "2026-10-15T03:15:53.791049+00:00",
        "facility_id": 5766,
        "schedule_id": 18198,
        "full": [20827],
        "exceptions": [18117],
    },
    "nps-heritage:foun": {
        "sha256": "df8415ad978dd737c71d6dceffc4fa0814dd1ba0a01afedeb02df13e08f19cc9",
        "checked_at": "2026-10-15T03:15:55.295131+00:00",
        "facility_id": 1222,
        "schedule_id": 1463,
        "full": [1466],
        "exceptions": [],
        "unconditional": [1699],
    },
    "nps-heritage:gicl": {
        "sha256": "317cadab18d73ee6246373f421c1b8b1598813b4e8e279e9a616c0ca3f39c3f4",
        "checked_at": "2026-10-15T03:15:55.763224+00:00",
        "facility_id": 2318,
        "schedule_id": 2706,
        "full": [18001],
        "exceptions": [],
    },
    "nps-heritage:moca": {
        "sha256": "3224d6ed9a2d26687aa3fbc643ea14d1d7d2b6d32cecb598f87e9eb35a6e5c43",
        "checked_at": "2026-10-15T03:15:57.481656+00:00",
        "facility_id": 154,
        "schedule_id": 1687,
        "full": [326],
        "exceptions": [],
    },
    "nps-heritage:wupa": {
        "sha256": "3b518a10f372c8bcfc7685cac1185413813ea683ea3b878a98ab26c7b76740f9",
        "checked_at": "2026-10-15T03:15:59.865145+00:00",
        "facility_id": 1305,
        "schedule_id": 1675,
        "full": [],
        "exceptions": [1673],
    },
    "nps-heritage:fova": {
        "sha256": "ffd95794933cbf9b65366a1281f86863505253adf7d66693aa84e89a24cf374a",
        "checked_at": "2026-10-15T03:15:55.380099+00:00",
        "facility_id": 1303,
        "schedule_id": 21265,
        "full": [1712],
        "exceptions": [],
    },
    "nps-heritage:jomu": {
        "sha256": "01f3d933f9a8c1ffba8b7ee279da6521c5fd8f6224bc91c6cfa55a401c85a580",
        "checked_at": "2026-10-15T03:15:56.621653+00:00",
        "facility_id": 94,
        "schedule_id": 205,
        "full": [204],
        "exceptions": [],
    },
    "nps-heritage:manz": {
        "sha256": "2b17930d6752f522a66a9035a83eae61547ea525b506f6a7648abfc7e727d5e8",
        "checked_at": "2026-10-15T03:15:57.167323+00:00",
        "facility_id": 5754,
        "schedule_id": 18153,
        "full": [],
        "exceptions": [18154],
    },
    "nps-heritage:puhe": {
        "sha256": "57be6f51b624731d58d544aaa066fe5f9a67bac4a5c59e50cc44fae6ac7baccb",
        "checked_at": "2026-10-15T03:15:58.250534+00:00",
        "facility_id": 2594,
        "schedule_id": 18203,
        "full": [3409, 18202],
        "exceptions": [],
    },
    "nps-heritage:rori": {
        "sha256": "809cdac8d847911e745e14eb5e2af6d5d0df73740cb34dc8a698114a78bed9a5",
        "checked_at": "2026-10-15T03:15:58.438220+00:00",
        "facility_id": 92,
        "schedule_id": 203,
        "full": [202],
        "exceptions": [],
    },
    "nps-heritage:home": {
        "sha256": "90e6c3f2a5c542204a4d0b12cf436ea4d36613a7edde87bb672dcb4414fcd6f3",
        "checked_at": "2026-10-15T03:15:56.286337+00:00",
        "facility_id": 1225,
        "schedule_id": 1474,
        "full": [],
        "exceptions": [19417],
    },
    "nps-heritage:wicr": {
        "sha256": "cbb2a09095cd8b6ab6b0f9bb9844e7bab909c2c810e6b1082cdae96d3f1f7942",
        "checked_at": "2026-10-15T03:15:59.744465+00:00",
        "facility_id": 1276,
        "schedule_id": 1613,
        "full": [],
        "exceptions": [18176],
    },
    "nps-heritage:chyo": {
        "sha256": "0285bbbd6cbfabe80c16a98d3b86c50f08e55c438ffd5b06bb97622036578f0f",
        "checked_at": "2026-10-15T03:15:54.152840+00:00",
        "facility_id": 1221,
        "schedule_id": 6675,
        "full": [1458],
        "exceptions": [],
    },
    "nps-heritage:rira": {
        "sha256": "47884544d27c865918661695d9e7f0bfa3cee2487ef618f63b3ab512d989ee18",
        "checked_at": "2026-10-15T03:15:58.435777+00:00",
        "facility_id": 1236,
        "schedule_id": 1512,
        "full": [1480],
        "exceptions": [],
    },
    "nps-heritage:alfl": {
        "sha256": "1a75bff766066653218102c224a8ea002bdb827ede8ce366118cfdac9594f222",
        "checked_at": "2026-10-15T03:15:52.601025+00:00",
        "facility_id": 1293,
        "schedule_id": 2712,
        "full": [1643],
        "exceptions": [],
    },
    "nps-heritage:chch": {
        "sha256": "4bd51d2c7e3ece4a1b4cae4ef6e472d22e88958e9dbe4b3a5b5e68f75799d822",
        "checked_at": "2026-10-15T03:15:53.915568+00:00",
        "facility_id": 1224,
        "schedule_id": 1476,
        "full": [],
        "exceptions": [18138],
    },
    "nps-heritage:fofr": {
        "sha256": "23b9b9b64252d2f4269fd567c679e40b4675752fcb50913c0c0c361e5f9f366c",
        "checked_at": "2026-10-15T03:15:54.942443+00:00",
        "facility_id": 1295,
        "schedule_id": 1652,
        "full": [1642, 21556],
        "exceptions": [],
    },
    "nps-heritage:fora": {
        "sha256": "14d4292c893ee667f22b6a933b183fd8f2b6884ed5425aef9cbc5d940b8edb68",
        "checked_at": "2026-10-15T03:15:55.158632+00:00",
        "facility_id": 32,
        "schedule_id": 3174,
        "full": [63],
        "exceptions": [],
    },
    "nps-heritage:fosu": {
        "sha256": "6f3a103cf62893528356619c64c4511d479845f4cadff615f28a72d120123ac4",
        "checked_at": "2026-10-15T03:15:55.267158+00:00",
        "facility_id": 62,
        "schedule_id": 139,
        "full": [136],
        "exceptions": [],
    },
    "nps-heritage:jica": {
        "sha256": "d2d8d702774b5710e75b2bbac81d98720dc2e939432d5c57458b1a47535aa9f3",
        "checked_at": "2026-10-15T03:15:56.513974+00:00",
        "facility_id": 5775,
        "schedule_id": 18224,
        "full": [],
        "exceptions": [],
    },
    "nps-heritage:kemo": {
        "sha256": "ade152521fff84fbf2c99994e00bb5411b8e813081e610c713c00eb921994521",
        "checked_at": "2026-10-15T03:15:56.742802+00:00",
        "facility_id": 5739,
        "schedule_id": 18099,
        "full": [19381],
        "exceptions": [],
        "unconditional": [26624],
    },
    "nps-heritage:lyjo": {
        "sha256": "76f0e6bae9a764786030c024b349affbd1998498da43b6b6978bfa8ade28080e",
        "checked_at": "2026-10-15T03:15:57.080598+00:00",
        "facility_id": 2326,
        "schedule_id": 2722,
        "full": [2696],
        "exceptions": [],
    },
    "nps-heritage:wrbr": {
        "sha256": "e269096e0a659fd135c9267bbddc6410f32935fd75c4d6bfeb1def8344d0d12a",
        "checked_at": "2026-10-15T03:15:59.792590+00:00",
        "facility_id": 2460,
        "schedule_id": 3173,
        "full": [3167],
        "exceptions": [],
    },
    "nps-heritage:anti": {
        "sha256": "e195af655a4b29bd6d1c228555c04b4db2e015e9fef4999163050cc572a86b4e",
        "checked_at": "2026-10-15T03:15:52.865096+00:00",
        "facility_id": 75,
        "schedule_id": 169,
        "full": [167],
        "exceptions": [21789],
    },
    "nps-heritage:gewa": {
        "sha256": "6204a58e53a0532fe929345514a529e1497b3150cfb5c4732d4516165ccdc57f",
        "checked_at": "2026-10-15T03:15:55.752299+00:00",
        "facility_id": 5703,
        "schedule_id": 17851,
        "full": [3306],
        "exceptions": [],
    },
    "nps-heritage:hamp": {
        "sha256": "613745296e77d6dcc9d9efe819908f248f9928f09f0ea475a84a91d319746e7e",
        "checked_at": "2026-10-15T03:15:56.015780+00:00",
        "facility_id": 5856,
        "schedule_id": 20494,
        "full": [],
        "exceptions": [3542],
    },
    "nps-heritage:mono": {
        "sha256": "7a35d117f148d224eda8df290b196443c0063f37e81dba0340223a616434ffd6",
        "checked_at": "2026-10-15T03:15:57.534310+00:00",
        "facility_id": 2386,
        "schedule_id": 2894,
        "full": [],
        "exceptions": [2893],
    },
    "nps-heritage:pete": {
        "sha256": "800cb4981ea26ba9cdf5b11f577547c707f4f2d07cda250bd86c88dad3d9258e",
        "checked_at": "2026-10-15T03:15:58.163037+00:00",
        "facility_id": 5836,
        "schedule_id": 19460,
        "full": [18160],
        "exceptions": [],
    },
}


class CalendarHold(ValueError):
    """The original does not support this reviewed transformation."""


CURRENT_EVIDENCE = {
    "jomu": {
        "source_url": "https://www.nps.gov/jomu/planyourvisit/hours.htm",
        "snapshot_sha256": "a860a23d2698e9590fcb25ca0fb717a99079ac7fb65fa721f6a9b41fdc0faf92",
        "checked_at": "2026-10-15T19:47:01.147700+00:00",
        "facts": [
            "Open Tuesday through Saturday from 10:00 AM – 5:00 PM",
            "We are closed on Sundays and Mondays.",
            "Muir/Strentzel House closes at 4:30 PM.",
            "Hours and operations may vary due to unforeseen circumstances.",
        ],
        "interpretation": "Confirms selected visitor-center weekdays and clocks; does not remove native noon closure. House 16:30 close is a different component. General unforeseen-condition caveat is retained, not invented as a specific closure.",
    },
    "rori": {
        "source_url": "https://www.nps.gov/rori/planyourvisit/hours.htm",
        "snapshot_sha256": "555a13835cabbf4c5ee0768d012b93787044be8a9bf9356e5bf4e7bf5dad73f3",
        "checked_at": "2026-10-15T19:47:01.414779+00:00",
        "facts": [
            "Open Daily: 10:00 AM – 5:00 PM",
            "Closed: Thanksgiving Day, Christmas Day, and New Year's Day",
        ],
        "interpretation": "Confirms selected visitor-center clocks and all three named holiday closures; native month/day exceptions remain restrictive, with no future annual fixed Thanksgiving date.",
    },
    "manz": {
        "source_url": "https://www.nps.gov/manz/planyourvisit/visitor-center-block-14-exhibits.htm",
        "snapshot_sha256": "ba5f9be40d144eb7b303bade0cc7a76732b2d9c900ae2600ed681bd603ea47cc",
        "checked_at": "2026-10-15T19:47:01.571400+00:00",
        "facts": ["Operating hours can be found on our basic information page."],
        "interpretation": "Current identity page refers elsewhere for hours. It supplies no new clocks and does not erase the retained exact facility schedule.",
    },
}

REVIEW_HOLDS = {
    "nps-heritage:cabr": "Retained facility URL returned official 404 in bounded current spotcheck; resolve a current facility/hour URL before this profile is admitted.",
    "nps-heritage:puho": "Applicable parent gate closes at sunset and defers exact closing time to phone/Facebook; no verified literal full-dwell access end.",
}


class _PageText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def _current_evidence(record):
    code = record["catalog_source_id"].split(":", 1)[1]
    if code not in CURRENT_EVIDENCE:
        return None, []
    pin = CURRENT_EVIDENCE[code]
    path = Path(record.get("current_official_evidence_path", ""))
    if not path.is_file():
        raise CalendarHold("Retained current official corroboration must also be supplied")
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != pin["snapshot_sha256"]:
        raise CalendarHold("Current official body differs from immutable corroboration pin")
    page = _PageText()
    page.feed(body.decode("utf-8"))
    text = " ".join(" ".join(page.parts).split())
    if any(literal not in text for literal in pin["facts"]):
        raise CalendarHold("Pinned official literal fact is absent")
    receipt = {key: pin[key] for key in ("source_url", "snapshot_sha256", "checked_at")}
    receipt["evidence_path"] = str(path)
    return receipt, [
        {
            **receipt,
            "literal": literal,
            "scope": "current_official_corroboration",
            "interpretation": pin["interpretation"],
        }
        for literal in pin["facts"]
    ]


def _clock(value: str) -> int:
    try:
        clock = datetime.strptime(value.strip(), "%I:%M %p")
    except (ValueError, AttributeError) as exc:
        raise CalendarHold("Missing or unsupported literal clock") from exc
    return clock.hour * 60 + clock.minute


def _day_windows(hours: list[dict], day: date) -> list[tuple[int, int]]:
    """NPS native Sunday=1; a blank flag-zero cell is unknown, never open."""
    native = (day.weekday() + 1) % 7 + 1
    rows = [row for row in hours if row.get("dayOfWeek") == native]
    if len(rows) != 1:
        raise CalendarHold("Missing or duplicate native weekday")
    row = rows[0]
    if row.get("is_closed") == 1:
        return []
    if row.get("is_closed") != 0 or row.get("sunrise_open") or row.get("sunset_close"):
        raise CalendarHold("Astronomical or unknown clock boundary")
    start, end = _clock(row.get("time_open")), _clock(row.get("time_close"))
    if end <= start:
        raise CalendarHold("Reversed or zero clocks; no inferred overnight or AM/PM repair")
    return [(start, end)]


def _intersect(left, right):
    return sorted(
        {(max(a, c), min(b, d)) for a, b in left for c, d in right if max(a, c) < min(b, d)}
    )


def _nth_weekday(year, month, weekday, nth):
    first = date(year, month, 1)
    return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (nth - 1))


def _holiday(value, year):
    # Only native named actual holidays. No inferred substitute/observed weekday.
    names = {
        "New Year’s Day": date(year, 1, 1),
        "Birthday of Martin Luther King, Jr.": _nth_weekday(year, 1, 0, 3),
        "Washington’s Birthday": _nth_weekday(year, 2, 0, 3),
        "Memorial Day": date(year, 5, 31) - timedelta(days=date(year, 5, 31).weekday()),
        "Juneteenth National Independence Day": date(year, 6, 19),
        "Independence Day": date(year, 7, 4),
        "Labor Day": _nth_weekday(year, 9, 0, 1),
        "Columbus Day": _nth_weekday(year, 10, 0, 2),
        "Veterans Day": date(year, 11, 11),
        "Thanksgiving Day": _nth_weekday(year, 11, 3, 4),
        "Christmas Day": date(year, 12, 25),
    }
    if value in (None, "", 0):
        return None
    if value not in names:
        raise CalendarHold(f"Unsupported native holiday selector: {value}")
    return names[value]


def _month_day(value, year):
    if value in (None, "", 0):
        return None
    try:
        return datetime.strptime(f"{value} {year}", "%B %d %Y").date()
    except ValueError as exc:
        raise CalendarHold(f"Unsupported native date selector: {value}") from exc


def _exception_applies(exception, day):
    """Union contradictory selectors to restrict both; never enlarge base hours."""
    ranges = []
    for parser, start_key, end_key in (
        (_month_day, "date_start", "date_end"),
        (_holiday, "holiday_start", "holiday_end"),
    ):
        start = parser(exception.get(start_key), day.year)
        end = parser(exception.get(end_key), day.year)
        if start or end:
            start, end = start or end, end or start
            ranges.append((start, end))
    if not ranges:
        raise CalendarHold("Exception lacks a resolvable native date selector")
    return any(
        start <= day <= end if start <= end else day >= start or day <= end for start, end in ranges
    )


def _exception_windows(exception, day):
    text = " ".join(str(exception.get(key, "")) for key in ("name", "description")).lower()
    rows = exception.get("schedule", [])
    # A named whole-day closure is stronger than a stale weekday-specific cell.
    # Mixed winter weekday tables still use their actual native weekday.
    if "closed" in text and "weekly" not in text and "tuesday" not in text:
        if any(row.get("is_closed") == 1 for row in rows):
            return []
    return _day_windows(rows, day)


def _schedule_windows(schedule, day, *, exceptions_only=False, unconditional=()):
    windows = [(0, 1440)] if exceptions_only else _day_windows(schedule["hours"], day)
    for exception in schedule.get("exceptions", []):
        if not windows:
            break  # Intersections cannot reopen a source-closed day.
        if exception["operatingScheduleExceptionID"] in unconditional or _exception_applies(
            exception, day
        ):
            windows = _intersect(windows, _exception_windows(exception, day))
    return windows


def _fact(receipt, pointer, value, scope, interpretation):
    return {
        **receipt,
        "native_json_pointer": pointer,
        "native_value": value,
        "scope": scope,
        "interpretation": interpretation,
    }


def _load_original(record, catalog_row):
    source_id = record["catalog_source_id"]
    profile = PROFILES.get(source_id)
    if not profile:
        raise CalendarHold(
            REVIEW_HOLDS.get(source_id, "No independently reviewed exact schedule/prose profile")
        )
    path = Path(record["retained_snapshot_path"])
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != profile["sha256"]:
        raise CalendarHold("Original body hash differs from immutable review pin")
    code = source_id.split(":", 1)[1]
    url = f"https://www.nps.gov/{code}/structured_data_{code}.json"
    if (
        record["source_url"] != url
        or record["source_snapshot_sha256"] != profile["sha256"]
        or record["source_acquired_at"] != profile["checked_at"]
        or catalog_row["source_id"] != source_id
    ):
        raise CalendarHold("Source identity or original acquisition receipt differs")
    original = json.loads(body.decode("utf-8-sig"))
    if original.get("siteCode") != code:
        raise CalendarHold("Native park code differs")
    matches = [
        (index, facility)
        for index, facility in enumerate(original["visitorCenters"])
        if facility.get("visitorCenterID") == profile["facility_id"]
    ]
    if len(matches) != 1:
        raise CalendarHold("Native facility identity is not unique")
    index, facility = matches[0]
    pointer = f"/visitorCenters/{index}"
    if record["facility_json_pointer"] != pointer:
        raise CalendarHold("Native facility pointer differs")
    if any(
        float(facility["location"][axis]) != catalog_row[axis] for axis in ("latitude", "longitude")
    ):
        raise CalendarHold("Catalog coordinates differ from original facility")
    receipts = [
        fact
        for fact in catalog_row.get("provenance", [])
        if fact.get("dataset") == "National Park Service structured visitor facility"
        and str(fact.get("record_id")) == str(profile["facility_id"])
        and fact.get("source_url") == url
        and fact.get("snapshot_sha256") == profile["sha256"]
        and fact.get("checked_at") == profile["checked_at"]
    ]
    if len(receipts) != 1:
        raise CalendarHold("Catalog original facility provenance differs")
    receipt = {
        "source_url": url,
        "snapshot_sha256": profile["sha256"],
        "checked_at": profile["checked_at"],
        "evidence_path": str(path),
        "native_facility_id": profile["facility_id"],
        "native_json_pointer": pointer,
    }
    return profile, original, facility, pointer, receipt


def transform_record(record: dict, catalog_row: dict) -> dict:
    """Emit the reviewed finite supplement, or hold without changing the source row."""
    profile, original, facility, pointer, receipt = _load_original(record, catalog_row)
    current_receipt, current_constraints = _current_evidence(record)
    schedules = facility["operatingHours"]
    if len(schedules) != 1:
        raise CalendarHold("Multiple selected facility schedules require separate review")
    key, selected = next(iter(schedules.items()))
    if selected["operatingScheduleID"] != profile["schedule_id"]:
        raise CalendarHold("Selected native schedule identity differs")
    selected_pointer = f"{pointer}/operatingHours/{key}"
    constraints = [
        _fact(
            receipt,
            f"{pointer}/description",
            facility.get("description", ""),
            "selected_facility",
            "Retain all component, ticket and access qualifications.",
        ),
        _fact(
            receipt,
            selected_pointer,
            selected,
            "selected_facility",
            "Base clocks intersect every applicable native exception; no widening.",
        ),
    ]
    constraints.extend(current_constraints)
    applied = []
    for index, schedule in enumerate(original["operatingHours"]):
        schedule_id = schedule["operatingScheduleID"]
        if schedule_id == profile["schedule_id"]:
            # Parent aggregation duplicates native facility schedules, with a prefixed name.
            for field in ("hours", "exceptions", "description", "label"):
                if schedule.get(field) != selected.get(field):
                    raise CalendarHold("Parent/facility duplicate schedule conflict")
            scope, reason = (
                "selected_facility_duplicate",
                "Exact hours, exceptions, description and label match selected native schedule.",
            )
        elif schedule_id in profile["full"]:
            applied.append((schedule, False))
            scope, reason = (
                "applicable_access",
                "Intersect applicable visitor/entry clocks and all exceptions.",
            )
        elif schedule_id in profile["exceptions"]:
            applied.append((schedule, True))
            scope, reason = (
                "applicable_negative_facts",
                "Apply attributed closures/exceptions; outdoor clocks do not establish indoor availability.",
            )
        else:
            scope, reason = (
                "other_component",
                "Different facility, district, trail, road activity or campground; not a positive availability source for selected facility.",
            )
        constraints.append(_fact(receipt, f"/operatingHours/{index}", schedule, scope, reason))

    start = datetime.fromisoformat(profile["checked_at"]).date()
    end = date(start.year, 12, 31)
    code = record["catalog_source_id"].split(":", 1)[1]
    horizon_facts = []
    if code == "fova":
        end = date(start.year, 12, 20)
        horizon_facts.append(
            "Stop before December 21: native winter month/day fields conflict with explicitly dated 12/21/25–01/05/26 prose; no annual repetition inferred."
        )
    if code in {"wupa", "pete"}:
        end = date(start.year, 11, 1)
        horizon_facts.append(
            "Stop at explicit source November 1 seasonal boundary; do not extrapolate the reviewed pre-boundary access regime."
        )
    overrides, withheld = [], []
    day = start
    while day <= end:
        try:
            if code == "liho" and (day.month, day.day) == (12, 24):
                raise CalendarHold(
                    "Christmas Eve exception explicitly says 2024; 2026 month/day ambiguity withheld"
                )
            if code == "moca" and day in {
                date(day.year, 12, 24),
                date(day.year, 12, 31),
                _holiday("Thanksgiving Day", day.year) - timedelta(days=1),
            }:
                raise CalendarHold("Published possible early closure has no exact closing clock")
            windows = _schedule_windows(selected, day)
            for schedule, exceptions_only in applied:
                if not windows:
                    break  # Preserve the independently explicit facility closure.
                windows = _intersect(
                    windows,
                    _schedule_windows(
                        schedule,
                        day,
                        exceptions_only=exceptions_only,
                        unconditional=profile.get("unconditional", ()),
                    ),
                )
            if code == "jomu":
                windows = _intersect(windows, [(0, 720), (780, 1440)])
            if code == "puhe":
                windows = _intersect(windows, [(0, 960)])
            overrides.append(
                {
                    "date": day.isoformat(),
                    "windows": [
                        {
                            "opens": f"{a // 60:02d}:{a % 60:02d}",
                            "closes": f"{b // 60:02d}:{b % 60:02d}",
                            "end_day_offset": 0,
                        }
                        for a, b in windows
                    ],
                }
            )
        except CalendarHold as exc:
            withheld.append({"date": day.isoformat(), "reason": str(exc)})
        day += timedelta(days=1)
    if not any(item["windows"] for item in overrides):
        raise CalendarHold("No supported positive dated window after all source restrictions")
    if code == "jomu":
        horizon_facts.append(
            "Facility description explicitly closes 12:00PM to 1:00PM every day; split sessions, never bridge lunch."
        )
    if code == "puhe":
        horizon_facts.append(
            "Entrance gate closes 4:00pm; conservative full-dwell end cap at literal entry cutoff, not a claimed facility closing time."
        )
    if profile.get("unconditional"):
        horizon_facts.append(
            "Conservatively intersect every clock variant of the reviewed seasonal exception even outside its ambiguous selector; all variants contain the selected facility session. No season date is inferred."
        )
    calendar = {
        "schema_version": SCHEMA,
        "weekly_windows": [],
        "seasons": [{"kind": "dated", "start": start.isoformat(), "end": end.isoformat()}],
        "date_overrides": overrides,
        "annual_closures": [],
        "source_receipts": [receipt, *([current_receipt] if current_receipt else [])],
        "unknown_reasons": [],
    }
    return {
        "source_id": record["catalog_source_id"],
        "source_visit_calendar": calendar,
        "source_constraints": constraints,
        "transformation": {
            "schema_version": TRANSFORMATION,
            "native_facility_id": profile["facility_id"],
            "native_schedule_id": profile["schedule_id"],
            "native_facility_pointer": pointer,
            "evaluated_date_scope": {"start": start.isoformat(), "end": end.isoformat()},
            "scope_basis": "Original acquisition date through acquisition-year end only; a finite interpretation scope, not source-published expiry or future validity guarantee.",
            "source_derived_horizon_and_prose_constraints": horizon_facts,
            "withheld_dates": withheld,
            "rules": [
                "Native Sunday=1 mapped to actual dated weekday.",
                "Intersect all applicable sources; closures win; blank cells remain unknown.",
                "Union conflicting native holiday/date selectors conservatively; never infer observed substitute days.",
                "No inferred hours, overnight clocks, timezone, prices, parking or fixed start instants.",
                "All selected and other-component native schedules retained with separately attributed scopes.",
            ],
        },
    }


def build_entries(extraction: dict, catalog_items: list[dict]) -> dict:
    """Build an auditable entry/hold ledger for every requested source row."""
    items = {item["source_id"]: item for item in catalog_items}
    entries, holds = [], []
    for record in extraction["records"]:
        source_id = record["catalog_source_id"]
        try:
            entries.append(transform_record(record, items[source_id]))
        except (CalendarHold, KeyError, OSError, TypeError, ValueError) as exc:
            holds.append(
                {
                    "source_id": source_id,
                    "native_facility_id": record.get("source_native_facility", {}).get(
                        "visitorCenterID"
                    ),
                    "snapshot_sha256": record.get("source_snapshot_sha256"),
                    "source_url": record.get("source_url"),
                    "checked_at": record.get("source_acquired_at"),
                    "evidence_path": record.get("retained_snapshot_path"),
                    "native_json_pointer": record.get("facility_json_pointer"),
                    "reason": str(exc),
                }
            )
    return {
        "schema_version": TRANSFORMATION,
        "entries": entries,
        "holds": holds,
        "summary": {
            "requested_rows": len(extraction["records"]),
            "emitted_rows": len(entries),
            "held_rows": len(holds),
            "positive_dated_days": sum(
                bool(day["windows"])
                for entry in entries
                for day in entry["source_visit_calendar"]["date_overrides"]
            ),
            "positive_dated_windows": sum(
                len(day["windows"])
                for entry in entries
                for day in entry["source_visit_calendar"]["date_overrides"]
            ),
            "withheld_ambiguous_dates": sum(
                len(entry["transformation"]["withheld_dates"]) for entry in entries
            ),
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extraction", required=True, type=Path)
    parser.add_argument("--items", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = build_entries(
        json.loads(args.extraction.read_text(encoding="utf-8")),
        json.loads(args.items.read_text(encoding="utf-8")),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(result["summary"], sort_keys=True))


if __name__ == "__main__":
    main()
