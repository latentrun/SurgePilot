from __future__ import annotations

import hashlib
import os
from pathlib import Path
import pty
import signal
import subprocess
import time

import pytest


ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "infra/release/surgepilot"


def release_description_case(
    *,
    host: str = "192.0.2.20",
    http_port: int = 8080,
    influx_port: int = 8086,
    configured: str = "auto",
    selected: str = "amd64",
    demo_enabled: str = "false",
) -> str:
    return f"""  *"release_preflight.py describe-release"*)
    cat <<'EOF'
SURGEPILOT_CONFIG_MODE=direct_lan_http
SURGEPILOT_CONFIG_HOST={host}
SURGEPILOT_HTTP_PORT={http_port}
SURGEPILOT_NODE_API_BASE_URL=http://{host}:{http_port}
SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT={influx_port}
SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL=http://{host}:{influx_port}
SURGEPILOT_RUNTIME_ARCHITECTURES={configured}
SURGEPILOT_SELECTED_RUNTIME_ARCHITECTURES={selected}
SURGEPILOT_DEMO_LOAD_NODE_ENABLED={demo_enabled}
SURGEPILOT_ENV_SHA256={"0" * 64}
EOF
    exit 0
    ;;
"""


def configuration_docker_script() -> str:
    return r"""#!/bin/sh
set -eu
printf '%s\n' "$*" >> "$DOCKER_LOG"
case "$*" in
  *"--publish ${TEST_OCCUPIED_PORT:-__none__}:80"*) exit 1 ;;
esac
case "$*" in
  "compose version") exit 0 ;;
  "compose version --short") printf '2.27.0\n'; exit 0 ;;
  "info") exit 0 ;;
  *"info --format {{.Architecture}}"*) printf '%s\n' "${TEST_DAEMON_ARCH:-amd64}"; exit 0 ;;
  *"info --format {{.MemTotal}}"*) printf '8589934592\n'; exit 0 ;;
  *"version --format {{.Server.Version}}"*) printf '26.1.0\n'; exit 0 ;;
  *"release_preflight.py describe-release"*)
    if [ "${TEST_ADVANCED_HTTPS:-false}" = true ]; then
      cat <<EOF
SURGEPILOT_CONFIG_MODE=advanced_https
SURGEPILOT_CONFIG_HOST=
SURGEPILOT_HTTP_PORT=8443
SURGEPILOT_NODE_API_BASE_URL=https://release.example.test:8443
SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT=8086
SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL=https://release.example.test:8086
SURGEPILOT_RUNTIME_ARCHITECTURES=auto
SURGEPILOT_SELECTED_RUNTIME_ARCHITECTURES=amd64
SURGEPILOT_DEMO_LOAD_NODE_ENABLED=false
SURGEPILOT_ENV_SHA256=$TEST_ENV_SHA256
EOF
      exit 0
    fi
    if [ -f "$TEST_ROOT/reconfigured" ]; then
      IFS=' ' read -r config_host http_port influx_port < "$TEST_ROOT/reconfigured"
      env_sha256=$TEST_ENV_SHA256
    else
      config_host=192.0.2.20
      http_port=8080
      influx_port=8086
      env_sha256=$TEST_ENV_SHA256
    fi
    cat <<EOF
SURGEPILOT_CONFIG_MODE=direct_lan_http
SURGEPILOT_CONFIG_HOST=$config_host
SURGEPILOT_HTTP_PORT=$http_port
SURGEPILOT_NODE_API_BASE_URL=http://$config_host:$http_port
SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT=$influx_port
SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL=http://$config_host:$influx_port
SURGEPILOT_RUNTIME_ARCHITECTURES=${TEST_RUNTIME_ARCHITECTURES:-auto}
SURGEPILOT_SELECTED_RUNTIME_ARCHITECTURES=${TEST_SELECTED_ARCHITECTURES:-amd64}
SURGEPILOT_DEMO_LOAD_NODE_ENABLED=${TEST_DEMO_ENABLED:-false}
SURGEPILOT_ENV_SHA256=$env_sha256
EOF
    exit 0
    ;;
  *"release_preflight.py normalize-bootstrap"*)
    host= http_port= influx_port=
    while [ "$#" -gt 0 ]; do
      case "$1" in
        --host) host=$2; shift 2 ;;
        --http-port) http_port=$2; shift 2 ;;
        --influx-port) influx_port=$2; shift 2 ;;
        *) shift ;;
      esac
    done
    if [ -n "${TEST_INVALID_NORMALIZED_HOST:-}" ] && [ "$host" = "$TEST_INVALID_NORMALIZED_HOST" ]; then
      printf 'Release preflight failed: LAN host is invalid\n'
      exit 2
    fi
    if [ -n "${TEST_FATAL_NORMALIZED_HOST:-}" ] && [ "$host" = "$TEST_FATAL_NORMALIZED_HOST" ]; then
      printf 'Release preflight failed: normalization helper unavailable\n'
      exit "${TEST_FATAL_NORMALIZE_STATUS:-1}"
    fi
    cat <<EOF
SURGEPILOT_HTTP_PORT=$http_port
SURGEPILOT_NODE_API_BASE_URL=http://$host:$http_port
SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT=$influx_port
SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL=http://$host:$influx_port
SURGEPILOT_DEMO_LOAD_NODE_ENABLED=false
SURGEPILOT_RUNTIME_ARCHITECTURES=amd64,arm64
SESSION_COOKIE_SECURE=false
EOF
    exit 0
    ;;
  *"bootstrap_deployment_env.py"*)
    host= http_port= api_url= influx_port= influx_url= mode=ensure
    while [ "$#" -gt 0 ]; do
      case "$1" in
        --reconfigure-release-network) mode=reconfigure; shift ;;
        --release-http-port) http_port=$2; [ "$mode" = ensure ] && mode=bootstrap; shift 2 ;;
        --release-node-api-base-url) api_url=$2; host=$(printf '%s' "$2" | sed 's#http://##;s#:[0-9][0-9]*$##'); shift 2 ;;
        --release-influxdb-host-port) influx_port=$2; shift 2 ;;
        --release-influxdb-node-write-url) influx_url=$2; shift 2 ;;
        *) shift ;;
      esac
    done
    if [ "$mode" = ensure ]; then
      if [ -n "${TEST_BOOTSTRAP_FAILURE:-}" ]; then
        printf 'Deployment bootstrap failed: %s\n' "$TEST_BOOTSTRAP_FAILURE" >&2
        exit 2
      fi
      exit 0
    fi
    if [ "$mode" = reconfigure ]; then
      if [ "${TEST_RECONFIGURE_PRE_REPLACE_FAILURE:-false}" = true ]; then
        printf 'Deployment bootstrap failed: existing .env changed before replacement\n' >&2
        exit 2
      fi
      sed \
        -e "s#^SURGEPILOT_HTTP_PORT=.*#SURGEPILOT_HTTP_PORT=$http_port#" \
        -e "s#^SURGEPILOT_NODE_API_BASE_URL=.*#SURGEPILOT_NODE_API_BASE_URL=$api_url#" \
        -e "s#^SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT=.*#SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT=$influx_port#" \
        -e "s#^SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL=.*#SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL=$influx_url#" \
        "$TEST_ROOT/.env" > "$TEST_ROOT/.env.reconfigured"
      chmod 600 "$TEST_ROOT/.env.reconfigured"
      mv "$TEST_ROOT/.env.reconfigured" "$TEST_ROOT/.env"
      printf '%s %s %s\n' "$host" "$http_port" "$influx_port" > "$TEST_ROOT/reconfigured"
      if [ "${TEST_RECONFIGURE_FAILURE:-false}" = true ]; then
        printf 'Deployment bootstrap failed: .env was updated but durability could not be confirmed; inspect .env\n' >&2
        exit 2
      fi
      exit 0
    fi
    cat > "$TEST_ROOT/.env" <<EOF
SURGEPILOT_HTTP_PORT=$http_port
SURGEPILOT_NODE_API_BASE_URL=$api_url
SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT=$influx_port
SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL=$influx_url
SURGEPILOT_DEMO_LOAD_NODE_ENABLED=false
SURGEPILOT_RUNTIME_ARCHITECTURES=amd64,arm64
SESSION_COOKIE_SECURE=false
PRESERVED_VALUE=keep-me
EOF
    chmod 600 "$TEST_ROOT/.env"
    exit 0
    ;;
  *"release_preflight.py select-runtime"*) printf '%s\n' "${TEST_SELECTED_ARCHITECTURES:-amd64}"; exit 0 ;;
esac
exit 0
"""


