# NeuroLab AI: Environment Variable Reference

**Document Version**: 1.0.0 (Production Release Preparation)  
**Security Notice**: Do NOT store real credentials, passwords, or private keys in this file or any file committed to source control.

---

## 1. Environment Variable Dictionary

| Variable Name | Required in Prod? | Default (Dev) | Allowed Values | Description |
| :--- | :---: | :--- | :--- | :--- |
| **`ENVIRONMENT`** | **Yes** | `development` | `development`, `test`, `staging`, `production` | Deployment mode. In `production`, enforces strict secret checks, fail-closed database mode, and disables wildcards. |
| **`IS_CONTAINER`** | Conditional | `false` | `true`, `false` | Must be `true` when running inside Docker containers to validate container-safe network hostnames. |
| **`PORT`** | Optional | `8000` | Valid TCP port | Listening port for FastAPI backend service. |
| **`HOST`** | Optional | `0.0.0.0` | IP Address | Network binding address for FastAPI backend service. |
| **`POSTGRES_URL`** | **Yes** (or Supabase) | None | Valid PostgreSQL connection URI | Canonical PostgreSQL connection string (e.g. `postgresql://user:pass@host:5432/db`). Must not point to `localhost` inside container. |
| **`POSTGRES_USER`** | Optional | `stemlab_app` | String | PostgreSQL database username. |
| **`POSTGRES_PASSWORD`** | **Yes** (if using PG) | None | High-entropy string | Password for PostgreSQL user. Insecure defaults (`postgres:postgres`) fail fast in production. |
| **`POSTGRES_DB`** | Optional | `stemlab` | String | PostgreSQL database name. |
| **`DATABASE_URL`** | Optional | None | Valid URI | Alias for `POSTGRES_URL`, automatically mapped in Render environments. |
| **`DB_POOL_MIN_SIZE`** | Optional | `2` | Integer $\ge 1$ | Minimum idle connections retained in the PostgreSQL async connection pool. |
| **`DB_POOL_MAX_SIZE`** | Optional | `10` | Integer $\le 50$ | Maximum concurrent connections per backend worker instance. |
| **`DB_ACQUISITION_TIMEOUT_SECONDS`** | Optional | `3.0` | Float seconds | Timeout for acquiring a free connection from the pool before returning `503`. |
| **`REDIS_URL`** | **Yes** | `redis://redis:6379/0` | `redis://...` or `rediss://...` | Connection URI for Redis cache, rate limiting, token revocation denylist, and Celery broker. |
| **`CELERY_BROKER_URL`** | Optional | Same as `REDIS_URL` | `redis://...` | Connection URI for Celery task broker. |
| **`ASYNC_TASKS_ENABLED`**| Optional | `false` | `true`, `false` | Enables asynchronous task submission to the Celery queue. |
| **`CELERY_CONCURRENCY`** | Optional | `2` | Integer | Number of concurrent worker execution threads/processes. |
| **`GEMINI_API_KEY`** | **Yes** (for AI) | None | Google AI Studio Key | API key powering Google Gemini 2.5 Flash Socratic tutoring and 768-dim embeddings. |
| **`GEMINI_MODEL_NAME`** | Optional | `gemini-2.5-flash` | Valid Gemini model | Target generative LLM model identifier. |
| **`ENABLE_YOLO`** | Optional | `false` | `true`, `false` | Enables YOLOv8 object detection. **Must be false on < 1GB RAM containers** (Render free tier) to prevent OOM kills. |
| **`YOLO_WEIGHTS_PATH`** | Optional | `backend/weights/yolov8n.pt` | File path | Path to YOLOv8 ONNX or PyTorch weights. Fallbacks to HSV tracker if missing. |
| **`SUPABASE_URL`** | Conditional | None | Valid HTTPS URL | API endpoint URL for Supabase managed authentication. |
| **`SUPABASE_KEY`** | Conditional | None | Supabase API Key | Supabase anon key or service role key. |
| **`METRICS_TOKEN`** | **Yes** | None | High-entropy string | Bearer token protecting the Prometheus `/metrics` scraper endpoint. |
| **`ALLOWED_ORIGINS`** | **Yes** | See config | Comma-delimited URLs | Permitted CORS frontend origins. **Wildcard `*` is strictly forbidden in production**. |
| **`ENABLE_HSTS`** | Optional | `false` | `true`, `false` | Injects `Strict-Transport-Security` header. Automatically enforced only over verified HTTPS connections. |
| **`SENTRY_DSN`** | Optional | None | Sentry DSN URI | Optional Sentry Application Performance Monitoring and error tracking endpoint. |
| **`LOG_LEVEL`** | Optional | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` | Logging verbosity for structured JSON logging. |

---

## 2. Frontend Environment Variables (`frontend/.env`)

| Variable Name | Required in Prod? | Default | Description |
| :--- | :---: | :--- | :--- |
| **`VITE_API_URL`** | Optional | `https://neurolab-backend-uxhv.onrender.com` | Override URL pointing frontend to backend. When empty, defaults to production Render backend or local `:8000`. |
| **`VITE_SUPABASE_URL`** | Optional | Project URL | Client-side Supabase URL for client authentication. Gracefully degrades to mock auth if unconfigured. |
| **`VITE_SUPABASE_ANON_KEY`** | Optional | Anon Key | Client-side Supabase public anon key. |

---

## 3. Production Startup Safety Validations

When `ENVIRONMENT=production` is declared, `backend/app/core_backend/core/config.py` enforces fail-fast startup checks:
1. **Database Presence**: Validates that either (`SUPABASE_URL` + `SUPABASE_KEY`) or `POSTGRES_URL` is configured. If neither is present, process startup aborts with a descriptive `RuntimeError`.
2. **Insecure Password Rejection**: Validates that `POSTGRES_URL` does not contain default passwords (e.g. `postgres:postgres@`).
3. **No Wildcard CORS**: Validates that `ALLOWED_ORIGINS` does not contain `*`, which violates web security standards when `allow_credentials=True`.
4. **Container Hostname Safety**: When `IS_CONTAINER=true`, validates that `POSTGRES_URL` does not reference `localhost` or `127.0.0.1`, which fail inside isolated Docker network namespaces.
