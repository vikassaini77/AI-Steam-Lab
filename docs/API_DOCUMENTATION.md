# NeuroLab AI: API Specification & Contracts

**API Base URLs**:
- Production Web: `https://neurolab-backend-uxhv.onrender.com/api`
- Versioned Production: `https://neurolab-backend-uxhv.onrender.com/api/v1`
- Local Development: `http://localhost:8000/api`
**OpenAPI Specification**: Interactive Swagger docs available at `/docs` (or `/api/v1/docs`).

---

## 1. Authentication & Security Endpoints

### 1.1 User Profile
- **Route**: `GET /api/auth/profile` (or `GET /api/v1/auth/profile`)
- **Access**: 🔒 Protected (`Authorization: Bearer <token>`)
- **Response `200 OK`**:
  ```json
  {
    "user_id": "usr_998811",
    "email": "student@neurolab.ai",
    "full_name": "Marie Curie",
    "student_level": "Senior Scientist",
    "total_xp": 1450,
    "created_at": "2026-11-01T12:00:00Z"
  }
  ```

### 1.2 User Logout & Token Revocation
- **Route**: `POST /api/auth/logout` (or `POST /api/v1/auth/logout`)
- **Access**: 🔒 Protected (`Authorization: Bearer <token>`)
- **Description**: Immediately invalidates the Bearer token in the distributed Redis revocation denylist. Subsequent requests with the token return `401 Unauthorized`.
- **Response `200 OK`**:
  ```json
  {
    "status": "success",
    "message": "Session successfully revoked."
  }
  ```

### 1.3 MFA Factor Enrollment & Verification
- **Route**: `POST /api/auth/mfa/enroll`
- **Route**: `POST /api/auth/mfa/verify`
- **Route**: `POST /api/auth/mfa/unenroll`
- **Description**: Manages TOTP authenticator factors with QR code payload generation and 6-digit challenge verification.

---

## 2. Socratic AI Tutor Endpoints

### 2.1 Server-Sent Events (SSE) Dialogue Streaming
- **Route**: `POST /api/tutor/chat/stream` (or `POST /api/v1/tutor/chat/stream`)
- **Access**: 🔒 Protected (`Authorization: Bearer <token>`)
- **Headers**:
  - `Accept: text/event-stream`
  - `Content-Type: application/json`
- **Request Body**:
  ```json
  {
    "message": "Why does changing the pendulum mass not alter the oscillation period?",
    "session_id": "sess_112233",
    "experiment_type": "pendulum",
    "parameters": {
      "length": 1.0,
      "gravity": 9.81,
      "mass": 0.5
    },
    "measured_values": {
      "period": 2.006
    }
  }
  ```
- **Stream Event Types**:
  - `event: metadata`: Emits `{"session_id": "...", "model": "gemini-2.5-flash"}`.
  - `event: token`: Emits `{"text": "Consider..."}` token-by-token.
  - `event: evaluation`: Emits mastery evaluation if the student was answering a Socratic prompt.
  - `event: done`: Emits `{"status": "complete"}`.
  - `event: error`: Emits `{"error": "...", "code": "..."}` on provider interruption.

### 2.2 Conversational Memory Management
- **Route**: `GET /api/tutor/memories` (Lists user memories; strict tenant isolation)
- **Route**: `DELETE /api/tutor/memories` (Prunes conversation memories for authenticated user)

---

## 3. Computer Vision & Kinematics Endpoints

### 3.1 Frame Tracking Analysis
- **Route**: `POST /api/cv/track` (or `POST /api/v1/cv/track`)
- **Access**: 🔒 Protected (`Authorization: Bearer <token>`)
- **Payload Limits**: Max 5 MB payload (`HTTP 413` if exceeded); maximum resolution $1920 \times 1080$.
- **Request Parameters (Multipart or JSON Base64)**:
  - `method`: `"color"` (HSV), `"optical_flow"` (Lucas-Kanade), or `"yolo"` (Deep Learning).
  - `session_id`: Unique tracking session.
  - `camera_id`: Optional identifier for multi-camera setups.
  - `frame`: Base64 JPEG or binary image payload.
