# NeuroLab AI: Production Deployment Guide

**Target Platforms**: Render.com, Docker Compose, Linux VPS (Ubuntu/Debian)  
**Document Version**: 1.0.0

---

## 1. Production Architecture Overview

In production, NeuroLab AI runs four primary containerized components:
1. **Web Service (`stemlab-backend`)**: FastAPI application serving HTTP REST, SSE streaming, and WebSocket tracking feeds.
2. **Asynchronous Worker (`stemlab-worker`)**: Celery worker executing long-running CV batch jobs and offline AI evaluations.
3. **Cache & Task Broker (`stemlab-redis`)**: Redis 7 cluster for session caching, rate-limit state, token revocation, and Celery queues.
4. **Primary Database (`stemlab-db`)**: PostgreSQL 16 with the `pgvector` extension enabled for relational records and 768-dimensional embedding search.

---

## 2. Platform 1: Render.com Cloud Deployment

NeuroLab AI provides a turnkey `render.yaml` infrastructure-as-code specification.

### 2.1 Services Provisioned

| Service Name | Render Type | Plan | Env / Image | Health Check Path | Memory Limit |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **stemlab-backend** | Web Service | Free / Starter | Docker (`./backend/Dockerfile`) | `/ready` | 512 MB (Free) / 2 GB |
| **stemlab-worker** | Background Worker | Free / Starter | Docker (`celery worker`) | Internal ping | 512 MB (Free) / 2 GB |
| **stemlab-redis** | Redis | Free | Managed Redis 7 | PING | Shared |
| **stemlab-db** | PostgreSQL | Free | PostgreSQL 16 | Internal socket | Shared |

### 2.2 Critical Free-Tier Resource Constraints

> [!WARNING]
> **512 MB Free Tier Container RAM Limit**:
> - Loading YOLOv8 PyTorch weights into memory increases container resident set size (RSS) by **+958.8 MB**, causing peak memory to reach **1,087.9 MB**.
> - On Render Free-tier web services, this triggers an immediate `SIGKILL (OOM)` termination.
> - **Production Requirement**: In `render.yaml`, ensure `ENABLE_YOLO=false` is declared on free-tier services. This activates NeuroLab's ultra-fast OpenCV HSV color tracking (`2.61 ms`, $< 150\,\text{MB}$ RAM).
> - When upgrading to Starter ($7/mo, 2 GB RAM) or higher, `ENABLE_YOLO=true` may be safely activated.

### 2.3 Deployment Steps on Render

1. **Connect GitHub Repository**:
   - In the Render Dashboard, select **New +** -> **Blueprint**.
   - Select the `vikassaini77/AI-Steam-Lab` repository and branch `main`.
2. **Render Parses `render.yaml`**:
   - Render automatically identifies the backend web service, worker, Redis instance, and PostgreSQL database.
