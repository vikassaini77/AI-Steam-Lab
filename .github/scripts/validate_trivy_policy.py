#!/usr/bin/env python3
"""
NeuroLab AI: Trivy Security Policy and Suppression Validator.
Problem 37: Enforce deliberate severity thresholds, non-zero exit codes,
and a formal process for approved exceptions and expiring suppressions.

Usage:
    python .github/scripts/validate_trivy_policy.py [--ignorefile .trivyignore] [--reference-date YYYY-MM-DD]
"""
import re
import sys
import json
import argparse
from datetime import datetime, timezone, date
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple


CVE_PATTERN = re.compile(r"^(CVE-\d{4}-\d{4,7}|GHSA-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}|PYSEC-\d{4}-\d+|RHSA-\d{4}:\d+|ALAS\d*-\d{4}-\d+)$", re.IGNORECASE)
EXP_PATTERN = re.compile(r"^#\s*exp:\s*(\d{4}-\d{2}-\d{2})", re.IGNORECASE)
FIELD_PATTERN = re.compile(r"^#\s*([a-zA-Z_-]+)\s*:\s*(.+)$")


class SuppressionEntry:
    def __init__(
        self,
        vuln_id: str,
        reason: Optional[str] = None,
        approver: Optional[str] = None,
        expiry: Optional[date] = None,
        compensating_control: Optional[str] = None,
        description: Optional[str] = None,
    ):
        self.vuln_id = vuln_id.strip()
        self.reason = reason.strip() if reason else None
        self.approver = approver.strip() if approver else None
        self.expiry = expiry
        self.compensating_control = compensating_control.strip() if compensating_control else None
        self.description = description.strip() if description else None

    def is_expired(self, current_date: Optional[date] = None) -> bool:
        if self.expiry is None:
            return True  # Missing expiry is considered invalid/expired
        now = current_date or datetime.now(timezone.utc).date()
        return self.expiry < now

    def to_dict(self) -> Dict[str, Any]:
        return {
            "vuln_id": self.vuln_id,
            "reason": self.reason,
            "approver": self.approver,
            "expiry": self.expiry.isoformat() if self.expiry else None,
            "compensating_control": self.compensating_control,
            "description": self.description,
        }


def parse_trivyignore(file_path: Path) -> List[SuppressionEntry]:
    """
    Parses .trivyignore and extracts structured suppression metadata.
    Associates preceding comment metadata lines (# Reason, # Approved-By, # Expiry, # exp)
    with the corresponding vulnerability ID.
    """
    if not file_path.exists():
        return []

    lines = file_path.read_text(encoding="utf-8").splitlines()
    entries: List[SuppressionEntry] = []
    
    current_comments: Dict[str, str] = {}
    
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            current_comments.clear()
            continue

        if line.startswith("#"):
            # Check for native exp:YYYY-MM-DD
            exp_match = EXP_PATTERN.match(line)
            if exp_match:
                current_comments["exp"] = exp_match.group(1)
                continue

            field_match = FIELD_PATTERN.match(line)
            if field_match:
                key = field_match.group(1).lower().replace("-", "_")
                val = field_match.group(2).strip()
                current_comments[key] = val
            continue

        # Non-comment line -> Vulnerability ID
        vuln_id = line.split("#")[0].strip()
        if not vuln_id:
            continue

        expiry_date = None
        exp_str = current_comments.get("expiry") or current_comments.get("exp")
        if exp_str:
            try:
                expiry_date = datetime.strptime(exp_str, "%Y-%m-%d").date()
            except ValueError:
                expiry_date = None

        entry = SuppressionEntry(
            vuln_id=vuln_id,
            reason=current_comments.get("reason"),
            approver=current_comments.get("approved_by") or current_comments.get("approver"),
            expiry=expiry_date,
            compensating_control=current_comments.get("compensating_control"),
            description=current_comments.get("description"),
        )
        entries.append(entry)
        current_comments.clear()

    return entries


def validate_suppressions(
    entries: List[SuppressionEntry],
    reference_date: Optional[date] = None,
) -> Tuple[bool, List[str]]:
    """
    Validates that each suppression entry complies with security policy:
    1. Valid vulnerability ID pattern.
    2. Documented business reason / justification.
    3. Designated approver.
    4. Valid, non-expired future expiration date.
    """
    errors: List[str] = []
    now = reference_date or datetime.now(timezone.utc).date()

    for entry in entries:
        if not CVE_PATTERN.match(entry.vuln_id):
            errors.append(f"Invalid vulnerability identifier format: '{entry.vuln_id}'")

        if not entry.reason:
            errors.append(f"Suppression for '{entry.vuln_id}' lacks mandatory '# Reason:' justification.")

        if not entry.approver:
            errors.append(f"Suppression for '{entry.vuln_id}' lacks mandatory '# Approved-By:' metadata.")

        if entry.expiry is None:
            errors.append(f"Suppression for '{entry.vuln_id}' lacks a valid ISO-8601 '# Expiry: YYYY-MM-DD' date.")
        elif entry.expiry < now:
            errors.append(
                f"Suppression for '{entry.vuln_id}' EXPIRED on {entry.expiry} (current date: {now})."
            )

    return len(errors) == 0, errors