- **Response `200 OK`**:
  ```json
  {
    "success": true,
    "tracking_method": "color",
    "coordinates": {"x": 320, "y": 240},
    "bounding_box": [300, 220, 340, 260],
    "confidence": 0.94,
    "kinematics": {
      "velocity_px_s": 142.5,
      "velocity_m_s": 0.285,
      "acceleration_m_s2": 9.78,
      "dt_ms": 33.2
    },
    "provenance": {
      "model_version": "hsv_morphology_v1.0",
      "configuration_version": "cv_config_v1.0",
      "latency_ms": 2.61
    }
  }
  ```

### 3.2 Real-Time WebSocket Tracking Stream
- **Route**: `ws://<host>/api/cv/ws/{session_id}` (or `wss://...`)
- **Protocol**: Binary frame array buffers or Base64 JSON messages. Emits real-time coordinate updates at up to 60 FPS.

---

## 4. Scientific Experiment Endpoints

### 4.1 Retrieve Supported Experiment Schemas
- **Route**: `GET /api/experiments/types`
- **Access**: 🌐 Public
- **Response `200 OK`**:
  ```json
  {
    "supported_types": [
      "pendulum",
      "projectile_motion",
      "free_fall",
      "circular_motion",
      "harmonic_motion",
      "collision"
    ]
  }
  ```

### 4.2 Save Validated Experiment
- **Route**: `POST /api/experiments/save`
- **Access**: 🔒 Protected (`Authorization: Bearer <token>`)
- **Request Body**:
  ```json
  {
    "type": "pendulum",
    "title": "Length vs Period Pendulum Run 1",
    "parameters": {
      "length": 1.0,
      "gravity": 9.81,
      "initial_angle": 15.0
    },
    "experimental_value": 2.006,
    "theoretical_value": 2.006,
    "unit": "s",
    "notes": "Verified Runge-Kutta 4th order numerical match."
  }
  ```

### 4.3 Experiment History & Detail
- **Route**: `GET /api/experiments/history` (Lists user's saved runs with pagination)
- **Route**: `GET /api/experiments/{id}` (Retrieves single experiment; enforces user ownership)
- **Route**: `DELETE /api/experiments/{id}` (Deletes experiment owned by user; `403` on cross-tenant access)

---

## 5. Gamification & XP Endpoints

### 5.1 Award Experience Points
- **Route**: `POST /api/gamification/add-xp`
- **Access**: 🔒 Protected (`Authorization: Bearer <token>`)
- **Security**: Server-authoritative validation; client cannot forge arbitrary XP values. Bound to validated experiment IDs or Socratic mastery evaluation.

### 5.2 User Badges & Leaderboard
- **Route**: `GET /api/gamification/badges` (Returns unlocked badges with cryptographic verification proof)
- **Route**: `GET /api/gamification/leaderboard` (Public ranked leaderboard cached in Redis)

---

## 6. Asynchronous Background Task Endpoints

- **Route**: `POST /api/tasks/submit-cv-frame` (Enqueues heavy video/frame analysis job)
- **Route**: `POST /api/tasks/submit-tutor-request` (Enqueues batch AI generation task)
- **Route**: `GET /api/tasks/{task_id}/status` (Returns `PENDING`, `STARTED`, `SUCCESS`, or `FAILURE`)
- **Route**: `GET /api/tasks/{task_id}/result` (Retrieves durable result; validates task owner)

---

## 7. System Health, Probing, and Telemetry

- **Route**: `GET /live` / `GET /healthz` (Liveness probe: verifies process event loop responsiveness)
- **Route**: `GET /ready` / `GET /health/ready` (Readiness probe: validates DB, Redis, and AI configurations)
- **Route**: `GET /metrics` (Prometheus telemetry scraper guarded by `METRICS_TOKEN`)
- **Route**: `GET /api/dependencies` (Exposes health status and fallback policies of all subsystems)
