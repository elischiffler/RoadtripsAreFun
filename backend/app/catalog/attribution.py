"""Stable source credits without repeating semicolon-delimited statements."""


def combine(values):
    return "; ".join(
        dict.fromkeys(
            token.strip() for value in values for token in value.split(";") if token.strip()
        )
    )
