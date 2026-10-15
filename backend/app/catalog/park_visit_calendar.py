"""Literal operator visit calendars from the immutable reviewed park originals.

This adapter emits local wall clocks only. Routing supplies the actual IANA zone.
Unknown seasons, component admission cutoffs and unacquired exception calendars
withhold automatic scheduling while leaving the original catalog row intact.
"""

import hashlib
import re
from collections import defaultdict
from datetime import datetime

from lxml import html

SCHEMA = "roadtrips-source-visit-calendar/1"
_PINS = {
    "Q44041": [
        (
            "https://www.belmontpark.com/park-hours",
            "d54c8bc5d8f336d02de856e987ce5cf35b5f6c9899ffc671c402d163444e1671",
        ),
        (
            "https://www.belmontpark.com/getting-here",
            "a1d81da31fdb8469d73589d9eee9e2506fc911f47c64d82ce35288a74ca22984",
        ),
        (
            "https://www.belmontpark.com/park-info",
            "498196db8810fa7505ab0ffeec9ef15b43355ab208de15fb0e4409110900bfc6",
        ),
    ],
    "Q5160318": [
        (
            "https://www.confusionhill.com/attractions",
            "de34ae58c9339dcdda273bea231311cb54b568b169c102af9be7f2766d499ae2",
        ),
        (
            "https://www.confusionhill.com/contact",
            "7b3ec375a960c0a9d0b551c17924fb61b3a897117f82efb897a8f8a6167cfe85",
        ),
        (
            "https://www.confusionhill.com/history",
            "68e5f4b3e1b9cd96072f78b23978f6469cc98fb3d56b10ce97f44c23f8b3fa93",
        ),
        (
            "https://www.confusionhill.com/faqs",
            "c1f8a864f9942ab88a51e490d1b30b2250308d5ee3f787f671c9736f614e6f77",
        ),
        (
            "https://www.confusionhill.com/blog",
            "3ae43bd6bfe12f064c8d5192eca3146fe455e9a26f897f088dedf58913f2daff",
        ),
    ],
    "Q24192030": [
        (
            "https://dezerlandpark.com/",
            "c7de3e35d3eb5f58a53aa59cd5d598df0a9c2241b1f09a791c21cecc5129a780",
        ),
        (
            "https://dezerlandpark.com/faq/",
            "0404c26d1538492c90d4081d039cafd61ca58cd25ee727dc0d1e3873300a86e9",
        ),
    ],
    "Q14685852": [
        (
            "https://www.dinosaurworld.com",
            "ec2c5e028c68b48333e8d42ca41b8ee4b746b84e542c0319a9e95bc8690343d7",
        )
    ],
    "Q23994725": [
        (
            "https://fun-spot.com/kissimmee/plan-your-visit/",
            "aa861e71fd06b263ab89aff597fd90e90045f4c01d824228ac230dee6531df25",
        ),
        (
            "https://fun-spot.com/policies-and-frequently-asked-questions/",
            "112386944bf832ae72f87a66de27e94315e77fce2cea18a767f58cb53fc4f8ab",
        ),
    ],
    "Q6386811": [
        (
            "https://www.kemahboardwalk.com/visitor-info",
            "d5df06671823eab6f83c4e4c1b6d06c0829d59b99433ff9282b659800ef9bf7d",
        ),
        (
            "https://www.kemahboardwalk.com",
            "98b0317c1daef5159457a85c6e98e0fe257a0bf8955e8b9d5e18691d957c87df",
        ),
    ],
    "Q131759816": [
        (
            "https://www.nascarspeedpark.com/",
            "e003cf8f48d19d4fdcedaed3ea7eb938c60005cf77173a2f2e875684be56163c",
        ),
        (
            "https://www.nascarspeedpark.com/hours-and-info/",
            "d1010031d55eaf6a1270650b2bee9dc071466a5e7e91b1cf7b867058fc38eb4e",
        ),
    ],
    "Q14709151": [
        (
            "https://www.oakspark.com/",
            "5a20f67af8dd3c2673b6b9c5cb93f23b8b7ee348de6d9563aca73521bc25680c",
        ),
        (
            "https://www.oakspark.com/roller-skating-rink",
            "e0ef67920cb3e64338595cf10a90f575d202a2fc70d8f9268760b434e4dd46a4",
        ),
        (
            "https://www.oakspark.com/directions",
            "249e113fddd93c466e6f3ec7cec01a745da4da920bc0366d31b7cebad53298ce",
        ),
    ],
    "Q7085259": [
        (
            "https://www.myoldtownusa.com/",
            "0a4b757e4bdd4e25963af6b3fe39d2acead342cc51623236abe9d161765e6db7",
        ),
        (
            "https://www.myoldtownusa.com/parking",
            "2e882b4f737eee4b627e270ea2ed452dc8fea485ca95061c3ab63e4dd75dc9e1",
        ),
        (
            "https://www.myoldtownusa.com/frequently-asked-questions",
            "6bcfccb900a3b943ed21df1eebcfb695b221ac8468b0121ae41275cc9a3c28f7",
        ),
    ],
    "Q26267473": [
        (
            "https://preciousmomentschapel.org/",
            "576b12f16dfc06f11c7da89612bb8715f12f6f9c1f0034bd292d0a977d8cc0f1",
        ),
        (
            "https://preciousmomentschapel.org/pages/visit",
            "1bce3225f3163e4429c4ae0b3b1866fadab284f3cbadc98740957e77f8a9205a",
        ),
    ],
    "Q689585": [
        (
            "https://www.gatorland.com/plan-your-visit/hours-and-prices/",
            "ac98b807010d4f4562d9a1079746f804008e29ffc5d19b2e787409e5f6f6dc09",
        ),
        (
            "https://www.gatorland.com/plan-your-visit/directions/",
            "9f35c681868702a43fbd598f035c4b66c192c108ecf760e898bf854d8127a5a1",
        ),
    ],
}


