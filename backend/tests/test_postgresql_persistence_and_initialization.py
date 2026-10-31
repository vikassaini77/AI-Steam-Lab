import os
import re
import yaml
import json
import gzip
import tempfile
import pytest
from unittest.mock import MagicMock, patch

from app.core_backend.database.backup import (
    create_database_backup,
    restore_database_backup,
    verify_backup_integrity,
    calculate_sha256,
)
from app.core_backend.database.migrations import (
    REQUIRED_SCHEMA_VERSION,
    verify_schema_version,
)


def test_docker_compose_named_volume_persistence():
    """
    Problem 33 Verification:
    docker-compose.yml must define durable named volumes (pgdata, db_backups)
    and replace ephemeral local bind mounts (./pgdata).
    """
    compose_path = "docker-compose.yml"
    assert os.path.exists(compose_path), "docker-compose.yml not found"

    with open(compose_path, "r", encoding="utf-8") as f:
        compose_cfg = yaml.safe_load(f)

    # 1. Named volumes defined at root level
    volumes = compose_cfg.get("volumes", {})
    assert "pgdata" in volumes, "docker-compose.yml must define top-level named volume 'pgdata'"
    assert "db_backups" in volumes, "docker-compose.yml must define top-level named volume 'db_backups'"

    # 2. Database service uses named volume
    services = compose_cfg.get("services", {})
    assert "db" in services, "Missing db service in docker-compose.yml"
    db_volumes = services["db"].get("volumes", [])

    assert any(v.startswith("pgdata:") for v in db_volumes), (
        "db service must mount named volume 'pgdata:/var/lib/postgresql/data'"
    )
    # Ensure no relative path bind mount for pgdata exists
    assert not any(v.startswith("./pgdata:") for v in db_volumes), (
        "db service must not use local bind mount './pgdata'"
    )


def test_docker_compose_versioned_migrations_as_separate_deployment_step():
    """
    Problem 33 Verification:
    Versioned migrations must run as a dedicated deployment step before application services start.
    - migration service defined
    - backend and celery_worker depend on migration service_completed_successfully
    """
    with open("docker-compose.yml", "r", encoding="utf-8") as f:
        compose_cfg = yaml.safe_load(f)

    services = compose_cfg.get("services", {})

    # 1. Dedicated migration service
    assert "migration" in services, "docker-compose.yml must define 'migration' service"
    migration_svc = services["migration"]
    assert "app.core_backend.database.migrations" in " ".join(migration_svc.get("command", [])), (
        "migration service must execute schema migrations module"
    )

    migration_deps = migration_svc.get("depends_on", {})
    assert "db" in migration_deps
    assert migration_deps["db"].get("condition") == "service_healthy"

    # 2. backend waits for database readiness AND migration completion
    backend_deps = services["backend"].get("depends_on", {})
    assert "db" in backend_deps
    assert backend_deps["db"].get("condition") == "service_healthy"
    assert "migration" in backend_deps, "backend must depend on migration service"
    assert backend_deps["migration"].get("condition") == "service_completed_successfully"

    # 3. celery_worker waits for database readiness AND migration completion
    worker_deps = services["celery_worker"].get("depends_on", {})
    assert "db" in worker_deps
    assert worker_deps["db"].get("condition") == "service_healthy"
    assert "migration" in worker_deps, "celery_worker must depend on migration service"
    assert worker_deps["migration"].get("condition") == "service_completed_successfully"


def test_docker_compose_database_healthcheck_and_network_isolation():
    """
    Problem 33 Verification:
    - db service has health check with interval, timeout, and start_period.
    - Database network access is restricted: no exposed host ports on db or redis.
    - All services communicate over internal network.
    """
    with open("docker-compose.yml", "r", encoding="utf-8") as f:
        compose_cfg = yaml.safe_load(f)

    services = compose_cfg.get("services", {})
    db_svc = services["db"]

    # 1. Healthcheck configuration
    assert "healthcheck" in db_svc, "db service missing healthcheck"
    hc = db_svc["healthcheck"]
    assert "pg_isready" in str(hc.get("test", []))
    assert "interval" in hc
    assert "timeout" in hc
    assert "start_period" in hc, "db healthcheck should specify start_period for initial startup"

    # 2. Network access restriction
    # db and redis must NOT publish host ports (only expose or network internal)
    assert "ports" not in db_svc, "db service must not publish host ports directly"
    assert "ports" not in services["redis"], "redis service must not publish host ports directly"

    # Networks defined
    assert "networks" in compose_cfg, "docker-compose.yml must define internal network"
    assert "neurolab_net" in compose_cfg["networks"]


