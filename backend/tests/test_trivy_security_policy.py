"""
Unit and Integration Tests for Problem 37:
Trivy Vulnerabilities CI Blocking, Supply Chain Hardening, and Suppression Governance.

Verifies:
1. Deliberate severity threshold: CRITICAL and HIGH severities trigger build failure.
2. Nonzero exit code: The Trivy scanning step is configured with exit-code: '1'.
3. GitHub Actions pinning: All third-party actions are pinned to immutable commit SHAs (no mutable @master/@main).
4. Machine-readable scan retention: SARIF reports are generated and retained via upload-artifact and upload-sarif.
5. Suppression lifecycle: .trivyignore schema enforces CVE ID, justification, approver, and expiration date.
6. Deliberately vulnerable image test: Policy engine blocks on unsuppressed/expired vulnerabilities (exit code 1)
   and passes on clean, sub-threshold, or approved unexpired suppressions (exit code 0).
"""
import re
import sys
import yaml
from pathlib import Path
from datetime import date, timedelta
import pytest

# Import policy validator functions from .github/scripts/validate_trivy_policy.py
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / ".github" / "scripts"))

from validate_trivy_policy import (
    SuppressionEntry,
    parse_trivyignore,
    validate_suppressions,
    evaluate_vulnerability_scan,
)


def get_ci_workflow() -> dict:
    ci_path = REPO_ROOT / ".github" / "workflows" / "ci.yml"
    assert ci_path.exists(), f"CI workflow not found at {ci_path}"
    content = ci_path.read_text(encoding="utf-8")
    return yaml.safe_load(content)


def get_ci_workflow_raw() -> str:
    ci_path = REPO_ROOT / ".github" / "workflows" / "ci.yml"
    return ci_path.read_text(encoding="utf-8")


class TestTrivyCIWorkflowConfiguration:
    """Verifies that the GitHub Actions CI workflow configures blocking and pinning policies."""

    def test_workflow_file_exists(self):
        ci_path = REPO_ROOT / ".github" / "workflows" / "ci.yml"
        assert ci_path.exists()

    def test_trivy_scan_step_blocks_with_nonzero_exit_code(self):
        """The blocking Trivy scan step must have exit-code: '1'."""
        wf = get_ci_workflow()
        scan_job = wf.get("jobs", {}).get("docker-security-scan", {})
        steps = scan_job.get("steps", [])
        
        blocking_steps = [
            step for step in steps
            if "trivy-action" in str(step.get("uses", ""))
            and str(step.get("with", {}).get("exit-code", "")) == "1"
        ]
        assert len(blocking_steps) >= 1, (
            "docker-security-scan must contain a Trivy scanning step with exit-code: '1' to block releases"
        )
        blocking_step = blocking_steps[0]
        assert blocking_step["with"]["exit-code"] == "1"

    def test_zero_exit_code_is_not_used_on_blocking_step(self):
        """The blocking table scan must not use exit-code: '0'."""
        raw_wf = get_ci_workflow_raw()
        # Find the block scan step
        assert "exit-code: '1'" in raw_wf
        # Check that there is no table format scan with exit-code '0'
        wf = get_ci_workflow()
        scan_job = wf.get("jobs", {}).get("docker-security-scan", {})
        for step in scan_job.get("steps", []):
            if "trivy-action" in str(step.get("uses", "")) and step.get("with", {}).get("format") == "table":
                assert str(step.get("with", {}).get("exit-code")) == "1"

    def test_deliberate_severity_threshold(self):
        """Trivy scan steps must configure deliberate severity thresholds (CRITICAL,HIGH)."""
        wf = get_ci_workflow()
        scan_job = wf.get("jobs", {}).get("docker-security-scan", {})
        trivy_steps = [
            step for step in scan_job.get("steps", [])
            if "trivy-action" in str(step.get("uses", ""))
        ]
        assert len(trivy_steps) >= 1
        for step in trivy_steps:
            severity = step.get("with", {}).get("severity", "")
            assert "CRITICAL" in severity
            assert "HIGH" in severity

    def test_all_github_actions_are_pinned(self):
        """Third-party GitHub Actions must be pinned to full immutable 40-character commit SHAs."""
        raw_wf = get_ci_workflow_raw()
        uses_matches = re.findall(r"uses:\s*([^\s\n#]+)", raw_wf)
        
        assert len(uses_matches) > 0
        sha_pattern = re.compile(r"^[a-zA-Z0-9_\-\.\/]+@[a-f0-9]{40}$")

        for action_ref in uses_matches:
            # Must not use mutable tags like @master, @main, @latest
            assert not action_ref.endswith("@master"), f"Action {action_ref} must not use mutable @master"
            assert not action_ref.endswith("@main"), f"Action {action_ref} must not use mutable @main"
            assert not action_ref.endswith("@latest"), f"Action {action_ref} must not use mutable @latest"
            
            # Verify pinned commit SHA
            assert sha_pattern.match(action_ref), (
                f"Action {action_ref} is not pinned to a 40-character commit SHA"
            )

    def test_machine_readable_results_generated_and_retained(self):
        """Workflow must generate SARIF scan results and retain them as artifacts."""
        wf = get_ci_workflow()
        scan_job = wf.get("jobs", {}).get("docker-security-scan", {})
        steps = scan_job.get("steps", [])

        # 1. SARIF generator step
        sarif_steps = [
            s for s in steps
            if "trivy-action" in str(s.get("uses", "")) and s.get("with", {}).get("format") == "sarif"
        ]
        assert len(sarif_steps) >= 1, "Must have a Trivy step generating SARIF report"
        assert sarif_steps[0]["with"]["output"] == "trivy-results.sarif"

        # 2. Artifact upload step
        artifact_steps = [
            s for s in steps
            if "upload-artifact" in str(s.get("uses", ""))
        ]
        assert len(artifact_steps) >= 1, "Must have an upload-artifact step to retain scan results"
        assert artifact_steps[0].get("if") == "always()"
        assert artifact_steps[0]["with"]["path"] == "trivy-results.sarif"

        # 3. Code scanning upload step
        codeql_steps = [
            s for s in steps
            if "upload-sarif" in str(s.get("uses", ""))
        ]
        assert len(codeql_steps) >= 1, "Must upload SARIF to GitHub Security code scanning tab"
        assert codeql_steps[0].get("if") == "always()"

    def test_docker_compose_backend_image_tag_matches_ci(self):
        """Backend image in docker-compose matches Trivy image-ref."""
        compose_path = REPO_ROOT / "docker-compose.yml"
        compose_data = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
        backend_image = compose_data.get("services", {}).get("backend", {}).get("image")
        assert backend_image == "ai-stem-lab-assistant-backend:latest"


