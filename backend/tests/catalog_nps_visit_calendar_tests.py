"""Authentic NPS fact vectors, fail-closed replay, and real full-dwell runtime proofs."""

import copy
import hashlib
import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app.catalog.nps_visit_calendar import (
    PROFILES,
    CalendarHold,
    _day_windows,
    _exception_applies,
    _schedule_windows,
    build_entries,
    transform_record,
)
from app.routing.visit_calendar import VisitCalendarConflict, solve_visit, source_calendar

# Literal source-native schedules extracted from the pinned originals. These are
# portable fact vectors; the optional local integration fixture below rechecks
# the complete authentic bodies, their original receipts and native identities.
FACT_VECTORS = {
    "fova": {
        "snapshot_sha256": "ffd95794933cbf9b65366a1281f86863505253adf7d66693aa84e89a24cf374a",
        "native_pointer": "/visitorCenters/0",
        "facility_description": "Begin your visit by learning about all the park's venues "
        "through new exhibits and activities. Watch a short film about "
        "the site's history, peruse the park's bookstore, and enjoy a "
        "display of artwork by American Indian artists. ",
        "schedule": {
            "exceptions": [
                {
                    "holiday_start": "Thanksgiving Day",
                    "description": "",
                    "operatingScheduleExceptionID": 26844,
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
                    "name": "Closed Thanksgiving Day",
                },
                {
                    "holiday_start": 0,
                    "description": "All visitor services (Pearson Air Museum, "
                    "Visitor Center, and Hudson's Bay Company "
                    "Reconstructed Fort) will be closed from "
                    "12/21/25 to 01/05/26. During the Winter "
                    "Season Closure, the park grounds will "
                    "remain open and available for recreational "
                    "visitation. ",
                    "operatingScheduleExceptionID": 28841,
                    "date_start": "December 21",
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
                    "holiday_end": 0,
                    "date_end": "January 5",
                    "name": "Winter Season Closure",
                },
            ],
            "hours": [
                {
                    "dayOfWeek": 1,
                    "time_close": "12:00 AM",
                    "time_open": "12:00 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 1,
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
                    "time_close": "4:00 PM",
                    "time_open": "9:00 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 0,
                },
                {
                    "dayOfWeek": 4.0,
                    "time_close": "4:00 PM",
                    "time_open": "9:00 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 0,
                },
                {
                    "dayOfWeek": 5.0,
                    "time_close": "4:00 PM",
                    "time_open": "9:00 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 0,
                },
                {
                    "dayOfWeek": 6.0,
                    "time_close": "4:00 PM",
                    "time_open": "9:00 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 0,
                },
                {
                    "dayOfWeek": 7.0,
                    "time_close": "4:00 PM",
                    "time_open": "9:00 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 0,
                },
            ],
            "description": "The Fort Vancouver Visitor Center operates Tuesday through "
            "Saturday, in correlation with all other Vancouver, "
            "Washington facilities.\n"
            "Standard Hours = 9AM to 4PM\n"
            "\n",
            "label": "",
            "operatingScheduleID": 21265,
            "type": "Visitor Center",
            "name": "Fort Vancouver Visitor Center",
        },
    },
    "jomu": {
        "snapshot_sha256": "01f3d933f9a8c1ffba8b7ee279da6521c5fd8f6224bc91c6cfa55a401c85a580",
        "native_pointer": "/visitorCenters/0",
        "facility_description": "Main visitor center for the John Muir National Historic Site in "
        "Martinez, California. Closed 12:00PM to 1:00PM every day.",
        "schedule": {
            "exceptions": [
                {
                    "holiday_start": "Thanksgiving Day",
                    "description": "",
                    "operatingScheduleExceptionID": 22481,
                    "date_start": "November 26",
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
                    "date_end": "November 26",
                    "name": "Thanksgiving",
                },
                {
                    "holiday_start": "Christmas Day",
                    "description": "",
                    "operatingScheduleExceptionID": 22480,
                    "date_start": "December 25",
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
                    "date_end": "December 25",
                    "name": "Christmas Day",
                },
                {
                    "holiday_start": "New Year’s Day",
                    "description": "",
                    "operatingScheduleExceptionID": 22479,
                    "date_start": "January 1",
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
                    "date_end": "January 1",
                    "name": "New Years Day",
                },
            ],
            "hours": [
                {
                    "dayOfWeek": 1,
                    "time_close": "12:00 AM",
                    "time_open": "12:00 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 1,
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
                    "time_close": "5:00 PM",
                    "time_open": "10:00 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 0,
                },
                {
                    "dayOfWeek": 4.0,
                    "time_close": "5:00 PM",
                    "time_open": "10:00 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 0,
                },
                {
                    "dayOfWeek": 5.0,
                    "time_close": "5:00 PM",
                    "time_open": "10:00 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 0,
                },
                {
                    "dayOfWeek": 6.0,
                    "time_close": "5:00 PM",
                    "time_open": "10:00 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 0,
                },
                {
                    "dayOfWeek": 7.0,
                    "time_close": "5:00 PM",
                    "time_open": "10:00 AM",
                    "sunrise_open": 0,
                    "sunset_close": 0,
                    "is_closed": 0,
                },
            ],
            "description": "The main park grounds, home and visitor center are open 10 "
            "A.M to 5 P.M. Tuesday through Saturday. We are closed on "
            "Sunday and Monday's. \n"
            "\n"
            "Mount Wanda Site: Open from sunrise to sunset. Some "
            "programs take place at night, which are ranger-guided "
            "only.\n"
            "\n"
            "Holidays\n"
            "Closed on Thanksgiving Day, Christmas Day, and New Year's "
            "Day.",
            "label": "",
            "operatingScheduleID": 205,
            "type": "Visitor Center",
            "name": "John Muir National Historic Site Visitor Center",
        },
    },
    "rira": {
        "snapshot_sha256": "47884544d27c865918661695d9e7f0bfa3cee2487ef618f63b3ab512d989ee18",
        "native_pointer": "/visitorCenters/0",
        "facility_description": "The visitor center is OPEN and offers a Diorama of the River "
        "Raisin Settlement, orientation maps, ranger programs, basic "
        "park orientation, gift shop, passport stamp and the Park film. "
        "The NEW education center is now open to the public while "
        "sections are still under development.",
        "schedule": {
            "exceptions": [
                {
                    "holiday_start": 0,
                    "description": "",
                    "operatingScheduleExceptionID": 29622,
                    "date_start": "October 1",
                    "schedule": [
                        {
                            "dayOfWeek": 1,
                            "time_close": "5:00 PM",
                            "time_open": "10:00 AM",
                            "sunrise_open": 0,
                            "sunset_close": 0,
                            "is_closed": 0,
                        },
                        {
                            "dayOfWeek": 2.0,
                            "time_close": "5:00 PM",
                            "time_open": "10:00 AM",
                            "sunrise_open": 0,
                            "sunset_close": 0,
                            "is_closed": 0,
                        },
                        {
                            "dayOfWeek": 3.0,
                            "time_close": "5:00 PM",
                            "time_open": "10:00 AM",
                            "sunrise_open": 0,
                            "sunset_close": 0,
                            "is_closed": 0,
                        },
                        {
                            "dayOfWeek": 4.0,
                            "time_close": "5:00 PM",
                            "time_open": "10:00 AM",
                            "sunrise_open": 0,
                            "sunset_close": 0,
                            "is_closed": 0,
                        },
                        {
                            "dayOfWeek": 5.0,
                            "time_close": "5:00 PM",
                            "time_open": "10:00 AM",
                            "sunrise_open": 0,
                            "sunset_close": 0,
                            "is_closed": 0,
                        },
                        {
                            "dayOfWeek": 6.0,
                            "time_close": "5:00 PM",
                            "time_open": "10:00 AM",
                            "sunrise_open": 0,
                            "sunset_close": 0,
                            "is_closed": 0,
                        },
                        {
                            "dayOfWeek": 7.0,
                            "time_close": "5:00 PM",
                            "time_open": "10:00 AM",
                            "sunrise_open": 0,
                            "sunset_close": 0,
                            "is_closed": 0,
                        },
                    ],
                    "holiday_end": 0,
                    "date_end": "March 31",
                    "name": "Winter Hours",
                },
                {
                    "holiday_start": "Thanksgiving Day",
                    "description": "",
                    "operatingScheduleExceptionID": 1712,
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
                    "name": "CLOSED Thanksgiving Day",
                },
                {
                    "holiday_start": "Christmas Day",
                    "description": "",
                    "operatingScheduleExceptionID": 1713,
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
                    "name": "CLOSED Christmas Day",
                },
                {
                    "holiday_start": "New Year’s Day",
                    "description": "",
                    "operatingScheduleExceptionID": 1714,
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
                    "name": "CLOSED New Year's Day",
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
            "description": "The new visitor center is open year-round except on "
            "Thanksgiving Day, Christmas Day, and New Year's Day.",
            "label": " Standard Hours",
            "operatingScheduleID": 1512,
            "type": "Visitor Center",
            "name": "River Raisin National Battlefield Park Visitor / Education Center",
        },
    },
}


def test_authentic_fort_vancouver_weekdays_and_winter_conflict():
    vector = FACT_VECTORS["fova"]
    assert vector["snapshot_sha256"] == PROFILES["nps-heritage:fova"]["sha256"]
    schedule = vector["schedule"]
    assert _schedule_windows(schedule, date(2026, 10, 16)) == [(540, 960)]
    assert _schedule_windows(schedule, date(2026, 10, 18)) == []
    assert _schedule_windows(schedule, date(2026, 11, 26)) == []
    winter = schedule["exceptions"][1]
    assert "12/21/25 to 01/05/26" in winter["description"]
    assert winter["date_start"] == "December 21"
    assert winter["date_end"] == "January 5"


def test_authentic_river_raisin_winter_opens_later():
    vector = FACT_VECTORS["rira"]
    assert _schedule_windows(vector["schedule"], date(2026, 10, 16)) == [(600, 1020)]
    assert _schedule_windows(vector["schedule"], date(2026, 11, 26)) == []


def test_authentic_john_muir_native_schedule_keeps_closed_weekdays():
    vector = FACT_VECTORS["jomu"]
    assert "Closed 12:00PM to 1:00PM every day." in vector["facility_description"]
    assert _schedule_windows(vector["schedule"], date(2026, 10, 17)) == [(600, 1020)]
    assert _schedule_windows(vector["schedule"], date(2026, 10, 18)) == []


@pytest.mark.parametrize("axis", ["sunrise_open", "sunset_close"])
def test_astronomical_boundaries_do_not_become_literal_hours(axis):
    hours = copy.deepcopy(FACT_VECTORS["fova"]["schedule"]["hours"])
    hours[6][axis] = 1
    with pytest.raises(CalendarHold, match="Astronomical"):
        _day_windows(hours, date(2026, 10, 17))


@pytest.mark.parametrize(
    "opened,closed", [("", ""), ("9:00 PM", "5:00 PM"), ("12:00 AM", "12:00 AM")]
)
def test_blank_flags_typo_and_midnight_placeholder_do_not_create_availability(opened, closed):
    hours = copy.deepcopy(FACT_VECTORS["fova"]["schedule"]["hours"])
    hours[6].update(time_open=opened, time_close=closed, is_closed=0)
    with pytest.raises(CalendarHold):
        _day_windows(hours, date(2026, 10, 17))


def test_native_holiday_and_literal_date_conflict_restricts_both_dates():
    exception = {
        "date_start": "November 25",
        "date_end": "November 25",
        "holiday_start": "Thanksgiving Day",
        "holiday_end": "Thanksgiving Day",
    }
    assert _exception_applies(exception, date(2026, 11, 25))
    assert _exception_applies(exception, date(2026, 11, 26))
    assert not _exception_applies(exception, date(2026, 11, 27))


def test_unknown_exception_selector_withholds_instead_of_disappearing():
    schedule = copy.deepcopy(FACT_VECTORS["fova"]["schedule"])
    schedule["exceptions"][0]["holiday_start"] = "Unspecified observed closure"
    with pytest.raises(CalendarHold, match="Unsupported native holiday"):
        _schedule_windows(schedule, date(2026, 10, 16))


@pytest.fixture(scope="module")
def retained_inputs():
    source = Path(
        "/workspace/calendar-enrichment-analysis-20261015/nps/nps-operating-hours-native.json"
    )
    items_path = Path("/workspace/catalog-expansion-next/production500-items.json")
    if not source.is_file() or not items_path.is_file():
        pytest.skip(
            "Private authentic acquisition originals are available only in source-replay environment"
        )
    extraction = json.loads(source.read_text(encoding="utf-8"))
    for record in extraction["records"]:
        code = record["catalog_source_id"].split(":")[-1]
        if code in {"jomu", "rori", "manz"}:
            record["current_official_evidence_path"] = str(
                source.parent / "current-official" / f"{code}.html"
            )
    items = json.loads(items_path.read_text(encoding="utf-8"))
    records = {record["catalog_source_id"]: record for record in extraction["records"]}
    return extraction, items, records


@pytest.fixture(scope="module")
def replay(retained_inputs):
    extraction, items, _ = retained_inputs
    return build_entries(extraction, items)


def test_authentic_replay_is_deterministic_preserves_all_source_rows_and_explains_every_hold(
    retained_inputs, replay
):
    extraction, items, _ = retained_inputs
    untouched = copy.deepcopy(items)
    assert build_entries(extraction, items) == replay
    assert items == untouched
    assert replay["summary"]["emitted_rows"] == 35
    assert replay["summary"]["held_rows"] == 87
    assert len({row["source_id"] for row in [*replay["entries"], *replay["holds"]]}) == 122
    assert all(row["reason"] and row["evidence_path"] for row in replay["holds"])
    holds = {row["source_id"]: row["reason"] for row in replay["holds"]}
    assert "sunset" in holds["nps-heritage:puho"]
    assert "404" in holds["nps-heritage:cabr"]
    assert "No supported positive" in holds["nps-heritage:pete"]


def test_all_receipts_resolve_to_exact_original_bytes_and_original_times(replay):
    for entry in replay["entries"]:
        for receipt in entry["source_visit_calendar"]["source_receipts"]:
            assert (
                hashlib.sha256(Path(receipt["evidence_path"]).read_bytes()).hexdigest()
                == receipt["snapshot_sha256"]
            )
            assert datetime.fromisoformat(receipt["checked_at"]).year == 2026
        calendar = entry["source_visit_calendar"]
        assert calendar["weekly_windows"] == []
        assert calendar["annual_closures"] == []
        assert calendar["unknown_reasons"] == []
        assert not calendar.get("fixed_starts")
        assert source_calendar({"source_provenance": [{"source_visit_calendar": calendar}]})
        assert all(day["date"].startswith("2026-") for day in calendar["date_overrides"])


def _entry(replay, code):
    return next(row for row in replay["entries"] if row["source_id"].split(":")[-1] == code)


def _stop(replay, code):
    entry = _entry(replay, code)
    return {
        "provider_id": entry["source_id"],
        "categories": ["culture"],
        "source_provenance": [{"source_visit_calendar": entry["source_visit_calendar"]}],
    }


@pytest.mark.parametrize(
    "code,arrival,deadline,expected",
    [
        ("rori", "2026-10-16T14:30", "2026-10-16T20:00", "14:30"),
        ("rori", "2026-10-16T15:01", "2026-10-16T20:00", None),
        ("rori", "2026-11-26T10:00", "2026-11-26T20:00", None),
        ("rori", "2026-12-25T10:00", "2026-12-25T20:00", None),
        ("rori", "2027-01-02T10:00", "2027-01-02T20:00", None),
        ("fova", "2026-10-16T14:00", "2026-10-16T20:00", "14:00"),
        ("fova", "2026-10-18T10:00", "2026-10-18T20:00", None),
        ("fova", "2026-10-20T09:00", "2026-10-20T20:00", "09:00"),
        ("fova", "2026-12-04T09:00", "2026-12-04T20:00", "09:00"),
        ("fova", "2026-12-22T09:00", "2026-12-22T20:00", None),
        ("jomu", "2026-10-17T10:00", "2026-10-17T12:00", "10:00"),
        ("jomu", "2026-10-17T11:00", "2026-10-17T13:00", None),
        ("jomu", "2026-10-17T11:00", "2026-10-17T17:00", "13:00"),
        ("jomu", "2026-10-18T10:00", "2026-10-18T20:00", None),
        ("rira", "2026-10-16T09:00", "2026-10-16T20:00", "10:00"),
        ("wupa", "2026-11-03T09:00", "2026-11-03T20:00", None),
        ("liho", "2026-12-24T09:00", "2026-12-24T20:00", None),
        ("moca", "2026-11-25T09:00", "2026-11-25T20:00", None),
        ("moca", "2026-12-24T09:00", "2026-12-24T20:00", None),
        ("puhe", "2026-10-16T14:01", "2026-10-16T20:00", None),
        ("chyo", "2026-11-11T09:00", "2026-11-11T20:00", None),
    ],
)
def test_authentic_calendars_constrain_whole_two_hour_dwell(
    replay, code, arrival, deadline, expected
):
    # This explicit zone is supplied by the test caller, never by the normalizer.
    zone = ZoneInfo("America/Los_Angeles")
    earliest = datetime.fromisoformat(arrival).replace(tzinfo=zone)
    latest = datetime.fromisoformat(deadline).replace(tzinfo=zone)
    if expected is None:
        with pytest.raises(VisitCalendarConflict):
            solve_visit(_stop(replay, code), earliest, latest)
    else:
        start, proof = solve_visit(_stop(replay, code), earliest, latest)
        assert start.strftime("%H:%M") == expected
        assert proof["dwell_seconds"] == 7200


def test_other_component_facts_are_attributed_without_transferring_their_hours(replay):
    facts = _entry(replay, "fova")["source_constraints"]
    oregon = next(
        fact
        for fact in facts
        if isinstance(fact.get("native_value"), dict)
        and fact["native_value"].get("operatingScheduleID") == 1713
    )
    assert oregon["scope"] == "other_component"
    assert "Oregon" in oregon["native_value"]["name"]
    assert any(
        fact.get("literal") == "Muir/Strentzel House closes at 4:30 PM."
        for fact in _entry(replay, "jomu")["source_constraints"]
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_acquired_at", "2026-10-16T00:00:00+00:00"),
        ("source_url", "https://www.nps.gov/other/structured_data_other.json"),
        ("facility_json_pointer", "/visitorCenters/999"),
    ],
)
def test_original_receipt_and_native_identity_cannot_be_refreshed_or_reassigned(
    retained_inputs, field, value
):
    _, items, records = retained_inputs
    record = copy.deepcopy(records["nps-heritage:fova"])
    record[field] = value
    item = next(row for row in items if row["source_id"] == record["catalog_source_id"])
    with pytest.raises(CalendarHold):
        transform_record(record, item)


def test_changed_original_body_and_moved_coordinate_are_held(retained_inputs, tmp_path):
    _, items, records = retained_inputs
    record = copy.deepcopy(records["nps-heritage:fova"])
    item = copy.deepcopy(
        next(row for row in items if row["source_id"] == record["catalog_source_id"])
    )
    original_path = Path(record["retained_snapshot_path"])
    changed = tmp_path / "changed.json"
    changed.write_bytes(original_path.read_bytes() + b" ")
    record["retained_snapshot_path"] = str(changed)
    with pytest.raises(CalendarHold, match="hash"):
        transform_record(record, item)
    record["retained_snapshot_path"] = str(original_path)
    item["latitude"] += 0.001
    with pytest.raises(CalendarHold, match="coordinates"):
        transform_record(record, item)


def test_current_corroborating_original_cannot_be_omitted_or_changed(retained_inputs, tmp_path):
    _, items, records = retained_inputs
    record = copy.deepcopy(records["nps-heritage:rori"])
    item = next(row for row in items if row["source_id"] == record["catalog_source_id"])
    record.pop("current_official_evidence_path")
    with pytest.raises(CalendarHold, match="corroboration"):
        transform_record(record, item)
    changed = tmp_path / "changed.html"
    changed.write_text("Open 24 hours", encoding="utf-8", newline="\n")
    record["current_official_evidence_path"] = str(changed)
    with pytest.raises(CalendarHold, match="immutable"):
        transform_record(record, item)