def _visible(raw):
    document = html.fromstring(raw)
    for element in document.xpath("//script|//style|//noscript"):
        element.drop_tree()
    return " ".join(" ".join(document.itertext()).split())


def _window(opens, closes, *, weekdays=None):
    result = {"opens": opens, "closes": closes, "end_day_offset": 0}
    if weekdays is not None:
        result["weekdays"] = weekdays
    return result


def _clock(literal):
    match = re.fullmatch(r"(1[0-2]|[1-9])(?::([0-5][0-9]))?\s*(am|pm)", literal, re.I)
    if not match:
        raise ValueError("unsupported literal operator clock")
    hour, minute, suffix = match.groups()
    hour = int(hour) % 12 + (12 if suffix.lower() == "pm" else 0)
    return f"{hour:02d}:{int(minute or 0):02d}"


def _require(pages, index, literal):
    if literal not in pages[index]["text"]:
        raise ValueError("literal operator calendar fact missing")
    if literal not in pages[index]["receipt"]["literal"]:
        pages[index]["receipt"]["literal"].append(literal)


def _daily(calendar, pages, index, literal, opens, closes):
    _require(pages, index, literal)
    calendar["weekly_windows"] = [_window(opens, closes, weekdays=list(range(7)))]


def _weekly(calendar, pages, index, entries):
    for weekdays, literal, opens, closes in entries:
        _require(pages, index, literal)
        calendar["weekly_windows"].append(_window(opens, closes, weekdays=weekdays))


def _belmont(calendar, pages):
    """Park-wide negatives override positive hours; ride closures stay separate."""
    document = html.fromstring(pages[0]["raw"])
    positive, negative = defaultdict(list), defaultdict(list)
    entries = []
    for element in document.xpath("//div[@data-date]"):
        title = " ".join(element.xpath(".//h2/text()")).strip()
        state = " ".join(" ".join(element.itertext()).split())
        date_literal, hours = element.get("data-date"), element.get("data-hours")
        day = datetime.strptime(date_literal, "%m/%d/%Y").date().isoformat()
        fact = {
            "date_literal": date_literal,
            "hours_literal": hours,
            "title_literal": title,
            "status_literal": state,
            "featured_literal": element.get("data-featured"),
        }
        entries.append(fact)
        if element.get("data-featured") != "yes":
            continue
        if title in {"Park Hours", "Thanksgiving Park Hours", "Early Closure due to Private Event"}:
            if "Open From " not in state:
                raise ValueError("positive park calendar entry lacks literal open status")
            start, end = (_clock(part.strip()) for part in hours.split(" - "))
            if end <= start:
                raise ValueError("unsupported overnight or empty dated park hours")
            positive[day].append((start, end))
        elif "Closed all day" in state:
            negative[day].append(("00:00", "24:00"))
        elif title in {"RIDES AND ATTRACTIONS CLOSED"} or "Closed due to" in title:
            if "Closed From " not in state:
                raise ValueError("park closure entry lacks literal closure bounds")
            start, end = (_clock(part.strip()) for part in hours.split(" - "))
            if end <= start:
                raise ValueError("unsupported partial park closure")
            negative[day].append((start, end))
        # A separately named open component, e.g. Lazerblast Arcade, does not
        # replace Park Hours or reopen a closed general amusement-park visit.
    if not positive:
        raise ValueError("dated Park Hours missing")
    for day in sorted(set(positive) | set(negative)):
        windows = sorted(set(positive[day]))
        if len(windows) > 1:
            raise ValueError("conflicting positive park-wide hours")
        for closed_start, closed_end in negative[day]:
            remaining = []
            for start, end in windows:
                if end <= closed_start or start >= closed_end:
                    remaining.append((start, end))
                else:
                    if start < closed_start:
                        remaining.append((start, closed_start))
                    if end > closed_end:
                        remaining.append((closed_end, end))
            windows = remaining
        # A partial closure without any published positive hours supplies no
        # admissible window, but is not relabelled an explicit all-day closure.
        if not windows and ("00:00", "24:00") not in negative[day]:
            continue
        calendar["date_overrides"].append(
            {"date": day, "windows": [_window(start, end) for start, end in windows]}
        )
    pages[0]["receipt"]["calendar_entries"] = entries