class PolicyResult:
    def __init__(
        self,
        passed: bool,
        exit_code: int,
        blocking_vulnerabilities: List[Dict[str, Any]],
        suppressed_vulnerabilities: List[Dict[str, Any]],
        expired_suppressions: List[SuppressionEntry],
        summary: str,
    ):
        self.passed = passed
        self.exit_code = exit_code
        self.blocking_vulnerabilities = blocking_vulnerabilities
        self.suppressed_vulnerabilities = suppressed_vulnerabilities
        self.expired_suppressions = expired_suppressions
        self.summary = summary


def evaluate_vulnerability_scan(
    findings: List[Dict[str, Any]],
    ignore_entries: List[SuppressionEntry],
    blocking_severities: Optional[List[str]] = None,
    reference_date: Optional[date] = None,
) -> PolicyResult:
    """
    Evaluates scan findings against the security policy and active suppressions.
    - Default blocking severities: ['CRITICAL', 'HIGH']
    - Unsuppressed findings at or above threshold cause failure (exit_code=1).
    - Expired suppressions in ignorefile cause failure (exit_code=1).
    - Findings below threshold or covered by valid, unexpired suppressions pass.
    """
    if blocking_severities is None:
        blocking_severities = ["CRITICAL", "HIGH"]
    blocking_severities_upper = {s.upper() for s in blocking_severities}

    now = reference_date or datetime.now(timezone.utc).date()

    # Index active and expired suppressions
    valid_suppressions: Dict[str, SuppressionEntry] = {}
    expired_suppressions: List[SuppressionEntry] = []

    for entry in ignore_entries:
        if entry.is_expired(now):
            expired_suppressions.append(entry)
        else:
            valid_suppressions[entry.vuln_id.upper()] = entry

    blocking_findings: List[Dict[str, Any]] = []
    suppressed_findings: List[Dict[str, Any]] = []

    for item in findings:
        vuln_id = item.get("VulnerabilityID") or item.get("id") or item.get("ruleId") or ""
        vuln_id_upper = vuln_id.upper()
        severity = (item.get("Severity") or item.get("level") or "UNKNOWN").upper()

        if severity in blocking_severities_upper:
            if vuln_id_upper in valid_suppressions:
                suppressed_findings.append({
                    **item,
                    "suppression": valid_suppressions[vuln_id_upper].to_dict(),
                })
            else:
                blocking_findings.append(item)

    has_errors = bool(blocking_findings) or bool(expired_suppressions)
    exit_code = 1 if has_errors else 0

    reasons = []
    if blocking_findings:
        reasons.append(f"{len(blocking_findings)} unsuppressed {','.join(blocking_severities)} vulnerabilities found.")
    if expired_suppressions:
        reasons.append(f"{len(expired_suppressions)} suppression exceptions have expired.")

    summary = "; ".join(reasons) if reasons else "All vulnerability policies satisfied."

    return PolicyResult(
        passed=not has_errors,
        exit_code=exit_code,
        blocking_vulnerabilities=blocking_findings,
        suppressed_vulnerabilities=suppressed_findings,
        expired_suppressions=expired_suppressions,
        summary=summary,
    )


def main():
    parser = argparse.ArgumentParser(description="Validate Trivy suppression policy and scan results.")
    parser.add_argument("--ignorefile", default=".trivyignore", help="Path to .trivyignore file")
    parser.add_argument("--reference-date", help="Reference date YYYY-MM-DD for testing (defaults to today UTC)")
    args = parser.parse_args()

    ref_date = None
    if args.reference_date:
        ref_date = datetime.strptime(args.reference_date, "%Y-%m-%d").date()

    ignore_path = Path(args.ignorefile)
    entries = parse_trivyignore(ignore_path)
    valid, errors = validate_suppressions(entries, reference_date=ref_date)

    if not valid:
        print(f"[SECURITY POLICY ERROR] .trivyignore validation failed with {len(errors)} error(s):", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(1)

    print(f"[SECURITY POLICY OK] Validated {len(entries)} suppression entry/entries in '{ignore_path}'. All policies satisfied.")
    sys.exit(0)


if __name__ == "__main__":
    main()

