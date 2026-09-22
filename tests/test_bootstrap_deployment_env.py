from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

import pytest
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import bootstrap_deployment_env as bootstrap_env  # noqa: E402


ENV_EXAMPLE = ROOT / ".env.example"
SCRIPT = ROOT / "scripts" / "bootstrap_deployment_env.py"
TOKEN_RELATIVE_PATH = Path(".surgepilot/secrets/influxdb-token.secret")
DEMO_PASSWORD_RELATIVE_PATH = Path(".surgepilot/secrets/demo-load-node-password.secret")
DEMO_PRIVATE_KEY_RELATIVE_PATH = Path(".surgepilot/demo-load-node/ssh_host_ed25519_key")
DEMO_PUBLIC_KEY_RELATIVE_PATH = Path(".surgepilot/demo-load-node/ssh_host_ed25519_key.pub")


@dataclass(frozen=True)
class BootstrapResult:
    returncode: int
    stdout: str
    stderr: str


def run_bootstrap(
    root: Path,
    capsys: pytest.CaptureFixture[str],
    *,
    environ: dict[str, str] | None = None,
    extra_args: list[str] | None = None,
) -> BootstrapResult:
    returncode = bootstrap_env.main(
        ["--root", str(root), *(extra_args or [])],
        environ={} if environ is None else environ,
    )
    captured = capsys.readouterr()
    return BootstrapResult(returncode, captured.out, captured.err)