def build(profile, originals):
    """Return source evidence, never invent an absent clock, season or time zone."""
    calendar = {
        "schema_version": SCHEMA,
        "weekly_windows": [],
        "seasons": [],
        "annual_closures": [],
        "date_overrides": [],
        "source_receipts": [],
        "unknown_reasons": [],
    }
    pages = []
    for receipt, raw in originals:
        pages.append(
            {
                "raw": raw,
                "text": _visible(raw),
                "receipt": {
                    "source_url": receipt["url"],
                    "snapshot_sha256": receipt["sha256"],
                    "checked_at": receipt["retrieved_at"],
                    "literal": list(receipt["required_facts"]),
                    "restrictions": list(receipt["restrictions"]),
                },
            }
        )
    calendar["source_receipts"] = [page["receipt"] for page in pages]
    expected = _PINS.get(profile["qid"])
    actual = [
        (page["receipt"]["source_url"], hashlib.sha256(page["raw"]).hexdigest()) for page in pages
    ]
    if (
        not expected
        or actual != expected
        or any(
            page["receipt"]["snapshot_sha256"] != checksum
            for page, (_, checksum) in zip(pages, actual)
        )
    ):
        calendar["unknown_reasons"].append(
            "Operator originals differ from the pinned calendar review."
        )
        return calendar
    try:
        _emit(profile["qid"], calendar, pages)
    except (ValueError, IndexError, TypeError, AttributeError):
        calendar["weekly_windows"] = []
        calendar["seasons"] = []
        calendar["annual_closures"] = []
        calendar["date_overrides"] = []
        calendar["unknown_reasons"].append(
            "Pinned operator calendar facts are unsupported or conflicting."
        )
    return calendar


