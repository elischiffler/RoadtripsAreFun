"""Authentic second-batch NPS vectors and full two-hour source access checks."""

import copy
import hashlib
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app.catalog import nps_visit_calendar_more as calendar_more
from app.catalog.nps_visit_calendar_more import (
    CURRENT_EVIDENCE,
    PROFILES,
    CalendarHold,
    EvidenceBoundaryError,
    _EvidenceReader,
    _prose_restrictions,
    _schedule,
    build_entries,
    transform_record,
)
from app.routing.visit_calendar import VisitCalendarConflict, solve_visit, source_calendar

# Source-native literal vectors from the exact immutable bodies. Only listed
# exceptions are included in these narrow unit vectors. The local integration
# fixture below rereads each complete body and every applicable exception.
FACT_VECTORS = {
    "mora": {
        "snapshot_sha256": "f77b484bc884c3891d5b3b534cf6848a6091d92d7afef12395f6e221e0b318ff",
        "native_json_pointer": "/visitorCenters/0",
        "facility": {
            "description": "Located on the south side of Mount Rainier at 2,700 feet above sea level, the museum makes up part of the historic Longmire district. Once a ranger office, the building now houses historic exhibits about the park's natural and geological history, and animals. A ranger or volunteer staffs the museum to assist with park information and book and map sales. "
        },
        "selected": {
            "hours": [
                {
                    "dayOfWeek": 1,
                    "time_close": "4:30 PM",
                    "time_open": "9:00 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 0,
                },
                {
                    "dayOfWeek": 2.0,
                    "time_close": "4:30 PM",
                    "time_open": "9:00 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 0,
                },
                {
                    "dayOfWeek": 3.0,
                    "time_close": "4:30 PM",
                    "time_open": "9:00 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 0,
                },
                {
                    "dayOfWeek": 4.0,
                    "time_close": "4:30 PM",
                    "time_open": "9:00 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 0,
                },
                {
                    "dayOfWeek": 5.0,
                    "time_close": "4:30 PM",
                    "time_open": "9:00 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 0,
                },
                {
                    "dayOfWeek": 6.0,
                    "time_close": "4:30 PM",
                    "time_open": "9:00 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 0,
                },
                {
                    "dayOfWeek": 7.0,
                    "time_close": "4:30 PM",
                    "time_open": "9:00 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 0,
                },
            ],
            "description": "Generally open daily year-round, hours and days of operation may change suddenly due to weather or staffing demands. Closed midday from 12:00 pm - 1:00 pm.",
            "label": "",
            "operatingScheduleID": 1606,
            "type": "Visitor Center",
            "name": "Longmire Museum",
            "exceptions": [],
        },
        "parents": {},
    },
    "chir": {
        "snapshot_sha256": "f7529df8f50c31d8aa86d86879ee312221fb57e9b02b7732b65dde5398c48699",
        "native_json_pointer": "/visitorCenters/0",
        "facility": {
            "description": "The visitor center is on the right 2 miles after the entrance. Open from 8:30 am to 4:30 pm, it has an information desk, museum, park film, and gift shop. It provides free maps, junior ranger booklets, and information.<br /><br />The museum includes geology, biodiversity, and human history exhibits. Its architecture showcases Civilian Conservation Corps rock work and Mission 66 architecture.<br /><br />The park store has shirts, books, stickers, and other collectibles. It is cashless! So, bring your card or mobile pay!"
        },
        "selected": {
            "exceptions": [
                {
                    "holiday_start": "Christmas Day",
                    "description": "The visitor center is closed on Christmas Day. Park facilities and the campground remain open.",
                    "operatingScheduleExceptionID": 3278,
                    "date_start": "",
                    "schedule": [
                        {
                            "dayOfWeek": 1,
                            "time_close": "",
                            "time_open": "",
                            "sunrise_open": 0,
                            "sunset_close": 0,
                            "is_closed": 0,
                        },
                        {
                            "dayOfWeek": 2.0,
                            "time_close": "",
                            "time_open": "",
                            "sunrise_open": 0,
                            "sunset_close": 0,
                            "is_closed": 0,
                        },
                        {
                            "dayOfWeek": 3.0,
                            "time_close": "",
                            "time_open": "",
                            "sunrise_open": 0,
                            "sunset_close": 0,
                            "is_closed": 0,
                        },
                        {
                            "dayOfWeek": 4.0,
                            "time_close": "",
                            "time_open": "",
                            "sunrise_open": 0,
                            "sunset_close": 0,
                            "is_closed": 0,
                        },
                        {
                            "dayOfWeek": 5.0,
                            "time_close": "",
                            "time_open": "",
                            "sunrise_open": 0,
                            "sunset_close": 0,
                            "is_closed": 0,
                        },
                        {
                            "dayOfWeek": 6.0,
                            "time_close": "",
                            "time_open": "",
                            "sunrise_open": 0,
                            "sunset_close": 0,
                            "is_closed": 0,
                        },
                        {
                            "dayOfWeek": 7.0,
                            "time_close": "",
                            "time_open": "",
                            "sunrise_open": 0,
                            "sunset_close": 0,
                            "is_closed": 0,
                        },
                    ],
                    "holiday_end": "Christmas Day",
                    "date_end": "",
                    "name": "Christmas Day",
                }
            ],
            "hours": [
                {
                    "dayOfWeek": 1,
                    "time_close": "4:30 PM",
                    "time_open": "8:30 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 0,
                },
                {
                    "dayOfWeek": 2.0,
                    "time_close": "4:30 PM",
                    "time_open": "8:30 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 0,
                },
                {
                    "dayOfWeek": 3.0,
                    "time_close": "4:30 PM",
                    "time_open": "8:30 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 0,
                },
                {
                    "dayOfWeek": 4.0,
                    "time_close": "4:30 PM",
                    "time_open": "8:30 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 0,
                },
                {
                    "dayOfWeek": 5.0,
                    "time_close": "4:30 PM",
                    "time_open": "8:30 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 0,
                },
                {
                    "dayOfWeek": 6.0,
                    "time_close": "4:30 PM",
                    "time_open": "8:30 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 0,
                },
                {
                    "dayOfWeek": 7.0,
                    "time_close": "4:30 PM",
                    "time_open": "8:30 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 0,
                },
            ],
            "description": "The visitor center is open from 8:30 am to 4:30 pm Mountain Standard Time. **Most of Arizona does not change for daylight savings time!",
            "label": "",
            "operatingScheduleID": 3102,
            "type": "Visitor Center",
            "name": "Chiricahua National Monument Visitor Center",
        },
        "parents": {},
    },
    "tont": {
        "snapshot_sha256": "894ade1b5d46ca4f01c6a19a907716f3429d4e52211724e627e9c0f1745f019e",
        "native_json_pointer": "/visitorCenters/0",
        "facility": {
            "description": "The Visitor Center offers an introduction on the people who built the dwellings 700 years ago. Artifacts and replicas of pottery and textiles are on display in the museum while the park store, operated by Western National Parks Association, sells educational items. The 20-minute park movie, located on the upstairs viewing platform, shows on demand throughout the day. Ask park staff for accessible movie options."
        },
        "selected": {
            "exceptions": [],
            "hours": [
                {
                    "dayOfWeek": 1,
                    "time_close": "4:00 PM",
                    "time_open": "8:00 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 0,
                },
                {
                    "dayOfWeek": 2.0,
                    "time_close": "4:00 PM",
                    "time_open": "8:00 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 0,
                },
                {
                    "dayOfWeek": 3.0,
                    "time_close": "4:00 PM",
                    "time_open": "8:00 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 0,
                },
                {
                    "dayOfWeek": 4.0,
                    "time_close": "4:00 PM",
                    "time_open": "8:00 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 0,
                },
                {
                    "dayOfWeek": 5.0,
                    "time_close": "4:00 PM",
                    "time_open": "8:00 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 0,
                },
                {
                    "dayOfWeek": 6.0,
                    "time_close": "4:00 PM",
                    "time_open": "8:00 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 0,
                },
                {
                    "dayOfWeek": 7.0,
                    "time_close": "4:00 PM",
                    "time_open": "8:00 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 0,
                },
            ],
            "description": "The Visitor Center/Museum is open 8 am to 4 p.m. except Thanksgiving Day, Christmas Day, and New Year's Day. The visitor center will close early at 2:00 p.m. on Christmas Eve and New Year's Eve.",
            "label": "Daily Hours",
            "operatingScheduleID": 3287,
            "type": "Visitor Center",
            "name": "Visitor Center",
        },
        "parents": {
            "3005": {
                "exceptions": [
                    {
                        "holiday_start": "Independence Day",
                        "description": "",
                        "operatingScheduleExceptionID": 28375,
                        "date_start": "",
                        "schedule": [
                            {
                                "dayOfWeek": 1,
                                "time_close": "4:00 PM",
                                "time_open": "8:00 AM",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 0,
                            },
                            {
                                "dayOfWeek": 2.0,
                                "time_close": "4:00 PM",
                                "time_open": "8:00 AM",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 0,
                            },
                            {
                                "dayOfWeek": 3.0,
                                "time_close": "4:00 PM",
                                "time_open": "8:00 AM",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 0,
                            },
                            {
                                "dayOfWeek": 4.0,
                                "time_close": "4:00 PM",
                                "time_open": "8:00 AM",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 0,
                            },
                            {
                                "dayOfWeek": 5.0,
                                "time_close": "4:00 PM",
                                "time_open": "8:00 AM",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 0,
                            },
                            {
                                "dayOfWeek": 6.0,
                                "time_close": "4:00 PM",
                                "time_open": "8:00 AM",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 0,
                            },
                            {
                                "dayOfWeek": 7.0,
                                "time_close": "4:00 PM",
                                "time_open": "8:00 AM",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 0,
                            },
                        ],
                        "holiday_end": "Independence Day",
                        "date_end": "",
                        "name": "Open Independence Day ",
                    },
                    {
                        "holiday_start": "Thanksgiving Day",
                        "description": "",
                        "operatingScheduleExceptionID": 25903,
                        "date_start": "",
                        "schedule": [
                            {
                                "dayOfWeek": 1,
                                "time_close": "",
                                "time_open": "",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 0,
                            },
                            {
                                "dayOfWeek": 2.0,
                                "time_close": "",
                                "time_open": "",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 0,
                            },
                            {
                                "dayOfWeek": 3.0,
                                "time_close": "",
                                "time_open": "",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 0,
                            },
                            {
                                "dayOfWeek": 4.0,
                                "time_close": "",
                                "time_open": "",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 0,
                            },
                            {
                                "dayOfWeek": 5.0,
                                "time_close": "",
                                "time_open": "",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 1,
                            },
                            {
                                "dayOfWeek": 6.0,
                                "time_close": "",
                                "time_open": "",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 0,
                            },
                            {
                                "dayOfWeek": 7.0,
                                "time_close": "",
                                "time_open": "",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 0,
                            },
                        ],
                        "holiday_end": "Thanksgiving Day",
                        "date_end": "",
                        "name": "Closed Thanksgiving Day ",
                    },
                    {
                        "holiday_start": "Christmas Day",
                        "description": "",
                        "operatingScheduleExceptionID": 3225,
                        "date_start": "",
                        "schedule": [
                            {
                                "dayOfWeek": 1,
                                "time_close": "",
                                "time_open": "",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 0,
                            },
                            {
                                "dayOfWeek": 2.0,
                                "time_close": "",
                                "time_open": "",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 0,
                            },
                            {
                                "dayOfWeek": 3.0,
                                "time_close": "",
                                "time_open": "",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 0,
                            },
                            {
                                "dayOfWeek": 4.0,
                                "time_close": "",
                                "time_open": "",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 0,
                            },
                            {
                                "dayOfWeek": 5.0,
                                "time_close": "",
                                "time_open": "",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 0,
                            },
                            {
                                "dayOfWeek": 6.0,
                                "time_close": "",
                                "time_open": "",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 0,
                            },
                            {
                                "dayOfWeek": 7.0,
                                "time_close": "",
                                "time_open": "",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 0,
                            },
                        ],
                        "holiday_end": "Christmas Day",
                        "date_end": "",
                        "name": "Closed December 25",
                    },
                    {
                        "holiday_start": "New Year’s Day",
                        "description": "",
                        "operatingScheduleExceptionID": 27971,
                        "date_start": "",
                        "schedule": [
                            {
                                "dayOfWeek": 1,
                                "time_close": "",
                                "time_open": "",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 0,
                            },
                            {
                                "dayOfWeek": 2.0,
                                "time_close": "",
                                "time_open": "",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 0,
                            },
                            {
                                "dayOfWeek": 3.0,
                                "time_close": "",
                                "time_open": "",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 0,
                            },
                            {
                                "dayOfWeek": 4.0,
                                "time_close": "",
                                "time_open": "",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 0,
                            },
                            {
                                "dayOfWeek": 5.0,
                                "time_close": "",
                                "time_open": "",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 0,
                            },
                            {
                                "dayOfWeek": 6.0,
                                "time_close": "",
                                "time_open": "",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 0,
                            },
                            {
                                "dayOfWeek": 7.0,
                                "time_close": "",
                                "time_open": "",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 0,
                            },
                        ],
                        "holiday_end": "New Year’s Day",
                        "date_end": "",
                        "name": "Closed New Year's Day ",
                    },
                    {
                        "holiday_start": "Juneteenth National Independence Day",
                        "description": "",
                        "operatingScheduleExceptionID": 28373,
                        "date_start": "",
                        "schedule": [
                            {
                                "dayOfWeek": 1,
                                "time_close": "4:00 PM",
                                "time_open": "8:00 AM",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 0,
                            },
                            {
                                "dayOfWeek": 2.0,
                                "time_close": "4:00 PM",
                                "time_open": "8:00 AM",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 0,
                            },
                            {
                                "dayOfWeek": 3.0,
                                "time_close": "4:00 PM",
                                "time_open": "8:00 AM",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 0,
                            },
                            {
                                "dayOfWeek": 4.0,
                                "time_close": "4:00 PM",
                                "time_open": "8:00 AM",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 0,
                            },
                            {
                                "dayOfWeek": 5.0,
                                "time_close": "4:00 PM",
                                "time_open": "8:00 AM",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 0,
                            },
                            {
                                "dayOfWeek": 6.0,
                                "time_close": "4:00 PM",
                                "time_open": "8:00 AM",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 0,
                            },
                            {
                                "dayOfWeek": 7.0,
                                "time_close": "4:00 PM",
                                "time_open": "8:00 AM",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 0,
                            },
                        ],
                        "holiday_end": "Juneteenth National Independence Day",
                        "date_end": "",
                        "name": "Open Juneteenth ",
                    },
                ],
                "hours": [
                    {
                        "dayOfWeek": 1,
                        "time_close": "4:00 PM",
                        "time_open": "8:00 AM",
                        "sunrise_open": 0,
                        "sunset_close": 0,
                        "is_closed": 0,
                    },
                    {
                        "dayOfWeek": 2.0,
                        "time_close": "4:00 PM",
                        "time_open": "8:00 AM",
                        "sunrise_open": 0,
                        "sunset_close": 0,
                        "is_closed": 0,
                    },
                    {
                        "dayOfWeek": 3.0,
                        "time_close": "4:00 PM",
                        "time_open": "8:00 AM",
                        "sunrise_open": 0,
                        "sunset_close": 0,
                        "is_closed": 0,
                    },
                    {
                        "dayOfWeek": 4.0,
                        "time_close": "4:00 PM",
                        "time_open": "8:00 AM",
                        "sunrise_open": 0,
                        "sunset_close": 0,
                        "is_closed": 0,
                    },
                    {
                        "dayOfWeek": 5.0,
                        "time_close": "4:00 PM",
                        "time_open": "8:00 AM",
                        "sunrise_open": 0,
                        "sunset_close": 0,
                        "is_closed": 0,
                    },
                    {
                        "dayOfWeek": 6.0,
                        "time_close": "4:00 PM",
                        "time_open": "8:00 AM",
                        "sunrise_open": 0,
                        "sunset_close": 0,
                        "is_closed": 0,
                    },
                    {
                        "dayOfWeek": 7.0,
                        "time_close": "4:00 PM",
                        "time_open": "8:00 AM",
                        "sunrise_open": 0,
                        "sunset_close": 0,
                        "is_closed": 0,
                    },
                ],
                "description": "Tonto National Monument is open 8:00 am to 4:00 pm all year round. The park is closed Thanksgiving Day, Christmas Day, and New Year's Day. The park closes early at 1:45 pm on Christmas Eve and New Year's Eve. October 3rd through May 3rd, the Lower Cliff Dwelling trail is open 8 am to 3 pm. May 4th to October 3rd, you must start your hike before 12 pm (noon). The Visitor Center, store and museum are open from 8 am to 4 pm.",
                "label": "",
                "operatingScheduleID": 3005,
                "name": "All Park - Tonto National Monument",
            }
        },
    },
    "heho": {
        "snapshot_sha256": "9e56089ae413c44f5371f2429dd1ae6a2a769c3742d27e46de74c4bd525e315f",
        "native_json_pointer": "/visitorCenters/0",
        "facility": {
            "description": "Start your visit at the Visitor Center, where park rangers are available to answer questions and help you get oriented. Allow yourself about 30 minutes in the Visitor Center, which is open from 9:00 a.m. to 5:00 p.m. daily. "
        },
        "selected": {
            "exceptions": [
                {
                    "holiday_start": 0,
                    "description": "The park visitor center and historic buildings will be open 9:00 AM - 4:30 PM from November 1 - March 31. Park grounds are open continually (24 hours) all year.",
                    "operatingScheduleExceptionID": 26594,
                    "date_start": "November 1",
                    "schedule": [
                        {
                            "dayOfWeek": 1,
                            "time_close": "5:00 PM",
                            "time_open": "9:00 AM",
                            "sunrise_open": 0,
                            "sunset_close": 0,
                            "is_closed": 0,
                        },
                        {
                            "dayOfWeek": 2.0,
                            "time_close": "5:00 PM",
                            "time_open": "9:00 AM",
                            "sunrise_open": 0,
                            "sunset_close": 0,
                            "is_closed": 0,
                        },
                        {
                            "dayOfWeek": 3.0,
                            "time_close": "5:00 PM",
                            "time_open": "9:00 AM",
                            "sunrise_open": 0,
                            "sunset_close": 0,
                            "is_closed": 0,
                        },
                        {
                            "dayOfWeek": 4.0,
                            "time_close": "5:00 PM",
                            "time_open": "9:00 AM",
                            "sunrise_open": 0,
                            "sunset_close": 0,
                            "is_closed": 0,
                        },
                        {
                            "dayOfWeek": 5.0,
                            "time_close": "5:00 PM",
                            "time_open": "9:00 AM",
                            "sunrise_open": 0,
                            "sunset_close": 0,
                            "is_closed": 0,
                        },
                        {
                            "dayOfWeek": 6.0,
                            "time_close": "5:00 PM",
                            "time_open": "9:00 AM",
                            "sunrise_open": 0,
                            "sunset_close": 0,
                            "is_closed": 0,
                        },
                        {
                            "dayOfWeek": 7.0,
                            "time_close": "5:00 PM",
                            "time_open": "9:00 AM",
                            "sunrise_open": 0,
                            "sunset_close": 0,
                            "is_closed": 0,
                        },
                    ],
                    "holiday_end": 0,
                    "date_end": "March 31",
                    "name": "Winter Hours of Operation",
                }
            ],
            "hours": [
                {
                    "dayOfWeek": 1,
                    "time_close": "5:00 PM",
                    "time_open": "9:00 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 0,
                },
                {
                    "dayOfWeek": 2.0,
                    "time_close": "5:00 PM",
                    "time_open": "9:00 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 0,
                },
                {
                    "dayOfWeek": 3.0,
                    "time_close": "5:00 PM",
                    "time_open": "9:00 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 0,
                },
                {
                    "dayOfWeek": 4.0,
                    "time_close": "5:00 PM",
                    "time_open": "9:00 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 0,
                },
                {
                    "dayOfWeek": 5.0,
                    "time_close": "5:00 PM",
                    "time_open": "9:00 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 0,
                },
                {
                    "dayOfWeek": 6.0,
                    "time_close": "5:00 PM",
                    "time_open": "9:00 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 0,
                },
                {
                    "dayOfWeek": 7.0,
                    "time_close": "5:00 PM",
                    "time_open": "9:00 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 0,
                },
            ],
            "description": "The loop road from the Presidential Library and Museum to the Gravesite and picnic shelters, and the Village Green Parking Lot (on Parkside Drive across from the Visitor Center) are closed to vehicles and parking from 10:00 p.m. to 6:00 a.m.\n\nThe grounds are open 24 hours.\n\nThe historic buildings have reduced hours of operation throughout the winter. ",
            "label": "Standard Hours",
            "operatingScheduleID": 88,
            "type": "Visitor Center",
            "name": "Visitor Center",
        },
        "parents": {
            "82": {
                "exceptions": [
                    {
                        "holiday_start": 0,
                        "description": "The park visitor center and historic buildings will be open 9:00 AM - 4:30 PM from November 1 - March 31. \n\nPark grounds are open continually (24 hours) all year. ",
                        "operatingScheduleExceptionID": 26487,
                        "date_start": "November 01",
                        "schedule": [
                            {
                                "dayOfWeek": 1,
                                "time_close": "4:30 PM",
                                "time_open": "9:00 AM",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 0,
                            },
                            {
                                "dayOfWeek": 2.0,
                                "time_close": "4:30 PM",
                                "time_open": "9:00 AM",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 0,
                            },
                            {
                                "dayOfWeek": 3.0,
                                "time_close": "4:30 PM",
                                "time_open": "9:00 AM",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 0,
                            },
                            {
                                "dayOfWeek": 4.0,
                                "time_close": "4:30 PM",
                                "time_open": "9:00 AM",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 0,
                            },
                            {
                                "dayOfWeek": 5.0,
                                "time_close": "4:30 PM",
                                "time_open": "9:00 AM",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 0,
                            },
                            {
                                "dayOfWeek": 6.0,
                                "time_close": "4:30 PM",
                                "time_open": "9:00 AM",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 0,
                            },
                            {
                                "dayOfWeek": 7.0,
                                "time_close": "4:30 PM",
                                "time_open": "9:00 AM",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 0,
                            },
                        ],
                        "holiday_end": 0,
                        "date_end": "March 31",
                        "name": "Winter Hours ",
                    },
                    {
                        "holiday_start": "Thanksgiving Day",
                        "description": "The Visitor Center and historic buildings are closed on Thanksgiving Day. Grounds and trails are open.",
                        "operatingScheduleExceptionID": 27910,
                        "date_start": "",
                        "schedule": [
                            {
                                "dayOfWeek": 1,
                                "time_close": "",
                                "time_open": "",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 1,
                            },
                            {
                                "dayOfWeek": 2.0,
                                "time_close": "",
                                "time_open": "",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 1,
                            },
                            {
                                "dayOfWeek": 3.0,
                                "time_close": "",
                                "time_open": "",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 1,
                            },
                            {
                                "dayOfWeek": 4.0,
                                "time_close": "",
                                "time_open": "",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 1,
                            },
                            {
                                "dayOfWeek": 5.0,
                                "time_close": "",
                                "time_open": "",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 1,
                            },
                            {
                                "dayOfWeek": 6.0,
                                "time_close": "",
                                "time_open": "",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 1,
                            },
                            {
                                "dayOfWeek": 7.0,
                                "time_close": "",
                                "time_open": "",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 1,
                            },
                        ],
                        "holiday_end": "Thanksgiving Day",
                        "date_end": "",
                        "name": "Thanksgiving Day",
                    },
                    {
                        "holiday_start": "Christmas Day",
                        "description": "The Visitor Center and historic buildings are closed on Christmas Day. Grounds and trails are open.",
                        "operatingScheduleExceptionID": 22424,
                        "date_start": "",
                        "schedule": [
                            {
                                "dayOfWeek": 1,
                                "time_close": "",
                                "time_open": "",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 1,
                            },
                            {
                                "dayOfWeek": 2.0,
                                "time_close": "",
                                "time_open": "",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 1,
                            },
                            {
                                "dayOfWeek": 3.0,
                                "time_close": "",
                                "time_open": "",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 1,
                            },
                            {
                                "dayOfWeek": 4.0,
                                "time_close": "",
                                "time_open": "",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 1,
                            },
                            {
                                "dayOfWeek": 5.0,
                                "time_close": "",
                                "time_open": "",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 1,
                            },
                            {
                                "dayOfWeek": 6.0,
                                "time_close": "",
                                "time_open": "",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 1,
                            },
                            {
                                "dayOfWeek": 7.0,
                                "time_close": "",
                                "time_open": "",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 1,
                            },
                        ],
                        "holiday_end": "Christmas Day",
                        "date_end": "",
                        "name": "Christmas Day",
                    },
                    {
                        "holiday_start": "New Year’s Day",
                        "description": "The Visitor Center and historic buildings are closed on New Year's Day. Grounds and trails are open.",
                        "operatingScheduleExceptionID": 22426,
                        "date_start": "",
                        "schedule": [
                            {
                                "dayOfWeek": 1,
                                "time_close": "",
                                "time_open": "",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 1,
                            },
                            {
                                "dayOfWeek": 2.0,
                                "time_close": "",
                                "time_open": "",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 1,
                            },
                            {
                                "dayOfWeek": 3.0,
                                "time_close": "",
                                "time_open": "",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 1,
                            },
                            {
                                "dayOfWeek": 4.0,
                                "time_close": "",
                                "time_open": "",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 1,
                            },
                            {
                                "dayOfWeek": 5.0,
                                "time_close": "",
                                "time_open": "",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 1,
                            },
                            {
                                "dayOfWeek": 6.0,
                                "time_close": "",
                                "time_open": "",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 1,
                            },
                            {
                                "dayOfWeek": 7.0,
                                "time_close": "",
                                "time_open": "",
                                "sunrise_open": 0,
                                "sunset_close": 0,
                                "is_closed": 1,
                            },
                        ],
                        "holiday_end": "New Year’s Day",
                        "date_end": "",
                        "name": "New Year's Day",
                    },
                ],
                "hours": [
                    {
                        "dayOfWeek": 1,
                        "time_close": "5:00 PM",
                        "time_open": "9:00 AM",
                        "sunrise_open": 0,
                        "sunset_close": 0,
                        "is_closed": 0,
                    },
                    {
                        "dayOfWeek": 2.0,
                        "time_close": "5:00 PM",
                        "time_open": "9:00 AM",
                        "sunrise_open": 0,
                        "sunset_close": 0,
                        "is_closed": 0,
                    },
                    {
                        "dayOfWeek": 3.0,
                        "time_close": "5:00 PM",
                        "time_open": "9:00 AM",
                        "sunrise_open": 0,
                        "sunset_close": 0,
                        "is_closed": 0,
                    },
                    {
                        "dayOfWeek": 4.0,
                        "time_close": "5:00 PM",
                        "time_open": "9:00 AM",
                        "sunrise_open": 0,
                        "sunset_close": 0,
                        "is_closed": 0,
                    },
                    {
                        "dayOfWeek": 5.0,
                        "time_close": "5:00 PM",
                        "time_open": "9:00 AM",
                        "sunrise_open": 0,
                        "sunset_close": 0,
                        "is_closed": 0,
                    },
                    {
                        "dayOfWeek": 6.0,
                        "time_close": "5:00 PM",
                        "time_open": "9:00 AM",
                        "sunrise_open": 0,
                        "sunset_close": 0,
                        "is_closed": 0,
                    },
                    {
                        "dayOfWeek": 7.0,
                        "time_close": "5:00 PM",
                        "time_open": "9:00 AM",
                        "sunrise_open": 0,
                        "sunset_close": 0,
                        "is_closed": 0,
                    },
                ],
                "description": "From April 1 - October 31, historic buildings and the visitor center are open 9:00 a.m. to 5:00 p.m. \nFrom November 1 - March 31, historic buildings are open 9:00 a.m. to 4:30 p.m. and the visitor center is open 9:00 a.m. to 5:00 p.m.\n\nThe grounds of the historic site are open 24 hours. Overnight parking is not allowed in the park. \n",
                "label": "April 1 - October 31 ",
                "operatingScheduleID": 82,
                "name": "All Park - Operating Hours",
            }
        },
    },
    "pipe": {
        "snapshot_sha256": "c6d82c1d036e431ed5d718c118616ff023c4761170c217efd49fb2f552cc8040",
        "native_json_pointer": "/visitorCenters/0",
        "facility": {
            "description": "Admission is free and includes cultural demonstrations, exhibits, a film, and park store. "
        },
        "selected": {
            "exceptions": [
                {
                    "holiday_start": 0,
                    "description": "The visitor center is closed on Sundays and Mondays from November through April.",
                    "operatingScheduleExceptionID": 29297,
                    "date_start": "November 30",
                    "schedule": [
                        {
                            "dayOfWeek": 1,
                            "time_close": "",
                            "time_open": "",
                            "sunrise_open": 0,
                            "sunset_close": 0,
                            "is_closed": 1,
                        },
                        {
                            "dayOfWeek": 2.0,
                            "time_close": "",
                            "time_open": "",
                            "sunrise_open": 0,
                            "sunset_close": 0,
                            "is_closed": 1,
                        },
                        {
                            "dayOfWeek": 3.0,
                            "time_close": "4:30 PM",
                            "time_open": "8:30 AM",
                            "sunrise_open": 0,
                            "sunset_close": 0,
                            "is_closed": 0,
                        },
                        {
                            "dayOfWeek": 4.0,
                            "time_close": "4:30 PM",
                            "time_open": "8:30 AM",
                            "sunrise_open": 0,
                            "sunset_close": 0,
                            "is_closed": 0,
                        },
                        {
                            "dayOfWeek": 5.0,
                            "time_close": "4:30 PM",
                            "time_open": "8:30 AM",
                            "sunrise_open": 0,
                            "sunset_close": 0,
                            "is_closed": 0,
                        },
                        {
                            "dayOfWeek": 6.0,
                            "time_close": "4:30 PM",
                            "time_open": "8:30 AM",
                            "sunrise_open": 0,
                            "sunset_close": 0,
                            "is_closed": 0,
                        },
                        {
                            "dayOfWeek": 7.0,
                            "time_close": "4:30 PM",
                            "time_open": "8:30 AM",
                            "sunrise_open": 0,
                            "sunset_close": 0,
                            "is_closed": 0,
                        },
                    ],
                    "holiday_end": 0,
                    "date_end": "April 30",
                    "name": "Off Season Hours",
                }
            ],
            "hours": [
                {
                    "dayOfWeek": 1,
                    "time_close": "4:30 PM",
                    "time_open": "8:30 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 0,
                },
                {
                    "dayOfWeek": 2.0,
                    "time_close": "4:30 PM",
                    "time_open": "8:30 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 0,
                },
                {
                    "dayOfWeek": 3.0,
                    "time_close": "4:30 PM",
                    "time_open": "8:30 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 0,
                },
                {
                    "dayOfWeek": 4.0,
                    "time_close": "4:30 PM",
                    "time_open": "8:30 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 0,
                },
                {
                    "dayOfWeek": 5.0,
                    "time_close": "4:30 PM",
                    "time_open": "8:30 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 0,
                },
                {
                    "dayOfWeek": 6.0,
                    "time_close": "4:30 PM",
                    "time_open": "8:30 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 0,
                },
                {
                    "dayOfWeek": 7.0,
                    "time_close": "4:30 PM",
                    "time_open": "8:30 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 0,
                },
            ],
            "description": "Visitor Center hours are subject to change seasonally. When open, the visitor center is open 8:30am - 4:30pm. \nDuring the winter months the visitor center is closed on Sunday and Monday, though the park including the walking trail remains open to visitors.",
            "label": "Summer Hours",
            "operatingScheduleID": 20519,
            "type": "Visitor Center",
            "name": "Visitor Center ",
        },
        "parents": {},
    },
    "kimo": {
        "snapshot_sha256": "e245a05a56585d04ac67919ad10e134f2762e4523e050d197df0af2e05d951e7",
        "native_json_pointer": "/visitorCenters/0",
        "facility": {
            "description": "The visitor center has a movie, a bookstore operated by America's National Parks, and a museum. The museum has artifacts from the battle and audio exhibits inside walk-in trees that resemble the 1780 battlefield."
        },
        "selected": {
            "exceptions": [
                {
                    "holiday_start": "Veterans Day",
                    "description": "",
                    "operatingScheduleExceptionID": 29311,
                    "date_start": "",
                    "schedule": [
                        {
                            "dayOfWeek": 1,
                            "time_close": "",
                            "time_open": "",
                            "sunrise_open": 0,
                            "sunset_close": 0,
                            "is_closed": 0,
                        },
                        {
                            "dayOfWeek": 2.0,
                            "time_close": "",
                            "time_open": "",
                            "sunrise_open": 0,
                            "sunset_close": 0,
                            "is_closed": 0,
                        },
                        {
                            "dayOfWeek": 3.0,
                            "time_close": "",
                            "time_open": "",
                            "sunrise_open": 0,
                            "sunset_close": 0,
                            "is_closed": 0,
                        },
                        {
                            "dayOfWeek": 4.0,
                            "time_close": "",
                            "time_open": "",
                            "sunrise_open": 0,
                            "sunset_close": 0,
                            "is_closed": 0,
                        },
                        {
                            "dayOfWeek": 5.0,
                            "time_close": "",
                            "time_open": "",
                            "sunrise_open": 0,
                            "sunset_close": 0,
                            "is_closed": 0,
                        },
                        {
                            "dayOfWeek": 6.0,
                            "time_close": "",
                            "time_open": "",
                            "sunrise_open": 0,
                            "sunset_close": 0,
                            "is_closed": 0,
                        },
                        {
                            "dayOfWeek": 7.0,
                            "time_close": "",
                            "time_open": "",
                            "sunrise_open": 0,
                            "sunset_close": 0,
                            "is_closed": 0,
                        },
                    ],
                    "holiday_end": "Veterans Day",
                    "date_end": "",
                    "name": "Veterans Day",
                }
            ],
            "hours": [
                {
                    "dayOfWeek": 1,
                    "time_close": "5:00 PM",
                    "time_open": "9:00 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 0,
                },
                {
                    "dayOfWeek": 2.0,
                    "time_close": "12:00 AM",
                    "time_open": "12:00 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 1,
                },
                {
                    "dayOfWeek": 3.0,
                    "time_close": "12:00 AM",
                    "time_open": "12:00 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 1,
                },
                {
                    "dayOfWeek": 4.0,
                    "time_close": "5:00 PM",
                    "time_open": "9:00 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 0,
                },
                {
                    "dayOfWeek": 5.0,
                    "time_close": "5:00 PM",
                    "time_open": "9:00 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 0,
                },
                {
                    "dayOfWeek": 6.0,
                    "time_close": "5:00 PM",
                    "time_open": "9:00 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 0,
                },
                {
                    "dayOfWeek": 7.0,
                    "time_close": "5:00 PM",
                    "time_open": "9:00 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 0,
                },
            ],
            "description": "The Visitor Center is open Wednesday - Sunday 9 am - 5 pm\n\nPark Grounds (trails, parking lot and restrooms) are open daily from 9 am - 5 pm.",
            "label": "",
            "operatingScheduleID": 212,
            "type": "Visitor Center",
            "name": "Kings Mountain National Military Park",
        },
        "parents": {},
    },
    "waco": {
        "snapshot_sha256": "f0baf9feddc41b2f6c69cf2266383c265a0cfa8234d4ddf7145e21e388d63c87",
        "native_json_pointer": "/visitorCenters/0",
        "facility": {
            "description": "Guided tours of the Dig Shelter begin here. Tours are conducted every 30 minutes, no reservation needed. Tours last from 45 minutes to one hour.<br /><br />Tour guides will lead you from the Welcome Center, down a 300 yard paved path to the Dig Shelter where mammoth fossils are in situ (still in their original position within the bone bed). "
        },
        "selected": {
            "exceptions": [],
            "hours": [
                {
                    "dayOfWeek": 1,
                    "time_close": "5:00 PM",
                    "time_open": "9:00 PM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 0,
                },
                {
                    "dayOfWeek": 2.0,
                    "time_close": "5:00 PM",
                    "time_open": "9:00 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 0,
                },
                {
                    "dayOfWeek": 3.0,
                    "time_close": "5:00 PM",
                    "time_open": "9:00 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 0,
                },
                {
                    "dayOfWeek": 4.0,
                    "time_close": "5:00 PM",
                    "time_open": "9:00 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 0,
                },
                {
                    "dayOfWeek": 5.0,
                    "time_close": "5:00 PM",
                    "time_open": "9:00 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 0,
                },
                {
                    "dayOfWeek": 6.0,
                    "time_close": "5:00 PM",
                    "time_open": "9:00 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 0,
                },
                {
                    "dayOfWeek": 7.0,
                    "time_close": "5:00 PM",
                    "time_open": "9:00 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 0,
                },
            ],
            "description": "Open everyday except for Thanksgiving, Christmas, and New Year's Day",
            "label": "",
            "operatingScheduleID": 2739,
            "type": "Visitor Center",
            "name": "Welcome Center",
        },
        "parents": {},
    },
}


