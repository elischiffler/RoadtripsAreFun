"""Versioned, persona-independent definitions for estimated attraction traits."""

VERSION = "attraction-traits-v3-destination-rubric"

RUBRIC = """
Score the named destination itself, not its town, nearby attractions, or regional reputation.
Source facts identify the exact component: a farmers market is not the surrounding beach;
an amusement park is not a natural park; a visitor center is not an entire national park.
Do not transfer a nearby trail, beach, habitat, or activity to this place unless the supplied
facts establish that visitors can experience it at this destination or its documented access.
Walking between shops or stalls is not hiking. Outdoor operation and produce sales alone
do not establish a nature experience. Adventure means outdoor exploration/challenge here,
not merely excitement from amusement rides. Do not infer beaches from a town's name.

Use a consistent absolute scale across all places, not a ranking within this batch:
0 = absent/not supported; 0.1-0.25 = incidental; 0.3-0.5 = meaningful secondary feature;
0.6-0.8 = a primary reason to visit; 0.9-1 = an exceptional defining experience.
Sparse facts are not evidence of a high score. Use conservative estimates for uncertain
features; never fill missing knowledge with 0.5. Scores remain estimates, not verified facts.

Definitions:
scenery: views and visual landscape experienced at this destination.
nature: direct experience of natural habitats, wild plants, wildlife, or geology.
hiking_outdoors: actual trails, hiking, or substantive outdoor exploration available here.
food: food and drink experiences offered here.
history: historical sites, interpretation, or artifacts experienced here.
culture_arts: art, performances, cultural interpretation, or traditions experienced here.
nightlife: evening/night entertainment offered here, not nearby nightlife.
shopping: shopping opportunities at this destination.
beaches_water: direct beach, shoreline, or water recreation/access here.
adventure: outdoor challenge, exploration, or adventure activities here.
relaxation: opportunity for a quiet, restful experience here.
unique_local_experiences: distinctive local experiences specific to this destination.
family_friendliness: suitability of the destination's activities for families with children.
crowd_avoidance: supported opportunity for low-crowd/solitary experiences; do not invent
current visitor counts or assume a small venue is uncrowded.
Apply these definitions independently; do not raise all attributes because a place is popular.
""".strip()
