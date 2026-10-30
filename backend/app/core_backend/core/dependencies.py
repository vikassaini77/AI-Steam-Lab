import os
import time
from typing import Optional, Dict, Any
from fastapi import Header, HTTPException, status
import jwt
from app.core_backend.core.supabase_client import get_supabase_client


def get_token_from_header(authorization: Optional[str] = Header(None)) -> str:
    """
    Extracts Bearer token from the Authorization header.
    Returns 401 Unauthorized for missing or invalid header formats.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Expected 'Bearer <token>'",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = parts[1].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Empty Bearer token provided",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token


async def get_current_user(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    """
    Validates the Supabase access token on every protected backend request.
    1. Rejects missing, malformed, or empty tokens with 401 Unauthorized.
    2. Rejects expired tokens with 401 Unauthorized.
    3. Rejects incorrectly signed or invalid tokens with 401 Unauthorized.
    4. Authenticates against SUPABASE_JWT_SECRET (if configured) or the Supabase Auth API.
    """
    token = get_token_from_header(authorization)

    # Fast-check expiration using standard JWT decoding without signature
    try:
        jwt.decode(token, options={"verify_signature": False, "verify_exp": True})
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.DecodeError:
        # If it cannot even be parsed as a JWT, it is malformed
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: malformed JWT structure",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception:
        # Continue to signature verification
        pass

    # 1. If SUPABASE_JWT_SECRET is set, perform local cryptographic verification
    jwt_secret = os.getenv("SUPABASE_JWT_SECRET")
    if jwt_secret:
        try:
            payload = jwt.decode(
                token,
                jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
                options={"verify_exp": True, "verify_signature": True},
            )
            return {
                "id": payload.get("sub"),
                "email": payload.get("email"),
                "role": payload.get("role", "authenticated"),
                "metadata": payload.get("user_metadata", {}),
            }
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.InvalidTokenError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token signature: {str(e)}",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # 2. Verify token validity directly against the Supabase Auth server
    try:
        client = get_supabase_client()
        user_response = client.auth.get_user(token)
        if not user_response or not getattr(user_response, "user", None):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or revoked authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user = user_response.user
        return {
            "id": str(user.id),
            "email": user.email,
            "role": getattr(user, "role", "authenticated") or "authenticated",
            "metadata": getattr(user, "user_metadata", {}) or {},
        }
    except HTTPException:
        raise
    except Exception as e:
        err_msg = str(e)
        if "expired" in err_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {err_msg}",
            headers={"WWW-Authenticate": "Bearer"},
        )


def verify_resource_ownership(resource_owner_id: str, current_user: Dict[str, Any]) -> None:
    """
    Enforces authorization: returns 403 Forbidden when an authenticated user
    attempts to view, modify, or create a resource belonging to another user.
    """
    authenticated_id = str(current_user.get("id"))
    target_id = str(resource_owner_id)
    if authenticated_id != target_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not have permission to access or modify resources belonging to another user.",
        )
