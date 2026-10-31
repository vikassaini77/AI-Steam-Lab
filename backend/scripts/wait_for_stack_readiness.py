#!/usr/bin/env python3
"""
NeuroLab AI: Compose Stack Readiness Checker
Problem 41: Polls and verifies end-to-end stack readiness through the proxy
before executing integration and end-to-end deployment tests.
"""
import sys
import time
import argparse
import urllib.request
import urllib.error
import json


def wait_for_readiness(url: str, timeout_seconds: int = 60, interval: float = 2.0) -> bool:
    start_time = time.time()
    deadline = start_time + timeout_seconds
    attempt = 0

    print(f"[POLLING] Waiting for stack readiness at {url} (timeout: {timeout_seconds}s)...")

    while time.time() < deadline:
        attempt += 1
        elapsed = round(time.time() - start_time, 1)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "NeuroLab-Readiness-Probe/1.0"})
            with urllib.request.urlopen(req, timeout=3.0) as response:
                status_code = response.getcode()
                body = response.read().decode("utf-8")
                
                if status_code == 200:
                    try:
                        data = json.loads(body)
                        status = data.get("status", "unknown")
                        if status in ("ready", "healthy"):
                            print(f"[SUCCESS] Stack became ready in {elapsed}s (attempt {attempt}): status='{status}'")
                            return True
                        else:
                            print(f"[WAITING] [{elapsed}s] HTTP 200 returned but status='{status}' (waiting for full readiness...)")
                    except json.JSONDecodeError:
                        print(f"[WAITING] [{elapsed}s] HTTP 200 received but non-JSON payload.")
                else:
                    print(f"[WAITING] [{elapsed}s] HTTP {status_code}")
        except urllib.error.HTTPError as e:
            print(f"[WAITING] [{elapsed}s] HTTP {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            print(f"[WAITING] [{elapsed}s] Connection failed: {e.reason}")
        except Exception as e:
            print(f"[WAITING] [{elapsed}s] Unexpected probe error: {e}")

        time.sleep(interval)

    print(f"[FAILED] Stack did not become ready within {timeout_seconds}s.", file=sys.stderr)
    return False


def main():
    parser = argparse.ArgumentParser(description="Wait for NeuroLab Compose stack readiness.")
    parser.add_argument("--url", default="http://localhost:8080/ready", help="Readiness endpoint URL")
    parser.add_argument("--timeout", type=int, default=60, help="Max wait time in seconds")
    parser.add_argument("--interval", type=float, default=2.0, help="Polling interval in seconds")
    args = parser.parse_args()

    ready = wait_for_readiness(args.url, timeout_seconds=args.timeout, interval=args.interval)
    sys.exit(0 if ready else 1)


if __name__ == "__main__":
    main()

