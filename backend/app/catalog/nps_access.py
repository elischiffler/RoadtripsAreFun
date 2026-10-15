"""Conservative exclusion of published NPS dated facility closures."""

import re
from datetime import datetime, timedelta


def dated_closure(facility, checked):
    """Conservatively withhold published closed-date exceptions in the US day window.

    This is an exclusion check, not an opening-hours solver. Holiday names and
    future availability remain unknown. Month/day NPS periods are recurring;
    an unparseable dated closure is held for manual review.
    """
    today = datetime.fromisoformat(checked.replace("Z", "+00:00")).date()
    days = [today, today - timedelta(days=1)]
    for schedule in facility.get("operatingHours", {}).values():
        for exception in schedule.get("exceptions", []):
            hours = exception.get("schedule", [])
            if not hours or any(h.get("is_closed") != 1 for h in hours):
                continue
            start, end = exception.get("date_start"), exception.get("date_end")
            if not start and not end:
                if not exception.get("holiday_start") and re.search(
                    r"closure|closed|renovation|construction", exception.get("name", ""), re.I
                ):
                    return True
                continue
            if not start or not end:
                return True
            try:
                if re.fullmatch(r"\d{4}-\d{2}-\d{2}", start) and re.fullmatch(
                    r"\d{4}-\d{2}-\d{2}", end
                ):
                    a, b = datetime.fromisoformat(start).date(), datetime.fromisoformat(end).date()
                    if any(a <= day <= b for day in days):
                        return True
                else:
                    a = datetime.strptime(start + " 2000", "%B %d %Y")
                    b = datetime.strptime(end + " 2000", "%B %d %Y")
                    low, high = (a.month, a.day), (b.month, b.day)
                    for day in days:
                        value = (day.month, day.day)
                        if (
                            (low <= value <= high)
                            if low <= high
                            else (value >= low or value <= high)
                        ):
                            return True
            except (ValueError, TypeError):
                return True
    return False