def _emit(qid, calendar, pages):
    if qid == "Q44041":
        _belmont(calendar, pages)
    elif qid == "Q24192030":
        _weekly(
            calendar,
            pages,
            0,
            [
                ([0], "Monday 11:00 am - 9:00 pm", "11:00", "21:00"),
                ([1], "Tuesday 12:00 pm - 9:00 pm", "12:00", "21:00"),
                ([2], "Wednesday 12:00 pm - 9:00 pm", "12:00", "21:00"),
                ([3], "Thursday 12:00 pm - 9:00 pm", "12:00", "21:00"),
                ([4], "Friday 12:00 pm - 10:00 pm", "12:00", "22:00"),
                ([5], "Saturday 11:00 am - 11:00 pm", "11:00", "23:00"),
                ([6], "Sunday 11:00 am - 10:00 pm", "11:00", "22:00"),
            ],
        )
    elif qid == "Q14685852":
        _require(pages, 0, "FLORIDA 5145 Harvey Tew Road")
        _require(pages, 0, "Open Daily: 10:00am to 5:00pm Closed Christmas Day KENTUCKY")
        _daily(calendar, pages, 0, "Open Daily: 10:00am to 5:00pm", "10:00", "17:00")
        calendar["annual_closures"] = ["12-25"]
        calendar["seasons"] = [{"kind": "annual", "start": "12-26", "end": "12-24"}]
    elif qid == "Q14709151":
        _require(pages, 0, "Roller skating is open year-round.")
        _require(pages, 1, "Fall/Winter Hours:")
        _require(pages, 1, "For holiday and school-out hours, view our hours calendar .")
        _weekly(
            calendar,
            pages,
            1,
            [
                ([1], "TUE: 3-5 PM", "15:00", "17:00"),
                ([2], "WED: 3-5 PM and 7-9:30 PM", "15:00", "17:00"),
                ([2], "WED: 3-5 PM and 7-9:30 PM", "19:00", "21:30"),
                ([3], "THU: 3-5 PM and 7-9:30 PM", "15:00", "17:00"),
                ([3], "THU: 3-5 PM and 7-9:30 PM", "19:00", "21:30"),
                ([4], "FRI: 1-5 PM and 7-10:30 PM", "13:00", "17:00"),
                ([4], "FRI: 1-5 PM and 7-10:30 PM", "19:00", "22:30"),
                ([5], "SAT: 1-5 PM and 7-10:30 PM", "13:00", "17:00"),
                ([5], "SAT: 1-5 PM and 7-10:30 PM", "19:00", "22:30"),
                ([6], "SUN: 1-5 PM and 7-9:30 PM", "13:00", "17:00"),
                ([6], "SUN: 1-5 PM and 7-9:30 PM", "19:00", "21:30"),
            ],
        )
        calendar["unknown_reasons"].extend(
            [
                "Oaks Open Skate hours apply to Fall/Winter; exact season boundary dates are not published in these originals.",
                "Oaks directs holiday and school-out exceptions to a separate calendar absent from this bundle.",
                "Specialty sessions have separate age/equipment/frequency rules and are excluded from general public skating windows.",
            ]
        )
    elif qid == "Q7085259":
        _weekly(
            calendar,
            pages,
            0,
            [
                ([6, 0, 1, 2, 3], "SUnday - Thursday: 11AM - 9pm", "11:00", "21:00"),
                ([4, 5], "Friday - Saturday: 11am - 11pm", "11:00", "23:00"),
            ],
        )
    elif qid == "Q689585":
        _daily(calendar, pages, 0, "WE’RE OPEN DAILY 10AM – 5PM", "10:00", "17:00")
        _require(pages, 0, "We are also open on ALL holidays.")
    elif qid == "Q26267473":
        _daily(calendar, pages, 0, "Open Daily 9:00am – 5:00pm", "09:00", "17:00")
        _require(pages, 0, "the last Chapel tour is at 4 PM.")
        calendar["unknown_reasons"].append(
            "The last Chapel tour starts at 16:00; general 09:00–17:00 access does not establish the full cultural visit's admission cutoff."
        )
    elif qid == "Q131759816":
        _weekly(
            calendar,
            pages,
            0,
            [
                ([0], "Monday 11:00 AM – 9:00 PM", "11:00", "21:00"),
                ([1], "Tuesday 11:00 AM – 8:00 PM", "11:00", "20:00"),
                ([2], "Wednesday 11:00 AM – 8:00 PM", "11:00", "20:00"),
                ([3], "Thursday 11:00 AM – 8:00 PM", "11:00", "20:00"),
                ([4], "Friday 11:00 AM – 9:00 PM", "11:00", "21:00"),
                ([5], "Saturday 11:00 AM – 10:00 PM", "11:00", "22:00"),
                ([6], "Sunday 11:00 AM – 10:00 PM", "11:00", "22:00"),
            ],
        )
        calendar["unknown_reasons"].append(
            "The operator hours page embeds dated monthly calendar images absent from these originals; weekly footer hours cannot resolve their exceptions."
        )
    elif qid == "Q5160318":
        calendar["unknown_reasons"].append(
            "The admitted Gravity House is open all year but has no verified daily clocks; seasonal Train and conflicting Snack Bar hours cannot be transferred."
        )
    elif qid == "Q23994725":
        calendar["unknown_reasons"].append(
            "Fun Spot Kissimmee is open daily but hours vary by date and no dated opening clocks are retained."
        )
    elif qid == "Q6386811":
        calendar["unknown_reasons"].append(
            "Kemah publishes daily boardwalk access but no actual clocks in the retained current-month hours table; ride hours are seasonal and dining hours differ."
        )
    else:
        calendar["unknown_reasons"].append(
            "No independently reviewed literal calendar for this destination."
        )