def _restrict(code, day):
    vector = FACT_VECTORS[code]
    selected = vector["selected"]
    return _prose_restrictions(
        code,
        date.fromisoformat(day),
        _schedule(selected, date.fromisoformat(day)),
        vector["facility"],
        selected,
        {int(k): value for k, value in vector["parents"].items()},
    )


def test_literal_longmire_lunch_never_becomes_uninterrupted_access():
    assert _restrict("mora", "2026-10-16") == [(540, 720), (780, 990)]


def test_earlier_pipe_spring_prose_restricts_the_whole_month():
    assert _schedule(FACT_VECTORS["pipe"]["selected"], date(2026, 11, 1)) == [(510, 990)]
    assert _restrict("pipe", "2026-11-01") == []
    assert _restrict("pipe", "2026-11-02") == []
    assert _restrict("pipe", "2026-11-03") == [(510, 990)]


def test_parent_tonto_eve_clock_is_stricter_than_facility_clock():
    assert _restrict("tont", "2026-12-24") == [(480, 825)]
    assert _restrict("tont", "2026-12-31") == [(480, 825)]
    assert _restrict("tont", "2026-12-23") == [(480, 960)]


def test_blank_flag_zero_closure_prose_never_establishes_open_holiday():
    assert _schedule(FACT_VECTORS["chir"]["selected"], date(2026, 12, 25)) == []