def prepare_configuration_docker(tmp_path: Path) -> tuple[Path, dict[str, str], Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "docker.log"
    docker = bin_dir / "docker"
    docker.write_text(configuration_docker_script(), encoding="utf-8")
    docker.chmod(0o755)
    environment = os.environ.copy()
    environment["PATH"] = f"{bin_dir}:{environment['PATH']}"
    environment["DOCKER_LOG"] = str(log)
    environment["TEST_ROOT"] = str(tmp_path)
    env_path = tmp_path / ".env"
    environment["TEST_ENV_SHA256"] = (
        hashlib.sha256(env_path.read_bytes()).hexdigest() if env_path.exists() else "0" * 64
    )
    return docker, environment, log


def write_release_env(
    directory: Path,
    *,
    host: str = "192.0.2.20",
    http_port: int = 8080,
    influx_port: int = 8086,
    demo_enabled: str = "false",
    runtime_architectures: str = "auto",
    cookie_secure: str = "false",
    extra: str = "",
) -> None:
    env_file = directory / ".env"
    env_file.write_text(
        f"SURGEPILOT_HTTP_PORT={http_port}\n"
        f"SURGEPILOT_NODE_API_BASE_URL=http://{host}:{http_port}\n"
        f"SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT={influx_port}\n"
        f"SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL=http://{host}:{influx_port}\n"
        f"SURGEPILOT_DEMO_LOAD_NODE_ENABLED={demo_enabled}\n"
        f"SURGEPILOT_RUNTIME_ARCHITECTURES={runtime_architectures}\n"
        f"SESSION_COOKIE_SECURE={cookie_secure}\n"
        f"{extra}",
        encoding="utf-8",
    )
    env_file.chmod(0o600)


def render_wrapper(directory: Path, *, create_env: bool = True) -> Path:
    text = WRAPPER.read_text(encoding="utf-8")
    text = text.replace("@@RELEASE_VERSION@@", "v0.3.0")
    text = text.replace(
        "@@API_IMAGE@@",
        f"ghcr.io/latentrun/surgepilot-api@sha256:{'1' * 64}",
    )
    path = directory / "surgepilot"
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)
    (directory / "compose").mkdir()
    (directory / "compose/docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    if create_env:
        write_release_env(directory)
    return path


def run_interactive(
    wrapper: Path,
    *,
    environment: dict[str, str],
    answers: str,
) -> tuple[int, str, str]:
    master, slave = pty.openpty()
    process = subprocess.Popen(
        [wrapper, "up"],
        env=environment,
        stdin=slave,
        stdout=slave,
        stderr=subprocess.PIPE,
        text=False,
    )
    os.close(slave)
    os.write(master, answers.encode())
    output = bytearray()
    try:
        while True:
            try:
                chunk = os.read(master, 4096)
            except OSError:
                break
            if not chunk:
                break
            output.extend(chunk)
        stderr = process.communicate(timeout=10)[1]
    finally:
        os.close(master)
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
    return process.returncode, output.decode(errors="replace"), stderr.decode(errors="replace")


def test_help_and_invalid_command_do_not_require_docker(tmp_path: Path) -> None:
    wrapper = render_wrapper(tmp_path)

    help_result = subprocess.run([wrapper, "help"], text=True, capture_output=True)
    installed_environment = os.environ.copy()
    installed_environment["SURGEPILOT_COMMAND_NAME"] = "surgepilot"
    installed_result = subprocess.run(
        [wrapper, "help"],
        env=installed_environment,
        text=True,
        capture_output=True,
    )
    invalid_result = subprocess.run([wrapper, "upgrade"], text=True, capture_output=True)

    assert help_result.returncode == 0
    assert "./surgepilot up" in help_result.stdout
    assert installed_result.returncode == 0
    assert "surgepilot up" in installed_result.stdout
    assert "./surgepilot up" not in installed_result.stdout
    assert invalid_result.returncode == 2
    assert "upgrade" not in invalid_result.stdout


@pytest.mark.parametrize("command", ["down", "status", "logs"])
@pytest.mark.parametrize(
    "key",
    [
        "SURGEPILOT_HTTP_PORT",
        "SURGEPILOT_NODE_API_BASE_URL",
        "SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT",
        "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL",
        "SURGEPILOT_RUNTIME_ARCHITECTURES",
        "SURGEPILOT_DEMO_LOAD_NODE_ENABLED",
        "SESSION_COOKIE_SECURE",
    ],
)
def test_lifecycle_commands_reject_process_level_quickstart_overrides(
    tmp_path: Path, command: str, key: str
) -> None:
    wrapper = render_wrapper(tmp_path)
    environment = os.environ.copy()
    environment[key] = ""

    result = subprocess.run([wrapper, command], env=environment, text=True, capture_output=True)

    assert result.returncode == 1
    assert key in result.stderr
    assert "process-level overrides are not supported" in result.stderr


def test_interactive_first_up_validates_release_before_prompting(tmp_path: Path) -> None:
    wrapper = render_wrapper(tmp_path, create_env=False)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker = bin_dir / "docker"
    docker.write_text(
        """#!/bin/sh
set -eu
case "$*" in
  "compose version") exit 0 ;;
  "compose version --short") printf '2.27.0\n'; exit 0 ;;
  "info") exit 0 ;;
  *"info --format {{.Architecture}}"*) printf 'amd64\n'; exit 0 ;;
  *"info --format {{.MemTotal}}"*) printf '8589934592\n'; exit 0 ;;
  *"version --format {{.Server.Version}}"*) printf '26.1.0\n'; exit 0 ;;
  "pull "*) exit 1 ;;
esac
exit 0
""",
        encoding="utf-8",
    )
    docker.chmod(0o755)
    environment = os.environ.copy()
    environment["PATH"] = f"{bin_dir}:{environment['PATH']}"

    code, output, _stderr = run_interactive(
        wrapper,
        environment=environment,
        answers="192.168.1.20\n\n\nno\n",
    )

    assert code != 0
    assert "LAN host or IP" not in output


def test_up_orders_preflight_bootstrap_runtime_and_compose_without_host_python(
    tmp_path: Path,
) -> None:
    wrapper = render_wrapper(tmp_path)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "docker.log"
    docker = bin_dir / "docker"
    docker.write_text(
        """#!/bin/sh
set -eu
printf '%s\n' "$*" >> "$DOCKER_LOG"
case "$*" in
  "compose version") exit 0 ;;
  "compose version --short") printf '2.27.0\n'; exit 0 ;;
  "info") exit 0 ;;
  *"info --format {{.Architecture}}"*) printf 'arm64\n'; exit 0 ;;
  *"info --format {{.MemTotal}}"*) printf '8589934592\n'; exit 0 ;;
  *"version --format {{.Server.Version}}"*) printf '26.1.0\n'; exit 0 ;;
"""
        + release_description_case(selected="arm64")
        + """  *"release_preflight.py select-runtime"*) printf 'arm64\n'; exit 0 ;;
esac
exit 0
""",
        encoding="utf-8",
    )
    docker.chmod(0o755)
    environment = os.environ.copy()
    environment["PATH"] = f"{bin_dir}:{environment['PATH']}"
    environment["DOCKER_LOG"] = str(log)

    result = subprocess.run([wrapper, "up"], env=environment, text=True, capture_output=True)

    assert result.returncode == 0, result.stderr
    commands = log.read_text(encoding="utf-8")
    pull_index = commands.index("pull ghcr.io/latentrun/surgepilot-api@sha256:")
    preflight_index = commands.index("release_preflight.py preflight")
    description_index = commands.index("release_preflight.py describe-release")
    http_port_index = commands.index("--publish 8080:80")
    influx_port_index = commands.index("--publish 8086:80")
    fetch_index = commands.index("fetch_runtime_release.py")
    bootstrap_index = commands.index("bootstrap_deployment_env.py --root /release")
    config_index = commands.index("compose --env-file")
    up_index = commands.rindex(" up -d --wait")
    assert (
        pull_index
        < preflight_index
        < description_index
        < http_port_index
        < influx_port_index
        < bootstrap_index
        < fetch_index
        < config_index
        < up_index
    )
    assert commands.count("bootstrap_deployment_env.py") == 1
    assert "SURGEPILOT_RUNTIME_ARCHITECTURES=auto" in (tmp_path / ".env").read_text(
        encoding="utf-8"
    )
    assert "--architectures arm64" in commands
    assert "--env COMPOSE_PROJECT_NAME" in commands
    assert "--env SURGEPILOT_HTTP_PORT" not in commands
    assert "--env SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT" not in commands
    assert "--env SESSION_COOKIE_SECURE" not in commands
    assert "/app/.venv/bin/python /opt/surgepilot/release-tools/release_preflight.py" in commands


def test_up_stops_before_compose_when_one_default_runtime_fails(tmp_path: Path) -> None:
    wrapper = render_wrapper(tmp_path)
    write_release_env(tmp_path, runtime_architectures="amd64,arm64")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "docker.log"
    docker = bin_dir / "docker"
    docker.write_text(
        """#!/bin/sh
set -eu
printf '%s\n' "$*" >> "$DOCKER_LOG"
case "$*" in
  "compose version") exit 0 ;;
  "compose version --short") printf '2.27.0\n'; exit 0 ;;
  "info") exit 0 ;;
  *"info --format {{.Architecture}}"*) printf 'amd64\n'; exit 0 ;;
  *"info --format {{.MemTotal}}"*) printf '8589934592\n'; exit 0 ;;
  *"version --format {{.Server.Version}}"*) printf '26.1.0\n'; exit 0 ;;
"""
        + release_description_case(configured="amd64,arm64", selected="amd64,arm64")
        + """  *"release_preflight.py select-runtime"*) printf 'amd64,arm64\n'; exit 0 ;;
  *"fetch_runtime_release.py"*) printf 'Runtime fetch failed: arm64 unavailable\n'; exit 1 ;;
esac
exit 0
""",
        encoding="utf-8",
    )
    docker.chmod(0o755)
    environment = os.environ.copy()
    environment["PATH"] = f"{bin_dir}:{environment['PATH']}"
    environment["DOCKER_LOG"] = str(log)

    result = subprocess.run([wrapper, "up"], env=environment, text=True, capture_output=True)

    commands = log.read_text(encoding="utf-8")
    assert result.returncode == 1
    assert "fetch_runtime_release.py" in commands
    assert " up -d --wait" not in commands


def test_helper_supplies_passwd_entry_for_host_uid_and_cleans_it_up(tmp_path: Path) -> None:
    wrapper = render_wrapper(tmp_path)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "docker.log"
    passwd_log = tmp_path / "passwd.log"
    docker = bin_dir / "docker"
    docker.write_text(
        """#!/bin/sh
set -eu
printf '%s\n' "$*" >> "$DOCKER_LOG"
arguments=$*
while [ "$#" -gt 0 ]; do
  if [ "$1" = "--volume" ]; then
    shift
    case "$1" in
      *:/etc/passwd:ro)
        passwd_source=${1%:/etc/passwd:ro}
        cat "$passwd_source" >> "$PASSWD_LOG"
        ;;
    esac
  fi
  shift
done
case "$arguments" in
  "compose version") exit 0 ;;
  "compose version --short") printf '2.27.0\n'; exit 0 ;;
  "info") exit 0 ;;
  *"info --format {{.Architecture}}"*) printf 'amd64\n'; exit 0 ;;
  *"info --format {{.MemTotal}}"*) printf '8589934592\n'; exit 0 ;;
  *"version --format {{.Server.Version}}"*) printf '26.1.0\n'; exit 0 ;;
"""
        + release_description_case()
        + """  *"release_preflight.py select-runtime"*) printf 'amd64\n'; exit 0 ;;
esac
exit 0
""",
        encoding="utf-8",
    )
    docker.chmod(0o755)
    environment = os.environ.copy()
    environment["PATH"] = f"{bin_dir}:{environment['PATH']}"
    environment["DOCKER_LOG"] = str(log)
    environment["PASSWD_LOG"] = str(passwd_log)
    environment["TMPDIR"] = str(tmp_path)

    result = subprocess.run([wrapper, "up"], env=environment, text=True, capture_output=True)

    assert result.returncode == 0, result.stderr
    helper_commands = [
        command
        for command in log.read_text(encoding="utf-8").splitlines()
        if "/app/.venv/bin/python" in command
    ]
    assert helper_commands
    assert all(":/etc/passwd:ro" in command for command in helper_commands)
    assert passwd_log.is_file()
    passwd = passwd_log.read_text(encoding="utf-8")
    assert f"surgepilot-helper:x:{os.getuid()}:{os.getgid()}:" in passwd
    assert not list(tmp_path.glob("surgepilot-helper.*/helper-passwd.*"))
    assert not (tmp_path / ".surgepilot").exists()


@pytest.mark.parametrize(
    "helper_command",
    ["release_preflight.py preflight", "release_preflight.py describe-release"],
)
def test_helper_cleans_passwd_entry_when_wrapper_is_interrupted(
    tmp_path: Path, helper_command: str
) -> None:
    wrapper = render_wrapper(tmp_path)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    helper_started = tmp_path / "helper-started"
    docker = bin_dir / "docker"
    docker.write_text(
        """#!/bin/sh
set -eu
case "$*" in
  "compose version") exit 0 ;;
  "compose version --short") printf '2.27.0\n'; exit 0 ;;
  "info") exit 0 ;;
  *"info --format {{.Architecture}}"*) printf 'amd64\n'; exit 0 ;;
  *"info --format {{.MemTotal}}"*) printf '8589934592\n'; exit 0 ;;
  *"version --format {{.Server.Version}}"*) printf '26.1.0\n'; exit 0 ;;
  *"$HELPER_COMMAND"*) touch "$HELPER_STARTED"; sleep 30; exit 0 ;;
"""
        + release_description_case()
        + """  *"release_preflight.py select-runtime"*) printf 'amd64\n'; exit 0 ;;
esac
exit 0
""",
        encoding="utf-8",
    )
    docker.chmod(0o755)
    environment = os.environ.copy()
    environment["PATH"] = f"{bin_dir}:{environment['PATH']}"
    environment["HELPER_STARTED"] = str(helper_started)
    environment["HELPER_COMMAND"] = helper_command
    environment["TMPDIR"] = str(tmp_path)
    process = subprocess.Popen(
        [wrapper, "up"],
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        deadline = time.monotonic() + 5
        helper_files: list[Path] = []
        output_files: list[Path] = []
        while time.monotonic() < deadline:
            helper_files = list(tmp_path.glob("surgepilot-helper.*/helper-passwd.*"))
            output_files = list(tmp_path.glob("surgepilot-helper.*/helper-output.*"))
            output_ready = helper_command != "release_preflight.py describe-release" or output_files
            if helper_started.exists() and helper_files and output_ready:
                break
            time.sleep(0.05)
        assert helper_started.exists()
        assert helper_files
        if helper_command == "release_preflight.py describe-release":
            assert output_files

        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=5)

        assert not list(tmp_path.glob("surgepilot-helper.*/helper-passwd.*"))
        assert not list(tmp_path.glob("surgepilot-helper.*/helper-output.*"))
        assert not (tmp_path / ".surgepilot").exists()
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)


