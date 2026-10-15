"""Stable public identity namespaces for explicitly reviewed source adapters."""


def identity(source_id):
    for prefix, source in (
        ("boulder:", "boulder-osmp"),
        ("nps:", "nps"),
        ("nps-public:", "nps-public"),
        ("nps-heritage:", "nps-heritage"),
        ("kaggle-loc:", "kaggle-loc-roadside"),
    ):
        if source_id.startswith(prefix):
            return source_id, source
    return "overture:" + source_id, "overture"