class TestSuppressionPolicyValidation:
    """Verifies parsing, metadata enforcement, and expiration handling for .trivyignore."""

    def test_real_trivyignore_is_valid(self):
        """The repository .trivyignore file must be valid under policy rules."""
        ignore_path = REPO_ROOT / ".trivyignore"
        assert ignore_path.exists()
        entries = parse_trivyignore(ignore_path)
        valid, errors = validate_suppressions(entries)
        assert valid, f"Validation errors in .trivyignore: {errors}"

    def test_suppression_with_valid_metadata_and_future_expiry_passes(self):
        """An entry with justification, approver, and future expiry passes."""
        future_date = date.today() + timedelta(days=30)
        entry = SuppressionEntry(
            vuln_id="CVE-2024-12345",
            reason="Component isolated in internal non-routable worker network",
            approver="security@neurolab.ai",
            expiry=future_date,
            compensating_control="Strict egress firewall",
        )
        valid, errors = validate_suppressions([entry])
        assert valid
        assert len(errors) == 0

    def test_suppression_without_reason_is_rejected(self):
        """An entry lacking reason/justification fails validation."""
        entry = SuppressionEntry(
            vuln_id="CVE-2024-12345",
            reason="",
            approver="security@neurolab.ai",
            expiry=date.today() + timedelta(days=10),
        )
        valid, errors = validate_suppressions([entry])
        assert not valid
        assert any("lacks mandatory '# Reason:'" in e for e in errors)

    def test_suppression_without_approver_is_rejected(self):
        """An entry lacking an approver fails validation."""
        entry = SuppressionEntry(
            vuln_id="CVE-2024-12345",
            reason="Some reason",
            approver="",
            expiry=date.today() + timedelta(days=10),
        )
        valid, errors = validate_suppressions([entry])
        assert not valid
        assert any("lacks mandatory '# Approved-By:'" in e for e in errors)

    def test_suppression_with_expired_date_is_rejected(self):
        """An entry with a past expiration date fails validation."""
        past_date = date.today() - timedelta(days=5)
        entry = SuppressionEntry(
            vuln_id="CVE-2024-12345",
            reason="Legacy temporary exception",
            approver="security@neurolab.ai",
            expiry=past_date,
        )
        valid, errors = validate_suppressions([entry])
        assert not valid
        assert any("EXPIRED" in e for e in errors)