3. **Configure Unsynchronized Secrets**:
   - Supply the following secret values in the Render Dashboard environment settings:
     - `GEMINI_API_KEY`: Google Gemini API key (from [AI Studio](https://aistudio.google.com/)).
     - `SUPABASE_URL`: Managed Supabase instance URL (or omit if relying entirely on managed PostgreSQL).
     - `SUPABASE_KEY`: Supabase anon/service-role key.
     - `METRICS_TOKEN`: Secure random token protecting the `/metrics` endpoint.
     - `ALLOWED_ORIGINS`: Permitted frontend origins, e.g.:
       `https://anna.partners,https://ai-steam-lab.vercel.app,https://neurolab.onrender.com`
4. **Pre-Deploy Migration Execution**:
   - Render automatically executes `preDeployCommand: python -m app.core_backend.database.migrations` prior to routing traffic to the updated container.
   - Migrations use PostgreSQL advisory locks (`pg_advisory_lock(88990011)`) to guarantee zero race conditions during rollouts.
5. **Readiness Probe Routing**:
   - The `/ready` health check verifies database connectivity, Celery broker status, and security configurations before routing live traffic.

---

## 3. Platform 2: Docker Compose Multi-Container Stack

For on-premises servers, developer workstations, or single-node VPS instances:

### 3.1 Pre-Flight Setup
```bash
git clone https://github.com/vikassaini77/AI-Steam-Lab.git
cd AI-Steam-Lab

# Copy environment template
cp .env.example .env

# Generate secure random passwords and tokens:
# Edit .env and supply GEMINI_API_KEY, POSTGRES_PASSWORD, METRICS_TOKEN
```

### 3.2 Starting the Stack
```bash
# Build images and start all containers in detached mode
docker-compose up --build -d

# Verify all containers are healthy
docker-compose ps
```

*Expected service states:*
- `db`: `healthy` (Port 5432 internal)
- `migration`: `exited (0)` (Completed schema migrations)
- `redis`: `running` (Port 6379 internal)
- `backend`: `running` (Port 8000 internal)
- `celery_worker`: `running`
- `frontend`: `running` (Port 8080 internal)
- `proxy`: `running` (Port 8080 host mapped)

### 3.3 Verifying Stack Health
```bash
# Check liveness (immediate process response)
curl -s http://localhost:8080/live | jq .

# Check readiness (verifies DB connection, Redis, and models)
curl -s http://localhost:8080/ready | jq .
```

---

## 4. Platform 3: Bare-Metal Linux VPS (Systemd & Nginx)

### 4.1 Systemd Service Unit (`/etc/systemd/system/neurolab-backend.service`)
```ini
[Unit]
Description=NeuroLab AI FastAPI Backend Service
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=neurolab
Group=neurolab
WorkingDirectory=/var/www/neurolab/backend
EnvironmentFile=/var/www/neurolab/backend/.env
ExecStart=/var/www/neurolab/backend/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4 --proxy-headers
Restart=always
RestartSec=5s
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
```

### 4.2 Systemd Celery Worker Unit (`/etc/systemd/system/neurolab-worker.service`)
```ini
[Unit]
Description=NeuroLab AI Celery Worker Service
After=network.target redis.service

[Service]
Type=simple
User=neurolab
Group=neurolab
WorkingDirectory=/var/www/neurolab/backend
EnvironmentFile=/var/www/neurolab/backend/.env
ExecStart=/var/www/neurolab/backend/venv/bin/celery -A app.worker.celery_app worker --loglevel=info --concurrency=2
Restart=always
RestartSec=5s

[Install]
WantedBy=multi-user.target
```

---

## 5. Health Check & Probing Architecture

NeuroLab strictly separates **Liveness** from **Readiness** to prevent orchestration restart loops:

| Probe Endpoint | Purpose | Upstream Dependencies Checked | Failure Response | Orchestrator Action |
| :--- | :--- | :--- | :---: | :--- |
| **`/live`** / **`/healthz`** | Process responsiveness | None (isolated process check) | `500` / Connection Refused | Kill and restart container |
| **`/ready`** / **`/health/ready`** | Traffic readiness | PostgreSQL, Redis, Models, Active Alerts | `503 Service Unavailable` | Pull instance from load balancer |

---

## 6. Zero-Downtime Rollout & Rollback Sequence

1. **Pre-Migration Snapshot**: The deployment automation generates a timestamped database backup in `/backups` with a SHA-256 integrity checksum.
2. **Forward Migration**: Runs `python -m app.core_backend.database.migrations` guarded by advisory lock `88990011`.
3. **Rolling Container Update**: New backend instances spin up and await readiness probe verification (`/ready == 200`).
4. **Traffic Cutover**: Proxy routes incoming requests to new instances once healthy.
5. **Automated Rollback Trigger**: If the new container returns `503` or fails health checks for 3 consecutive polls:
   - Roll back container image to previous Git SHA.
   - Run rollback migration command:
     ```bash
     python -m app.core_backend.database.migrations --rollback
     ```
