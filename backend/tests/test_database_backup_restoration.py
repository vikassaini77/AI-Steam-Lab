"""
Tests for Problem 22 & Problem 33:
PostgreSQL Database Backup Creation, SHA-256 Integrity Verification, and Transactional Restoration Drill.
"""
import gzip
import json
import os
import tempfile
import pytest
from app.core_backend.database.backup import (
    calculate_sha256,
    verify_backup_integrity,
    create_database_backup,
    restore_database_backup,
)


def test_calculate_sha256_and_tamper_detection():
    """
    Verifies that SHA-256 hashes detect file modification or corruption.
    """
    with tempfile.NamedTemporaryFile("w", delete=False) as f:
        f.write("original_database_payload_content_12345")
        filepath = f.name

    try:
        hash1 = calculate_sha256(filepath)
        assert len(hash1) == 64
        assert hash1 == calculate_sha256(filepath)

        # Modify content (simulate bit rot or tampering)
        with open(filepath, "a") as f:
            f.write("_tampered")

        hash2 = calculate_sha256(filepath)
        assert hash1 != hash2, "Tampered backup must produce a different SHA-256 hash"
    finally:
        os.remove(filepath)


def test_verify_backup_integrity_valid():
    """
    Verifies that valid gzip and raw JSON backups pass integrity checks.
    """
    sample_backup = {
        "metadata": {
            "created_at": "2026-11-01T12:00:00Z",
            "schema_version": 5,
            "table_counts": {"user_xp": 2, "xp_ledger": 2},
            "format_version": "1.0",
        },
        "data": {
            "user_xp": [
                {"user_id": "u1", "xp": 100},
                {"user_id": "u2", "xp": 200},
            ],
            "xp_ledger": [
                {"event_id": "e1", "user_id": "u1", "amount": 100},
                {"event_id": "e2", "user_id": "u2", "amount": 200},
            ],
        },
    }

    # 1. Test compressed .json.gz
    with tempfile.NamedTemporaryFile("wb", suffix=".json.gz", delete=False) as f:
        with gzip.open(f, "wt", encoding="utf-8") as gz:
            json.dump(sample_backup, gz)
        gz_path = f.name

    # 2. Test plain .json
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(sample_backup, f)
        json_path = f.name

    try:
        res_gz = verify_backup_integrity(gz_path)
        assert res_gz["valid"] is True
        assert res_gz["schema_version"] == 5
        assert res_gz["table_counts"]["user_xp"] == 2

        res_json = verify_backup_integrity(json_path)
        assert res_json["valid"] is True
        assert res_json["schema_version"] == 5
        assert res_json["table_counts"]["xp_ledger"] == 2
    finally:
        os.remove(gz_path)
        os.remove(json_path)


def test_verify_backup_integrity_corrupt_file_rejected():
    """
    Verifies that corrupt or truncated files fail verification cleanly.
    """
    with tempfile.NamedTemporaryFile("wb", suffix=".json.gz", delete=False) as f:
        f.write(b"NOT_A_VALID_GZIP_STREAM_CORRUPTED_BYTES_123456789")
        bad_path = f.name

    try:
        with pytest.raises(ValueError) as exc:
            verify_backup_integrity(bad_path)
        assert "corrupt or invalid" in str(exc.value).lower()
    finally:
        os.remove(bad_path)


def test_verify_backup_integrity_missing_keys_rejected():
    """
    Verifies that backups missing metadata or data root keys are rejected.
    """
    bad_payload = {"some_other_key": 123}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(bad_payload, f)
        bad_path = f.name

    try:
        with pytest.raises(ValueError) as exc:
            verify_backup_integrity(bad_path)
        assert "missing required 'metadata' or 'data'" in str(exc.value).lower()
    finally:
        os.remove(bad_path)

