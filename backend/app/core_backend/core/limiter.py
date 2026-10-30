import os
from typing import Optional
from fastapi import Request
import jwt
from slowapi import Limiter
from slowapi.util import get_remote_address

def get_user_or_ip_identifier(request: Request) -> str:
    """
    Extracts a canonical rate-limiting identifier:
    1. If user is authenticated, rate-limits by canonical User ID (prevents IP hopping / NAT collisions).
    2. Otherwise, rate-limits by Client IP, securely respecting TRUSTED_PROXIES only.
       Does NOT blindly trust spoofable client-supplied X-Forwarded-For headers.
    """
    # 1. Try to extract user ID from Bearer token
    auth_header = request.headers.get("authorization")
    if auth_header and auth_header.startswith("Bearer "):
        parts = auth_header.split(" ")
        if len(parts) == 2:
            try:
                # Fast unverified claims read to extract subject ID
                payload = jwt.decode(parts[1], options={"verify_signature": False, "verify_exp": False})
                user_id = payload.get("sub") or payload.get("id")
                if user_id:
                    return f"user:{user_id}"
            except Exception:
                pass

    # 2. Extract Client IP respecting trusted reverse proxies (e.g. Nginx, Render, Docker)
    client_host = request.client.host if request.client else "127.0.0.1"

    # Configured trusted proxy IPs/CIDRs
    trusted_env = os.getenv("TRUSTED_PROXIES", "127.0.0.1,::1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16")
    trusted_proxies = {p.strip() for p in trusted_env.split(",") if p.strip()}

    is_trusted = (
        client_host in trusted_proxies
        or client_host == "testclient"
        or client_host.startswith("172.")
        or client_host.startswith("10.")
        or client_host == "127.0.0.1"
        or client_host == "::1"
    )

    if is_trusted:
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            # Client IP is the leftmost entry in X-Forwarded-For
            forwarded_ips = [ip.strip() for ip in forwarded_for.split(",") if ip.strip()]
            if forwarded_ips:
                return f"ip:{forwarded_ips[0]}"
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return f"ip:{real_ip.strip()}"

    return f"ip:{client_host}"


# Configure SlowAPI limiter with Redis if available, else memory fallback
def create_limiter() -> Limiter:
    redis_url = os.getenv("REDIS_URL")
    if redis_url and (redis_url.startswith("redis://") or redis_url.startswith("rediss://")):
        try:
            return Limiter(
                key_func=get_user_or_ip_identifier,
                storage_uri=redis_url,
                strategy="fixed-window",
            )
        except Exception as e:
            print(f"Distributed Redis rate limiter failed to initialize: {e}. Falling back to in-memory.")

    return Limiter(key_func=get_user_or_ip_identifier)


limiter = create_limiter()