def test_up_fails_before_bootstrap_when_required_http_port_is_unavailable(
    tmp_path: Path,
) -> None:
    wrapper = render_wrapper(tmp_path)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "docker.log"
    docker = bin_dir / "docker"
    docker.write_text(
        """#!/bin/sh
set -eu
printf '%s\n' "$*" >> "$DOCKER_LOG"
case "$*" in
  "compose version") exit 0 ;;
  "compose version --short") printf '2.27.0\n'; exit 0 ;;
  "info") exit 0 ;;
  *"info --format {{.Architecture}}"*) printf 'amd64\n'; exit 0 ;;
  *"info --format {{.MemTotal}}"*) printf '8589934592\n'; exit 0 ;;
  *"version --format {{.Server.Version}}"*) printf '26.1.0\n'; exit 0 ;;
"""
        + release_description_case()
        + """
  *"--publish 8080:80"*) exit 1 ;;
esac
exit 0
""",
        encoding="utf-8",
    )
    docker.chmod(0o755)
    environment = os.environ.copy()
    environment["PATH"] = f"{bin_dir}:{environment['PATH']}"
    environment["DOCKER_LOG"] = str(log)

    result = subprocess.run([wrapper, "up"], env=environment, text=True, capture_output=True)

    commands = log.read_text(encoding="utf-8")
    assert result.returncode == 1
    assert "host port 8080 is unavailable" in result.stderr
    assert "bootstrap_deployment_env.py" not in commands
    assert "fetch_runtime_release.py" not in commands


