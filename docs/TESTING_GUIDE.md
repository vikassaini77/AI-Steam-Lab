# NeuroLab AI: Quality Assurance & Testing Guide

**Document Version**: 1.0.0 (Production Release Preparation)  
**Total Verified Test Count**: 586 Backend Tests, 7 Frontend Tests, 0 TypeScript Errors

---

## 1. Testing Philosophy & Verification Gateways

NeuroLab AI adheres to a strict "no fabricated guarantees" testing discipline:
- No feature is declared complete without a corresponding automated integration test.
- Production configurations fail fast when unconfigured or insecure.
- Every release must pass unit tests, contract validations, security audits, empirical performance benchmarks, and end-to-end multi-tenant lifecycle simulations.

---

## 2. Frontend Test Suite Execution

### 2.1 Unit & Store Tests (Vitest)
Executes component and store state tests (Zustand user store, chat store, session persistence, and streaming token accumulation):
```bash
# Run Vitest test suite
npx --prefix frontend vitest run
```
*Expected Output*: `2 passed (2)`, `7 passed (7)` (duration: $< 1.0\,\text{s}$).

### 2.2 TypeScript Static Typecheck
Validates strict type contracts, null-safety, and interface conformance:
```bash
npm --prefix frontend run typecheck
```
*Expected Output*: `0 errors` (`tsc -b` completes silently).

### 2.3 ESLint Code Hygiene
Checks for syntax errors, React hooks violations, and dead imports:
```bash
npm --prefix frontend run lint
```
*Expected Output*: `0 warnings, 0 errors`.

### 2.4 Production Builds Verification
Verifies both standalone web and Anna embedded bundle builds:
```bash
# 1. Standalone Web Build (with PWA service workers)
npm --prefix frontend run build

# 2. Anna Partners Embedded SPA Build (relative paths, no PWA)
npm --prefix frontend run build:anna
```

---

## 3. Backend Pytest Suites Execution

All backend tests are organized under `backend/tests/` and run using standard `pytest`:

```bash
# Activate virtual environment
cd backend
source venv/bin/activate  # Or .\venv\Scripts\Activate.ps1 on Windows
```

### 3.1 Physics Engine & Numerical Validation (28 Tests)
```bash
pytest backend/tests/test_physics_engine.py backend/tests/test_physics_engine_numerical_validation.py -v
```
- Validates analytical formulas, Runge-Kutta 4th order numerical solutions, boundary conditions, and negative parameter rejections across all 6 physics experiment engines.

### 3.2 Computer Vision Subsystem (76 Tests)
```bash
pytest backend/tests/test_cv_tracking_methods_genuine.py \
       backend/tests/test_cv_image_security.py \
       backend/tests/test_cv_performance_limits.py \
       backend/tests/test_cv_tracker_security.py \
       backend/tests/test_cv_inference_correctness.py \
       backend/tests/test_cv_physics_and_persistence.py \
       backend/tests/test_cv_tracker_isolation_and_state.py -v
```
- Validates HSV morphology, Lucas-Kanade optical flow, YOLOv8 model loading, corrupt image payloads, 5MB ceiling, camera/session isolation, and tracker TTL pruning.

### 3.3 Security, Auth, and Multi-Tenant Isolation (76 Tests)
```bash
pytest backend/tests/test_auth_security.py \
       backend/tests/test_auth_mfa.py \
       backend/tests/test_jwt_verification_security.py \
       backend/tests/test_logout_session_revocation.py \
       backend/tests/test_user_isolation.py \
       backend/tests/test_cors_preflight.py \
       backend/tests/test_secret_management_security.py \
       backend/tests/test_metrics_and_headers_security.py \
       backend/tests/test_rate_limiting_load.py \
       backend/tests/test_xp_manipulation_prevention.py \
       backend/tests/test_achievement_evidence_security.py -v
```
- Validates JWT verification, MFA enrollment, logout token denylisting in Redis, IDOR prevention, CORS preflight policies, IP rate limiting, and XP ledger tampering prevention.

