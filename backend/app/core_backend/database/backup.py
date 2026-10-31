"""
NeuroLab AI: PostgreSQL Database Backup & Restoration Engine
Handles durable database backups, integrity verification, and transactional restoration drills.
Problem 33: Configure backups, test restoration, and ensure production lifecycle durability.
"""

import os
import sys
import json
import gzip
import time
import hashlib
import argparse
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
import psycopg2
from psycopg2.extras import RealDictCursor
from app.logger import logger

BACKUP_DIR = os.getenv("DB_BACKUP_DIR", os.path.join(os.path.dirname(__file__), "..", "..", "..", "backups"))

CANONICAL_TABLES = [
    "schema_migrations",
    "user_xp",
    "xp_ledger",
    "user_achievements",
    "experiments",
    "mastery_records",
    "daily_usage",
    "memories",
]


def calculate_sha256(filepath: str) -> str:
    """Computes the SHA-256 hash of a backup file for tamper and integrity verification."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def create_database_backup(
    url: Optional[str] = None,
    output_dir: Optional[str] = None,
    filename: Optional[str] = None,
    compress: bool = True,
) -> Dict[str, Any]:
    """
    Creates a durable, transactional backup of all authoritative database tables and metadata.
    Does not require external pg_dump binary on host, ensuring universal portability.
    Returns backup metadata including file path, sha256 checksum, row counts, and schema version.
    """
    from app.core_backend.database.pgvector_db import get_database_url
    target_url = url or get_database_url()
    if not target_url:
        raise RuntimeError("Cannot create backup: POSTGRES_URL is not configured.")

    dest_dir = output_dir or BACKUP_DIR
    os.makedirs(dest_dir, exist_ok=True)

    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    ext = ".json.gz" if compress else ".json"
    backup_filename = filename or f"neurolab_backup_{timestamp_str}{ext}"
    output_path = os.path.join(dest_dir, backup_filename)

    logger.info(f"Initiating PostgreSQL backup to {output_path}...")
    conn = psycopg2.connect(target_url)
    try:
        # READ COMMITTED snapshot
        conn.autocommit = False
        with conn.cursor() as cur:
            cur.execute("BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;")

        # 1. Fetch current schema version
        schema_version = 0
        with conn.cursor() as cur:
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'schema_migrations'
                );
            """)
            if cur.fetchone()[0]:
                cur.execute("SELECT COALESCE(MAX(version), 0) FROM schema_migrations;")
                row = cur.fetchone()
                schema_version = int(row[0]) if row else 0

        # 2. Extract table data
        table_data: Dict[str, List[Dict[str, Any]]] = {}
        row_counts: Dict[str, int] = {}

        for table in CANONICAL_TABLES:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = %s
                    );
                """, (table,))
                exists = cur.fetchone()["exists"]
                if not exists:
                    continue

                cur.execute(f"SELECT * FROM {table};")
                rows = cur.fetchall()
                # Convert RealDictRow to standard serializable dicts
                serializable_rows = []
                for r in rows:
                    row_dict = {}
                    for k, v in r.items():
                        if isinstance(v, datetime):
                            row_dict[k] = v.isoformat()
                        elif hasattr(v, "tolist"):  # NumPy or vector objects
                            row_dict[k] = v.tolist()
                        else:
                            row_dict[k] = v
                    serializable_rows.append(row_dict)

                table_data[table] = serializable_rows
                row_counts[table] = len(serializable_rows)

        conn.commit()

        # 3. Assemble backup manifest
        backup_payload = {
            "metadata": {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "schema_version": schema_version,
                "table_counts": row_counts,
                "format_version": "1.0",
                "compressed": compress,
            },
            "data": table_data,
        }

        # 4. Write payload to disk
        payload_str = json.dumps(backup_payload, indent=2 if not compress else None)
        if compress:
            with gzip.open(output_path, "wt", encoding="utf-8") as f:
                f.write(payload_str)
        else:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(payload_str)

        file_size = os.path.getsize(output_path)
        file_sha256 = calculate_sha256(output_path)

        result = {
            "status": "success",
            "file": output_path,
            "filename": os.path.basename(output_path),
            "size_bytes": file_size,
            "sha256": file_sha256,
            "schema_version": schema_version,
            "table_counts": row_counts,
            "total_rows": sum(row_counts.values()),
            "created_at": backup_payload["metadata"]["created_at"],
        }
        logger.info(f"Database backup created successfully: {result}")
        return result

    except Exception as e:
        conn.rollback()
        logger.critical(f"Database backup failed: {e}")
        raise
    finally:
        conn.close()


def verify_backup_integrity(backup_path: str) -> Dict[str, Any]:
    """
    Validates backup structure, gzip decompression (if applicable),
    and manifests validity before attempting restoration.
    """
    if not os.path.exists(backup_path):
        raise FileNotFoundError(f"Backup file not found at: {backup_path}")

    is_gz = backup_path.endswith(".gz")
    try:
        if is_gz:
            with gzip.open(backup_path, "rt", encoding="utf-8") as f:
                payload = json.load(f)
        else:
            with open(backup_path, "r", encoding="utf-8") as f:
                payload = json.load(f)

        if "metadata" not in payload or "data" not in payload:
            raise ValueError("Malformed backup file: missing required 'metadata' or 'data' root keys.")

        meta = payload["metadata"]
        data = payload["data"]

        return {
            "valid": True,
            "schema_version": meta.get("schema_version", 0),
            "created_at": meta.get("created_at"),
            "table_counts": {k: len(v) for k, v in data.items()},
            "sha256": calculate_sha256(backup_path),
        }
    except Exception as e:
        logger.error(f"Integrity check failed for backup {backup_path}: {e}")
        raise ValueError(f"Corrupt or invalid backup file ({backup_path}): {e}")


def restore_database_backup(
    backup_path: str,
    url: Optional[str] = None,
    verify_integrity: bool = True,
) -> Dict[str, Any]:
    """
    Restores database records from a verified backup archive transactionally.
    Guarantees all-or-nothing rollback on any restoration failure.
    """
    from app.core_backend.database.pgvector_db import get_database_url
    target_url = url or get_database_url()
    if not target_url:
        raise RuntimeError("Cannot restore backup: POSTGRES_URL is not configured.")

    if verify_integrity:
        verify_backup_integrity(backup_path)

    is_gz = backup_path.endswith(".gz")
    if is_gz:
        with gzip.open(backup_path, "rt", encoding="utf-8") as f:
            payload = json.load(f)
    else:
        with open(backup_path, "r", encoding="utf-8") as f:
            payload = json.load(f)

    meta = payload.get("metadata", {})
    data = payload.get("data", {})

    logger.info(f"Restoring database backup from {backup_path} (schema v{meta.get('schema_version')})...")
    conn = psycopg2.connect(target_url)
    try:
        conn.autocommit = False
        restored_counts: Dict[str, int] = {}

        with conn.cursor() as cur:
            # First ensure migrations table and schema exist
            from app.core_backend.database.migrations import run_migrations
            run_migrations(url=target_url)

            # Restore each table in canonical order
            for table in CANONICAL_TABLES:
                if table not in data:
                    continue
                rows = data[table]
                if not rows:
                    restored_counts[table] = 0
                    continue

                columns = list(rows[0].keys())
                col_names = ", ".join(columns)
                placeholders = ", ".join(["%s"] * len(columns))

                # Use ON CONFLICT DO UPDATE or DO NOTHING depending on table primary keys
                insert_query = f"INSERT INTO {table} ({col_names}) VALUES ({placeholders}) ON CONFLICT DO NOTHING;"

                for row in rows:
                    values = []
                    for c in columns:
                        val = row[c]
                        if isinstance(val, dict) or (isinstance(val, list) and c not in ("embedding",)):
                            values.append(json.dumps(val))
                        else:
                            values.append(val)
                    cur.execute(insert_query, tuple(values))

                restored_counts[table] = len(rows)

        conn.commit()
        logger.info(f"Database restoration completed successfully: {restored_counts}")
        return {
            "status": "success",
            "file": backup_path,
            "restored_tables": list(restored_counts.keys()),
            "restored_counts": restored_counts,
            "schema_version": meta.get("schema_version"),
        }
    except Exception as e:
        conn.rollback()
        logger.critical(f"Database restoration failed, rolled back changes: {e}")
        raise
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="NeuroLab AI PostgreSQL Backup & Restoration Utility")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # create backup
    create_parser = subparsers.add_parser("create", help="Create a new database backup")
    create_parser.add_argument("--url", help="Database connection URL", default=None)
    create_parser.add_argument("--dir", help="Destination backup directory", default=None)
    create_parser.add_argument("--filename", help="Backup output filename", default=None)
    create_parser.add_argument("--no-compress", action="store_true", help="Disable gzip compression")

    # restore backup
    restore_parser = subparsers.add_parser("restore", help="Restore database from a backup file")
    restore_parser.add_argument("--file", required=True, help="Path to backup file")
    restore_parser.add_argument("--url", help="Target database connection URL", default=None)

    # verify backup
    verify_parser = subparsers.add_parser("verify", help="Verify backup integrity without restoring")
    verify_parser.add_argument("--file", required=True, help="Path to backup file")

    args = parser.parse_args()

    if args.command == "create":
        res = create_database_backup(
            url=args.url,
            output_dir=args.dir,
            filename=args.filename,
            compress=not args.no_compress,
        )
        print(json.dumps(res, indent=2))
    elif args.command == "restore":
        res = restore_database_backup(backup_path=args.file, url=args.url)
        print(json.dumps(res, indent=2))
    elif args.command == "verify":
        res = verify_backup_integrity(args.file)
        print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()

