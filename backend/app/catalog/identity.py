"""Stable public identity namespaces for explicitly reviewed source adapters."""

PREFIXES = (
    ("catalog-pilot:", "catalog-pilot"),
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
)


def identity(source_id):
    for prefix, source in PREFIXES:
        if source_id.startswith(prefix):
            return source_id, source
    return "overture:" + source_id, "overture"


def catalog_source_id(provider_id):
    """Invert only catalog namespaces; other providers do not trigger DB lookups."""
    if not isinstance(provider_id, str) or not 1 <= len(provider_id) <= 512:
        return None
    if provider_id.startswith("overture:") and len(provider_id) > len("overture:"):
        source_id = provider_id.removeprefix("overture:")
        return source_id if identity(source_id)[0] == provider_id else None
    if any(
        provider_id.startswith(prefix) and len(provider_id) > len(prefix) for prefix, _ in PREFIXES
    ):
        return provider_id
    return None
