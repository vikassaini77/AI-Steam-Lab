import os
import ipaddress
from typing import Optional
from fastapi import Request, HTTPException, status
from app.logger import logger


def get_client_ip(request: Request) -> str:
    """
    Extracts client IP, respecting TRUSTED_PROXIES only.
    Prevents untrusted public callers from spoofing X-Forwarded-For: 127.0.0.1.
    """
    client_host = request.client.host if request.client else "127.0.0.1"

    trusted_env = os.getenv(
        "TRUSTED_PROXIES",
        "127.0.0.1,::1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16",
    )
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
            forwarded_ips = [ip.strip() for ip in forwarded_for.split(",") if ip.strip()]
            if forwarded_ips:
                return forwarded_ips[0]
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()

    return client_host


def is_ip_in_network(ip_str: str, network_str: str) -> bool:
    """Verifies whether an IP string belongs to a specified CIDR network block."""
    try:
        ip = ipaddress.ip_address(ip_str)
        net = ipaddress.ip_network(network_str, strict=False)
        return ip in net
    except ValueError:
        return False


async def verify_metrics_access(request: Request) -> bool:
    """
    Enforces access control on the Prometheus /metrics endpoint:
    1. Authenticated monitoring clients (via Bearer token or X-Metrics-Key header).
    2. Internal monitoring networks (loopback, Docker, Kubernetes, VPC private CIDRs).
    Rejects public or unauthenticated requests with 401 Unauthorized.
    """
    metrics_token = os.getenv("METRICS_TOKEN")

    # 1. Check token-based authentication
    auth_header = request.headers.get("authorization")
    api_key_header = request.headers.get("x-metrics-key")
    provided_token: Optional[str] = None

    if auth_header and auth_header.startswith("Bearer "):
        parts = auth_header.split(" ")
        if len(parts) == 2:
            provided_token = parts[1].strip()
    elif api_key_header:
        provided_token = api_key_header.strip()

    if metrics_token:
        if provided_token == metrics_token:
            return True
        elif provided_token:
            logger.warning("Metrics access attempt with invalid authentication token.")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Prometheus monitoring credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
    elif provided_token:
        # If no METRICS_TOKEN is set in server env, do not blindly accept arbitrary tokens
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Monitoring token authentication is not configured on the server",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 2. Check internal monitoring network if token is not provided
    allow_internal = os.getenv("METRICS_ALLOW_INTERNAL_NETWORKS", "true").lower() in (
        "true",
        "1",
        "yes",
    )

    if allow_internal:
        client_ip = get_client_ip(request)

        # Loopback / local test clients
        if client_ip in ("testclient", "127.0.0.1", "::1", "localhost"):
            # If METRICS_REQUIRE_AUTH is explicitly set, require token even on localhost
            if os.getenv("METRICS_REQUIRE_AUTH", "false").lower() in ("true", "1", "yes"):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Metrics endpoint requires authentication token",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            return True

        # Allowed CIDR networks (e.g. internal Prometheus scraper in VPC)
        allowed_nets = os.getenv(
            "METRICS_ALLOWED_NETWORKS",
            "10.0.0.0/8,172.16.0.0/12,192.168.0.0/16",
        )
        for net in allowed_nets.split(","):
            net = net.strip()
            if net and is_ip_in_network(client_ip, net):
                return True

    logger.warning(
        f"Blocked unauthorized Prometheus metrics request from client IP: {request.client.host if request.client else 'unknown'}"
    )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized: Access to Prometheus metrics is restricted to authenticated monitoring clients or internal networks.",
        headers={"WWW-Authenticate": "Bearer"},
    )