def test_up_reports_safe_diagnostics_when_health_readiness_fails(tmp_path: Path) -> None:
    wrapper = render_wrapper(tmp_path)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "docker.log"
    docker = bin_dir / "docker"
    docker.write_text(
        """#!/bin/sh
set -eu
printf '%s\n' "$*" >> "$DOCKER_LOG"
case "$*" in
  "compose version") exit 0 ;;
  "compose version --short") printf '2.27.0\n'; exit 0 ;;
  "info") exit 0 ;;
  *"info --format {{.Architecture}}"*) printf 'amd64\n'; exit 0 ;;
  *"info --format {{.MemTotal}}"*) printf '8589934592\n'; exit 0 ;;
  *"version --format {{.Server.Version}}"*) printf '26.1.0\n'; exit 0 ;;
"""
        + release_description_case()
        + """  *"release_preflight.py select-runtime"*) printf 'amd64\n'; exit 0 ;;
  *" up -d --wait"*) exit 1 ;;
esac
exit 0
""",
        encoding="utf-8",
    )
    docker.chmod(0o755)
    environment = os.environ.copy()
    environment["PATH"] = f"{bin_dir}:{environment['PATH']}"
    environment["DOCKER_LOG"] = str(log)

    result = subprocess.run([wrapper, "up"], env=environment, text=True, capture_output=True)

    commands = log.read_text(encoding="utf-8")
    assert result.returncode == 1
    assert "did not become healthy" in result.stderr
    assert "./surgepilot status" in result.stderr
    assert "./surgepilot logs" in result.stderr
    assert " ps" in commands


def test_up_preflights_external_influxdb_publish_port(tmp_path: Path) -> None:
    wrapper = render_wrapper(tmp_path)
    write_release_env(tmp_path, influx_port=18086)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "docker.log"
    docker = bin_dir / "docker"
    docker.write_text(
        """#!/bin/sh
set -eu
printf '%s\n' "$*" >> "$DOCKER_LOG"
case "$*" in
  "compose version") exit 0 ;;
  "compose version --short") printf '2.27.0\n'; exit 0 ;;
  "info") exit 0 ;;
  *"info --format {{.Architecture}}"*) printf 'amd64\n'; exit 0 ;;
  *"info --format {{.MemTotal}}"*) printf '8589934592\n'; exit 0 ;;
  *"version --format {{.Server.Version}}"*) printf '26.1.0\n'; exit 0 ;;
"""
        + release_description_case(influx_port=18086)
        + """  *"release_preflight.py select-runtime"*) printf 'amd64\n'; exit 0 ;;
esac
exit 0
""",
        encoding="utf-8",
    )
    docker.chmod(0o755)
    environment = os.environ.copy()
    environment["PATH"] = f"{bin_dir}:{environment['PATH']}"
    environment["DOCKER_LOG"] = str(log)

    result = subprocess.run([wrapper, "up"], env=environment, text=True, capture_output=True)

    assert result.returncode == 0, result.stderr
    assert "--publish 18086:80" in log.read_text(encoding="utf-8")


def test_repeated_up_accepts_ports_owned_by_the_same_compose_project(tmp_path: Path) -> None:
    wrapper = render_wrapper(tmp_path)
    write_release_env(tmp_path, extra="COMPOSE_PROJECT_NAME=surgepilot\n")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "docker.log"
    docker = bin_dir / "docker"
    docker.write_text(
        """#!/bin/sh
set -eu
printf '%s\n' "$*" >> "$DOCKER_LOG"
case "$*" in
  "compose version") exit 0 ;;
  "compose version --short") printf '2.27.0\n'; exit 0 ;;
  "info") exit 0 ;;
  *"info --format {{.Architecture}}"*) printf 'amd64\n'; exit 0 ;;
  *"info --format {{.MemTotal}}"*) printf '8589934592\n'; exit 0 ;;
  *"version --format {{.Server.Version}}"*) printf '26.1.0\n'; exit 0 ;;
  *"--publish 8080:80"*) exit 1 ;;
  *"ps --filter label=com.docker.compose.project=surgepilot"*) printf '0.0.0.0:8080->80/tcp\n'; exit 0 ;;
"""
        + release_description_case()
        + """  *"release_preflight.py select-runtime"*) printf 'amd64\n'; exit 0 ;;
esac
exit 0
""",
        encoding="utf-8",
    )
    docker.chmod(0o755)
    environment = os.environ.copy()
    environment["PATH"] = f"{bin_dir}:{environment['PATH']}"
    environment["DOCKER_LOG"] = str(log)

    result = subprocess.run([wrapper, "up"], env=environment, text=True, capture_output=True)

    assert result.returncode == 0, result.stderr
    assert "com.docker.compose.project=surgepilot" in log.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "key",
    [
        "SURGEPILOT_HTTP_PORT",
        "SURGEPILOT_NODE_API_BASE_URL",
        "SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT",
        "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL",
        "SURGEPILOT_RUNTIME_ARCHITECTURES",
        "SURGEPILOT_DEMO_LOAD_NODE_ENABLED",
        "SESSION_COOKIE_SECURE",
    ],
)
def test_up_rejects_process_level_release_quickstart_overrides(tmp_path: Path, key: str) -> None:
    wrapper = render_wrapper(tmp_path)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "docker.log"
    docker = bin_dir / "docker"
    docker.write_text(
        """#!/bin/sh
set -eu
printf '%s\n' "$*" >> "$DOCKER_LOG"
case "$*" in
  "compose version") exit 0 ;;
  "compose version --short") printf '2.27.0\n'; exit 0 ;;
  "info") exit 0 ;;
  *"info --format {{.Architecture}}"*) printf 'amd64\n'; exit 0 ;;
  *"info --format {{.MemTotal}}"*) printf '8589934592\n'; exit 0 ;;
  *"version --format {{.Server.Version}}"*) printf '26.1.0\n'; exit 0 ;;
esac
exit 0
""",
        encoding="utf-8",
    )
    docker.chmod(0o755)
    environment = os.environ.copy()
    environment["PATH"] = f"{bin_dir}:{environment['PATH']}"
    environment["DOCKER_LOG"] = str(log)
    environment[key] = ""

    result = subprocess.run([wrapper, "up"], env=environment, text=True, capture_output=True)

    assert result.returncode == 1
    assert key in result.stderr
    assert "process-level overrides are not supported" in result.stderr
    assert not log.exists()


def test_up_rejects_old_docker_before_pulling_images(tmp_path: Path) -> None:
    wrapper = render_wrapper(tmp_path)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "docker.log"
    docker = bin_dir / "docker"
    docker.write_text(
        """#!/bin/sh
set -eu
printf '%s\n' "$*" >> "$DOCKER_LOG"
case "$*" in
  "compose version") exit 0 ;;
  "compose version --short") printf '2.27.0\n'; exit 0 ;;
  "info") exit 0 ;;
  *"info --format {{.Architecture}}"*) printf 'amd64\n'; exit 0 ;;
  *"info --format {{.MemTotal}}"*) printf '8589934592\n'; exit 0 ;;
  *"version --format {{.Server.Version}}"*) printf '25.0.5\n'; exit 0 ;;
esac
exit 0
""",
        encoding="utf-8",
    )
    docker.chmod(0o755)
    environment = os.environ.copy()
    environment["PATH"] = f"{bin_dir}:{environment['PATH']}"
    environment["DOCKER_LOG"] = str(log)

    result = subprocess.run([wrapper, "up"], env=environment, text=True, capture_output=True)

    assert result.returncode == 1
    assert "Docker Engine 26.0.0 or newer" in result.stderr
    assert "pull ghcr.io" not in log.read_text(encoding="utf-8")


def test_first_up_without_terminal_fails_before_pull_or_deployment_state(tmp_path: Path) -> None:
    wrapper = render_wrapper(tmp_path, create_env=False)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "docker.log"
    docker = bin_dir / "docker"
    docker.write_text(
        """#!/bin/sh
set -eu
printf '%s\n' "$*" >> "$DOCKER_LOG"
case "$*" in
  "compose version") exit 0 ;;
  "compose version --short") printf '2.27.0\n'; exit 0 ;;
  "info") exit 0 ;;
  *"info --format {{.Architecture}}"*) printf 'amd64\n'; exit 0 ;;
  *"info --format {{.MemTotal}}"*) printf '8589934592\n'; exit 0 ;;
  *"version --format {{.Server.Version}}"*) printf '26.1.0\n'; exit 0 ;;
esac
exit 0
""",
        encoding="utf-8",
    )
    docker.chmod(0o755)
    environment = os.environ.copy()
    environment["PATH"] = f"{bin_dir}:{environment['PATH']}"
    environment["DOCKER_LOG"] = str(log)

    result = subprocess.run([wrapper, "up"], env=environment, text=True, capture_output=True)

    assert result.returncode == 1
    assert "first-run release setup requires an interactive terminal" in result.stderr
    assert "pull ghcr.io" not in log.read_text(encoding="utf-8")
    assert not (tmp_path / ".env").exists()
    assert not (tmp_path / ".surgepilot").exists()


