"""Inspected October 15 public visitor arrivals; no inferred parking or hours."""

PROFILES = {
    "9c27cb43-ae9f-4c1f-bf9a-d2f71713053f": {
        "profile": "jurassic-technology/1",
        "name": "The Museum of Jurassic Technology",
        "region": "CA",
        "address": "9341 Venice Blvd",
        "host": "mjt.org",
        "coordinates": [34.0258105, -118.39500601],
        "pages": {
            "https://www.mjt.org/vistinfo/hours.html": [
                "9341 Venice Boulevard",
                "The Museum is open Thursday and Friday",
                "Street parking is available",
                "Children 12 and under, Free",
            ]
        },
        "roads": {"Venice Boulevard"},
        "distance_m": 20,
        "primary_category": "museums",
        "arrival_type": "unchanged licensed venue point at the "
        "published visitor frontage or "
        "documented visitor parking",
        "limitations": "Public museum frontage on Venice "
        "Boulevard; nearby street/structure "
        "parking requires a walk. Suggested "
        "advance reservations and holiday closures "
        "apply. Thursday and Friday evening "
        "visits are published; no scheduler hours "
        "or prices imported. Access evidence is "
        "dated; verify current restrictions "
        "before travel.",
    },
    "f541cb40-d4b5-4cb7-9394-e4b436e32efc": {
        "profile": "glbt-history/1",
        "name": "GLBT Historical Society Museum",
        "region": "CA",
        "address": "4127 18th St",
        "host": "glbthistory.org",
        "coordinates": [37.76068126731418, -122.43568003177644],
        "pages": {
            "https://www.glbthistory.org/museum-about-visitor-info": [
                "4127 18th Street",
                "Tuesday–Sunday",
                "Metered street parking is available",
                "Saturday, October 17: Closed for annual Reunion Gala",
            ]
        },
        "roads": {"18th Street"},
        "distance_m": 25,
        "primary_category": "museums",
        "arrival_type": "unchanged licensed venue point at the "
        "published visitor frontage or "
        "documented visitor parking",
        "limitations": "Published museum frontage, with limited "
        "metered street parking requiring a walk. "
        "Closed October 17, 2026 for its annual "
        "gala; closed Mondays and midday break. "
        "Check dated exceptions and reserve "
        "admission; scheduler hours and future "
        "availability remain unknown. Access "
        "evidence is dated; verify current "
        "restrictions before travel.",
    },
    "c630ba4d-42aa-40af-87d7-57e2256b5f1b": {
        "profile": "martin-auto/1",
        "name": "Martin Auto Museum",
        "region": "AZ",
        "address": "4320 W Thunderbird Rd",
        "host": "martinautomuseum.org",
        "coordinates": [33.6120255, -112.15253723],
        "pages": {
            "https://martinautomuseum.org/visit": [
                "4320 W. Thunderbird Rd",
                "Tuesday–Sunday 9am–5pm",
                "Free on-site parking is available",
            ]
        },
        "roads": {""},
        "distance_m": 50,
        "primary_category": "museums",
        "arrival_type": "unchanged licensed venue point at the "
        "published visitor frontage or "
        "documented visitor parking",
        "limitations": "Published current museum site and "
        "on-site visitor parking. Driving link is "
        "unnamed; not described as Thunderbird "
        "Road. Closed Mondays; group visits need "
        "coordination. Verify current admission "
        "and parking; no prices or scheduler "
        "hours imported. Access evidence is "
        "dated; verify current restrictions "
        "before travel.",
    },
    "e4919ff5-f961-431a-9f46-0ecdd6b20a5d": {
        "profile": "japanese-friendship-phoenix/1",
        "name": "Japanese Friendship Garden",
        "region": "AZ",
        "address": "1125 N 3rd Ave",
        "host": "japanesefriendshipgarden.org",
        "coordinates": [33.460958311576, -112.07668033297],
        "pages": {
            "https://www.japanesefriendshipgarden.org/visit": [
                "1125 N. 3rd Avenue",
                "Tuesday to Sunday",
                "spacious parking lot on the West side of the Garden",
            ]
        },
        "roads": {""},
        "distance_m": 50,
        "primary_category": "nature",
        "arrival_type": "unchanged licensed venue point at the "
        "published visitor frontage or "
        "documented visitor parking",
        "limitations": "Published garden site with west-side "
        "visitor parking; unnamed driving link. "
        "Seasonal schedules differ and last "
        "admission precedes closing. Tickets, "
        "rules, weather, future access and "
        "parking availability require checking; "
        "native point is not a surveyed parking "
        "entrance. Access evidence is dated; "
        "verify current restrictions before "
        "travel.",
    },
    "440a13bb-c07b-4b4f-87aa-8dcbe7b691f1": {
        "profile": "lucky-strike-mar-vista/1",
        "name": "Lucky Strike Mar Vista",
        "region": "CA",
        "address": "12125 Venice Blvd",
        "host": "luckystrikeent.com",
        "coordinates": [34.005406, -118.430548],
        "pages": {
            "https://www.luckystrikeent.com/location/lucky-strike-mar-vista": [
                "12125 Venice Blvd.",
                "This Week’s Hours",
                "Sports Bar",
                "Walk-in only. Subject to lane availability.",
            ]
        },
        "roads": {"Venice Boulevard"},
        "distance_m": 5,
        "primary_category": "entertainment",
        "arrival_type": "unchanged licensed venue point at the "
        "published visitor frontage or "
        "documented visitor parking",
        "limitations": "Published public "
        "bowling/arcade/sports-bar frontage at "
        "the current visitor address. Evening "
        "service is published. On-site parking is "
        "unverified: chain FAQ only says almost "
        "all centers have free parking. Confirm "
        "parking and lane availability; "
        "reservations, prices and future "
        "scheduler hours are unknown. Access "
        "evidence is dated; verify current "
        "restrictions before travel.",
        "additional_categories": ["nightlife"],
    },
    "5679c675-5035-4a2c-91d4-2f4550b3f20f": {
        "profile": "castles-coasters/1",
        "name": "Castles N' Coasters",
        "region": "AZ",
        "address": "9445 N Metro Pkwy E",
        "host": "castlesncoasters.com",
        "coordinates": [33.57261375, -112.11885445],
        "pages": {
            "https://www.castlesncoasters.com/": [
                "HOURS MINI GOLF N’ ARCADE",
                "MONDAY -FRIDAY",
                "10 AM - 10 PM",
            ],
            "https://www.castlesncoasters.com/contact-us": [
                "9445 N Metro Parkway East",
                "OPEN DAILY",
            ],
        },
        "roads": {"North Metro Parkway East"},
        "distance_m": 25,
        "primary_category": "entertainment",
        "arrival_type": "unchanged licensed venue point at the "
        "published visitor frontage or "
        "documented visitor parking",
        "limitations": "Published amusement-park frontage on "
        "Metro Parkway East, with daily visitor "
        "hours and evening mini-golf/arcade "
        "service. On-site parking "
        "location/availability is unverified and "
        "must be checked. Ride schedules differ, "
        "and sales may close before the "
        "attraction. No prices or scheduler "
        "intervals imported. Access evidence is "
        "dated; verify current restrictions "
        "before travel.",
    },
}

for _profile in PROFILES.values():
    _profile["require_raw_driving"] = True