def test_database_backup_creation_and_integrity_verification():
    """
    Problem 33 Verification:
    Tests database backup creation, checksumming, manifest assembly, and integrity check.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        mock_cur.fetchone.side_effect = [
            (True,),  # schema_migrations table exists
            (REQUIRED_SCHEMA_VERSION,),  # version
            {"exists": True},  # user_xp table exists
            {"exists": True},  # experiments table exists
            {"exists": False},  # etc.
            {"exists": False},
            {"exists": False},
            {"exists": False},
            {"exists": False},
            {"exists": False},
        ]
        mock_cur.fetchall.side_effect = [
            [{"user_id": "u1", "xp": 100}],
            [{"id": "exp_1", "user_id": "u1", "data": {"height": 50.0}, "timestamp": 12345}],
        ]

        with patch("psycopg2.connect", return_value=mock_conn):
            res = create_database_backup(
                url="postgresql://user:pass@db:5432/stemlab",
                output_dir=tmp_dir,
                filename="test_backup.json.gz",
                compress=True,
            )

        assert res["status"] == "success"
        assert os.path.exists(res["file"])
        assert res["sha256"] == calculate_sha256(res["file"])
        assert res["schema_version"] == REQUIRED_SCHEMA_VERSION

        # Verify integrity
        integrity = verify_backup_integrity(res["file"])
        assert integrity["valid"] is True
        assert integrity["schema_version"] == REQUIRED_SCHEMA_VERSION
        assert integrity["sha256"] == res["sha256"]


def test_database_restoration_drill_transactional_rollback():
    """
    Problem 33 Verification:
    Tests database restoration drill and transactional rollback on unexpected errors.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        backup_file = os.path.join(tmp_dir, "sample_backup.json")
        backup_content = {
            "metadata": {
                "created_at": "2026-10-31T08:00:00Z",
                "schema_version": 5,
                "table_counts": {"user_xp": 1},
                "format_version": "1.0",
                "compressed": False,
            },
            "data": {
                "user_xp": [{"user_id": "u_test", "xp": 250}],
            },
        }
        with open(backup_file, "w", encoding="utf-8") as f:
            json.dump(backup_content, f)

        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur

        with patch("psycopg2.connect", return_value=mock_conn), \
             patch("app.core_backend.database.migrations.run_migrations", return_value=5):
            restore_res = restore_database_backup(
                backup_path=backup_file,
                url="postgresql://user:pass@db:5432/stemlab",
            )

        assert restore_res["status"] == "success"
        assert "user_xp" in restore_res["restored_tables"]
        mock_conn.commit.assert_called_once()

        # Test failure triggers rollback
        mock_conn_err = MagicMock()
        mock_cur_err = MagicMock()
        mock_conn_err.cursor.return_value.__enter__.return_value = mock_cur_err
        mock_cur_err.execute.side_effect = RuntimeError("Disk full during restoration drill")

        with patch("psycopg2.connect", return_value=mock_conn_err), \
             patch("app.core_backend.database.migrations.run_migrations", return_value=5):
            with pytest.raises(RuntimeError):
                restore_database_backup(
                    backup_path=backup_file,
                    url="postgresql://user:pass@db:5432/stemlab",
                )
            mock_conn_err.rollback.assert_called_once()


def test_corrupted_backup_rejected_by_integrity_verifier():
    """
    Problem 33 Verification:
    Corrupted, truncated, or invalid backup files are safely rejected without touching database.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        corrupt_file = os.path.join(tmp_dir, "corrupt.json.gz")
        with open(corrupt_file, "wb") as f:
            f.write(b"this is not a valid gzip or json archive payload")

        with pytest.raises(ValueError) as exc_info:
            verify_backup_integrity(corrupt_file)
        assert "Corrupt or invalid backup file" in str(exc_info.value)
