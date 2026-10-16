"""Stable public identity namespaces for explicitly reviewed source adapters."""


def identity(source_id):
    for prefix, source in (
        ("boulder:", "boulder-osmp"),
        ("nps:", "nps"),
        ("nps-public:", "nps-public"),
        ("nps-heritage:", "nps-heritage"),
        ("kaggle-loc:", "kaggle-loc-roadside"),
        ("usfs:", "usfs"),
        ("usda-market:", "kaggle-usda-markets"),
        ("wikidata-park:", "kaggle-rideinpark"),
        ("la-cultural:", "kaggle-la-cultural"),
        ("nys-historic:", "kaggle-nys-historic"),
        ("chicago-facility:", "kaggle-chicago-facilities"),
    ):
        if source_id.startswith(prefix):
            return source_id, source
    return "overture:" + source_id, "overture"
