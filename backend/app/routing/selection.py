"""Backend-owned eligibility and selection for every interactive planner path."""

from app.routing.registry import DEFAULT_ALGORITHM, get_planner
from app.utils.auth import verified_identity_claims

OWNER_EMAIL = "eschiffler1122@gmail.com"


def owner_routing_claims(subject: str, identity_token: str | None) -> dict | None:
    claims = verified_identity_claims(identity_token, subject)
    if (
        claims is not None
        and claims.get("email_verified") is True
        and claims.get("email") == OWNER_EMAIL
    ):
        return claims
    return None


def select_algorithm(requested: str | None, can_select: bool = False) -> str:
    """Only a verified owner can override the canonical default.

    Environment overrides never apply to interactive planning, including owners.
    Validate owner selections against the registry before local or remote use.
    """
    selected = requested if can_select and requested else DEFAULT_ALGORITHM
    get_planner(selected)
    return selected
