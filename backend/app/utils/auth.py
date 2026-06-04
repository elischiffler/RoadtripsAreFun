import jwt
import logging

logger = logging.getLogger(__name__)


def get_user_id_from_token(token: str) -> str:
    """
    Decodes a JWT (like an AWS Cognito Access Token) to extract the user's permanent unique ID (sub).
    """
    try:
        # Decode without verifying the signature just to extract the payload
        # (In production, consider verifying the signature against Cognito's JWKS)
        payload = jwt.decode(token, options={"verify_signature": False})

        # AWS Cognito stores the unique User ID in the 'sub' claim
        user_id = payload.get("sub") or payload.get("username")

        if user_id:
            return str(user_id)
        return token
    except Exception as e:
        logger.error(f"Failed to decode token: {e}")
        return token
