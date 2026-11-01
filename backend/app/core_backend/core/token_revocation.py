import hashlib
import logging
import threading
import time
from typing import Dict, Optional
import jwt

logger = logging.getLogger(__name__)

# Thread-safe in-memory registry of revoked tokens: {token_hash: expiry_timestamp}
_revoked_tokens_lock = threading.Lock()
_revoked_tokens: Dict[str, float] = {}


def _hash_token(token: str) -> str:
    """Computes SHA-256 digest of token to avoid storing raw tokens in memory or cache."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def revoke_token(
    token: str,
    user_id: Optional[str] = None,
    expires_at: Optional[float] = None,
) -> bool:
    """
    Records a token as revoked until its cryptographic expiration.
    Guarantees immediate invalidation across subsequent protected requests.
    """
    if not token or not isinstance(token, str):
        return False

    token_hash = _hash_token(token)

    # Resolve token expiration timestamp
    if expires_at is None:
        try:
            unverified = jwt.decode(token, options={"verify_signature": False, "verify_exp": False})
            expires_at = unverified.get("exp")
        except Exception:
            pass

    now = time.time()
    if expires_at is None or expires_at <= now:
        # Default fallback TTL: 24 hours
        expiry_ts = now + 86400.0
    else:
        expiry_ts = float(expires_at)

    with _revoked_tokens_lock:
        _revoked_tokens[token_hash] = expiry_ts

    logger.info(
        f"Token revoked successfully for user '{user_id or 'unknown'}'. Expiry: {expiry_ts:.0f}",
        extra={
            "event": "token_revoked",
            "user_id": user_id,
            "token_hash_prefix": token_hash[:12],
            "expires_at": expiry_ts,
        },
    )
    return True


def is_token_revoked(token: str) -> bool:
    """
    Checks if a token has been explicitly revoked through logout or session termination.
    Automatically evicts expired entries from the revocation registry.
    """
    if not token or not isinstance(token, str):
        return False

    token_hash = _hash_token(token)
    now = time.time()

    with _revoked_tokens_lock:
        expiry_ts = _revoked_tokens.get(token_hash)
        if expiry_ts is not None:
            if expiry_ts > now:
                return True
            # Entry has expired naturally past the token lifetime; evict to free memory
            del _revoked_tokens[token_hash]

    return False


def clear_revoked_tokens() -> None:
    """Resets the revoked token store for hermetic testing."""
    with _revoked_tokens_lock:
        _revoked_tokens.clear()