### 3.4 AI Systems, Streaming, and RAG Memory (114 Tests)
```bash
pytest backend/tests/test_phase2_ai_tutor_system.py \
       backend/tests/test_tutor_async_nonblocking.py \
       backend/tests/test_tutor_error_handling.py \
       backend/tests/test_tutor_learning_evaluation.py \
       backend/tests/test_tutor_nonblocking_streaming.py \
       backend/tests/test_tutor_orchestration_service_boundaries.py \
       backend/tests/test_tutor_retrieval_service_observability.py \
       backend/tests/test_tutor_streaming_semantics.py \
       backend/tests/test_conversation_memory_tenant_isolation.py \
       backend/tests/test_memory_ownership_and_lifecycle.py \
       backend/tests/test_embedding_correctness.py \
       backend/tests/test_embedding_production_readiness.py \
       backend/tests/test_hybrid_retrieval.py \
       backend/tests/test_hybrid_retrieval_validation.py -v
```
- Validates Server-Sent Events (SSE) token delivery, thread offloading, Gemini error resilience, prompt injection resistance, 768-dim vector embeddings, and hybrid RRF search.

### 3.5 Database, Contracts, and Resilience (147 Tests)
```bash
pytest backend/tests/test_api_endpoints.py \
       backend/tests/test_api_request_response_contracts.py \
       backend/tests/test_experiment_type_schema_validation.py \
       backend/tests/test_phase5_hardening.py \
       backend/tests/test_database_persistence_modes.py \
       backend/tests/test_database_connection_pool.py \
       backend/tests/test_database_error_handling_and_resilience.py \
       backend/tests/test_database_backup_restoration.py \
       backend/tests/test_postgresql_persistence_and_initialization.py \
       backend/tests/test_postgres_service_configuration.py \
       backend/tests/test_redis_cache_failures_and_telemetry.py \
       backend/tests/test_celery_worker_tasks.py \
       backend/tests/test_leaderboard_authenticity.py \
       backend/tests/test_badge_achievement_integrity.py \
       backend/tests/test_xp_integrity_and_ledger.py -v
```
- Validates OpenAPI schemas, fail-closed persistence, connection pool capacity ($C_{\text{total}} \le 150$), pre-migration backups, advisory locking, and Redis circuit breaking.

### 3.6 Infrastructure, Deployment, and Security Policy (144 Tests)
```bash
pytest backend/tests/test_ci_pipeline_enforcement.py \
       backend/tests/test_docker_and_nginx_config.py \
       backend/tests/test_docker_compose_environment_configuration.py \
       backend/tests/test_e2e_compose_deployment.py \
       backend/tests/test_health_and_readiness_probes.py \
       backend/tests/test_lifespan_and_dependency_injection.py \
       backend/tests/test_model_versioning_and_provenance.py \
       backend/tests/test_nginx_streaming_and_payload_policies.py \
       backend/tests/test_observability_and_diagnostics.py \
       backend/tests/test_render_configuration_and_architecture.py \
       backend/tests/test_service_dependencies_and_fallbacks.py \
       backend/tests/test_trivy_security_policy.py -v
```
- Validates Dockerfile unprivileged user execution, Trivy vulnerability policies, Nginx SSE buffering rules, pinned requirements, and `/live` vs. `/ready` probe contracts.

### 3.7 Complete End-to-End Student Lifecycle (Phase 7 E2E)
```bash
pytest backend/tests/test_phase7_e2e_student_lifecycle.py -v
```
- Runs a complete multi-step simulation: registration $\to$ curriculum $\to$ tracking $\to$ simulation $\to$ persistence $\to$ IDOR tenant boundary verification $\to$ AI tutoring $\to$ gamification $\to$ logout revocation.

---

## 4. Empirical Performance Benchmarking Harness

To measure hardware-grounded latencies and throughput:
```bash
python backend/scripts/run_benchmarks.py --runs 10 --warmup 2
```
Outputs empirical JSON to `backend/benchmark_results.json`.
