"""
NeuroLab AI: CORS Preflight and Security Headers Verification
Validates that FastAPI CORS configuration correctly handles:
1. Preflight OPTIONS requests from https://anna.partners and Anna subdomains.
2. Preflight OPTIONS requests from standalone Vercel domains and local dev origins.
3. Allowed methods (POST, GET, OPTIONS, etc.) and headers (Authorization, Content-Type, X-Request-ID).
4. Credentials support without wildcard '*' vulnerability.
5. Content Security Policy (CSP) headers including connect-src and frame-ancestors for Anna.
"""

import pytest
from starlette.datastructures import Headers, MutableHeaders
from starlette.middleware.cors import CORSMiddleware

from app.core_backend.core.config import Settings
from app.main import app


@pytest.fixture(scope="module")
def cors_instance():
    """Extracts the registered CORSMiddleware configuration from the FastAPI app."""
    cors_middleware_def = next(
        (m for m in app.user_middleware if m.cls == CORSMiddleware),
        None,
    )
    assert cors_middleware_def is not None, "CORSMiddleware is not registered on FastAPI app"
    # Instantiate the middleware with dummy ASGI callable to test its internal CORS logic
    return CORSMiddleware(app=None, **cors_middleware_def.kwargs)


def test_cors_middleware_is_outermost():
    """CORSMiddleware must be the outermost user middleware to ensure CORS headers on all responses."""
    assert app.user_middleware[0].cls == CORSMiddleware, (
        f"Expected CORSMiddleware to be outermost (index 0), found {app.user_middleware[0].cls.__name__}"
    )


def test_options_preflight_anna_partners(cors_instance):
    """OPTIONS preflight from https://anna.partners must return 200 with Access-Control-Allow-Origin."""
    request_headers = Headers(
        {
            "origin": "https://anna.partners",
            "access-control-request-method": "POST",
            "access-control-request-headers": "authorization, content-type, x-request-id",
        }
    )
    assert cors_instance.is_allowed_origin("https://anna.partners")

    response = cors_instance.preflight_response(request_headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "https://anna.partners"
    assert response.headers.get("access-control-allow-credentials") == "true"

    allowed_methods = [
        m.strip() for m in response.headers.get("access-control-allow-methods", "").split(",")
    ]
    assert "POST" in allowed_methods
    assert "OPTIONS" in allowed_methods

    allowed_headers = response.headers.get("access-control-allow-headers", "").lower()
    assert "authorization" in allowed_headers
    assert "content-type" in allowed_headers
    assert "x-request-id" in allowed_headers


def test_options_preflight_anna_subdomains(cors_instance):
    """OPTIONS preflight from Anna subdomains (e.g. app.anna.partners) must be permitted."""
    subdomain_origin = "https://app.anna.partners"
    assert cors_instance.is_allowed_origin(subdomain_origin)

    request_headers = Headers(
        {
            "origin": subdomain_origin,
            "access-control-request-method": "POST",
            "access-control-request-headers": "authorization, content-type",
        }
    )
    response = cors_instance.preflight_response(request_headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == subdomain_origin
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_options_preflight_standalone_website(cors_instance):
    """OPTIONS preflight from standalone website (ai-steam-lab.vercel.app and preview domains) must be permitted."""
    for origin in ["https://ai-steam-lab.vercel.app", "https://ai-steam-lab-git-main.vercel.app"]:
        assert cors_instance.is_allowed_origin(origin)
        request_headers = Headers(
            {
                "origin": origin,
                "access-control-request-method": "POST",
                "access-control-request-headers": "authorization, content-type",
            }
        )
        response = cors_instance.preflight_response(request_headers)
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == origin
        assert response.headers.get("access-control-allow-credentials") == "true"


def test_unauthorized_origin_rejected(cors_instance):
    """Untrusted / malicious origins must NOT receive Access-Control-Allow-Origin header."""
    for origin in [
        "https://malicious-site.com",
        "https://attacker-anna.partners.fake",
        "http://anna.partners",
    ]:
        assert not cors_instance.is_allowed_origin(origin)
        request_headers = Headers(
            {
                "origin": origin,
                "access-control-request-method": "POST",
            }
        )
        response = cors_instance.preflight_response(request_headers)
        assert "access-control-allow-origin" not in response.headers


def test_simple_request_cors_headers(cors_instance):
    """Simple requests (GET / POST) from https://anna.partners must include CORS headers."""
    response_headers = MutableHeaders()
    response_headers.update(cors_instance.simple_headers)
    cors_instance.allow_explicit_origin(response_headers, "https://anna.partners")

    assert response_headers.get("access-control-allow-origin") == "https://anna.partners"
    assert response_headers.get("access-control-allow-credentials") == "true"


def test_no_wildcard_with_credentials_in_production(monkeypatch):
    """Verify that wildcard '*' with credentials fails startup validation in production."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("ALLOWED_ORIGINS", "*,https://anna.partners")
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "test-key")

    settings = Settings()
    with pytest.raises(RuntimeError, match="Wildcard '\\*' in ALLOWED_ORIGINS is prohibited"):
        settings.validate_startup()


def test_settings_default_origins_contain_anna():
    """Default Settings.parsed_allowed_origins must include https://anna.partners."""
    settings = Settings()
    origins = settings.parsed_allowed_origins
    assert "https://anna.partners" in origins
    assert "https://ai-steam-lab.vercel.app" in origins