def test_blank_holiday_without_literal_clocks_remains_unknown():
    with pytest.raises(CalendarHold, match="clock"):
        _schedule(FACT_VECTORS["kimo"]["selected"], date(2026, 11, 11))


def test_reversed_waco_clock_is_not_repaired_from_neighboring_days():
    with pytest.raises(CalendarHold, match="Reversed"):
        _schedule(FACT_VECTORS["waco"]["selected"], date(2026, 10, 18))
    assert _schedule(FACT_VECTORS["waco"]["selected"], date(2026, 10, 19)) == [(540, 1020)]


def test_herbert_hoover_parent_retains_earlier_winter_close():
    vector = FACT_VECTORS["heho"]
    day = date(2026, 11, 1)
    assert _schedule(vector["selected"], day) == [(540, 1020)]
    assert _schedule(vector["parents"]["82"], day) == [(540, 990)]


def test_missing_literal_restriction_cannot_silently_disappear():
    vector = copy.deepcopy(FACT_VECTORS["mora"])
    vector["selected"]["description"] = ""
    with pytest.raises(CalendarHold, match="literal"):
        _prose_restrictions(
            "mora", date(2026, 10, 16), [(540, 990)], vector["facility"], vector["selected"], {}
        )


@pytest.fixture(scope="module")
def retained_inputs():
    base = Path("/tmp/roadtrips-growth-next/hours")
    extraction = base / "extraction-index.json"
    items = Path("/tmp/roadtrips-hours-next/combined-v2/catalog.preview.json")
    if not extraction.is_file() or not items.is_file():
        pytest.skip(
            "Optional complete immutable originals are supplied by the private replay bundle"
        )
    data = json.loads(extraction.read_text(encoding="utf-8"))
    rows = json.loads(items.read_text(encoding="utf-8"))
    return data, rows, {record["catalog_source_id"]: record for record in data["records"]}