def test_existing_configuration_default_yes_is_read_only_and_precedes_startup(
    tmp_path: Path,
) -> None:
    wrapper = render_wrapper(tmp_path)
    env_before = (tmp_path / ".env").read_bytes()
    _docker, environment, log = prepare_configuration_docker(tmp_path)

    code, output, stderr = run_interactive(wrapper, environment=environment, answers="\n")

    assert code == 0, stderr
    assert "Web and API: http://192.0.2.20:8080" in output
    assert "InfluxDB node write: http://192.0.2.20:8086" in output
    assert "Runtime architectures: auto" in output
    assert "Demo Load Node: disabled" in output
    assert "Use this configuration? [Y/n]:" in output
    commands = log.read_text(encoding="utf-8")
    assert (
        commands.index("release_preflight.py describe-release")
        < commands.index("bootstrap_deployment_env.py --root /release")
        < commands.index("fetch_runtime_release.py")
    )
    assert commands.count("bootstrap_deployment_env.py") == 1
    assert "--reconfigure-release-network" not in commands
    assert (tmp_path / ".env").read_bytes() == env_before


@pytest.mark.parametrize("answer", ["y\n", "Y\n", "yes\n", "YES\n", "YeS\n"])
def test_existing_configuration_accepts_uppercase_yes_without_reconfiguration(
    tmp_path: Path, answer: str
) -> None:
    wrapper = render_wrapper(tmp_path)
    env_before = (tmp_path / ".env").read_bytes()
    _docker, environment, log = prepare_configuration_docker(tmp_path)

    code, _output, stderr = run_interactive(wrapper, environment=environment, answers=answer)

    assert code == 0, stderr
    commands = log.read_text(encoding="utf-8")
    assert "normalize-bootstrap" not in commands
    assert "--reconfigure-release-network" not in commands
    assert (tmp_path / ".env").read_bytes() == env_before


def test_existing_configuration_no_reenters_and_persists_only_normalized_network(
    tmp_path: Path,
) -> None:
    wrapper = render_wrapper(tmp_path)
    write_release_env(tmp_path, extra="PRESERVED_VALUE=keep-me\n")
    expected_sha256 = hashlib.sha256((tmp_path / ".env").read_bytes()).hexdigest()
    _docker, environment, log = prepare_configuration_docker(tmp_path)
    environment["DOCKER_DEFAULT_PLATFORM"] = "linux/arm64"

    code, output, stderr = run_interactive(
        wrapper,
        environment=environment,
        answers="n\nrelease.lan\n18080\n18086\n\n",
    )

    assert code == 0, stderr
    assert "LAN host or IP [192.0.2.20]:" in output
    assert "HTTP port [8080]:" in output
    assert "InfluxDB node-write port [8086]:" in output
    assert "Web and API: http://release.lan:18080" in output
    commands = log.read_text(encoding="utf-8")
    assert (
        "normalize-bootstrap --host release.lan --http-port 18080 --influx-port 18086 "
        "--runtime-architectures auto --daemon-arch amd64 "
        "--forced-platform linux/arm64"
    ) in commands
    assert "--reconfigure-release-network" in commands
    ensure_command = next(
        line
        for line in commands.splitlines()
        if "bootstrap_deployment_env.py --root /release" in line
        and "--reconfigure-release-network" not in line
    )
    assert (
        commands.index("--reconfigure-release-network")
        < commands.index(ensure_command)
        < commands.index("fetch_runtime_release.py")
    )
    assert f"--expected-env-sha256 {expected_sha256}" in commands
    assert "--release-http-port 18080" in commands
    assert "--release-node-api-base-url http://release.lan:18080" in commands
    assert "--release-influxdb-host-port 18086" in commands
    assert "--release-influxdb-node-write-url http://release.lan:18086" in commands
    assert "--daemon-arch amd64 --forced-platform linux/arm64" in commands
    assert commands.index("--publish 18080:80") < commands.index("--reconfigure-release-network")
    assert "Web: http://release.lan:18080" in output
    persisted = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "PRESERVED_VALUE=keep-me" in persisted
    assert "http://release.lan:18080" in persisted


def test_existing_configuration_repeated_no_consumes_another_proposal(
    tmp_path: Path,
) -> None:
    wrapper = render_wrapper(tmp_path)
    _docker, environment, log = prepare_configuration_docker(tmp_path)

    code, output, stderr = run_interactive(
        wrapper,
        environment=environment,
        answers=("n\nfirst.lan\n18080\n18086\nn\nsecond.lan\n28080\n28086\n\n"),
    )

    assert code == 0, stderr
    commands = log.read_text(encoding="utf-8")
    assert commands.count("release_preflight.py normalize-bootstrap") == 2
    assert "--host first.lan --http-port 18080 --influx-port 18086" in commands
    assert "--host second.lan --http-port 28080 --influx-port 28086" in commands
    assert commands.count("--reconfigure-release-network") == 1
    assert output.count("LAN host or IP [192.0.2.20]:") == 2
    assert output.count("HTTP port [8080]:") == 2
    assert output.count("InfluxDB node-write port [8086]:") == 2
    assert "Web: http://second.lan:28080" in output
    assert "http://first.lan" not in (tmp_path / ".env").read_text(encoding="utf-8")


def test_existing_demo_configuration_reentry_preserves_every_non_network_value(
    tmp_path: Path,
) -> None:
    wrapper = render_wrapper(tmp_path)
    write_release_env(
        tmp_path,
        demo_enabled="true",
        runtime_architectures="arm64",
        extra="# operator state\nADMIN_PASSWORD=keep-secret\nUNKNOWN_VALUE=keep-me\n",
    )
    before_lines = (tmp_path / ".env").read_text(encoding="utf-8").splitlines()
    _docker, environment, log = prepare_configuration_docker(tmp_path)
    environment["TEST_DAEMON_ARCH"] = "arm64"
    environment["TEST_DEMO_ENABLED"] = "true"
    environment["TEST_RUNTIME_ARCHITECTURES"] = "arm64"
    environment["TEST_SELECTED_ARCHITECTURES"] = "arm64"

    code, output, stderr = run_interactive(
        wrapper,
        environment=environment,
        answers=("n\nfirst.lan\n18080\n18086\nn\nsecond.lan\n28080\n28086\n\n"),
    )

    assert code == 0, stderr
    assert output.count("Demo Load Node: enabled") == 3
    assert "Demo Load Node: disabled" not in output
    assert output.count("Runtime architectures: arm64") == 3
    commands = log.read_text(encoding="utf-8")
    compose_commands = [
        line for line in commands.splitlines() if line.startswith("compose --env-file")
    ]
    assert compose_commands
    assert all("--profile demo" in line for line in compose_commands)

    network_prefixes = (
        "SURGEPILOT_HTTP_PORT=",
        "SURGEPILOT_NODE_API_BASE_URL=",
        "SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT=",
        "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL=",
    )
    after_lines = (tmp_path / ".env").read_text(encoding="utf-8").splitlines()
    assert [line for line in after_lines if not line.startswith(network_prefixes)] == [
        line for line in before_lines if not line.startswith(network_prefixes)
    ]
    assert "SURGEPILOT_DEMO_LOAD_NODE_ENABLED=true" in after_lines
    assert "SURGEPILOT_RUNTIME_ARCHITECTURES=arm64" in after_lines
    assert "SESSION_COOKIE_SECURE=false" in after_lines
    assert "ADMIN_PASSWORD=keep-secret" in after_lines
    assert "SURGEPILOT_NODE_API_BASE_URL=http://second.lan:28080" in after_lines


def test_existing_configuration_occupied_proposed_port_returns_to_entry_loop(
    tmp_path: Path,
) -> None:
    wrapper = render_wrapper(tmp_path)
    _docker, environment, log = prepare_configuration_docker(tmp_path)
    environment["TEST_OCCUPIED_PORT"] = "18080"

    code, output, stderr = run_interactive(
        wrapper,
        environment=environment,
        answers=("n\nbusy.lan\n18080\n18086\n\nready.lan\n28080\n28086\n\n"),
    )

    assert code == 0, stderr
    assert "SurgePilot HTTP host port 18080 is unavailable" in stderr
    assert output.count("LAN host or IP [192.0.2.20]:") == 2
    commands = log.read_text(encoding="utf-8")
    assert commands.count("release_preflight.py normalize-bootstrap") == 2
    assert commands.count("--reconfigure-release-network") == 1
    assert "--release-node-api-base-url http://ready.lan:28080" in commands
    assert "Web: http://ready.lan:28080" in output


