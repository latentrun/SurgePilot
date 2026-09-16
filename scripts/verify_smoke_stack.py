from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.request


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMPOSE = [
    "docker",
    "compose",
    "-f",
    "infra/docker/docker-compose.base.yml",
    "-f",
    "infra/docker/docker-compose.smoke.yml",
    "--profile",
    "smoke",
]
PROJECT_NAME = os.environ.get("COMPOSE_PROJECT_NAME", "surgepilot-smoke-test")
HEALTHZ_URL = os.environ.get("SURGEPILOT_SMOKE_HEALTHZ_URL", "http://localhost:8000/api/healthz")
WORKER_LOG_FAILURE_MARKERS = (
    "api-worker cycle failed",
    "Traceback (most recent call last)",
    "IndexError",
)
TEST_RUNNER_INTERNAL_TOKEN = os.environ.get("RUNNER_INTERNAL_TOKEN", "surgepilot-e2e-runner-token")
TEST_MINIO_ACCESS_KEY = "minioadmin"
TEST_MINIO_SECRET_KEY = "surgepilot-verification-minio-secret"
TEST_MINIO_BUCKET = "surgepilot"


def run(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "COMPOSE_PROJECT_NAME": PROJECT_NAME,
        "RUNNER_INTERNAL_TOKEN": TEST_RUNNER_INTERNAL_TOKEN,
        "MINIO_ACCESS_KEY": TEST_MINIO_ACCESS_KEY,
        "MINIO_SECRET_KEY": TEST_MINIO_SECRET_KEY,
        "MINIO_ROOT_USER": TEST_MINIO_ACCESS_KEY,
        "MINIO_ROOT_PASSWORD": TEST_MINIO_SECRET_KEY,
        "MINIO_BUCKET": TEST_MINIO_BUCKET,
    }
    return subprocess.run(
        [*COMPOSE, *args],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=check,
    )


def wait_for_healthz(timeout_seconds: int = 90) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(HEALTHZ_URL, timeout=3) as response:
                body = response.read().decode("utf-8")
            if response.status == 200 and '"status":"ok"' in body.replace(" ", ""):
                return
        except Exception as exc:  # noqa: BLE001 - keep the smoke poll robust.
            last_error = exc
        time.sleep(2)
    raise RuntimeError(f"{HEALTHZ_URL} did not become healthy: {last_error}")


def assert_worker_is_clean() -> None:
    # The worker poll interval defaults to 2 seconds. Waiting a little longer ensures
    # this smoke check observes at least one post-start cycle.
    time.sleep(6)
    logs = run(["logs", "--no-color", "--tail=200", "api-worker"]).stdout
    failures = [marker for marker in WORKER_LOG_FAILURE_MARKERS if marker in logs]
    if failures:
        raise RuntimeError(
            f"api-worker reported a smoke startup failure ({', '.join(failures)}):\n{logs}"
        )


def main() -> int:
    keep_stack = os.environ.get("SURGEPILOT_SMOKE_KEEP_STACK") == "1"
    try:
        # Do not use docker compose --wait here: the smoke profile includes
        # one-shot migration/init services that exit successfully before api starts.
        # The explicit health and worker-log checks below are the readiness gates.
        run(["up", "-d", "--build"])
        wait_for_healthz()
        assert_worker_is_clean()
        print("Smoke compose stack started cleanly.")
        return 0
    except Exception as exc:  # noqa: BLE001 - print compose diagnostics before exit.
        print(f"Smoke compose verification failed: {exc}", file=sys.stderr)
        try:
            print(run(["ps"], check=False).stdout, file=sys.stderr)
            print(run(["logs", "--no-color", "--tail=120"], check=False).stdout, file=sys.stderr)
        except Exception as diagnostics_exc:  # noqa: BLE001
            print(f"Could not collect smoke diagnostics: {diagnostics_exc}", file=sys.stderr)
        return 1
    finally:
        if not keep_stack:
            run(["down", "-v"], check=False)


if __name__ == "__main__":
    raise SystemExit(main())