@pytest.fixture(scope="module")
def replay(retained_inputs):
    extraction, rows, _ = retained_inputs
    return build_entries(extraction, rows, allow_private_absolute=True)


def _entry(replay, code):
    return next(row for row in replay["entries"] if row["source_id"].split(":")[-1] == code)


def _stop(entry):
    return {
        "provider_id": entry["source_id"],
        "categories": ["culture"],
        "source_provenance": [{"source_visit_calendar": entry["source_visit_calendar"]}],
    }


def test_full_body_replay_is_additive_finite_and_preserves_every_raw_row(retained_inputs, replay):
    extraction, rows, _ = retained_inputs
    before_rows = copy.deepcopy(rows)
    before_extraction = copy.deepcopy(extraction)
    assert replay == build_entries(extraction, rows, allow_private_absolute=True)
    assert rows == before_rows
    assert extraction == before_extraction
    assert replay["summary"] == {
        "requested_rows": 87,
        "emitted_rows": 42,
        "held_rows": 45,
        "positive_dated_days": 2861,
        "positive_dated_windows": 2939,
        "withheld_ambiguous_dates": 14,
    }
    for entry in replay["entries"]:
        calendar = entry["source_visit_calendar"]
        assert calendar["weekly_windows"] == []
        assert calendar["annual_closures"] == []
        assert calendar["unknown_reasons"] == []
        assert not calendar.get("fixed_starts")
        assert source_calendar(_stop(entry))
        assert all(day["date"].startswith("2026-") for day in calendar["date_overrides"])
        for receipt in calendar["source_receipts"]:
            assert (
                hashlib.sha256(Path(receipt["evidence_path"]).read_bytes()).hexdigest()
                == receipt["snapshot_sha256"]
            )


