from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.request

os.environ.setdefault("SURGEPILOT_P0_06_SSH_E2E_PROJECT", "surgepilot-p1-00-monitoring-write")
os.environ.setdefault("SURGEPILOT_P0_06_RUNNER_HOME", "/opt/surgepilot/runner")
os.environ.setdefault("SURGEPILOT_P0_06_API_BASE_URL", "http://localhost:8000")
os.environ.setdefault(
    "SURGEPILOT_P0_06_DATABASE_URL",
    "postgresql://surgepilot:surgepilot@localhost:5432/surgepilot",
)
os.environ.setdefault("SURGEPILOT_P0_06_MINIO_ENDPOINT", "localhost:9000")
os.environ.setdefault("SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT", "18086")
import verify_p0_06_ssh_taurus_smoke as base  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
STACK_SERVICES = [
    "postgres",
    "minio",
    "minio-init",
    "influxdb",
    "grafana",
    "api-migrate",
    "api",
    "api-worker",
    base.SSH_SERVICE,
]
APP_BUILD_SERVICES = ["api-migrate", "api", "api-worker"]
INFLUXDB_ORG = os.environ.get("SURGEPILOT_MONITORING_INFLUXDB_ORG", "surgepilot")
INFLUXDB_BUCKET = os.environ.get("SURGEPILOT_MONITORING_INFLUXDB_BUCKET", "jmeter")
REQUIRED_MEASUREMENTS = {"requestsRaw", "virtualUsers", "testStartEnd"}
SKIP_EXIT_CODE = 77


def compose_cmd(*args: str) -> list[str]:
    command = [
        "docker",
        "compose",
        "-f",
        "infra/docker/docker-compose.yml",
        "-f",
        "infra/docker/docker-compose.ssh-e2e.yml",
    ]
    command.extend(["--profile", "ssh-e2e"])
    command.extend(args)
    return command


base.compose_cmd = compose_cmd


def run_command(args: list[str], *, check: bool = True) -> base.subprocess.CompletedProcess[str]:
    return base.run_command(args, check=check)


def node_write_url() -> str | None:
    return os.environ.get("SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL") or None


def node_api_url() -> str | None:
    return os.environ.get("SURGEPILOT_NODE_API_BASE_URL") or None


def environment_skip_reason() -> str | None:
    if os.environ.get("SURGEPILOT_P1_MONITORING_REMOTE_WRITE") != "1":
        return "SURGEPILOT_P1_MONITORING_REMOTE_WRITE=1 is not set"
    if not node_api_url():
        return (
            "SURGEPILOT_NODE_API_BASE_URL is not set; this smoke needs the final node-facing "
            "SurgePilot API origin and cannot be used as release/nightly green evidence"
        )
    if not node_write_url():
        return (
            "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL is not set; this smoke needs a real "
            "node-facing InfluxDB URL and cannot be used as release/nightly green evidence"
        )
    return None


def setup_stack(*, build_app: bool, build_ssh: bool) -> None:
    run_command(compose_cmd("down", "-v"), check=False)
    if build_ssh:
        run_command(compose_cmd("build", base.SSH_SERVICE))
    base.seed_runtime_artifact()
    if build_app:
        run_command(compose_cmd("build", *APP_BUILD_SERVICES))
    run_command(compose_cmd("up", "-d", "--no-build", *STACK_SERVICES))
    base.wait_for_api_health()
    base.verify_api_worker_can_reach_node_ssh()
    base.verify_node_api_reachable()
    base.verify_target_reachable()
    base.verify_influxdb_node_write_reachable()


def diagnostics() -> None:
    print("\n--- compose ps ---", file=sys.stderr)
    print(run_command(compose_cmd("ps"), check=False).stdout, file=sys.stderr)
    print("\n--- compose logs tail ---", file=sys.stderr)
    print(
        run_command(compose_cmd("logs", "--no-color", "--tail=200"), check=False).stdout,
        file=sys.stderr,
    )