def test_existing_configuration_invalid_answer_repeats_only_confirmation(
    tmp_path: Path,
) -> None:
    wrapper = render_wrapper(tmp_path)
    _docker, environment, log = prepare_configuration_docker(tmp_path)

    code, output, stderr = run_interactive(wrapper, environment=environment, answers="maybe\n\n")

    assert code == 0, stderr
    assert "Please enter y or n." in output
    assert output.count("Use this configuration? [Y/n]:") == 2
    assert "LAN host or IP" not in output
    commands = log.read_text(encoding="utf-8")
    assert "normalize-bootstrap" not in commands
    assert "--reconfigure-release-network" not in commands


def test_existing_configuration_eof_preserves_state_and_stops_before_runtime(
    tmp_path: Path,
) -> None:
    wrapper = render_wrapper(tmp_path)
    env_before = (tmp_path / ".env").read_bytes()
    _docker, environment, log = prepare_configuration_docker(tmp_path)

    code, output, stderr = run_interactive(wrapper, environment=environment, answers="\x04")

    assert code == 1
    assert "Use this configuration? [Y/n]:" in output
    assert "configuration confirmation ended unexpectedly" in stderr
    commands = log.read_text(encoding="utf-8")
    assert "fetch_runtime_release.py" not in commands
    assert "compose --env-file" not in commands
    assert (tmp_path / ".env").read_bytes() == env_before


def test_existing_configuration_post_replace_helper_error_stops_startup(
    tmp_path: Path,
) -> None:
    wrapper = render_wrapper(tmp_path)
    _docker, environment, log = prepare_configuration_docker(tmp_path)
    environment["TEST_RECONFIGURE_FAILURE"] = "true"

    code, _output, stderr = run_interactive(
        wrapper,
        environment=environment,
        answers="n\nrelease.lan\n18080\n18086\n\n",
    )

    assert code == 2
    assert "updated but durability could not be confirmed; inspect .env" in stderr
    commands = log.read_text(encoding="utf-8")
    assert "--reconfigure-release-network" in commands
    assert "fetch_runtime_release.py" not in commands
    assert "compose --env-file" not in commands
    assert "http://release.lan:18080" in (tmp_path / ".env").read_text(encoding="utf-8")


def test_existing_configuration_pre_replace_helper_error_preserves_state_and_stops_startup(
    tmp_path: Path,
) -> None:
    wrapper = render_wrapper(tmp_path)
    env_before = (tmp_path / ".env").read_bytes()
    _docker, environment, log = prepare_configuration_docker(tmp_path)
    environment["TEST_RECONFIGURE_PRE_REPLACE_FAILURE"] = "true"

    code, _output, stderr = run_interactive(
        wrapper,
        environment=environment,
        answers="n\nrelease.lan\n18080\n18086\n\n",
    )

    assert code == 2
    assert "existing .env changed before replacement" in stderr
    commands = log.read_text(encoding="utf-8")
    assert "--reconfigure-release-network" in commands
    assert "fetch_runtime_release.py" not in commands
    assert "compose --env-file" not in commands
    assert not (tmp_path / "reconfigured").exists()
    assert (tmp_path / ".env").read_bytes() == env_before


def test_existing_advanced_https_no_requires_manual_env_edit(tmp_path: Path) -> None:
    wrapper = render_wrapper(tmp_path)
    (tmp_path / ".env").write_text(
        "SURGEPILOT_HTTP_PORT=8443\n"
        "SURGEPILOT_NODE_API_BASE_URL=https://release.example.test:8443\n"
        "SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT=8086\n"
        "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL=https://release.example.test:8086\n"
        "SURGEPILOT_DEMO_LOAD_NODE_ENABLED=false\n"
        "SURGEPILOT_RUNTIME_ARCHITECTURES=auto\n"
        "SESSION_COOKIE_SECURE=true\n",
        encoding="utf-8",
    )
    (tmp_path / ".env").chmod(0o600)
    env_before = (tmp_path / ".env").read_bytes()
    _docker, environment, log = prepare_configuration_docker(tmp_path)
    environment["TEST_ADVANCED_HTTPS"] = "true"

    code, output, stderr = run_interactive(wrapper, environment=environment, answers="n\n")

    assert code == 1
    assert "Advanced HTTPS configuration cannot be changed by this prompt." in stderr
    assert "Edit .env explicitly, then run ./surgepilot up again." in stderr
    commands = log.read_text(encoding="utf-8")
    assert "normalize-bootstrap" not in commands
    assert "fetch_runtime_release.py" not in commands
    assert "compose --env-file" not in commands
    assert (tmp_path / ".env").read_bytes() == env_before


def test_noninteractive_existing_configuration_prints_summary_without_prompt(
    tmp_path: Path,
) -> None:
    wrapper = render_wrapper(tmp_path)
    _docker, environment, log = prepare_configuration_docker(tmp_path)

    result = subprocess.run([wrapper, "up"], env=environment, text=True, capture_output=True)

    assert result.returncode == 0, result.stderr
    assert "Web and API: http://192.0.2.20:8080" in result.stdout
    assert "Runtime architectures: auto" in result.stdout
    assert "Use this configuration?" not in result.stdout
    commands = log.read_text(encoding="utf-8")
    assert "--reconfigure-release-network" not in commands
    assert (
        commands.index("release_preflight.py describe-release")
        < commands.index("bootstrap_deployment_env.py --root /release")
        < commands.index("fetch_runtime_release.py")
    )
    assert commands.count("bootstrap_deployment_env.py") == 1


@pytest.mark.parametrize(
    "diagnostic",
    [
        "deployment .env must use owner-only permissions",
        "RUNNER_INTERNAL_TOKEN still uses a template placeholder",
        "Monitoring token file is empty",
        "Demo Load Node SSH identity is incomplete; refusing automatic repair",
    ],
)
def test_existing_bootstrap_safety_failure_stops_before_runtime_and_compose(
    tmp_path: Path, diagnostic: str
) -> None:
    wrapper = render_wrapper(tmp_path)
    env_before = (tmp_path / ".env").read_bytes()
    _docker, environment, log = prepare_configuration_docker(tmp_path)
    environment["TEST_BOOTSTRAP_FAILURE"] = diagnostic

    result = subprocess.run([wrapper, "up"], env=environment, text=True, capture_output=True)

    assert result.returncode == 2
    assert diagnostic in result.stderr
    commands = log.read_text(encoding="utf-8")
    assert "bootstrap_deployment_env.py --root /release" in commands
    assert "fetch_runtime_release.py" not in commands
    assert "compose --env-file" not in commands
    assert (tmp_path / ".env").read_bytes() == env_before