@pytest.mark.parametrize(
    "code,day,start,deadline,expected",
    [
        ("cabr", "2026-10-16", "14:00", "18:00", "14:00"),
        ("cabr", "2026-10-16", "14:01", "18:00", None),
        ("cabr", "2026-10-17", "15:00", "18:00", "15:00"),
        ("cabr", "2026-11-26", "10:00", "18:00", None),
        ("seki", "2026-10-16", "14:30", "18:00", "14:30"),
        ("seki", "2026-10-16", "14:31", "18:00", None),
        ("labe", "2026-11-26", "09:00", "18:00", None),
        ("mora", "2026-10-16", "11:00", "13:00", None),
        ("mora", "2026-10-16", "11:00", "17:00", "13:00"),
        ("mora", "2026-10-16", "14:31", "18:00", None),
        ("zion", "2026-11-28", "15:00", "18:00", "15:00"),
        ("zion", "2026-11-29", "10:00", "18:00", None),
        ("crmo", "2026-11-29", "14:30", "18:00", "14:30"),
        ("crmo", "2026-11-30", "10:00", "18:00", None),
        ("nabr", "2026-10-15", "09:00", "18:00", None),
        ("nabr", "2026-10-16", "14:00", "18:00", "14:00"),
        ("heho", "2026-11-02", "14:31", "18:00", None),
        ("pipe", "2026-11-01", "09:00", "18:00", None),
        ("anjo", "2026-10-19", "09:00", "18:00", None),
        ("kimo", "2026-11-11", "09:00", "18:00", None),
        ("malu", "2026-10-18", "09:00", "18:00", None),
        ("tont", "2026-12-24", "11:45", "18:00", "11:45"),
        ("tont", "2026-12-24", "11:46", "18:00", None),
        ("waco", "2026-10-18", "09:00", "18:00", None),
        ("deto", "2026-11-02", "09:00", "18:00", "10:00"),
        ("grpo", "2026-11-01", "09:00", "18:00", None),
        ("cabr", "2027-10-16", "10:00", "18:00", None),
    ],
)
def test_actual_local_full_dwell_contract(replay, code, day, start, deadline, expected):
    # Deliberately caller-supplied test zone, never claimed as each venue's zone.
    zone = ZoneInfo("America/Los_Angeles")
    arrival = datetime.fromisoformat(f"{day}T{start}").replace(tzinfo=zone)
    end = datetime.fromisoformat(f"{day}T{deadline}").replace(tzinfo=zone)
    stop = _stop(_entry(replay, code))
    if expected is None:
        with pytest.raises(VisitCalendarConflict):
            solve_visit(stop, arrival, end)
    else:
        found, proof = solve_visit(stop, arrival, end)
        assert found.strftime("%H:%M") == expected
        assert proof["dwell_seconds"] == 7200