def influxdb_token() -> str:
    configured = os.environ.get("SURGEPILOT_MONITORING_INFLUXDB_TOKEN")
    if configured:
        return configured
    file_name = os.environ.get("SURGEPILOT_MONITORING_INFLUXDB_TOKEN_FILE_HOST")
    token_file = (
        Path(file_name) if file_name else ROOT / "infra/docker/monitoring/influxdb-token.example"
    )
    if not token_file.is_absolute():
        token_file = ROOT / "infra/docker" / token_file
    return token_file.read_text(encoding="utf-8").strip()


def influxdb_url() -> str:
    return f"http://localhost:{os.environ['SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT']}"


def query_measurements(run_id: str) -> set[str]:
    flux = f"""
from(bucket: {json.dumps(INFLUXDB_BUCKET)})
  |> range(start: -30m)
  |> filter(fn: (r) => r.runId == {json.dumps(run_id)})
  |> keep(columns: ["_measurement"])
  |> distinct(column: "_measurement")
"""
    request = urllib.request.Request(
        f"{influxdb_url()}/api/v2/query?org={INFLUXDB_ORG}",
        data=flux.encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Token {influxdb_token()}",
            "Accept": "application/csv",
            "Content-Type": "application/vnd.flux",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise base.SmokeFailure(f"InfluxDB query failed: {exc.code} {exc.read().decode()}") from exc
    measurements: set[str] = set()
    for row in csv.DictReader(line for line in body.splitlines() if not line.startswith("#")):
        for key in ("_measurement", "_value"):
            value = row.get(key)
            if value:
                measurements.add(value)
    return measurements


def wait_for_monitoring_points(run_id: str) -> None:
    def present() -> bool:
        measurements = query_measurements(run_id)
        missing = REQUIRED_MEASUREMENTS - measurements
        if missing:
            print(f"Waiting for InfluxDB measurements for {run_id}; missing {sorted(missing)}")
            return False
        return True

    base.wait_until(f"InfluxDB JMeter measurements for {run_id}", 120, present)


def run_smoke() -> None:
    if not node_write_url():
        raise base.SmokeFailure("SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL must be explicit.")
    session = base.register_user()
    _env_id, scenario_id, node_id = base.prepare_assets(session)
    plan = base.create_plan(session, scenario_id, node_id, 10, "P1-00 Monitoring write run")
    run = base.create_run_now(session, plan)
    run_id = run["id"]
    print(f"Started P1-00 Monitoring remote-node write Run: {run_id}")
    base.verify_finished_run(run_id, node_id)
    wait_for_monitoring_points(run_id)
    print(f"Verified P1-00 Monitoring InfluxDB measurements for Run: {run_id}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify P1-00 Monitoring remote-node write path.")
    parser.add_argument("--build-app", action="store_true", help="Build API images before running.")
    parser.add_argument(
        "--build-ssh", action="store_true", help="Build SSH load-node image before running."
    )
    parser.add_argument(
        "--keep-stack", action="store_true", help="Leave Docker Compose stack running."
    )
    parser.add_argument(
        "--keep-data",
        action="store_true",
        help="Stop containers but keep volumes and business data after the smoke.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    skip_reason = environment_skip_reason()
    if skip_reason is not None:
        print(
            "P1-00 Monitoring remote-node write smoke skipped: "
            f"{skip_reason}. Skipped is not release/nightly green evidence."
        )
        return SKIP_EXIT_CODE
    try:
        setup_stack(build_app=args.build_app, build_ssh=args.build_ssh)
        run_smoke()
    except Exception as exc:  # noqa: BLE001 - smoke tool prints actionable diagnostics.
        diagnostics()
        print(f"P1-00 Monitoring remote-node write smoke failed: {exc}", file=sys.stderr)
        return 1
    finally:
        if not args.keep_stack:
            down_args = ("down",) if args.keep_data else ("down", "-v")
            run_command(compose_cmd(*down_args), check=False)
    print("P1-00 Monitoring remote-node write smoke passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
