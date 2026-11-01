import os
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request, Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Applies comprehensive browser security headers and defenses:
    1. Content Security Policy (CSP) tailored to Vite React, Three.js, Lucide, Supabase, and Gemini API.
    2. Explicit frame-ancestors in CSP to control iframe embedding (permitting Hugging Face Spaces & Vercel, blocking clickjacking).
    3. HSTS configured strictly at the HTTPS edge and only for domains where HTTPS is active.
    4. X-Content-Type-Options: nosniff to prevent MIME confusion.
    5. Referrer-Policy: strict-origin-when-cross-origin.
    6. Permissions-Policy: camera=(self) for CV tracker, while locking down unused sensors (mic, geolocation).
    7. Removed obsolete and insecure X-XSS-Protection header.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # 1. Prevent MIME-type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # 2. Strict Referrer Policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # 3. Explicit Permissions Policy (camera allowed for CV experiments, restrict rest)
        response.headers["Permissions-Policy"] = (
            "camera=(self), microphone=(), geolocation=(), payment=()"
        )

        # 4. Tailored Content Security Policy (CSP)
        # Allows Vite scripts, Tailwind styles, Three.js canvas/blobs, Supabase endpoints, and controlled frame embedding
        default_csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob: https:; "
            "font-src 'self' data:; "
            "connect-src 'self' https://*.supabase.co wss://*.supabase.co https://generativelanguage.googleapis.com https://ai-steam-lab.vercel.app http://localhost:8000 http://127.0.0.1:8000 https://*.onrender.com; "
            "media-src 'self' blob: data:; "
            "worker-src 'self' blob:; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "frame-ancestors 'self' https://huggingface.co https://*.huggingface.co https://ai-steam-lab.vercel.app;"
        )
        response.headers["Content-Security-Policy"] = os.getenv("CONTENT_SECURITY_POLICY", default_csp)

        # 5. HSTS: Configure strictly over HTTPS (directly or via TLS-terminating reverse proxy)
        # Avoids local developer browser lockouts on localhost while protecting HTTPS traffic
        is_https = (
            request.url.scheme == "https"
            or request.headers.get("x-forwarded-proto", "").lower() == "https"
        )
        if is_https:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        # 6. Explicit API Version Contract
        response.headers["X-API-Version"] = "1.0.0"

        # Note: X-XSS-Protection is intentionally omitted as it is obsolete and introduces security flaws in modern browsers.

        return response