def test_all_positive_windows_fit_full_dwell_and_reject_one_minute_late(replay):
    # UTC is only an explicit arithmetic test zone, not a venue-zone assertion.
    zone = ZoneInfo("UTC")
    count = 0
    for entry in replay["entries"]:
        for day in entry["source_visit_calendar"]["date_overrides"]:
            for window in day["windows"]:
                opening = datetime.fromisoformat(f"{day['date']}T{window['opens']}").replace(
                    tzinfo=zone
                )
                closing = datetime.fromisoformat(f"{day['date']}T{window['closes']}").replace(
                    tzinfo=zone
                )
                # Isolate a genuine disjoint session: a later afternoon session
                # cannot rescue a start that overruns this morning's cutoff.
                isolated = copy.deepcopy(entry)
                isolated["source_visit_calendar"]["date_overrides"] = [
                    {"date": day["date"], "windows": [window]}
                ]
                latest = closing - timedelta(hours=2)
                actual, proof = solve_visit(_stop(isolated), opening, closing)
                assert actual == opening and proof["dwell_seconds"] == 7200
                actual, _ = solve_visit(_stop(isolated), latest, closing)
                assert actual == latest
                with pytest.raises(VisitCalendarConflict):
                    solve_visit(_stop(isolated), latest + timedelta(minutes=1), closing)
                count += 1
    assert count == 2939


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_acquired_at", "2026-10-16T00:00:00+00:00"),
        ("source_url", "https://www.nps.gov/other/structured_data_other.json"),
        ("facility_json_pointer", "/visitorCenters/999"),
    ],
)
def test_receipt_time_url_and_native_pointer_are_immutable(retained_inputs, field, value):
    _, rows, records = retained_inputs
    record = copy.deepcopy(records["nps-heritage:cabr"])
    record[field] = value
    row = next(r for r in rows if r["source_id"] == record["catalog_source_id"])
    with pytest.raises(CalendarHold):
        transform_record(record, row, allow_private_absolute=True)