class TestDeliberatelyVulnerableScanBehavior:
    """
    Tests the vulnerability policy evaluation against mock scan outputs
    representing clean, vulnerable, suppressed, and expired scenarios.
    """

    def test_clean_image_passes_with_zero_exit_code(self):
        """A clean image with no vulnerabilities passes (exit code 0)."""
        findings = []
        result = evaluate_vulnerability_scan(findings, ignore_entries=[])
        assert result.passed is True
        assert result.exit_code == 0
        assert len(result.blocking_vulnerabilities) == 0

    def test_deliberately_vulnerable_critical_image_blocks_release(self):
        """An image containing an unsuppressed CRITICAL vulnerability blocks release (exit code 1)."""
        findings = [
            {
                "VulnerabilityID": "CVE-2024-99999",
                "PkgName": "openssl",
                "InstalledVersion": "1.1.1u",
                "FixedVersion": "1.1.1w",
                "Severity": "CRITICAL",
                "Title": "Remote Code Execution in OpenSSL",
            }
        ]
        result = evaluate_vulnerability_scan(findings, ignore_entries=[])
        assert result.passed is False
        assert result.exit_code == 1
        assert len(result.blocking_vulnerabilities) == 1
        assert result.blocking_vulnerabilities[0]["VulnerabilityID"] == "CVE-2024-99999"

    def test_deliberately_vulnerable_high_image_blocks_release(self):
        """An image containing an unsuppressed HIGH vulnerability blocks release (exit code 1)."""
        findings = [
            {
                "VulnerabilityID": "CVE-2024-88888",
                "PkgName": "curl",
                "InstalledVersion": "7.88.1",
                "FixedVersion": "8.0.0",
                "Severity": "HIGH",
                "Title": "Buffer Overflow in Curl",
            }
        ]
        result = evaluate_vulnerability_scan(findings, ignore_entries=[])
        assert result.passed is False
        assert result.exit_code == 1
        assert len(result.blocking_vulnerabilities) == 1

    def test_low_and_medium_vulnerabilities_do_not_block(self):
        """Vulnerabilities below the deliberate threshold (MEDIUM, LOW) do not block CI."""
        findings = [
            {
                "VulnerabilityID": "CVE-2024-11111",
                "Severity": "MEDIUM",
                "PkgName": "zlib",
            },
            {
                "VulnerabilityID": "CVE-2024-22222",
                "Severity": "LOW",
                "PkgName": "tar",
            },
        ]
        result = evaluate_vulnerability_scan(findings, ignore_entries=[])
        assert result.passed is True
        assert result.exit_code == 0
        assert len(result.blocking_vulnerabilities) == 0

    def test_approved_unexpired_suppressed_vulnerability_passes(self):
        """A CRITICAL vulnerability with an approved and unexpired suppression passes."""
        future_date = date.today() + timedelta(days=45)
        suppression = SuppressionEntry(
            vuln_id="CVE-2024-99999",
            reason="Temporary vendor patch pending, isolated internal service",
            approver="ciso@neurolab.ai",
            expiry=future_date,
        )
        findings = [
            {
                "VulnerabilityID": "CVE-2024-99999",
                "Severity": "CRITICAL",
                "PkgName": "openssl",
            }
        ]
        result = evaluate_vulnerability_scan(findings, ignore_entries=[suppression])
        assert result.passed is True
        assert result.exit_code == 0
        assert len(result.blocking_vulnerabilities) == 0
        assert len(result.suppressed_vulnerabilities) == 1

    def test_expired_suppression_blocks_release(self):
        """When an approved suppression expires, the vulnerability blocks release (exit code 1)."""
        past_date = date.today() - timedelta(days=2)
        expired_suppression = SuppressionEntry(
            vuln_id="CVE-2024-99999",
            reason="Temporary vendor patch pending",
            approver="ciso@neurolab.ai",
            expiry=past_date,
        )
        findings = [
            {
                "VulnerabilityID": "CVE-2024-99999",
                "Severity": "CRITICAL",
                "PkgName": "openssl",
            }
        ]
        result = evaluate_vulnerability_scan(findings, ignore_entries=[expired_suppression])
        assert result.passed is False
        assert result.exit_code == 1
        assert len(result.expired_suppressions) == 1
        assert len(result.blocking_vulnerabilities) == 1

    def test_mixed_findings_with_unsuppressed_blocking(self):
        """A mix of suppressed and unsuppressed vulnerabilities blocks release."""
        future_date = date.today() + timedelta(days=30)
        suppression = SuppressionEntry(
            vuln_id="CVE-2024-11111",
            reason="Approved exception",
            approver="sec@neurolab.ai",
            expiry=future_date,
        )
        findings = [
            {"VulnerabilityID": "CVE-2024-11111", "Severity": "CRITICAL"},  # Suppressed
            {"VulnerabilityID": "CVE-2024-22222", "Severity": "HIGH"},      # Unsuppressed
        ]
        result = evaluate_vulnerability_scan(findings, ignore_entries=[suppression])
        assert result.passed is False
        assert result.exit_code == 1
        assert len(result.suppressed_vulnerabilities) == 1
        assert len(result.blocking_vulnerabilities) == 1
        assert result.blocking_vulnerabilities[0]["VulnerabilityID"] == "CVE-2024-22222"