def prepare_root(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    (root / ".env.example").write_text(ENV_EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
    return root


def parse_env(path: Path) -> dict[str, str]:
    return {key: value for key, value in dotenv_values(path).items() if value is not None}


def file_mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def dotenv_effective_values(
    env_path: Path,
    keys: set[str],
    inherited: dict[str, str],
) -> dict[str, str]:
    command = [
        "uv",
        "run",
        "--all-packages",
        "dotenv",
        "-f",
        str(env_path),
        "run",
        "--no-override",
        "--",
        sys.executable,
        "-c",
        (
            "import json, os; "
            f"keys={sorted(keys)!r}; "
            "print(json.dumps({key: os.environ[key] for key in keys}, sort_keys=True))"
        ),
    ]
    environment = os.environ.copy()
    for key in bootstrap_env.PERSISTED_ENV_KEYS:
        environment.pop(key, None)
    environment.update(inherited)
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(result.stdout)


def test_first_run_generates_secure_deployment_configuration(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = prepare_root(tmp_path)

    result = run_bootstrap(root, capsys)

    assert result.returncode == 0, result.stderr
    env_path = root / ".env"
    token_path = root / TOKEN_RELATIVE_PATH
    demo_password_path = root / DEMO_PASSWORD_RELATIVE_PATH
    demo_private_key_path = root / DEMO_PRIVATE_KEY_RELATIVE_PATH
    demo_public_key_path = root / DEMO_PUBLIC_KEY_RELATIVE_PATH
    assert env_path.is_file()
    assert token_path.is_file()
    assert demo_password_path.is_file()
    assert demo_private_key_path.is_file()
    assert demo_public_key_path.is_file()
    assert file_mode(env_path) == 0o600
    assert file_mode(token_path) == 0o600
    assert file_mode(demo_password_path) == 0o600
    assert file_mode(demo_private_key_path) == 0o600
    assert file_mode(demo_public_key_path) == 0o600
    assert file_mode(demo_private_key_path.parent) == 0o700
    assert file_mode(token_path.parent) == 0o700
    values = parse_env(env_path)
    assert len(values["RUNNER_INTERNAL_TOKEN"]) == 64
    assert bytes.fromhex(values["RUNNER_INTERNAL_TOKEN"])
    assert len(base64.b64decode(values["SSH_CREDENTIAL_ENCRYPTION_KEY"], validate=True)) == 32
    assert values["MINIO_SECRET_KEY"] == values["MINIO_ROOT_PASSWORD"]
    assert values["COMPOSE_PROJECT_NAME"] == "surgepilot"
    assert values["SURGEPILOT_DEMO_LOAD_NODE_ENABLED"] == "true"
    assert values["SURGEPILOT_RUNTIME_ARCHITECTURES"] == "auto"
    assert demo_password_path.read_text(encoding="utf-8").strip()
    assert demo_private_key_path.read_text(encoding="utf-8").startswith("-----BEGIN OPENSSH")
    assert demo_public_key_path.read_text(encoding="utf-8").startswith("ssh-ed25519 ")
    assert values["MINIO_SECRET_KEY"] != "replace-with-minio-password"
    assert values["SURGEPILOT_MONITORING_INFLUXDB_PASSWORD"] != "replace-with-influxdb-password"
    assert (
        values["SURGEPILOT_MONITORING_INFLUXDB_TOKEN_FILE_HOST"]
        == "../../.surgepilot/secrets/influxdb-token.secret"
    )
    assert token_path.read_text(encoding="utf-8").strip()
    assert "replace-with-" not in env_path.read_text(encoding="utf-8")


def test_release_bootstrap_reads_payload_from_release_root_and_writes_deployment_root(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    release_root = prepare_release_root(tmp_path)
    deployment_root = tmp_path / "deployment"
    deployment_root.mkdir()

    result = run_bootstrap(
        release_root,
        capsys,
        extra_args=["--deployment-root", str(deployment_root), *release_bootstrap_args()],
    )

    assert result.returncode == 0, result.stderr
    assert (deployment_root / ".env").is_file()
    assert (deployment_root / TOKEN_RELATIVE_PATH).is_file()
    assert not (release_root / ".env").exists()
    assert not (release_root / ".surgepilot").exists()


def test_generated_influxdb_password_cannot_be_parsed_as_a_cli_flag(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = prepare_root(tmp_path)
    monkeypatch.setattr(bootstrap_env.secrets, "token_urlsafe", lambda _length: "-unsafe")

    result = run_bootstrap(root, capsys)

    assert result.returncode == 0, result.stderr
    password = parse_env(root / ".env")["SURGEPILOT_MONITORING_INFLUXDB_PASSWORD"]
    assert not password.startswith("-")


def test_existing_environment_is_never_modified(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = prepare_root(tmp_path)
    first = run_bootstrap(root, capsys)
    assert first.returncode == 0
    env_path = root / ".env"
    original = env_path.read_text(encoding="utf-8")
    env_path.chmod(0o600)

    result = run_bootstrap(root, capsys)

    assert result.returncode == 0, result.stderr
    assert env_path.read_text(encoding="utf-8") == original
    assert file_mode(env_path) == 0o600
    assert (root / TOKEN_RELATIVE_PATH).is_file()
    assert "unchanged" in result.stdout.lower()


def test_existing_generated_token_is_reused_when_env_is_absent(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = prepare_root(tmp_path)
    token_path = root / TOKEN_RELATIVE_PATH
    token_path.parent.mkdir(parents=True)
    (root / ".surgepilot").chmod(0o700)
    token_path.parent.chmod(0o700)
    token_path.write_text("stable-existing-token\n", encoding="utf-8")
    token_path.chmod(0o600)

    result = run_bootstrap(root, capsys)

    assert result.returncode == 0, result.stderr
    assert token_path.read_text(encoding="utf-8") == "stable-existing-token\n"
    assert file_mode(token_path) == 0o600
    assert parse_env(root / ".env")["SURGEPILOT_MONITORING_INFLUXDB_TOKEN_FILE_HOST"] == (
        "../../.surgepilot/secrets/influxdb-token.secret"
    )


def test_release_bundle_uses_token_path_relative_to_release_compose_directory(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "release"
    root.mkdir()
    (root / ".env.example").write_text(
        (ROOT / "infra/release/.env.example").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (root / "release-manifest.json").write_text("{}\n", encoding="utf-8")

    result = run_bootstrap(root, capsys)

    assert result.returncode == 0, result.stderr
    assert parse_env(root / ".env")["SURGEPILOT_MONITORING_INFLUXDB_TOKEN_FILE_HOST"] == (
        "../.surgepilot/secrets/influxdb-token.secret"
    )


def release_bootstrap_args(*, demo_enabled: str = "false") -> list[str]:
    return [
        "--release-http-port",
        "18080",
        "--release-node-api-base-url",
        "http://192.168.1.20:18080",
        "--release-influxdb-host-port",
        "18086",
        "--release-influxdb-node-write-url",
        "http://192.168.1.20:18086",
        "--release-demo-enabled",
        demo_enabled,
        "--release-runtime-architectures",
        "auto",
        "--session-cookie-secure",
        "false",
    ]


def prepare_release_root(tmp_path: Path) -> Path:
    root = tmp_path / "release"
    root.mkdir()
    (root / ".env.example").write_text(
        (ROOT / "infra/release/.env.example").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (root / "release-manifest.json").write_text("{}\n", encoding="utf-8")
    return root


def prepare_existing_release_environment(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> Path:
    root = prepare_release_root(tmp_path)
    result = run_bootstrap(root, capsys, extra_args=release_bootstrap_args())
    assert result.returncode == 0, result.stderr
    return root


def release_network_updates() -> dict[str, str]:
    return {
        "SURGEPILOT_HTTP_PORT": "18081",
        "SURGEPILOT_NODE_API_BASE_URL": "http://192.168.1.21:18081",
        "SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT": "18087",
        "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL": "http://192.168.1.21:18087",
    }


def env_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def release_validation_context() -> dict[str, str]:
    return {"daemon_arch": "amd64", "forced_platform": ""}


def test_reconfigure_release_network_updates_only_four_existing_assignments(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = prepare_existing_release_environment(tmp_path, capsys)
    env_path = root / ".env"
    original = env_path.read_text(encoding="utf-8")
    original_values = parse_env(env_path)

    changed = bootstrap_env.reconfigure_release_network(
        root,
        expected_sha256=env_sha256(env_path),
        updates=release_network_updates(),
        **release_validation_context(),
    )

    assert changed is True
    updated_values = parse_env(env_path)
    assert {
        key: updated_values[key] for key in bootstrap_env.RELEASE_NETWORK_KEYS
    } == release_network_updates()
    assert {
        key: value
        for key, value in updated_values.items()
        if key not in bootstrap_env.RELEASE_NETWORK_KEYS
    } == {
        key: value
        for key, value in original_values.items()
        if key not in bootstrap_env.RELEASE_NETWORK_KEYS
    }
    assert env_path.read_text(encoding="utf-8") != original
    assert file_mode(env_path) == 0o600


def test_reconfigure_release_network_validates_arm64_demo_with_actual_platform(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = prepare_release_root(tmp_path)
    args = release_bootstrap_args(demo_enabled="true")
    args[args.index("auto")] = "arm64"
    assert run_bootstrap(root, capsys, extra_args=args).returncode == 0
    env_path = root / ".env"

    changed = bootstrap_env.reconfigure_release_network(
        root,
        expected_sha256=env_sha256(env_path),
        updates=release_network_updates(),
        daemon_arch="arm64",
        forced_platform="linux/arm64/v8",
    )

    assert changed is True
    assert (
        parse_env(env_path)["SURGEPILOT_NODE_API_BASE_URL"]
        == (release_network_updates()["SURGEPILOT_NODE_API_BASE_URL"])
    )


def test_reconfigure_release_network_rejects_conflicting_forced_platform(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = prepare_release_root(tmp_path)
    args = release_bootstrap_args(demo_enabled="true")
    args[args.index("auto")] = "arm64"
    assert run_bootstrap(root, capsys, extra_args=args).returncode == 0
    env_path = root / ".env"
    original = env_path.read_bytes()

    with pytest.raises(bootstrap_env.BootstrapError, match="forced Docker platform conflicts"):
        bootstrap_env.reconfigure_release_network(
            root,
            expected_sha256=env_sha256(env_path),
            updates=release_network_updates(),
            daemon_arch="arm64",
            forced_platform="linux/amd64",
        )

    assert env_path.read_bytes() == original


@pytest.mark.parametrize("separator", ["\n", "\r\n"])
def test_reconfigure_release_network_preserves_lf_or_crlf_and_non_target_bytes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    separator: str,
) -> None:
    root = prepare_existing_release_environment(tmp_path, capsys)
    env_path = root / ".env"
    original = env_path.read_text(encoding="utf-8").replace("\n", separator)
    decorated = (
        f"# operator comment{separator}UNKNOWN_SETTING='keep this exactly'{separator}{original}"
    )
    env_path.write_bytes(decorated.encode())
    env_path.chmod(0o600)
    updates = release_network_updates()

    assert bootstrap_env.reconfigure_release_network(
        root,
        expected_sha256=env_sha256(env_path),
        updates=updates,
        **release_validation_context(),
    )

    expected = decorated
    for key, value in updates.items():
        expected = re.sub(
            rf"^{re.escape(key)}=.*?(\r?)$",
            lambda match: f"{key}={value}{match.group(1)}",
            expected,
            count=1,
            flags=re.MULTILINE,
        )
    assert env_path.read_bytes() == expected.encode()
    assert [
        line.split("=", maxsplit=1)[0]
        for line in env_path.read_text(encoding="utf-8").splitlines()
        if line.split("=", maxsplit=1)[0] in bootstrap_env.RELEASE_NETWORK_KEYS
    ] == [
        line.split("=", maxsplit=1)[0]
        for line in decorated.splitlines()
        if line.split("=", maxsplit=1)[0] in bootstrap_env.RELEASE_NETWORK_KEYS
    ]


@pytest.mark.parametrize(
    "separator",
    ["\r", "\v", "\f", "\x1c", "\x1d", "\x1e", "\x85", "\u2028", "\u2029"],
)
def test_render_release_network_update_rejects_non_lf_crlf_separators(
    separator: str,
) -> None:
    original_values = {
        "SURGEPILOT_HTTP_PORT": "18080",
        "SURGEPILOT_NODE_API_BASE_URL": "http://192.168.1.20:18080",
        "SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT": "18086",
        "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL": "http://192.168.1.20:18086",
    }
    original = separator.join(f"{key}={value}" for key, value in original_values.items())
    original += f"{separator}UNCHANGED=adjacent{separator}"

    with pytest.raises(bootstrap_env.BootstrapError, match="LF or CRLF"):
        bootstrap_env._render_release_network_update(original, release_network_updates())


def test_reconfigure_release_network_noop_does_not_replace_file(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = prepare_existing_release_environment(tmp_path, capsys)
    env_path = root / ".env"
    before = env_path.stat()
    values = parse_env(env_path)
    updates = {key: values[key] for key in bootstrap_env.RELEASE_NETWORK_KEYS}
    monkeypatch.setattr(
        bootstrap_env.os,
        "replace",
        lambda *_args: pytest.fail("no-op reconfiguration must not replace .env"),
    )

    changed = bootstrap_env.reconfigure_release_network(
        root,
        expected_sha256=env_sha256(env_path),
        updates=updates,
        **release_validation_context(),
    )

    assert changed is False
    assert env_path.stat().st_ino == before.st_ino


@pytest.mark.parametrize("unsafe_kind", ["mode", "owner", "symlink"])
def test_reconfigure_release_network_rejects_unsafe_env_file(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    unsafe_kind: str,
) -> None:
    root = prepare_existing_release_environment(tmp_path, capsys)
    env_path = root / ".env"
    expected_sha256 = env_sha256(env_path)
    if unsafe_kind == "mode":
        env_path.chmod(0o640)
    elif unsafe_kind == "owner":
        current_uid = os.geteuid()
        monkeypatch.setattr(bootstrap_env.os, "geteuid", lambda: current_uid + 1)
    else:
        external = tmp_path / "external.env"
        env_path.replace(external)
        env_path.symlink_to(external)

    with pytest.raises(bootstrap_env.BootstrapError):
        bootstrap_env.reconfigure_release_network(
            root,
            expected_sha256=expected_sha256,
            updates=release_network_updates(),
            **release_validation_context(),
        )


@pytest.mark.parametrize("assignment_kind", ["missing", "duplicate"])
def test_reconfigure_release_network_requires_one_active_assignment_per_target(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    assignment_kind: str,
) -> None:
    root = prepare_existing_release_environment(tmp_path, capsys)
    env_path = root / ".env"
    original = env_path.read_text(encoding="utf-8")
    target = "SURGEPILOT_HTTP_PORT=18080"
    if assignment_kind == "missing":
        mutated = original.replace(target, f"# {target}", 1)
    else:
        mutated = f"{target}\n{original}"
    env_path.write_text(mutated, encoding="utf-8")
    env_path.chmod(0o600)

    with pytest.raises(bootstrap_env.BootstrapError):
        bootstrap_env.reconfigure_release_network(
            root,
            expected_sha256=env_sha256(env_path),
            updates=release_network_updates(),
            **release_validation_context(),
        )

    assert env_path.read_text(encoding="utf-8") == mutated


@pytest.mark.parametrize(
    "updates",
    [
        {
            key: value
            for key, value in release_network_updates().items()
            if key != "SURGEPILOT_HTTP_PORT"
        },
        {**release_network_updates(), "RUNNER_INTERNAL_TOKEN": "not-allowed"},
    ],
)
def test_reconfigure_release_network_rejects_incomplete_or_unknown_update_keys(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    updates: dict[str, str],
) -> None:
    root = prepare_existing_release_environment(tmp_path, capsys)
    env_path = root / ".env"
    original = env_path.read_bytes()

    with pytest.raises(bootstrap_env.BootstrapError, match="exactly"):
        bootstrap_env.reconfigure_release_network(
            root,
            expected_sha256=env_sha256(env_path),
            updates=updates,
            **release_validation_context(),
        )

    assert env_path.read_bytes() == original


@pytest.mark.parametrize(
    "overrides",
    [
        {"SURGEPILOT_HTTP_PORT": "70000"},
        {"SURGEPILOT_HTTP_PORT": "18087"},
        {"SURGEPILOT_NODE_API_BASE_URL": "http://192.168.1.21:19000"},
        {"SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL": "http://192.168.1.22:18087"},
    ],
)
def test_reconfigure_release_network_rejects_invalid_url_port_combinations(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    overrides: dict[str, str],
) -> None:
    root = prepare_existing_release_environment(tmp_path, capsys)
    env_path = root / ".env"
    original = env_path.read_bytes()

    with pytest.raises(bootstrap_env.BootstrapError):
        bootstrap_env.reconfigure_release_network(
            root,
            expected_sha256=env_sha256(env_path),
            updates={**release_network_updates(), **overrides},
            **release_validation_context(),
        )

    assert env_path.read_bytes() == original


def test_reconfigure_release_network_refuses_advanced_https_state(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = prepare_existing_release_environment(tmp_path, capsys)
    env_path = root / ".env"
    advanced = env_path.read_text(encoding="utf-8")
    advanced = advanced.replace("SESSION_COOKIE_SECURE=false", "SESSION_COOKIE_SECURE=true")
    advanced = advanced.replace(
        "SURGEPILOT_NODE_API_BASE_URL=http://192.168.1.20:18080",
        "SURGEPILOT_NODE_API_BASE_URL=https://example.com:443",
    )
    advanced = advanced.replace(
        "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL=http://192.168.1.20:18086",
        "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL=https://metrics.example.com:443",
    )
    env_path.write_text(advanced, encoding="utf-8")
    env_path.chmod(0o600)

    with pytest.raises(bootstrap_env.BootstrapError, match="advanced HTTPS"):
        bootstrap_env.reconfigure_release_network(
            root,
            expected_sha256=env_sha256(env_path),
            updates=release_network_updates(),
            **release_validation_context(),
        )

    assert env_path.read_text(encoding="utf-8") == advanced


@pytest.mark.parametrize("digest_kind", ["mismatch", "uppercase", "short"])
def test_reconfigure_release_network_requires_exact_lowercase_sha256(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    digest_kind: str,
) -> None:
    root = prepare_existing_release_environment(tmp_path, capsys)
    env_path = root / ".env"
    original = env_path.read_bytes()
    digest = env_sha256(env_path)
    if digest_kind == "mismatch":
        digest = "0" * 64 if digest != "0" * 64 else "1" * 64
    elif digest_kind == "uppercase":
        digest = digest.upper()
    else:
        digest = digest[:-1]

    with pytest.raises(bootstrap_env.BootstrapError, match="SHA-256"):
        bootstrap_env.reconfigure_release_network(
            root,
            expected_sha256=digest,
            updates=release_network_updates(),
            **release_validation_context(),
        )

    assert env_path.read_bytes() == original


def test_reconfigure_release_network_rejects_final_sha_change_before_replace(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = prepare_existing_release_environment(tmp_path, capsys)
    env_path = root / ".env"
    expected_sha256 = env_sha256(env_path)
    original_mkstemp = bootstrap_env.tempfile.mkstemp
    raced = b"concurrent operator content\n"

    def racing_mkstemp(*args: object, **kwargs: object) -> tuple[int, str]:
        result = original_mkstemp(*args, **kwargs)
        env_path.write_bytes(raced)
        env_path.chmod(0o600)
        return result

    monkeypatch.setattr(bootstrap_env.tempfile, "mkstemp", racing_mkstemp)

    with pytest.raises(bootstrap_env.BootstrapError, match="changed before replacement"):
        bootstrap_env.reconfigure_release_network(
            root,
            expected_sha256=expected_sha256,
            updates=release_network_updates(),
            **release_validation_context(),
        )

    assert env_path.read_bytes() == raced
    assert not list(root.glob(".reconfigure-*"))


def test_reconfigure_release_network_uses_standard_same_directory_replace(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = prepare_existing_release_environment(tmp_path, capsys)
    env_path = root / ".env"
    original_replace = bootstrap_env.os.replace
    calls = 0

    def recording_replace(source: Path, target: Path) -> None:
        nonlocal calls
        calls += 1
        source_path = Path(source)
        assert source_path.parent == root
        assert file_mode(source_path) == 0o600
        assert Path(target) == env_path
        original_replace(source, target)

    monkeypatch.setattr(bootstrap_env.os, "replace", recording_replace)

    assert bootstrap_env.reconfigure_release_network(
        root,
        expected_sha256=env_sha256(env_path),
        updates=release_network_updates(),
        **release_validation_context(),
    )

    assert calls == 1
    assert parse_env(env_path)["SURGEPILOT_HTTP_PORT"] == "18081"
    assert not list(root.glob(".reconfigure-*"))


def test_reconfigure_release_network_validates_candidate_mode_before_replace(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = prepare_existing_release_environment(tmp_path, capsys)
    env_path = root / ".env"
    original = env_path.read_bytes()
    original_fchmod = bootstrap_env.os.fchmod

    def make_candidate_group_readable(descriptor: int, _mode: int) -> None:
        original_fchmod(descriptor, 0o640)

    monkeypatch.setattr(bootstrap_env.os, "fchmod", make_candidate_group_readable)

    with pytest.raises(bootstrap_env.BootstrapError, match="candidate.*0600"):
        bootstrap_env.reconfigure_release_network(
            root,
            expected_sha256=env_sha256(env_path),
            updates=release_network_updates(),
            **release_validation_context(),
        )

    assert env_path.read_bytes() == original
    assert not list(root.glob(".reconfigure-*"))


def test_reconfigure_release_network_validates_candidate_bytes_before_replace(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = prepare_existing_release_environment(tmp_path, capsys)
    env_path = root / ".env"
    original = env_path.read_bytes()
    original_validate = bootstrap_env._validate_reconfiguration_candidate

    def corrupt_then_validate(path: Path, *, expected_bytes: bytes) -> None:
        path.write_bytes(b"corrupted candidate\n")
        path.chmod(0o600)
        original_validate(path, expected_bytes=expected_bytes)

    monkeypatch.setattr(
        bootstrap_env,
        "_validate_reconfiguration_candidate",
        corrupt_then_validate,
    )

    with pytest.raises(bootstrap_env.BootstrapError, match="candidate bytes"):
        bootstrap_env.reconfigure_release_network(
            root,
            expected_sha256=env_sha256(env_path),
            updates=release_network_updates(),
            **release_validation_context(),
        )

    assert env_path.read_bytes() == original
    assert not list(root.glob(".reconfigure-*"))


def test_reconfiguration_candidate_requires_current_user_ownership(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = tmp_path / "candidate"
    expected = b"candidate bytes\n"
    candidate.write_bytes(expected)
    candidate.chmod(0o600)
    current_uid = os.geteuid()
    monkeypatch.setattr(bootstrap_env.os, "geteuid", lambda: current_uid + 1)

    with pytest.raises(bootstrap_env.BootstrapError, match="owned by the deployment user"):
        bootstrap_env._validate_reconfiguration_candidate(candidate, expected_bytes=expected)


def test_reconfigure_release_network_replace_failure_keeps_original_and_cleans_temp(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = prepare_existing_release_environment(tmp_path, capsys)
    env_path = root / ".env"
    original = env_path.read_bytes()

    def fail_private_same_directory_replace(source: Path, target: Path) -> None:
        source_path = Path(source)
        assert source_path.parent == root
        assert file_mode(source_path) == 0o600
        assert Path(target) == env_path
        raise OSError("simulated replace failure")

    monkeypatch.setattr(bootstrap_env.os, "replace", fail_private_same_directory_replace)

    with pytest.raises(bootstrap_env.BootstrapError, match="cannot replace deployment .env"):
        bootstrap_env.reconfigure_release_network(
            root,
            expected_sha256=env_sha256(env_path),
            updates=release_network_updates(),
            daemon_arch="amd64",
            forced_platform="",
        )

    assert env_path.read_bytes() == original
    assert not list(root.glob(".reconfigure-*"))


def test_reconfigure_release_network_reports_post_replace_fsync_failure_without_rollback(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = prepare_existing_release_environment(tmp_path, capsys)
    env_path = root / ".env"

    def fail_reconfiguration_directory_fsync(path: Path) -> None:
        assert path == root
        raise OSError("simulated directory fsync failure")

    monkeypatch.setattr(bootstrap_env, "_fsync_directory", fail_reconfiguration_directory_fsync)

    with pytest.raises(
        bootstrap_env.BootstrapError,
        match="updated but durability could not be confirmed; inspect .env",
    ):
        bootstrap_env.reconfigure_release_network(
            root,
            expected_sha256=env_sha256(env_path),
            updates=release_network_updates(),
            **release_validation_context(),
        )

    assert parse_env(env_path)["SURGEPILOT_HTTP_PORT"] == "18081"
    assert not list(root.glob(".reconfigure-*"))


def test_reconfigure_release_network_cli_failure_does_not_print_secret_values(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = prepare_existing_release_environment(tmp_path, capsys)
    env_path = root / ".env"
    sentinel = "unique-secret-must-not-be-printed"
    rendered = re.sub(
        r"^RUNNER_INTERNAL_TOKEN=.*$",
        f"RUNNER_INTERNAL_TOKEN={sentinel}",
        env_path.read_text(encoding="utf-8"),
        count=1,
        flags=re.MULTILINE,
    )
    env_path.write_text(rendered, encoding="utf-8")
    env_path.chmod(0o600)
    updates = release_network_updates()

    result = run_bootstrap(
        root,
        capsys,
        extra_args=[
            "--reconfigure-release-network",
            "--daemon-arch",
            "amd64",
            "--forced-platform",
            "",
            "--expected-env-sha256",
            "0" * 64,
            "--release-http-port",
            updates["SURGEPILOT_HTTP_PORT"],
            "--release-node-api-base-url",
            updates["SURGEPILOT_NODE_API_BASE_URL"],
            "--release-influxdb-host-port",
            updates["SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT"],
            "--release-influxdb-node-write-url",
            updates["SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL"],
        ],
    )

    assert result.returncode == 2
    assert sentinel not in result.stdout
    assert sentinel not in result.stderr


def test_reconfigure_release_network_requires_release_manifest_and_existing_env(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = prepare_existing_release_environment(tmp_path, capsys)
    env_path = root / ".env"
    digest = env_sha256(env_path)
    (root / "release-manifest.json").unlink()
    with pytest.raises(bootstrap_env.BootstrapError, match="release-manifest"):
        bootstrap_env.reconfigure_release_network(
            root,
            expected_sha256=digest,
            updates=release_network_updates(),
            **release_validation_context(),
        )

    (root / "release-manifest.json").write_text("{}\n", encoding="utf-8")
    env_path.unlink()
    with pytest.raises(bootstrap_env.BootstrapError, match="existing .env"):
        bootstrap_env.reconfigure_release_network(
            root,
            expected_sha256=digest,
            updates=release_network_updates(),
            **release_validation_context(),
        )


def test_reconfigure_release_network_cli_dispatches_only_reconfiguration(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = prepare_existing_release_environment(tmp_path, capsys)
    env_path = root / ".env"
    monkeypatch.setattr(
        bootstrap_env,
        "bootstrap",
        lambda *_args, **_kwargs: pytest.fail("reconfiguration must not run bootstrap"),
    )
    updates = release_network_updates()

    result = run_bootstrap(
        root,
        capsys,
        extra_args=[
            "--reconfigure-release-network",
            "--daemon-arch",
            "amd64",
            "--forced-platform",
            "",
            "--expected-env-sha256",
            env_sha256(env_path),
            "--release-http-port",
            updates["SURGEPILOT_HTTP_PORT"],
            "--release-node-api-base-url",
            updates["SURGEPILOT_NODE_API_BASE_URL"],
            "--release-influxdb-host-port",
            updates["SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT"],
            "--release-influxdb-node-write-url",
            updates["SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL"],
        ],
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "Updated release network configuration in .env.\n"


def test_reconfigure_release_network_cli_reports_unchanged_without_replacing(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = prepare_existing_release_environment(tmp_path, capsys)
    env_path = root / ".env"
    values = parse_env(env_path)
    monkeypatch.setattr(
        bootstrap_env.os,
        "replace",
        lambda *_args: pytest.fail("unchanged CLI request must not replace .env"),
    )

    result = run_bootstrap(
        root,
        capsys,
        extra_args=[
            "--reconfigure-release-network",
            "--daemon-arch",
            "amd64",
            "--forced-platform",
            "",
            "--expected-env-sha256",
            env_sha256(env_path),
            "--release-http-port",
            values["SURGEPILOT_HTTP_PORT"],
            "--release-node-api-base-url",
            values["SURGEPILOT_NODE_API_BASE_URL"],
            "--release-influxdb-host-port",
            values["SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT"],
            "--release-influxdb-node-write-url",
            values["SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL"],
        ],
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "Release network configuration is unchanged.\n"


@pytest.mark.parametrize(
    "extra_args",
    [
        [
            "--reconfigure-release-network",
            "--daemon-arch",
            "amd64",
            "--forced-platform",
            "",
            "--expected-env-sha256",
            "0" * 64,
        ],
        ["--expected-env-sha256", "0" * 64],
        [
            "--reconfigure-release-network",
            "--daemon-arch",
            "amd64",
            "--forced-platform",
            "",
            *release_bootstrap_args(),
        ],
    ],
)
def test_reconfigure_release_network_cli_rejects_partial_or_mixed_modes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    extra_args: list[str],
) -> None:
    root = prepare_release_root(tmp_path)

    result = run_bootstrap(root, capsys, extra_args=extra_args)

    assert result.returncode == 2
    assert not (root / ".env").exists()


def test_release_first_run_persists_explicit_lan_values_without_demo_state(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = prepare_release_root(tmp_path)

    result = run_bootstrap(root, capsys, extra_args=release_bootstrap_args())

    assert result.returncode == 0, result.stderr
    values = parse_env(root / ".env")
    assert values["SURGEPILOT_HTTP_PORT"] == "18080"
    assert values["SURGEPILOT_NODE_API_BASE_URL"] == "http://192.168.1.20:18080"
    assert values["SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT"] == "18086"
    assert values["SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL"] == "http://192.168.1.20:18086"
    assert values["SURGEPILOT_DEMO_LOAD_NODE_ENABLED"] == "false"
    assert values["SURGEPILOT_RUNTIME_ARCHITECTURES"] == "auto"
    assert values["SESSION_COOKIE_SECURE"] == "false"
    assert file_mode(root / ".env") == 0o600
    assert not (root / DEMO_PASSWORD_RELATIVE_PATH).exists()
    assert not (root / DEMO_PRIVATE_KEY_RELATIVE_PATH).exists()
    assert not (root / DEMO_PUBLIC_KEY_RELATIVE_PATH).exists()


def test_release_first_run_creates_demo_state_only_when_explicitly_enabled(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = prepare_release_root(tmp_path)

    result = run_bootstrap(root, capsys, extra_args=release_bootstrap_args(demo_enabled="true"))

    assert result.returncode == 0, result.stderr
    assert parse_env(root / ".env")["SURGEPILOT_DEMO_LOAD_NODE_ENABLED"] == "true"
    assert (root / DEMO_PASSWORD_RELATIVE_PATH).is_file()
    assert (root / DEMO_PRIVATE_KEY_RELATIVE_PATH).is_file()
    assert (root / DEMO_PUBLIC_KEY_RELATIVE_PATH).is_file()


def test_release_bootstrap_requires_all_explicit_arguments(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = prepare_release_root(tmp_path)

    result = run_bootstrap(
        root,
        capsys,
        extra_args=["--release-http-port", "18080"],
    )

    assert result.returncode == 2
    assert "release bootstrap arguments must be supplied together" in result.stderr
    assert not (root / ".env").exists()


def test_release_bootstrap_rejects_non_strict_demo_boolean(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = prepare_release_root(tmp_path)

    result = run_bootstrap(
        root,
        capsys,
        extra_args=release_bootstrap_args(demo_enabled="yes"),
    )

    assert result.returncode == 2
    assert "SURGEPILOT_DEMO_LOAD_NODE_ENABLED must be true or false" in result.stderr
    assert not (root / ".env").exists()


def test_existing_release_environment_rejects_unexpanded_secret_placeholder(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = prepare_release_root(tmp_path)
    assert run_bootstrap(root, capsys, extra_args=release_bootstrap_args()).returncode == 0
    env_path = root / ".env"
    rendered = env_path.read_text(encoding="utf-8")
    rendered = re.sub(
        r"^SSH_CREDENTIAL_ENCRYPTION_KEY=.*$",
        "SSH_CREDENTIAL_ENCRYPTION_KEY=replace-with-base64-32-byte-key",
        rendered,
        flags=re.MULTILINE,
    )
    env_path.write_text(rendered, encoding="utf-8")
    env_path.chmod(0o600)

    result = run_bootstrap(root, capsys)

    assert result.returncode == 2
    assert "SSH_CREDENTIAL_ENCRYPTION_KEY still uses a template placeholder" in result.stderr


def test_source_demo_state_is_preserved_when_source_env_disables_demo(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = prepare_root(tmp_path)
    template_path = root / ".env.example"
    template_path.write_text(
        template_path.read_text(encoding="utf-8").replace(
            "SURGEPILOT_DEMO_LOAD_NODE_ENABLED=true",
            "SURGEPILOT_DEMO_LOAD_NODE_ENABLED=false",
        ),
        encoding="utf-8",
    )

    result = run_bootstrap(root, capsys)

    assert result.returncode == 0, result.stderr
    assert (root / DEMO_PASSWORD_RELATIVE_PATH).is_file()
    assert (root / DEMO_PRIVATE_KEY_RELATIVE_PATH).is_file()
    assert (root / DEMO_PUBLIC_KEY_RELATIVE_PATH).is_file()


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("SURGEPILOT_NODE_API_BASE_URL", "http://192.168.1.20:8080"),
        ("SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL", "http://192.168.1.20:8086"),
        ("SESSION_COOKIE_SECURE", "false"),
    ],
)
def test_existing_source_environment_ignores_release_only_process_values(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    key: str,
    value: str,
) -> None:
    root = prepare_root(tmp_path)
    assert run_bootstrap(root, capsys).returncode == 0
    original = (root / ".env").read_text(encoding="utf-8")

    result = run_bootstrap(root, capsys, environ={key: value})

    assert result.returncode == 0, result.stderr
    assert (root / ".env").read_text(encoding="utf-8") == original


def test_existing_release_environment_rejects_conflicting_explicit_bootstrap_values(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = prepare_release_root(tmp_path)
    assert run_bootstrap(root, capsys, extra_args=release_bootstrap_args()).returncode == 0
    original = (root / ".env").read_text(encoding="utf-8")
    conflicting = release_bootstrap_args()
    conflicting[1] = "28080"

    result = run_bootstrap(root, capsys, extra_args=conflicting)

    assert result.returncode == 2
    assert "conflicts with existing .env" in result.stderr
    assert (root / ".env").read_text(encoding="utf-8") == original


def test_generated_secrets_are_not_printed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = prepare_root(tmp_path)

    result = run_bootstrap(root, capsys)

    values = parse_env(root / ".env")
    output = result.stdout + result.stderr
    for key in (
        "RUNNER_INTERNAL_TOKEN",
        "SSH_CREDENTIAL_ENCRYPTION_KEY",
        "MINIO_SECRET_KEY",
        "SURGEPILOT_MONITORING_INFLUXDB_PASSWORD",
    ):
        assert values[key] not in output
    assert (root / TOKEN_RELATIVE_PATH).read_text(encoding="utf-8").strip() not in output
    assert (root / DEMO_PASSWORD_RELATIVE_PATH).read_text(encoding="utf-8").strip() not in output


def test_demo_identity_is_unique_per_installation_and_stable_on_reuse(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    first_base = tmp_path / "first"
    second_base = tmp_path / "second"
    first_base.mkdir()
    second_base.mkdir()
    first = prepare_root(first_base)
    second = prepare_root(second_base)

    assert run_bootstrap(first, capsys).returncode == 0
    first_password = (first / DEMO_PASSWORD_RELATIVE_PATH).read_bytes()
    first_private_key = (first / DEMO_PRIVATE_KEY_RELATIVE_PATH).read_bytes()
    first_public_key = (first / DEMO_PUBLIC_KEY_RELATIVE_PATH).read_bytes()

    assert run_bootstrap(first, capsys).returncode == 0
    assert (first / DEMO_PASSWORD_RELATIVE_PATH).read_bytes() == first_password
    assert (first / DEMO_PRIVATE_KEY_RELATIVE_PATH).read_bytes() == first_private_key
    assert (first / DEMO_PUBLIC_KEY_RELATIVE_PATH).read_bytes() == first_public_key

    assert run_bootstrap(second, capsys).returncode == 0
    assert (second / DEMO_PASSWORD_RELATIVE_PATH).read_bytes() != first_password
    assert (second / DEMO_PRIVATE_KEY_RELATIVE_PATH).read_bytes() != first_private_key
    assert (second / DEMO_PUBLIC_KEY_RELATIVE_PATH).read_bytes() != first_public_key


def test_partial_demo_identity_is_rejected_without_overwrite(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = prepare_root(tmp_path)
    key_dir = root / DEMO_PRIVATE_KEY_RELATIVE_PATH.parent
    key_dir.mkdir(parents=True)
    (root / ".surgepilot").chmod(0o700)
    key_dir.chmod(0o700)
    private_key = root / DEMO_PRIVATE_KEY_RELATIVE_PATH
    private_key.write_text("existing-private-key\n", encoding="utf-8")
    private_key.chmod(0o600)

    result = run_bootstrap(root, capsys)

    assert result.returncode == 2
    assert "Demo Load Node SSH identity is incomplete" in result.stderr
    assert private_key.read_text(encoding="utf-8") == "existing-private-key\n"
    assert not (root / DEMO_PUBLIC_KEY_RELATIVE_PATH).exists()
    assert not (root / ".env").exists()


def test_missing_template_fails_without_partial_environment(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "repo"
    root.mkdir()

    result = run_bootstrap(root, capsys)

    assert result.returncode != 0
    assert ".env.example" in result.stderr
    assert not (root / ".env").exists()
    assert not (root / TOKEN_RELATIVE_PATH).exists()


def test_invalid_private_state_path_fails_without_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = prepare_root(tmp_path)
    (root / ".surgepilot").write_text("not-a-directory\n", encoding="utf-8")

    result = run_bootstrap(root, capsys)

    assert result.returncode == 2
    assert "cannot prepare private deployment state" in result.stderr
    assert "Traceback" not in result.stderr
    assert not (root / ".env").exists()


def test_private_file_is_not_published_when_atomic_install_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    private_dir = tmp_path / "private"
    private_dir.mkdir(mode=0o700)
    target = tmp_path / "secret"
    fsync_calls: list[int] = []

    monkeypatch.setattr(bootstrap_env.os, "fsync", fsync_calls.append)

    def fail_install(source: str | bytes | Path, destination: str | bytes | Path) -> None:
        assert Path(destination) == target
        assert not target.exists()
        assert Path(source).read_text(encoding="utf-8") == "secret-value\n"
        raise OSError("atomic install failed")

    monkeypatch.setattr(bootstrap_env.os, "link", fail_install)

    with pytest.raises(OSError, match="atomic install failed"):
        bootstrap_env._write_private_file(
            target,
            "secret-value\n",
            temporary_directory=private_dir,
        )

    assert fsync_calls
    assert not target.exists()
    assert list(private_dir.iterdir()) == []


def test_malformed_template_fails_before_creating_private_state(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = prepare_root(tmp_path)
    template_path = root / ".env.example"
    template_path.write_text(
        template_path.read_text(encoding="utf-8").replace(
            "replace-with-random-runner-token", "missing-placeholder"
        ),
        encoding="utf-8",
    )

    result = run_bootstrap(root, capsys)

    assert result.returncode == 2
    assert "must contain 1 occurrence" in result.stderr
    assert not (root / ".env").exists()
    assert not (root / ".surgepilot").exists()


def test_non_file_monitoring_token_path_is_rejected(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = prepare_root(tmp_path)
    token_path = root / TOKEN_RELATIVE_PATH
    token_path.mkdir(parents=True)
    (root / ".surgepilot").chmod(0o700)
    token_path.parent.chmod(0o700)

    result = run_bootstrap(root, capsys)

    assert result.returncode == 2
    assert "Monitoring token file is not a regular file" in result.stderr
    assert not (root / ".env").exists()


def test_monitoring_token_write_failure_is_reported(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = prepare_root(tmp_path)

    def fail_write(*_args: object, **_kwargs: object) -> None:
        raise OSError("token disk failure")

    monkeypatch.setattr(bootstrap_env, "_write_private_file", fail_write)

    result = run_bootstrap(root, capsys)

    assert result.returncode == 2
    assert "cannot create Monitoring token file" in result.stderr
    assert not (root / ".env").exists()


def test_concurrent_env_creation_preserves_the_winner(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = prepare_root(tmp_path)
    original_write = bootstrap_env._write_private_file

    def race_write(
        path: Path,
        content: str,
        *,
        temporary_directory: Path,
    ) -> None:
        if path.name == ".env":
            path.write_text(f"{content}\nRACE_WINNER=keep\n", encoding="utf-8")
            path.chmod(0o600)
            raise FileExistsError(path)
        original_write(path, content, temporary_directory=temporary_directory)

    monkeypatch.setattr(bootstrap_env, "_write_private_file", race_write)

    result = run_bootstrap(root, capsys)

    assert result.returncode == 0
    assert "RACE_WINNER=keep" in (root / ".env").read_text(encoding="utf-8")
    assert "unchanged" in result.stdout.lower()


def test_env_write_failure_is_reported(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = prepare_root(tmp_path)
    original_write = bootstrap_env._write_private_file

    def fail_env_write(
        path: Path,
        content: str,
        *,
        temporary_directory: Path,
    ) -> None:
        if path.name == ".env":
            raise OSError("env disk failure")
        original_write(path, content, temporary_directory=temporary_directory)

    monkeypatch.setattr(bootstrap_env, "_write_private_file", fail_env_write)

    result = run_bootstrap(root, capsys)

    assert result.returncode == 2
    assert "cannot create" in result.stderr
    assert "env disk failure" in result.stderr
    assert not (root / ".env").exists()


def test_concurrent_first_run_accepts_safely_created_winners(tmp_path: Path) -> None:
    root = prepare_root(tmp_path)
    processes = [
        subprocess.Popen(
            [sys.executable, str(SCRIPT), "--root", str(root)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={},
        )
        for _ in range(16)
    ]

    results = [process.communicate(timeout=15) + (process.returncode,) for process in processes]

    failures = [result for result in results if result[2] != 0]
    assert failures == []
    assert (root / ".env").is_file()
    token_path = root / TOKEN_RELATIVE_PATH
    assert token_path.is_file()
    assert token_path.read_text(encoding="utf-8").strip()
    assert not list(token_path.parent.glob(".bootstrap-*"))


def test_inherited_persistent_values_are_written_for_future_restarts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = prepare_root(tmp_path)
    ssh_key = base64.b64encode(b"s" * 32).decode("ascii")
    inherited = {
        "RUNNER_INTERNAL_TOKEN": "outer'runner token",
        "SSH_CREDENTIAL_ENCRYPTION_KEY": ssh_key,
        "MINIO_ACCESS_KEY": "outer-minio-user",
        "MINIO_ROOT_USER": "outer-minio-user",
        "MINIO_SECRET_KEY": "outer-minio-password",
        "MINIO_ROOT_PASSWORD": "outer-minio-password",
        "SURGEPILOT_MONITORING_INFLUXDB_USERNAME": "outer-influx-user",
        "SURGEPILOT_MONITORING_INFLUXDB_PASSWORD": "outer !nflux $password\\value",
        "SURGEPILOT_MONITORING_INFLUXDB_TOKEN_FILE_HOST": "/tmp/outer-influx-token",
        "SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT": "18086",
    }
    result = run_bootstrap(root, capsys, environ=inherited)

    assert result.returncode == 0, result.stderr
    persisted = parse_env(root / ".env")
    for key, value in inherited.items():
        assert persisted[key] == value
    assert not (root / TOKEN_RELATIVE_PATH).exists()

    inherited_keys = set(inherited)
    assert dotenv_effective_values(root / ".env", inherited_keys, inherited) == inherited
    assert dotenv_effective_values(root / ".env", inherited_keys, {}) == inherited

    repeated = run_bootstrap(root, capsys, environ=inherited)
    assert repeated.returncode == 0
    restart = run_bootstrap(root, capsys)
    assert restart.returncode == 0
    assert parse_env(root / ".env") == persisted


@pytest.mark.parametrize(
    "key",
    [
        "SURGEPILOT_MONITORING_INFLUXDB_USERNAME",
        "SURGEPILOT_MONITORING_INFLUXDB_PASSWORD",
        "SURGEPILOT_MONITORING_INFLUXDB_ORG",
        "SURGEPILOT_MONITORING_INFLUXDB_BUCKET",
    ],
)
def test_inherited_influxdb_init_values_cannot_be_parsed_as_cli_flags(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    key: str,
) -> None:
    root = prepare_root(tmp_path)

    result = run_bootstrap(root, capsys, environ={key: "-unsafe"})

    assert result.returncode == 2
    assert key in result.stderr
    assert "must not start with '-'" in result.stderr
    assert not (root / ".env").exists()


@pytest.mark.parametrize(
    "key",
    [
        "SURGEPILOT_MONITORING_INFLUXDB_USERNAME",
        "SURGEPILOT_MONITORING_INFLUXDB_PASSWORD",
        "SURGEPILOT_MONITORING_INFLUXDB_ORG",
        "SURGEPILOT_MONITORING_INFLUXDB_BUCKET",
    ],
)
def test_existing_influxdb_init_values_cannot_be_parsed_as_cli_flags(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    key: str,
) -> None:
    root = prepare_root(tmp_path)
    assert run_bootstrap(root, capsys).returncode == 0
    env_path = root / ".env"
    original = env_path.read_text(encoding="utf-8")
    current_value = parse_env(env_path)[key]
    unsafe = original.replace(f"{key}={current_value}", f"{key}=-unsafe", 1)
    assert unsafe != original
    env_path.write_text(unsafe, encoding="utf-8")

    result = run_bootstrap(root, capsys)

    assert result.returncode == 2
    assert key in result.stderr
    assert "must not start with '-'" in result.stderr
    assert env_path.read_text(encoding="utf-8") == unsafe


def test_conflicting_inherited_minio_identity_fails_before_env_creation(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = prepare_root(tmp_path)

    result = run_bootstrap(
        root,
        capsys,
        environ={
            "MINIO_ACCESS_KEY": "client-user",
            "MINIO_ROOT_USER": "different-root-user",
        },
    )

    assert result.returncode == 2
    assert "MINIO_ACCESS_KEY must match MINIO_ROOT_USER" in result.stderr
    assert not (root / ".env").exists()


@pytest.mark.parametrize("token_kind", ["empty", "symlink", "unreadable"])
def test_invalid_existing_monitoring_token_is_rejected(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    token_kind: str,
) -> None:
    root = prepare_root(tmp_path)
    token_path = root / TOKEN_RELATIVE_PATH
    token_path.parent.mkdir(parents=True)
    (root / ".surgepilot").chmod(0o700)
    token_path.parent.chmod(0o700)
    if token_kind == "empty":
        token_path.write_text("", encoding="utf-8")
        token_path.chmod(0o600)
    elif token_kind == "symlink":
        external = tmp_path / "external-token"
        external.write_text("external-secret\n", encoding="utf-8")
        token_path.symlink_to(external)
    else:
        token_path.write_text("unreadable-secret\n", encoding="utf-8")
        token_path.chmod(0o000)

    result = run_bootstrap(root, capsys)

    assert result.returncode == 2
    assert "Monitoring token" in result.stderr
    assert not (root / ".env").exists()


@pytest.mark.parametrize(
    ("key", "conflicting_value"),
    [
        ("RUNNER_INTERNAL_TOKEN", "different-runner-token"),
        (
            "SSH_CREDENTIAL_ENCRYPTION_KEY",
            base64.b64encode(b"d" * 32).decode("ascii"),
        ),
    ],
)
def test_existing_environment_rejects_conflicting_persistent_credentials(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    key: str,
    conflicting_value: str,
) -> None:
    root = prepare_root(tmp_path)
    first = run_bootstrap(root, capsys)
    assert first.returncode == 0
    original = (root / ".env").read_text(encoding="utf-8")

    conflict = run_bootstrap(root, capsys, environ={key: conflicting_value})

    assert conflict.returncode == 2
    assert f"inherited {key} conflicts with existing .env" in conflict.stderr
    assert (root / ".env").read_text(encoding="utf-8") == original


def test_existing_environment_rejects_one_sided_minio_password_override(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = prepare_root(tmp_path)
    first = run_bootstrap(root, capsys)
    assert first.returncode == 0

    conflict = run_bootstrap(
        root,
        capsys,
        environ={"MINIO_SECRET_KEY": "different-minio-password"},
    )

    assert conflict.returncode == 2
    assert "inherited MINIO_SECRET_KEY conflicts with existing .env" in conflict.stderr


def test_concurrent_distinct_inherited_credentials_allow_only_the_env_winner(
    tmp_path: Path,
) -> None:
    root = prepare_root(tmp_path)
    processes = []
    for index in range(16):
        inherited = {"RUNNER_INTERNAL_TOKEN": f"runner-token-{index}"}
        processes.append(
            subprocess.Popen(
                [sys.executable, str(SCRIPT), "--root", str(root)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=inherited,
            )
        )

    results = [process.communicate(timeout=15) + (process.returncode,) for process in processes]

    successes = [result for result in results if result[2] == 0]
    failures = [result for result in results if result[2] != 0]
    assert len(successes) == 1
    assert len(failures) == 15
    assert all("conflicts with existing .env" in stderr for _stdout, stderr, _code in failures)
    persisted = parse_env(root / ".env")["RUNNER_INTERNAL_TOKEN"]
    assert persisted in {f"runner-token-{index}" for index in range(16)}


@pytest.mark.parametrize("value", ["", "unsafe\nvalue"])
def test_inherited_environment_rejects_empty_or_multiline_values(value: str) -> None:
    with pytest.raises(bootstrap_env.BootstrapError, match="must not be empty|NUL or newline"):
        bootstrap_env._encode_environment_value("RUNNER_INTERNAL_TOKEN", value)


def test_required_environment_value_reports_missing_key() -> None:
    with pytest.raises(bootstrap_env.BootstrapError, match="missing required MINIO_ACCESS_KEY"):
        bootstrap_env._required_environment_value({}, "MINIO_ACCESS_KEY")


def test_minio_secret_pair_must_match() -> None:
    with pytest.raises(bootstrap_env.BootstrapError, match="MINIO_SECRET_KEY"):
        bootstrap_env._validate_minio_pairs(
            {
                "MINIO_ACCESS_KEY": "surgepilot",
                "MINIO_ROOT_USER": "surgepilot",
                "MINIO_SECRET_KEY": "client-secret",
                "MINIO_ROOT_PASSWORD": "root-secret",
            }
        )


@pytest.mark.parametrize("nested", [False, True])
def test_secret_state_rejects_symbolic_link_directories(tmp_path: Path, nested: bool) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    external = tmp_path / "external"
    external.mkdir()
    if nested:
        state = root / ".surgepilot"
        state.mkdir()
        state.chmod(0o700)
        (state / "secrets").symlink_to(external, target_is_directory=True)
    else:
        (root / ".surgepilot").symlink_to(external, target_is_directory=True)

    with pytest.raises(NotADirectoryError, match="not a directory"):
        bootstrap_env._ensure_secret_directory(root)


@pytest.mark.parametrize("kind", ["symlink", "directory", "empty"])
def test_private_text_validation_rejects_unsafe_files(tmp_path: Path, kind: str) -> None:
    path = tmp_path / "private-state"
    if kind == "symlink":
        target = tmp_path / "target"
        target.write_text("secret\n", encoding="utf-8")
        path.symlink_to(target)
    elif kind == "directory":
        path.mkdir()
    else:
        path.write_text("\n", encoding="utf-8")

    with pytest.raises(bootstrap_env.BootstrapError):
        bootstrap_env._validate_private_text_file(path, label="private state")


@pytest.mark.parametrize(
    ("kind", "message"),
    [
        ("unsafe-directory", "identity path is unsafe"),
        ("missing", "identity is missing"),
        ("private-format", "private key is not OpenSSH format"),
        ("public-format", "public key is not Ed25519"),
    ],
)
def test_demo_identity_validation_rejects_invalid_state(
    tmp_path: Path, kind: str, message: str
) -> None:
    directory = tmp_path / "identity"
    if kind == "unsafe-directory":
        directory.write_text("not a directory\n", encoding="utf-8")
    else:
        directory.mkdir()
        directory.chmod(0o700)
        if kind != "missing":
            private_key = directory / bootstrap_env.DEMO_PRIVATE_KEY_NAME
            public_key = directory / bootstrap_env.DEMO_PUBLIC_KEY_NAME
            private_key.write_text(
                "invalid\n"
                if kind == "private-format"
                else "-----BEGIN OPENSSH PRIVATE KEY-----\n",
                encoding="utf-8",
            )
            public_key.write_text(
                "invalid\n" if kind == "public-format" else "ssh-ed25519 AAAATEST\n",
                encoding="utf-8",
            )
            private_key.chmod(0o600)
            public_key.chmod(0o600)

    with pytest.raises(bootstrap_env.BootstrapError, match=message):
        bootstrap_env._validate_demo_identity(directory)


def test_demo_identity_generation_failure_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    state = root / ".surgepilot"
    state.mkdir(parents=True)
    monkeypatch.setattr(
        bootstrap_env.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 1, "", "keygen failed"),
    )

    with pytest.raises(bootstrap_env.BootstrapError, match="keygen failed"):
        bootstrap_env._ensure_demo_identity(root)

    assert not list(state.glob(".demo-load-node-*"))


@pytest.mark.parametrize("failure", ["password", "identity"])
def test_demo_state_wraps_filesystem_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    root = tmp_path / "repo"
    secret_directory = root / ".surgepilot" / "secrets"
    secret_directory.mkdir(parents=True)
    (root / ".surgepilot").chmod(0o700)
    secret_directory.chmod(0o700)
    if failure == "password":
        monkeypatch.setattr(
            bootstrap_env,
            "_write_private_file",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("password disk failure")),
        )
        expected = "cannot create Demo Load Node password file"
    else:
        password = root / DEMO_PASSWORD_RELATIVE_PATH
        password.write_text("stable-password\n", encoding="utf-8")
        password.chmod(0o600)
        monkeypatch.setattr(
            bootstrap_env,
            "_ensure_demo_identity",
            lambda _root: (_ for _ in ()).throw(OSError("identity disk failure")),
        )
        expected = "cannot prepare Demo Load Node SSH identity"

    with pytest.raises(bootstrap_env.BootstrapError, match=expected):
        bootstrap_env._ensure_demo_state(root, secret_directory)


def test_existing_environment_private_state_failure_is_reported(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = prepare_root(tmp_path)
    (root / ".env").write_text("existing=true\n", encoding="utf-8")
    (root / ".env").chmod(0o600)
    (root / ".surgepilot").write_text("not-a-directory\n", encoding="utf-8")

    result = run_bootstrap(root, capsys)

    assert result.returncode == 2
    assert "cannot prepare private deployment state" in result.stderr


def test_concurrent_monitoring_token_creation_accepts_winner(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = prepare_root(tmp_path)
    original_write = bootstrap_env._write_private_file

    def race_token_write(
        path: Path,
        content: str,
        *,
        temporary_directory: Path,
    ) -> None:
        if path.name == bootstrap_env.TOKEN_RELATIVE_PATH.name:
            path.write_text("winner-token\n", encoding="utf-8")
            path.chmod(0o600)
            raise FileExistsError(path)
        original_write(path, content, temporary_directory=temporary_directory)

    monkeypatch.setattr(bootstrap_env, "_write_private_file", race_token_write)

    result = run_bootstrap(root, capsys)

    assert result.returncode == 0, result.stderr
    assert (root / TOKEN_RELATIVE_PATH).read_text(encoding="utf-8") == "winner-token\n"


@pytest.mark.parametrize(
    "relative_path",
    [
        Path(".env"),
        TOKEN_RELATIVE_PATH,
        DEMO_PASSWORD_RELATIVE_PATH,
        DEMO_PRIVATE_KEY_RELATIVE_PATH,
    ],
)
def test_existing_private_state_rejects_group_readable_files(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    relative_path: Path,
) -> None:
    root = prepare_root(tmp_path)
    assert run_bootstrap(root, capsys).returncode == 0
    (root / relative_path).chmod(0o640)

    result = run_bootstrap(root, capsys)

    assert result.returncode == 2
    assert "owner-only permissions" in result.stderr


def test_existing_private_state_rejects_group_accessible_directory(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = prepare_root(tmp_path)
    assert run_bootstrap(root, capsys).returncode == 0
    (root / ".surgepilot").chmod(0o750)

    result = run_bootstrap(root, capsys)

    assert result.returncode == 2
    assert "owner-only permissions" in result.stderr


def test_private_state_rejects_different_owner() -> None:
    metadata = os.stat_result(
        (stat.S_IFREG | 0o600, 0, 0, 1, os.geteuid() + 1, os.getegid(), 1, 0, 0, 0)
    )

    with pytest.raises(bootstrap_env.BootstrapError, match="current deployment user"):
        bootstrap_env._validate_owner_only(metadata, label="private state")