def test_changed_source_bytes_and_coordinates_are_held(retained_inputs, tmp_path):
    _, rows, records = retained_inputs
    record = copy.deepcopy(records["nps-heritage:cabr"])
    row = copy.deepcopy(next(r for r in rows if r["source_id"] == record["catalog_source_id"]))
    original = Path(record["retained_snapshot_path"])
    changed = tmp_path / "changed.json"
    changed.write_bytes(original.read_bytes() + b" ")
    record["retained_snapshot_path"] = str(changed)
    with pytest.raises(CalendarHold, match="body"):
        transform_record(record, row, allow_private_absolute=True)
    record["retained_snapshot_path"] = str(original)
    row["latitude"] += 0.001
    with pytest.raises(CalendarHold, match="coordinates"):
        transform_record(record, row, allow_private_absolute=True)


def test_original_admitted_provenance_must_match_selected_facility(retained_inputs):
    _, rows, records = retained_inputs
    record = records["nps-heritage:cabr"]
    row = copy.deepcopy(next(r for r in rows if r["source_id"] == record["catalog_source_id"]))
    row["provenance"] = []
    with pytest.raises(CalendarHold, match="provenance"):
        transform_record(record, row, allow_private_absolute=True)


def test_current_official_corroboration_cannot_be_omitted_or_changed(retained_inputs, tmp_path):
    _, rows, records = retained_inputs
    record = copy.deepcopy(records["nps-heritage:cabr"])
    row = next(r for r in rows if r["source_id"] == record["catalog_source_id"])
    record.pop("current_official_evidence_path")
    with pytest.raises(CalendarHold, match="required"):
        transform_record(record, row, allow_private_absolute=True)
    body = tmp_path / "changed.html"
    body.write_text("Open 24 hours", encoding="utf-8", newline="\n")
    record["current_official_evidence_path"] = str(body)
    with pytest.raises(CalendarHold, match="hash"):
        transform_record(record, row, allow_private_absolute=True)


def test_other_component_closures_and_raw_values_are_retained(replay):
    entry = _entry(replay, "mora")
    carbon = next(
        f
        for f in entry["source_constraints"]
        if isinstance(f.get("native_value"), dict)
        and f["native_value"].get("operatingScheduleID") == 1506
    )
    assert carbon["scope"] == "other_component"
    assert "bridge" in json.dumps(carbon["native_value"]).lower()
    assert any(
        "road to Paradise from Longmire" in f.get("literal", "")
        for f in entry["source_constraints"]
    )
    assert len(entry["source_visit_calendar"]["source_receipts"]) == 2


def test_duplicate_rows_and_unreviewed_profiles_fail_closed(retained_inputs):
    extraction, rows, records = retained_inputs
    with pytest.raises(CalendarHold, match="Duplicate admitted"):
        build_entries(extraction, [*rows, rows[0]], allow_private_absolute=True)
    duplicate = {"records": [records["nps-heritage:cabr"], records["nps-heritage:cabr"]]}
    with pytest.raises(CalendarHold, match="Duplicate extraction"):
        build_entries(duplicate, rows, allow_private_absolute=True)
    row = next(r for r in rows if r["source_id"] == "nps-heritage:puho")
    with pytest.raises(CalendarHold, match="sunset"):
        transform_record(records[row["source_id"]], row, allow_private_absolute=True)


def test_authentic_vector_and_current_review_pins_are_bound_to_profiles():
    assert len(PROFILES) == 42
    assert set(CURRENT_EVIDENCE) == {"mora", "cabr", "seki", "labe"}
    for code, vector in FACT_VECTORS.items():
        profile = next(value for key, value in PROFILES.items() if key.split(":")[1] == code)
        assert vector["snapshot_sha256"] == profile["sha256"]
        assert vector["selected"]["operatingScheduleID"] == profile["schedule_id"]


@pytest.mark.parametrize(
    "path",
    [
        "../outside.json",
        "evidence/../../outside.json",
        "/etc/passwd",
        "C:/outside.json",
        "C:outside.json",
        "\\\\host\\share\\outside.json",
        "evidence\\outside.json",
        "evidence//outside.json",
        "evidence/./outside.json",
        "evidence/CON.json",
        "evidence/LPT1.txt",
        "evidence/body.json.",
        "evidence/body.json ",
        "evidence/body\x00.json",
        "",
    ],
)
def test_portable_evidence_paths_are_confined_before_any_content_read(tmp_path, monkeypatch, path):
    def forbidden(*args, **kwargs):
        pytest.fail("Unsafe evidence must be rejected before opening content")

    monkeypatch.setattr(calendar_more.os, "fdopen", forbidden)
    reader = _EvidenceReader(tmp_path)
    with pytest.raises(EvidenceBoundaryError, match="portable relative"):
        reader.read(path)
    assert reader.total_bytes == 0


def test_portable_reader_rejects_file_and_directory_symlink_escapes(tmp_path, monkeypatch):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    body = outside / "body.json"
    body.write_bytes(b"outside")
    (root / "file.json").symlink_to(body)
    (root / "subdir").symlink_to(outside, target_is_directory=True)

    def forbidden(*args, **kwargs):
        pytest.fail("Symlinks must be rejected before opening content")

    monkeypatch.setattr(calendar_more.os, "fdopen", forbidden)
    for path in ("file.json", "subdir/body.json"):
        reader = _EvidenceReader(root)
        with pytest.raises(EvidenceBoundaryError):
            reader.read(path)
        assert reader.total_bytes == 0


def test_stat_proven_oversize_and_nonregular_evidence_are_never_read(tmp_path, monkeypatch):
    oversized = tmp_path / "large.json"
    with oversized.open("wb") as stream:
        stream.truncate(calendar_more.MAX_SOURCE_BYTES + 1)
    (tmp_path / "directory").mkdir()
    (tmp_path / "empty.json").write_bytes(b"")

    def forbidden(*args, **kwargs):
        pytest.fail("Invalid evidence must fail stat checks before content reads")

    monkeypatch.setattr(calendar_more.os, "fdopen", forbidden)
    reader = _EvidenceReader(tmp_path)
    for path in ("large.json", "directory", "empty.json"):
        with pytest.raises(EvidenceBoundaryError):
            reader.read(path)
    assert reader.total_bytes == 0


def test_aggregate_unique_file_budget_is_checked_before_second_read(tmp_path, monkeypatch):
    # A smaller test-only ceiling exercises the same pre-read boundary without
    # allocating two production-sized100MiB bodies. Production constants remain.
    monkeypatch.setattr(calendar_more, "MAX_SOURCE_BYTES", 8)
    (tmp_path / "one.bin").write_bytes(b"12345")
    (tmp_path / "two.bin").write_bytes(b"abcde")
    original = calendar_more.os.fdopen
    opened = []

    def counted(*args, **kwargs):
        opened.append(True)
        return original(*args, **kwargs)

    monkeypatch.setattr(calendar_more.os, "fdopen", counted)
    reader = _EvidenceReader(tmp_path)
    assert reader.read("one.bin")[1] == b"12345"
    with pytest.raises(EvidenceBoundaryError, match="Aggregate unique-file"):
        reader.read("two.bin")
    assert opened == [True]
    assert reader.total_bytes == 5
    # No invocation shares mutable counters or byte caches.
    independent = _EvidenceReader(tmp_path)
    assert independent.read("two.bin")[1] == b"abcde"
    assert independent.total_bytes == 5