def test_interactive_first_up_normalizes_confirms_and_persists_before_start(
    tmp_path: Path,
) -> None:
    wrapper = render_wrapper(tmp_path, create_env=False)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "docker.log"
    docker = bin_dir / "docker"
    docker.write_text(
        """#!/bin/sh
set -eu
printf '%s\n' "$*" >> "$DOCKER_LOG"
case "$*" in
  "compose version") exit 0 ;;
  "compose version --short") printf '2.27.0\n'; exit 0 ;;
  "info") exit 0 ;;
  *"info --format {{.Architecture}}"*) printf 'amd64\n'; exit 0 ;;
  *"info --format {{.MemTotal}}"*) printf '8589934592\n'; exit 0 ;;
  *"version --format {{.Server.Version}}"*) printf '26.1.0\n'; exit 0 ;;
  *"release_preflight.py normalize-bootstrap"*)
    if IFS= read -r unexpected; then
      printf 'helper unexpectedly read terminal input: %s\n' "$unexpected" >&2
      exit 99
    fi
    cat <<'EOF'
SURGEPILOT_HTTP_PORT=8080
SURGEPILOT_NODE_API_BASE_URL=http://192.168.1.20:8080
SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT=8086
SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL=http://192.168.1.20:8086
SURGEPILOT_DEMO_LOAD_NODE_ENABLED=false
SURGEPILOT_RUNTIME_ARCHITECTURES=amd64,arm64
SESSION_COOKIE_SECURE=false
EOF
    exit 0
    ;;
  *"bootstrap_deployment_env.py"*)
    cat > "$TEST_ROOT/.env" <<'EOF'
SURGEPILOT_HTTP_PORT=8080
SURGEPILOT_NODE_API_BASE_URL=http://192.168.1.20:8080
SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT=8086
SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL=http://192.168.1.20:8086
SURGEPILOT_DEMO_LOAD_NODE_ENABLED=false
SURGEPILOT_RUNTIME_ARCHITECTURES=amd64,arm64
SESSION_COOKIE_SECURE=false
EOF
    chmod 600 "$TEST_ROOT/.env"
    exit 0
    ;;
"""
        + release_description_case(configured="amd64,arm64", selected="amd64,arm64")
        + """  *"release_preflight.py select-runtime"*) printf 'amd64,arm64\n'; exit 0 ;;
esac
exit 0
""",
        encoding="utf-8",
    )
    docker.chmod(0o755)
    environment = os.environ.copy()
    environment["PATH"] = f"{bin_dir}:{environment['PATH']}"
    environment["DOCKER_LOG"] = str(log)
    environment["TEST_ROOT"] = str(tmp_path)
    environment["SURGEPILOT_COMMAND_NAME"] = "surgepilot"

    code, output, stderr = run_interactive(
        wrapper,
        environment=environment,
        answers="192.168.1.20\n\n\n\n",
    )

    assert code == 0, stderr
    assert "LAN host or IP [required]:" in output
    assert "HTTP port [8080]:" in output
    assert "InfluxDB node-write port [8086]:" in output
    assert "Runtime architectures [auto]:" not in output
    assert "Web and API: http://192.168.1.20:8080" in output
    assert "InfluxDB node write: http://192.168.1.20:8086" in output
    assert "Runtime architectures: amd64,arm64" in output
    assert "Demo Load Node: disabled" in output
    assert "SurgePilot v0.3.0 is ready." in output
    assert "Web: http://192.168.1.20:8080" in output
    assert "Commands: surgepilot status | surgepilot logs | surgepilot down" in output
    assert "./surgepilot status" not in output
    commands = log.read_text(encoding="utf-8")
    assert "--host 192.168.1.20 --http-port 8080 --influx-port 8086" in commands
    assert "--runtime-architectures amd64,arm64" in commands
    assert "--release-http-port 8080" in commands
    assert "--release-demo-enabled false" in commands
    assert "--release-runtime-architectures amd64,arm64" in commands
    assert "--architectures amd64,arm64" in commands
    assert commands.index("--publish 8080:80") < commands.index("bootstrap_deployment_env.py")
    assert commands.index("--publish 8086:80") < commands.index("bootstrap_deployment_env.py")
    assert "SURGEPILOT_RUNTIME_ARCHITECTURES=amd64,arm64" in (tmp_path / ".env").read_text(
        encoding="utf-8"
    )
    assert (tmp_path / ".env").stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize(
    ("input_host", "url_host"),
    [("localhost", "localhost"), ("127.0.0.1", "127.0.0.1"), ("::1", "[::1]")],
)
def test_interactive_local_only_first_up_warns_and_starts_complete_stack(
    tmp_path: Path, input_host: str, url_host: str
) -> None:
    wrapper = render_wrapper(tmp_path, create_env=False)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "docker.log"
    docker = bin_dir / "docker"
    docker.write_text(
        """#!/bin/sh
set -eu
printf '%s\n' "$*" >> "$DOCKER_LOG"
case "$*" in
  "compose version") exit 0 ;;
  "compose version --short") printf '2.27.0\n'; exit 0 ;;
  "info") exit 0 ;;
  *"info --format {{.Architecture}}"*) printf 'arm64\n'; exit 0 ;;
  *"info --format {{.MemTotal}}"*) printf '8589934592\n'; exit 0 ;;
  *"version --format {{.Server.Version}}"*) printf '26.1.0\n'; exit 0 ;;
  *"release_preflight.py normalize-bootstrap"*)
    cat <<EOF
SURGEPILOT_HTTP_PORT=8080
SURGEPILOT_NODE_API_BASE_URL=http://$LOCAL_URL_HOST:8080
SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT=8086
SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL=http://$LOCAL_URL_HOST:8086
SURGEPILOT_DEMO_LOAD_NODE_ENABLED=false
SURGEPILOT_RUNTIME_ARCHITECTURES=amd64,arm64
SESSION_COOKIE_SECURE=false
EOF
    exit 0
    ;;
  *"bootstrap_deployment_env.py"*)
    cat > "$TEST_ROOT/.env" <<EOF
SURGEPILOT_HTTP_PORT=8080
SURGEPILOT_NODE_API_BASE_URL=http://$LOCAL_URL_HOST:8080
SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT=8086
SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL=http://$LOCAL_URL_HOST:8086
SURGEPILOT_DEMO_LOAD_NODE_ENABLED=false
SURGEPILOT_RUNTIME_ARCHITECTURES=amd64,arm64
SESSION_COOKIE_SECURE=false
EOF
    chmod 600 "$TEST_ROOT/.env"
    exit 0
    ;;
"""
        + release_description_case(configured="amd64,arm64", selected="amd64,arm64")
        + """  *"release_preflight.py select-runtime"*) printf 'amd64,arm64\n'; exit 0 ;;
esac
exit 0
""",
        encoding="utf-8",
    )
    docker.chmod(0o755)
    environment = os.environ.copy()
    environment["PATH"] = f"{bin_dir}:{environment['PATH']}"
    environment["DOCKER_LOG"] = str(log)
    environment["TEST_ROOT"] = str(tmp_path)
    environment["LOCAL_URL_HOST"] = url_host

    code, output, stderr = run_interactive(
        wrapper,
        environment=environment,
        answers=f"{input_host}\n\n\n\n",
    )

    assert code == 0, stderr
    assert "Configured node-facing URLs: this computer only" in output
    assert "other computers and external Load Nodes cannot reach" in output
    assert "Docker still publishes these ports on host interfaces" in output
    assert "host firewall" in output
    assert "SurgePilot v0.3.0 is ready." in output
    assert f"Web: http://{url_host}:8080" in output
    assert "External Load Nodes must reach:" not in output
    assert "Update both node-facing URLs in .env" in stderr
    assert " up -d --wait" in log.read_text(encoding="utf-8")


def test_interactive_normalization_failure_remains_visible(tmp_path: Path) -> None:
    wrapper = render_wrapper(tmp_path, create_env=False)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker = bin_dir / "docker"
    docker.write_text(
        """#!/bin/sh
set -eu
case "$*" in
  "compose version") exit 0 ;;
  "compose version --short") printf '2.27.0\n'; exit 0 ;;
  "info") exit 0 ;;
  *"info --format {{.Architecture}}"*) printf 'amd64\n'; exit 0 ;;
  *"info --format {{.MemTotal}}"*) printf '8589934592\n'; exit 0 ;;
  *"version --format {{.Server.Version}}"*) printf '26.1.0\n'; exit 0 ;;
  *"release_preflight.py normalize-bootstrap"*)
    printf 'Release preflight failed: LAN host is invalid\n'
    exit 2
    ;;
esac
exit 0
""",
        encoding="utf-8",
    )
    docker.chmod(0o755)
    environment = os.environ.copy()
    environment["PATH"] = f"{bin_dir}:{environment['PATH']}"

    code, _output, stderr = run_interactive(
        wrapper,
        environment=environment,
        answers="bad_host\n\n\n\x04",
    )

    assert code == 1
    assert "Release preflight failed: LAN host is invalid" in stderr
    assert not (tmp_path / ".env").exists()


def test_first_up_invalid_lan_input_returns_to_entry_and_persists_only_correction(
    tmp_path: Path,
) -> None:
    wrapper = render_wrapper(tmp_path, create_env=False)
    _docker, environment, log = prepare_configuration_docker(tmp_path)
    environment["TEST_INVALID_NORMALIZED_HOST"] = "invalid.lan"

    code, output, stderr = run_interactive(
        wrapper,
        environment=environment,
        answers="invalid.lan\n\n\nvalid.lan\n\n\n\n",
    )

    assert code == 0, stderr
    assert "Release preflight failed: LAN host is invalid" in stderr
    assert output.count("LAN host or IP [required]:") == 2
    commands = log.read_text(encoding="utf-8")
    assert commands.count("release_preflight.py normalize-bootstrap") == 2
    assert commands.count("bootstrap_deployment_env.py") == 1
    persisted = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "http://valid.lan:8080" in persisted
    assert "invalid.lan" not in persisted


def test_existing_invalid_lan_input_returns_to_entry_without_early_mutation(
    tmp_path: Path,
) -> None:
    wrapper = render_wrapper(tmp_path)
    write_release_env(tmp_path, extra="PRESERVED_VALUE=keep-me\n")
    _docker, environment, log = prepare_configuration_docker(tmp_path)
    environment["TEST_INVALID_NORMALIZED_HOST"] = "invalid.lan"

    code, output, stderr = run_interactive(
        wrapper,
        environment=environment,
        answers="n\ninvalid.lan\n\n\nvalid.lan\n18080\n18086\n\n",
    )

    assert code == 0, stderr
    assert "Release preflight failed: LAN host is invalid" in stderr
    assert output.count("LAN host or IP [192.0.2.20]:") == 2
    commands = log.read_text(encoding="utf-8")
    assert commands.count("release_preflight.py normalize-bootstrap") == 2
    assert commands.count("--reconfigure-release-network") == 1
    persisted = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "PRESERVED_VALUE=keep-me" in persisted
    assert "http://valid.lan:18080" in persisted
    assert "invalid.lan" not in persisted


