"""
NeuroLab AI: Mandatory Test Suite Verification & Quality Gate
Problem 38: Ensure backend tests are mandatory, fail CI when required tests are missing,
and verify that unit, integration, and API authorization suites are present.
"""
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Tuple


REQUIRED_CATEGORIES: Dict[str, List[str]] = {
    "unit": [
        "test_physics_engine_numerical_validation.py",
        "test_physics_engine.py",
        "test_health_and_readiness_probes.py",
        "test_metrics_and_headers_security.py",
    ],
    "integration": [
        "test_docker_and_nginx_config.py",
        "test_service_dependencies_and_fallbacks.py",
        "test_postgresql_persistence_and_initialization.py",
        "test_nginx_streaming_and_payload_policies.py",
        "test_lifespan_and_dependency_injection.py",
    ],
    "api_authorization": [
        "test_auth_security.py",
        "test_user_isolation.py",
        "test_secret_management_security.py",
        "test_api_request_response_contracts.py",
        "test_leaderboard_authenticity.py",
    ],
}

MIN_TEST_FILES = 20


def verify_test_suite_presence(tests_dir: Path) -> Tuple[bool, List[str]]:
    """
    Validates that the tests directory exists and that all required
    test categories and files are present.
    """
    errors: List[str] = []

    if not tests_dir.exists():
        errors.append(f"CRITICAL: Mandatory tests directory '{tests_dir}' does not exist!")
        return False, errors

    if not tests_dir.is_dir():
        errors.append(f"CRITICAL: '{tests_dir}' is not a directory!")
        return False, errors

    test_files = {p.name for p in tests_dir.glob("test_*.py")}
    if len(test_files) < MIN_TEST_FILES:
        errors.append(
            f"Insufficient test suites: Found {len(test_files)} test files in '{tests_dir}', "
            f"minimum required is {MIN_TEST_FILES}."
        )

    for category, required_files in REQUIRED_CATEGORIES.items():
        missing = [f for f in required_files if f not in test_files]
        if missing:
            errors.append(
                f"Missing required {category} test files: {missing}"
            )

    return len(errors) == 0, errors


def main():
    parser = argparse.ArgumentParser(description="Verify backend mandatory test suite presence.")
    parser.add_argument(
        "--tests-dir",
        default="tests",
        help="Path to tests directory (default: 'tests')",
    )
    parser.add_argument(
        "--verify-all",
        action="store_true",
        help="Enforce all mandatory test categories (unit, integration, authorization)",
    )
    args = parser.parse_args()

    tests_path = Path(args.tests_dir).resolve()
    valid, errors = verify_test_suite_presence(tests_path)

    if not valid:
        print("[TEST SUITE VERIFICATION FAILED] Backend tests are mandatory and cannot be skipped:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(1)

    print(f"[TEST SUITE OK] Verified mandatory test suites in '{tests_path}'. All categories present.")
    sys.exit(0)


if __name__ == "__main__":
    main()