def test_repeated_paths_and_hardlink_aliases_share_one_file_budget(tmp_path, monkeypatch):
    monkeypatch.setattr(calendar_more, "MAX_SOURCE_BYTES", 5)
    original = tmp_path / "original.bin"
    original.write_bytes(b"12345")
    (tmp_path / "alias.bin").hardlink_to(original)
    reader = _EvidenceReader(tmp_path)
    assert reader.read("original.bin")[1] == b"12345"
    assert reader.read("original.bin")[1] == b"12345"
    assert reader.read("alias.bin")[1] == b"12345"
    assert reader.total_bytes == 5


def test_cli_control_jsons_share_the_evidence_aggregate_budget(tmp_path, monkeypatch):
    monkeypatch.setattr(calendar_more, "MAX_SOURCE_BYTES", 8)
    control = tmp_path / "control.json"
    control.write_bytes(b"12345")
    (tmp_path / "evidence.bin").write_bytes(b"abcde")
    reader = _EvidenceReader(tmp_path)
    assert reader.read_control(control) == b"12345"
    with pytest.raises(EvidenceBoundaryError, match="Aggregate unique-file"):
        reader.read("evidence.bin")
    assert reader.total_bytes == 5


def test_file_replacement_after_stat_is_rejected_before_content_read(tmp_path, monkeypatch):
    body = tmp_path / "body.json"
    body.write_bytes(b"original")
    real_open = calendar_more.os.open
    reader = _EvidenceReader(tmp_path)

    def changed_open(path, flags, *args, **kwargs):
        if path == "body.json":
            body.write_bytes(b"changed-longer")
        return real_open(path, flags, *args, **kwargs)

    def forbidden(*args, **kwargs):
        pytest.fail("Changed evidence must be rejected before content reads")

    monkeypatch.setattr(calendar_more.os, "open", changed_open)
    monkeypatch.setattr(calendar_more.os, "fdopen", forbidden)
    with pytest.raises(EvidenceBoundaryError, match="changed before reading"):
        reader.read("body.json")
    assert reader.total_bytes == 0


def test_unsupported_platform_has_an_explicit_safe_replay_boundary(monkeypatch):
    monkeypatch.setattr(calendar_more, "_confined_reads_supported", lambda: False)
    with pytest.raises(CalendarHold, match="run standalone replay on Linux"):
        _EvidenceReader(allow_private_absolute=True)


def test_cached_evidence_cannot_change_mid_invocation(tmp_path):
    body = tmp_path / "body.json"
    body.write_bytes(b"original")
    reader = _EvidenceReader(tmp_path)
    reader.read("body.json")
    body.write_bytes(b"changed")
    with pytest.raises(EvidenceBoundaryError, match="changed during"):
        reader.read("body.json")


def test_absolute_fixtures_need_explicit_private_offline_mode(tmp_path):
    body = tmp_path / "body.json"
    body.write_bytes(b"original")
    with pytest.raises(EvidenceBoundaryError, match="explicit private offline"):
        _EvidenceReader()
    private = _EvidenceReader(allow_private_absolute=True)
    assert private.read(str(body))[1] == b"original"
    with pytest.raises(EvidenceBoundaryError, match="absolute paths"):
        private.read("body.json")
    # An explicit root never permits absolute paths, even if a caller also
    # accidentally passes the legacy private-mode flag.
    confined = _EvidenceReader(tmp_path, allow_private_absolute=True)
    with pytest.raises(EvidenceBoundaryError, match="portable relative"):
        confined.read(str(body))


@pytest.mark.parametrize("oversized", ["extraction", "parent"])
def test_row_limits_are_enforced_before_record_iteration_or_file_reads(tmp_path, oversized):
    class Unreadable(dict):
        def get(self, *args, **kwargs):
            pytest.fail("Record cap must be checked before iteration")

    records = [Unreadable()] * (calendar_more.MAX_SOURCE_ROWS + 1)
    extraction = (
        {"records": records}
        if oversized == "extraction"
        else {"records": [{"catalog_source_id": "one"}]}
    )
    parent = records if oversized == "parent" else [{"source_id": "one"}]
    with pytest.raises(EvidenceBoundaryError, match="1..50000"):
        build_entries(extraction, parent, evidence_root=tmp_path)


def test_path_boundary_failure_aborts_import_instead_of_becoming_partial_hold(
    retained_inputs, tmp_path
):
    _, rows, records = retained_inputs
    record = copy.deepcopy(records["nps-heritage:cabr"])
    record["retained_snapshot_path"] = "../outside.json"
    with pytest.raises(EvidenceBoundaryError, match="portable relative"):
        build_entries({"records": [record]}, rows, evidence_root=tmp_path)


def test_portable_root_replay_keeps_all42_original_calendar_entries_identical(retained_inputs):
    _, rows, _ = retained_inputs
    root = Path("/tmp/roadtrips-growth-next/hours/nps-more-v1")
    extraction = json.loads((root / "extraction-portable.json").read_text(encoding="utf-8"))
    expected = json.loads((root / "entries-and-holds.json").read_text(encoding="utf-8"))
    replayed = build_entries(extraction, rows, evidence_root=root)
    assert replayed["entries"] == expected["entries"]
    assert replayed["summary"] == expected["summary"]
    # Original absolute-fixture replay remains explicitly available and byte-
    # equivalent to the frozen result, without weakening portable root mode.
    original = json.loads((root / "extraction-index.json").read_text(encoding="utf-8"))
    assert build_entries(original, rows, allow_private_absolute=True) == expected


def test_native_and_current_bodies_share_the_same_import_budget(retained_inputs, monkeypatch):
    _, rows, records = retained_inputs
    record = records["nps-heritage:cabr"]
    sizes = [
        Path(record[key]).stat().st_size
        for key in ("retained_snapshot_path", "current_official_evidence_path")
    ]
    # Each genuine body individually fits this test-only cap, but their sum does
    # not. A separate reader in _current would incorrectly admit the row.
    monkeypatch.setattr(calendar_more, "MAX_SOURCE_BYTES", max(sizes))
    with pytest.raises(EvidenceBoundaryError, match="Aggregate unique-file"):
        build_entries({"records": [record]}, rows, allow_private_absolute=True)


def test_individual_native_rows_share_the_same_import_budget(retained_inputs, monkeypatch):
    _, rows, records = retained_inputs
    selected = [records[source_id] for source_id in ("nps:pefo", "nps:zion")]
    monkeypatch.setattr(
        calendar_more,
        "MAX_SOURCE_BYTES",
        max(Path(record["retained_snapshot_path"]).stat().st_size for record in selected),
    )
    with pytest.raises(EvidenceBoundaryError, match="Aggregate unique-file"):
        build_entries({"records": selected}, rows, allow_private_absolute=True)


def test_current_corroboration_cannot_escape_a_portable_evidence_root(retained_inputs):
    _, rows, _ = retained_inputs
    root = Path("/tmp/roadtrips-growth-next/hours/nps-more-v1")
    data = json.loads((root / "extraction-portable.json").read_text(encoding="utf-8"))
    record = next(row for row in data["records"] if row["catalog_source_id"] == "nps-heritage:cabr")
    record["current_official_evidence_path"] = "../outside.html"
    with pytest.raises(EvidenceBoundaryError, match="portable relative"):
        build_entries({"records": [record]}, rows, evidence_root=root)
