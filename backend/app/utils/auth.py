"""Validate Cognito access tokens before using their subject as a user ID."""

import logging
import os
import re
from functools import lru_cache

import jwt
from fastapi import HTTPException

logger = logging.getLogger(__name__)


def _cognito_settings() -> tuple[str, str]:
    pool_id = os.getenv("COGNITO_USER_POOL_ID", "").strip()
    client_id = os.getenv("COGNITO_APP_CLIENT_ID", "").strip()
    region, separator, suffix = pool_id.partition("_")
    if (
        not separator
        or not re.fullmatch(r"[a-z]{2}(?:-[a-z0-9]+)+-\d+", region)
        or not re.fullmatch(r"[A-Za-z0-9]+", suffix)
        or not client_id
    ):
        logger.error("Cognito token verification is not configured")
        raise HTTPException(status_code=503, detail="Authentication unavailable")
    return f"https://cognito-idp.{region}.amazonaws.com/{pool_id}", client_id


@lru_cache(maxsize=4)
def _jwks_client(issuer: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(f"{issuer}/.well-known/jwks.json", timeout=5, lifespan=300)


def bearer_token(authorization: str | None) -> str:
    """Extract exactly one Bearer token from an Authorization header."""
    scheme, separator, token = (authorization or "").partition(" ")
    if not separator or scheme.lower() != "bearer" or not token or " " in token:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    return token


def get_user_id_from_token(token: str) -> str:
    """Return the verified access token subject, or reject the request."""
    if not isinstance(token, str) or not token:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    issuer, client_id = _cognito_settings()
    try:
        header = jwt.get_unverified_header(token)
        if header.get("alg") != "RS256" or not header.get("kid"):
            raise jwt.InvalidTokenError("Unexpected signing algorithm or key ID")

        signing_key = _jwks_client(issuer).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=issuer,
            options={
                "require": ["exp", "iat", "iss", "sub", "client_id", "token_use"],
                "verify_aud": False,
            },
        )
        subject = claims["sub"]
        if (
            claims["client_id"] != client_id
            or claims["token_use"] != "access"
            or not isinstance(subject, str)
            or not subject.strip()
        ):
            raise jwt.InvalidTokenError("Unexpected access token claims")
        return subject
    except (jwt.PyJWTError, ValueError, TypeError) as exc:
        logger.warning("Cognito token validation failed: %s", type(exc).__name__)
        raise HTTPException(status_code=401, detail="Invalid authentication token") from None
