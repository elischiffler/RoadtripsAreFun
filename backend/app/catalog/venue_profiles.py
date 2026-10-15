"""Explicit October 15 publisher/parking reviews; source points remain unchanged.

Bounds apply only to these inspected venues and retained evidence. An unnamed
network link is not a street-name or public-parking assertion by itself.
"""

PROFILES = {
    "0810c0be-b526-4ae2-8d78-45171e9642ae": {
        "profile": "gates-brovi/1",
        "name": "Gates & Brovi",
        "region": "WI",
        "address": "3502 Monroe St",
        "host": "gatesandbrovi.com",
        "coordinates": [43.05293244, -89.43552756],
        "pages": {
            "https://gatesandbrovi.com/location": [
                "3502 Monroe Street",
                "small parking lot",
                "DINNER Monday - Thursday",
            ]
        },
        "roads": {"Glenway Street"},
        "distance_m": 15,
        "primary_category": "food",
        "arrival_type": "licensed venue point at published Monroe/Glenway corner with guest parking",
        "limitations": "Small guest lot; driving waypoint is on Glenway Street. Check current visitor hours, holidays and parking restrictions before travel; future access and parking availability are unknown.",
    },
    "dd062c88-fb8c-4b5d-bde9-39acea846503": {
        "profile": "lombardinos/1",
        "name": "Lombardino's Restaurant",
        "region": "WI",
        "address": "2500 University Ave",
        "host": "lombardinos.com",
        "coordinates": [43.07223441096537, -89.42890405654909],
        "pages": {
            "https://lombardinos.com/": [
                "2500 UNIVERSITY AVE",
                "off street parking on the west side",
                "Thursday thru Sunday",
            ]
        },
        "roads": {""},
        "distance_m": 15,
        "primary_category": "food",
        "arrival_type": "licensed venue point beside published west-side guest parking",
        "limitations": "Unnamed driving link is not labeled University Avenue. Limited dinner days and seating; verify availability. Check current visitor hours, holidays and parking restrictions before travel; future access and parking availability are unknown.",
    },
    "f3e80899-5de4-4e86-9639-bed1dbf3faf9": {
        "profile": "everly/1",
        "name": "Everly",
        "region": "WI",
        "address": "2701 Monroe St",
        "host": "everlymadison.com",
        "coordinates": [43.05688575, -89.42870342],
        "pages": {
            "http://www.everlymadison.com/location/everly/": [
                "2701 Monroe St",
                "large parking lot in front",
                "Monday - Thursday",
            ]
        },
        "roads": {""},
        "distance_m": 5,
        "primary_category": "food",
        "arrival_type": "licensed venue point beside published front guest lot",
        "limitations": "Shared plaza lot; unnamed driving link. Reservations encouraged. Check current visitor hours, holidays and parking restrictions before travel; future access and parking availability are unknown.",
    },
    "134bc52d-0c47-4bac-be75-850c593498e4": {
        "profile": "lallande/1",
        "name": "Lallande",
        "region": "WI",
        "address": "1859 Monroe St",
        "host": "lallandemadison.com",
        "coordinates": [43.06473107, -89.41707949],
        "pages": {
            "https://www.lallandemadison.com/faqs": [
                "1859 Monroe St",
                "open Wednesday through Saturday",
                "metered spots",
                "Monroe Street",
            ]
        },
        "roads": {"Monroe Street"},
        "distance_m": 20,
        "primary_category": "food",
        "arrival_type": "licensed venue frontage at published address",
        "limitations": "Wednesday–Saturday dinner service; street parking requires a walk. No guest lot behind the restaurant. Check current visitor hours, holidays and parking restrictions before travel; future access and parking availability are unknown.",
    },
    "7dbd1568-a1cc-4f6c-bfe2-a94d1a5765a6": {
        "profile": "begonia-madison/1",
        "name": "Begonia. Modern Latin",
        "region": "WI",
        "address": "1835 Monroe St",
        "host": "begoniamadison.com",
        "coordinates": [43.0650371, -89.41686227],
        "pages": {
            "https://www.begoniamadison.com/parking-directions": [
                "1835 Monroe St",
                "Street parking and nearby public parking",
                "Tues–Thurs",
            ]
        },
        "roads": {"Monroe Street"},
        "distance_m": 10,
        "primary_category": "food",
        "arrival_type": "licensed venue frontage at published address",
        "limitations": "Street/public lot parking requires a walk. Nearby Badger games affect restrictions and availability; limited dinner days. Check current visitor hours, holidays and parking restrictions before travel; future access and parking availability are unknown.",
    },
    "06e42244-a32a-4e3b-a590-0a67aae60ce0": {
        "profile": "garths-brew-bar/1",
        "name": "Garth's Brew Bar",
        "region": "WI",
        "address": "1726 Monroe St",
        "host": "garthsbrewbar.com",
        "coordinates": [43.06559112, -89.41628371],
        "pages": {
            "https://www.garthsbrewbar.com/faq/": [
                "1726 Monroe Street",
                "DRINKING HOURS",
                "Street parking",
                "free in the evenings",
            ]
        },
        "roads": {"Monroe Street"},
        "distance_m": 10,
        "primary_category": "nightlife",
        "arrival_type": "licensed venue frontage at published address",
        "limitations": "Bar serving alcohol; verify party eligibility. Closed Mondays. Street parking requires a walk. Check current visitor hours, holidays and parking restrictions before travel; future access and parking availability are unknown.",
    },
    "a83224d1-0e20-459e-94bf-7163444a2821": {
        "profile": "alaska-aviation-museum/1",
        "name": "Alaska Aviation Museum",
        "region": "AK",
        "address": "4721 Aircraft Dr",
        "host": "alaskaairmuseum.org",
        "coordinates": [61.17939588, -149.97191488],
        "pages": {
            "https://alaskaairmuseum.org/visitor-map/": [
                "4721 Aircraft Drive",
                "CONVENIENT PARKING",
                "Open Daily 10am to 5pm",
            ]
        },
        "roads": {""},
        "distance_m": 15,
        "primary_category": "museums",
        "arrival_type": "licensed museum point beside publisher-advertised visitor parking",
        "limitations": "Unnamed driving link at Lake Hood museum; no claim of access to airport aprons. Seasonal weekly hours vary. Check current visitor hours, holidays and parking restrictions before travel; future access and parking availability are unknown.",
    },
    "08b82fef-d926-46f4-b92c-42aa32ada778": {
        "profile": "brumby-gone-with-wind/1",
        "name": "Gone With the Wind Museum at Brumby Hall",
        "region": "GA",
        "address": "472 Powder Springs St SW",
        "host": "gwtwmarietta.com",
        "coordinates": [33.943760469697324, -84.55215453522075],
        "pages": {
            "https://www.gwtwmarietta.com/": [
                "472 Powder Springs Street",
                "Hilton parking lot",
                "Tuesday — Saturday",
            ]
        },
        "roads": {""},
        "distance_m": 10,
        "primary_category": "museums",
        "arrival_type": "licensed visitor point beside published Hilton parking approach",
        "limitations": "Use Hilton Conference Center entrance and walk uphill through the gate to Brumby Hall. Unnamed driving link; Tuesday–Saturday visits. Check current visitor hours, holidays and parking restrictions before travel; future access and parking availability are unknown.",
    },
    "91a99172-f3a6-4e36-9c6d-7ba4852fcee3": {
        "profile": "california-heritage-museum/1",
        "name": "California Heritage Museum",
        "region": "CA",
        "address": "2612 Main St",
        "host": "californiaheritagemuseum.org",
        "coordinates": [34.00206326, -118.4839382],
        "pages": {
            "https://californiaheritagemuseum.org/visit": [
                "Wednesday through Sunday",
                "Limited free parking adjacent",
                "Ocean Park Boulevard",
            ],
            "https://californiaheritagemuseum.org/": ["2612 Main Street"],
        },
        "roads": {"Ocean Park Boulevard"},
        "distance_m": 15,
        "primary_category": "museums",
        "arrival_type": "licensed venue point at Main/Ocean Park frontage",
        "limitations": "Limited adjacent parking and nearby paid lots require a walk. Sunday parking differs; Wednesday–Sunday public visits, last tour 3:30 pm. Check current visitor hours, holidays and parking restrictions before travel; future access and parking availability are unknown.",
    },
    "05672cd0-77c3-41db-97c1-929f3c0ebe9d": {
        "profile": "armenian-museum-america/1",
        "name": "Armenian Museum of America",
        "region": "MA",
        "address": "65 Main St",
        "host": "armenianmuseum.org",
        "coordinates": [42.36641168, -71.18568955],
        "pages": {
            "https://www.armenianmuseum.org/visit": [
                "65 Main Street",
                "Watertown Municipal lots behind the Museum",
                "Thursday 12:00 pm",
            ]
        },
        "roads": {"Main Street"},
        "distance_m": 20,
        "primary_category": "museums",
        "arrival_type": "licensed venue frontage at published address",
        "limitations": "Public gallery Thursday–Sunday; weekday administrative office hours are not visitor hours. Municipal lots behind museum require a walk. Check current visitor hours, holidays and parking restrictions before travel; future access and parking availability are unknown.",
    },
    "2abb1511-8b94-4503-8c49-46c17ddae309": {
        "profile": "connections-seattle/1",
        "name": "Connections Museum",
        "region": "WA",
        "address": "7000 E Marginal Wy S",
        "host": "connectionsmuseum.org",
        "coordinates": [47.540846055746044, -122.32320968704548],
        "pages": {
            "https://www.telcomhistory.org/ConnectionsSeattle.html": [
                "7000 E Marginal Way S",
                "parking lot entrance is on Corson Avenue",
                "every Sunday",
            ]
        },
        "roads": {""},
        "distance_m": 20,
        "primary_category": "museums",
        "arrival_type": "licensed visitor point beside published museum parking",
        "limitations": "Sunday-only volunteer guided tours; doors close at 2:30 pm. Lot entrance is published on Corson Avenue; checked link is unnamed. Check current visitor hours, holidays and parking restrictions before travel; future access and parking availability are unknown.",
    },
    "815d0220-8400-4205-93f9-8e12cf265c0f": {
        "profile": "phoenix-art-museum/1",
        "name": "Phoenix Art Museum",
        "region": "AZ",
        "address": "1625 N Central Ave",
        "host": "phxart.org",
        "coordinates": [33.46712768, -112.07296265],
        "pages": {
            "https://phxart.org/visit/": [
                "1625 North Central Ave",
                "Complimentary visitor parking",
                "north of the main entrance",
                "Wednesday",
            ]
        },
        "roads": {""},
        "distance_m": 35,
        "primary_category": "museums",
        "arrival_type": "licensed museum point beside published public arrival/parking approach",
        "limitations": "Unnamed driving link beside museum approach; complimentary visitor parking north of main entrance. Museum closed Mondays/Tuesdays; special exhibitions may require tickets. Check current visitor hours, holidays and parking restrictions before travel; future access and parking availability are unknown.",
    },
    "60b146ed-0641-4d47-add5-9ed70d34cb26": {
        "profile": "jacques-marchais/1",
        "name": "Jacques Marchais Museum of Tibetan Art",
        "region": "NY",
        "address": "338 Lighthouse Ave",
        "host": "tibetanmuseum.org",
        "coordinates": [40.57634431, -74.13809986],
        "pages": {
            "https://www.tibetanmuseum.org/visit": [
                "338 Lighthouse Avenue",
                "Parking is limited",
                "WED – SUN",
            ]
        },
        "roads": {"Lighthouse Avenue"},
        "distance_m": 15,
        "primary_category": "museums",
        "arrival_type": "licensed venue frontage at published address",
        "limitations": "Limited parking; do not block driveways. Main-staircase entry; Wednesday–Sunday public visits and holiday exceptions. Check current visitor hours, holidays and parking restrictions before travel; future access and parking availability are unknown.",
    },
    "69bc4e96-e908-43cc-af03-8aa4c9d5880f": {
        "profile": "seattle-pinball-museum/1",
        "name": "Seattle Pinball Museum",
        "region": "WA",
        "address": "508 Maynard Ave S",
        "host": "seattlepinballmuseum.com",
        "coordinates": [47.59806249, -122.3248855],
        "pages": {
            "https://seattlepinballmuseum.com/plan-your-trip": [
                "508 Maynard Avenue South",
                "Paid parking is available on the street",
                "Thursday through Monday",
                "7 years",
            ]
        },
        "roads": {"Maynard Avenue South"},
        "distance_m": 15,
        "primary_category": "museums",
        "arrival_type": "licensed venue frontage at published address",
        "limitations": "Thursday–Monday public hours; age restrictions apply (seven and older). Paid street/nearby lot parking requires a walk. Check current visitor hours, holidays and parking restrictions before travel; future access and parking availability are unknown.",
    },
    "848aaf62-f0db-4f4c-917f-19c5a1c3fe23": {
        "profile": "historic-richmond-town/1",
        "name": "Historic Richmond Town",
        "region": "NY",
        "address": "441 Clarke Ave",
        "host": "historicrichmondtown.org",
        "coordinates": [40.57091044, -74.14560481],
        "pages": {
            "https://www.historicrichmondtown.org/visit": [
                "441 Clarke Avenue",
                "Parking is FREE and plentiful",
                "Wed 1:00-5:00",
            ],
            "https://www.historicrichmondtown.org/faq-1": [
                "main parking lot at 441 Clarke Ave",
                "directly outside the entrance",
            ],
        },
        "roads": {""},
        "distance_m": 25,
        "primary_category": "museums",
        "arrival_type": "licensed visitor-center point beside published main visitor lot",
        "limitations": "Enter at courthouse/visitor center, 441 Clarke Avenue. Unnamed driving link; Wednesday–Sunday public hours; some buildings have steps. Check current visitor hours, holidays and parking restrictions before travel; future access and parking availability are unknown.",
    },
    "b40354ec-e19c-42e4-9600-4a55887eb235": {
        "profile": "fort-ward-museum/1",
        "name": "Fort Ward Museum & Historic Site",
        "region": "VA",
        "address": "4301 W Braddock Rd",
        "host": "alexandriava.gov",
        "coordinates": [38.82923165216222, -77.10185229778291],
        "pages": {
            "https://www.alexandriava.gov/museums/location/visit-fort-ward-museum-historic-site": [
                "4301 West Braddock Road",
                "Free parking is available on site for cars",
                "Regular hours Thursday",
            ]
        },
        "roads": {""},
        "distance_m": 30,
        "primary_category": "museums",
        "arrival_type": "licensed visitor point beside published museum car parking",
        "limitations": "Unnamed driving link beside museum; public museum hours Thursday–Sunday differ from park and appointment-only office hours. No Saturday time imported from ambiguous operator typography. Check current visitor hours, holidays and parking restrictions before travel; future access and parking availability are unknown.",
    },
    "e082091c-fca6-43ec-923a-34c496076962": {
        "profile": "sea-life-arizona/1",
        "name": "SEA LIFE Arizona Aquarium",
        "region": "AZ",
        "address": "5000 S Arizona Mills Cir",
        "host": "visitsealife.com",
        "coordinates": [33.38492618, -111.9632171],
        "pages": {
            "https://www.visitsealife.com/arizona/plan-your-day/before-you-visit/directions-parking/": [
                "5000 S. Arizona Mills Circle",
                "Ste 145",
                "parking is always free",
                "Entrance 1",
                "Attraction Hours",
            ]
        },
        "roads": {""},
        "distance_m": 30,
        "primary_category": "entertainment",
        "arrival_type": "licensed venue point beside published Arizona Mills Entrance 1 approach",
        "limitations": "Use Neighborhood 1 / Entrance 1 visitor parking and walk to Suite 145. Checked driving link is unnamed; tickets and current admission schedule need checking. Check current visitor hours, holidays and parking restrictions before travel; future access and parking availability are unknown.",
    },
}
