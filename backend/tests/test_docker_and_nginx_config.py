import os
import re
import yaml
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_backend_dockerfile_standardizes_port_8000():
    """
    Problem 31 Verification:
    backend/Dockerfile must standardize on port 8000:
    - EXPOSE 8000
    - CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
    - Port 7860 must be completely removed.
    """
    dockerfile_path = os.path.join("backend", "Dockerfile")
    assert os.path.exists(dockerfile_path), "backend/Dockerfile not found"

    with open(dockerfile_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Verify EXPOSE 8000 is present
    assert re.search(r"^\s*EXPOSE\s+8000\b", content, re.MULTILINE), (
        "backend/Dockerfile must specify 'EXPOSE 8000'"
    )

    # Verify CMD uses port 8000
    assert re.search(r'--port["\s,]+8000', content), (
        "backend/Dockerfile CMD must start uvicorn with '--port 8000'"
    )

    # Verify port 7860 is absent
    assert "7860" not in content, (
        "backend/Dockerfile must not contain legacy port 7860"
    )


def test_docker_compose_backend_exposes_port_8000():
    """
    Problem 31 Verification:
    docker-compose.yml must expose port 8000 on backend, wire reverse proxy on 8080,
    and have all service dependencies configured.
    """
    compose_path = "docker-compose.yml"
    assert os.path.exists(compose_path), "docker-compose.yml not found"

    with open(compose_path, "r", encoding="utf-8") as f:
        compose_cfg = yaml.safe_load(f)

    services = compose_cfg.get("services", {})
    assert "backend" in services, "docker-compose.yml missing backend service"
    assert "proxy" in services, "docker-compose.yml missing proxy service"

    backend_svc = services["backend"]
    expose_ports = [str(p) for p in backend_svc.get("expose", [])]
    assert "8000" in expose_ports, (
        f"backend service expose list must contain '8000', got {expose_ports}"
    )
    assert "7860" not in expose_ports, (
        "backend service expose list must not contain '7860'"
    )

    proxy_svc = services["proxy"]
    proxy_ports = [str(p) for p in proxy_svc.get("ports", [])]
    assert any("8080:8080" in p or "8080" in p for p in proxy_ports), (
        f"proxy service must publish port 8080, got {proxy_ports}"
    )

    proxy_deps = proxy_svc.get("depends_on", [])
    assert "backend" in proxy_deps, "proxy must depend on backend service"


def test_nginx_conf_upstream_and_proxy_pass_to_port_8000():
    """
    Problem 31 Verification:
    Root nginx.conf must define an upstream for backend at backend:8000,
    forward /api/ to backend:8000, and preserve streaming buffer headers.
    """
    nginx_path = "nginx.conf"
    assert os.path.exists(nginx_path), "nginx.conf not found"

    with open(nginx_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Verify upstream or proxy_pass targets backend:8000
    assert "backend:8000" in content, (
        "nginx.conf must route to backend internal service on port 8000"
    )
    assert "7860" not in content, (
        "nginx.conf must not contain port 7860"
    )

    # Verify upstream block
    assert "upstream backend_service" in content, (
        "nginx.conf should define explicit upstream backend_service"
    )
    assert re.search(r"server\s+backend:8000\s*;", content), (
        "upstream backend_service must define server backend:8000"
    )

    # Verify proxy_pass uses upstream or direct backend
    assert "proxy_pass http://backend_service/api/;" in content or "proxy_pass http://backend:8000/api/;" in content

    # Verify reverse proxy SSE streaming settings
    assert "proxy_buffering off;" in content, "nginx.conf must disable proxy buffering for SSE"
    assert "chunked_transfer_encoding on;" in content


def test_backend_production_nginx_conf_targets_port_8000():
    """
    Problem 31 Verification:
    backend/nginx.conf must route to port 8000 on localhost/internal loopback.
    """
    backend_nginx = os.path.join("backend", "nginx.conf")
    assert os.path.exists(backend_nginx), "backend/nginx.conf not found"

    with open(backend_nginx, "r", encoding="utf-8") as f:
        content = f.read()

    assert "8000" in content, "backend/nginx.conf must target port 8000"
    assert "7860" not in content, "backend/nginx.conf must not contain port 7860"
    assert re.search(r"server\s+127\.0\.0\.1:8000\s*;", content), (
        "backend/nginx.conf upstream must define server 127.0.0.1:8000"
    )


from unittest.mock import patch

def test_zero_occurrences_of_port_7860_in_project():
    """
    Problem 31 Verification:
    No legacy references to port 7860 should remain anywhere in the project configs/code.
    """
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    scan_exts = {".py", ".yml", ".yaml", ".conf", ".json", ".md", ".env", ".example", ".dockerfile", ""}
    exclude_dirs = {".git", "__pycache__", "node_modules", "dist", ".gemini", "pgdata", ".pytest_cache"}
    exclude_files = {"test_docker_and_nginx_config.py", "test_e2e_compose_deployment.py", "local_stem_db.json"}

    offending_files = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
        for filename in filenames:
            if filename in exclude_files:
                continue
            ext = os.path.splitext(filename)[1].lower()
            if ext in scan_exts or filename.startswith("Dockerfile"):
                filepath = os.path.join(dirpath, filename)
                try:
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        lines = f.readlines()
                    for idx, line in enumerate(lines, 1):
                        if re.search(r"\b7860\b", line):
                            offending_files.append(f"{filepath}:{idx}: {line.strip()}")
                except Exception:
                    pass

    assert len(offending_files) == 0, (
        f"Found unexpected references to port 7860:\n" + "\n".join(offending_files)
    )


def test_api_routes_accessible_at_proxied_paths():
    """
    Problem 31 Verification:
    Ensures endpoints configured for proxy forwarding (/api/..., /ready, /)
    respond successfully without internal 502/routing discrepancies.
    """
    # 1. Health check at root
    r_root = client.get("/")
    assert r_root.status_code == 200
    assert r_root.json().get("status") == "ok"

    # 2. Readiness check at /ready with mock
    with patch("app.core_backend.database.pgvector_db.check_database_readiness", return_value={"status": "healthy", "database": "connected"}):
        r_ready = client.get("/ready")
        assert r_ready.status_code == 200
        assert r_ready.json().get("status") == "healthy"

    # 3. Proxied API route (/api/experiments/analyze/free-fall)
    r_exp = client.post("/api/experiments/analyze/free-fall", json={"height": 50.0, "mass": 1.0, "gravity": 9.81})
    assert r_exp.status_code == 200
    data = r_exp.json()
    assert "parameters" in data
    assert "series" in data

