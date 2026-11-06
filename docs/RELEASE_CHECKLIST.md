# NeuroLab AI: Production Release Checklist & Operational Procedures

**System**: NeuroLab AI / AI Steam Lab  
**Anna App ID**: `744` (`neurolab-ai`)  
**Release Target Version**: `1.0.0` (Draft for Production Verification)  
**Evaluator Roles**: Senior DevOps Engineer, MLOps Engineer, Release Manager, Production Architect

---

## 1. Production Release Checklist

Every item in this checklist must be independently audited prior to cutting a production release or deploying to live user traffic:

### 1.1 Build Status
- [x] **Frontend Standalone Build**: `npm run build` succeeds cleanly in $<35\,\text{s}$, producing valid `dist/` with PWA service worker.
- [x] **Frontend Anna Build**: `npm run build:anna` succeeds cleanly, producing valid `dist/` with relative asset paths (`./assets/...`) and PWA disabled.
- [x] **Frontend Typecheck**: `npm run typecheck` passes with 0 TypeScript compiler errors.
- [x] **Frontend Linting**: `npm run lint` passes with 0 warnings and 0 errors.
- [x] **Backend Dockerfile Build**: Multi-stage Docker build passes with unprivileged user `appuser` (UID 10001).
- [x] **Dependency Locking**: Python packages pinned with exact versions (`google-genai==2.7.0`) in `backend/requirements.txt`.

### 1.2 Automated Test Status
- [x] **Physics Engine Validation**: 28 / 28 passed.
- [x] **Computer Vision Subsystem**: 76 / 76 passed.
- [x] **Security & Tenant Isolation**: 76 / 76 passed.
- [x] **AI Systems & Streaming**: 114 / 114 passed (3 mock skips for external live API).
- [x] **Database & API Contracts**: 147 / 147 passed.
- [x] **Infrastructure & Policy**: 144 / 144 passed.
- [x] **Phase 7 E2E Student Lifecycle**: 1 / 1 passed (12-step complete workflow + IDOR isolation).
- [x] **Frontend Unit & Store Tests**: 7 / 7 passed.
- [x] **Total Test Count**: **613 passing tests**, 0 failing tests.

### 1.3 Security & Access Control Status
- [x] **Fail-Closed Production Database**: Connection drops in production immediately raise `DatabasePersistenceError` (`HTTP 503`); no false in-memory commits.
- [x] **Authentication & Token Revocation**: Logout actively writes JTI to Redis denylist; revoked tokens return `HTTP 401`.
- [x] **Tenant Boundaries (IDOR Prevention)**: All experiment and conversation queries require matching `user_id`.
- [x] **CORS Configuration**: Wildcard `*` rejected when `allow_credentials=True`. Explicit origins set for Anna Partners and production web.
- [x] **Rate Limiting**: SlowAPI limits enforced on auth (30-60/min), streaming (30/min), and CV (120/min).
- [x] **Payload Limits**: Max 5 MB payload enforced at Nginx proxy and FastAPI level (`HTTP 413`).
- [x] **Zero Plaintext Secrets**: No credentials, private tokens, or database passwords in source code.

### 1.4 Database Migrations & Backup Strategy
- [x] **Advisory Locks**: Migrations guarded by `pg_advisory_lock(88990011)` to prevent concurrent execution races across replicas.
- [x] **Pre-Migration Snapshot**: Automated `pg_dump` snapshot generated with SHA-256 integrity checksum verification before migrations execute.
- [x] **Bidirectional Rollback**: Rollback migration handlers registered for every schema change.
- [x] **Connection Pool Capacity Budget**: $C_{\text{total}} \le 150$, staying safely within PostgreSQL connection limits.

### 1.5 Anna Application Identity Readiness
- [x] **Identity Manifests**: `app.json` (`neurolab-ai`), `manifest.json` (schema 2), and `.anna/app.json` (app ID `744`, handle `vikas-saini`).
- [x] **CORS & External Origins**: `manifest.json` declares `https://neurolab-backend-uxhv.onrender.com` in `external_origins`.
- [x] **Asset Paths**: Verified relative paths (`./`) in `dist/index.html`.
- [x] **Release Policy Enforced**: No Anna version cut or publish executed without user authorization.

### 1.6 Monitoring & Health Probing
- [x] **Liveness Probe**: `/live` responds immediately without external dependencies to prevent restart loops.
- [x] **Readiness Probe**: `/ready` verifies database, Redis, and model provider health; returns `503` if degraded.
- [x] **Metrics Authentication**: `/metrics` guarded by `METRICS_TOKEN`.
- [x] **Structured Logging**: JSON logging with request IDs, trace IDs, and sanitized error bodies.

---

## 2. Emergency Rollback Procedures

If an unrecoverable failure or critical regression occurs post-deployment:

```mermaid
flowchart TD
    Incident["Critical Production Incident Detected"] --> Assess{"Severity Assessment"}
    Assess -->|"Database Schema Corruption"| DB_Rollback["1. Roll Back Database Schema via Advisory Lock"]
    Assess -->|"Container Crash / High Error Rate"| Cont_Rollback["2. Revert Container Image / Git SHA on Host"]
    Assess -->|"Corrupted Anna Frontend"| Anna_Rollback["3. Revert Anna Manifest / Re-run build:anna"]
    DB_Rollback --> Verify["4. Verify /ready Probe Returns 200 OK"]
    Cont_Rollback --> Verify
    Anna_Rollback --> Verify
```

### 2.1 Backend Container Rollback (Render / Docker Compose)
- **Docker Compose**:
  ```bash
  # Revert to previous release tag or Git SHA
  git checkout <previous-stable-sha>
  docker-compose up --build -d
  ```
- **Render Cloud**:
  - In Render Dashboard $\to$ `stemlab-backend` $\to$ **Events** $\to$ Select previous successful deploy $\to$ Click **Rollback to this deploy**.

### 2.2 Database Schema Rollback
- Execute the migration rollback command:
  ```bash
  python -m app.core_backend.database.migrations --rollback
  ```
- If restoring from an emergency pre-migration snapshot:
  ```bash
  python -m app.core_backend.database.backup restore --file /backups/<timestamp>_backup.sql.gz
  ```

---

## 3. Known Issues & Operational Limitations

1. **YOLOv8 Memory Footprint on 512 MB Free Tier**:
   - Initializing YOLOv8 PyTorch models increases memory to ~1,087 MB, which triggers OOM kills on 512 MB containers.
   - **Mitigation**: `ENABLE_YOLO=false` is enforced on free-tier Render services. The system uses OpenCV HSV color tracking (`2.61 ms` latency, $< 150\,\text{MB}$ RAM).
2. **Model Accuracy on Diverse Real-World Datasets**:
   - Tracking has been validated against physical high-contrast markers (red/blue bobs) and synthetic frames.
   - However, because the repository does not bundle an annotated video benchmark dataset, formal statistical precision, recall, and mAP across diverse lighting have **not been established**.
3. **Browser Webcam Permissions**:
   - Physical webcam tracking requires explicit user camera permission over HTTPS. In unsecure HTTP contexts, browsers disable `getUserMedia`.