@pytest.mark.parametrize("failure_status", [1, 125])
def test_first_up_fatal_normalization_helper_failure_does_not_reprompt(
    tmp_path: Path, failure_status: int
) -> None:
    wrapper = render_wrapper(tmp_path, create_env=False)
    _docker, environment, log = prepare_configuration_docker(tmp_path)
    environment["TEST_FATAL_NORMALIZED_HOST"] = "fatal.lan"
    environment["TEST_FATAL_NORMALIZE_STATUS"] = str(failure_status)

    code, output, stderr = run_interactive(
        wrapper,
        environment=environment,
        answers="fatal.lan\n\n\n",
    )

    assert code == failure_status
    assert "Release preflight failed: normalization helper unavailable" in stderr
    assert output.count("LAN host or IP [required]:") == 1
    commands = log.read_text(encoding="utf-8")
    assert commands.count("release_preflight.py normalize-bootstrap") == 1
    assert "bootstrap_deployment_env.py" not in commands
    assert "fetch_runtime_release.py" not in commands
    assert not (tmp_path / ".env").exists()


@pytest.mark.parametrize(
    "host",
    ["127.1", "127.0.0.01", "2130706433", "0177.0.0.1", "0x7f000001"],
)
def test_interactive_legacy_ipv4_never_reaches_local_or_lan_ready_summary(
    tmp_path: Path, host: str
) -> None:
    wrapper = render_wrapper(tmp_path, create_env=False)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker = bin_dir / "docker"
    docker.write_text(
        """#!/bin/sh
set -eu
case "$*" in
  "compose version") exit 0 ;;
  "compose version --short") printf '2.27.0\n'; exit 0 ;;
  "info") exit 0 ;;
  *"info --format {{.Architecture}}"*) printf 'amd64\n'; exit 0 ;;
  *"info --format {{.MemTotal}}"*) printf '8589934592\n'; exit 0 ;;
  *"version --format {{.Server.Version}}"*) printf '26.1.0\n'; exit 0 ;;
  *"release_preflight.py normalize-bootstrap"*)
    printf 'Release preflight failed: LAN host must use canonical IPv4 address notation\n'
    exit 2
    ;;
esac
exit 0
""",
        encoding="utf-8",
    )
    docker.chmod(0o755)
    environment = os.environ.copy()
    environment["PATH"] = f"{bin_dir}:{environment['PATH']}"

    code, output, stderr = run_interactive(
        wrapper,
        environment=environment,
        answers=f"{host}\n\n\n\x04",
    )

    assert code == 1
    assert "canonical IPv4 address notation" in stderr
    assert "Configured node-facing URLs:" not in output
    assert "External Load Nodes must reach:" not in output
    assert not (tmp_path / ".env").exists()


def test_first_up_no_reenters_and_only_persists_second_proposal(tmp_path: Path) -> None:
    wrapper = render_wrapper(tmp_path, create_env=False)
    _docker, environment, log = prepare_configuration_docker(tmp_path)

    code, output, stderr = run_interactive(
        wrapper,
        environment=environment,
        answers=("first.lan\n\n\nno\nsecond.lan\n18080\n18086\n\n"),
    )

    assert code == 0, stderr
    assert output.count("LAN host or IP [required]:") == 2
    assert "Web and API: http://first.lan:8080" in output
    assert "Web and API: http://second.lan:18080" in output
    commands = log.read_text(encoding="utf-8")
    assert commands.count("release_preflight.py normalize-bootstrap") == 2
    assert commands.count("bootstrap_deployment_env.py") == 1
    assert "--release-node-api-base-url http://second.lan:18080" in commands
    persisted = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "http://second.lan:18080" in persisted
    assert "first.lan" not in persisted


def test_first_up_confirmation_eof_leaves_no_deployment_state(tmp_path: Path) -> None:
    wrapper = render_wrapper(tmp_path, create_env=False)
    _docker, environment, log = prepare_configuration_docker(tmp_path)

    code, output, stderr = run_interactive(
        wrapper,
        environment=environment,
        answers="release.lan\n\n\n\x04",
    )

    assert code == 1
    assert "Use this configuration? [Y/n]:" in output
    assert "configuration confirmation ended unexpectedly" in stderr
    commands = log.read_text(encoding="utf-8")
    assert "bootstrap_deployment_env.py" not in commands
    assert "fetch_runtime_release.py" not in commands
    assert " up -d" not in commands
    assert not (tmp_path / ".env").exists()
    assert not (tmp_path / ".surgepilot").exists()


def test_ready_output_uses_persisted_lan_origins_and_http_warning(tmp_path: Path) -> None:
    wrapper = render_wrapper(tmp_path)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker = bin_dir / "docker"
    docker.write_text(
        """#!/bin/sh
set -eu
case "$*" in
  "compose version") exit 0 ;;
  "compose version --short") printf '2.27.0\n'; exit 0 ;;
  "info") exit 0 ;;
  *"info --format {{.Architecture}}"*) printf 'amd64\n'; exit 0 ;;
  *"info --format {{.MemTotal}}"*) printf '8589934592\n'; exit 0 ;;
  *"version --format {{.Server.Version}}"*) printf '26.1.0\n'; exit 0 ;;
"""
        + release_description_case()
        + """  *"release_preflight.py select-runtime"*) printf 'amd64\n'; exit 0 ;;
esac
exit 0
""",
        encoding="utf-8",
    )
    docker.chmod(0o755)
    environment = os.environ.copy()
    environment["PATH"] = f"{bin_dir}:{environment['PATH']}"

    result = subprocess.run([wrapper, "up"], env=environment, text=True, capture_output=True)

    assert result.returncode == 0, result.stderr
    assert "Web: http://192.0.2.20:8080" in result.stdout
    assert "Grafana: http://192.0.2.20:8080/grafana/" in result.stdout
    assert "API: http://192.0.2.20:8080" in result.stdout
    assert "InfluxDB: http://192.0.2.20:8086" in result.stdout
    assert "trusted LAN" in result.stderr
    assert "does not provide transport encryption" in result.stderr


@pytest.mark.parametrize(("demo_enabled", "expects_profile"), [("false", False), ("true", True)])
def test_compose_demo_profile_is_only_enabled_explicitly(
    tmp_path: Path, demo_enabled: str, expects_profile: bool
) -> None:
    wrapper = render_wrapper(tmp_path)
    write_release_env(tmp_path, demo_enabled=demo_enabled)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "docker.log"
    docker = bin_dir / "docker"
    docker.write_text(
        """#!/bin/sh
set -eu
printf '%s\n' "$*" >> "$DOCKER_LOG"
case "$*" in
  "compose version") exit 0 ;;
  "compose version --short") printf '2.27.0\n'; exit 0 ;;
  "info") exit 0 ;;
  *"info --format {{.Architecture}}"*) printf 'amd64\n'; exit 0 ;;
  *"info --format {{.MemTotal}}"*) printf '8589934592\n'; exit 0 ;;
  *"version --format {{.Server.Version}}"*) printf '26.1.0\n'; exit 0 ;;
"""
        + release_description_case(demo_enabled=demo_enabled)
        + """  *"release_preflight.py select-runtime"*) printf 'amd64\n'; exit 0 ;;
esac
exit 0
""",
        encoding="utf-8",
    )
    docker.chmod(0o755)
    environment = os.environ.copy()
    environment["PATH"] = f"{bin_dir}:{environment['PATH']}"
    environment["DOCKER_LOG"] = str(log)

    result = subprocess.run([wrapper, "up"], env=environment, text=True, capture_output=True)

    assert result.returncode == 0, result.stderr
    assert ("Demo Load Node: enabled" in result.stdout) is expects_profile
    assert ("Demo Load Node: disabled" in result.stdout) is not expects_profile
    compose_commands = [
        line
        for line in log.read_text(encoding="utf-8").splitlines()
        if line.startswith("compose --env-file")
    ]
    assert compose_commands
    assert all(("--profile demo" in line) is expects_profile for line in compose_commands)
    assert all("docker-compose.external-node.yml" not in line for line in compose_commands)
