"""Create secure first-run deployment configuration for official Make startup."""

from __future__ import annotations

import argparse
import base64
from collections.abc import Mapping
import errno
import hashlib
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import sys
import tempfile


ENV_TEMPLATE_NAME = ".env.example"
ENV_NAME = ".env"
TOKEN_RELATIVE_PATH = Path(".surgepilot/secrets/influxdb-token.secret")
DEMO_PASSWORD_RELATIVE_PATH = Path(".surgepilot/secrets/demo-load-node-password.secret")
DEMO_KEY_DIRECTORY_RELATIVE_PATH = Path(".surgepilot/demo-load-node")
DEMO_PRIVATE_KEY_NAME = "ssh_host_ed25519_key"
DEMO_PUBLIC_KEY_NAME = "ssh_host_ed25519_key.pub"
COMPOSE_TOKEN_PATH = "../../.surgepilot/secrets/influxdb-token.secret"
RELEASE_COMPOSE_TOKEN_PATH = "../.surgepilot/secrets/influxdb-token.secret"
PERSISTED_ENV_KEYS = frozenset(
    {
        "COMPOSE_PROJECT_NAME",
        "DEFAULT_WORKSPACE_NAME",
        "SURGEPILOT_HTTP_PORT",
        "SURGEPILOT_DEMO_LOAD_NODE_ENABLED",
        "SURGEPILOT_RUNTIME_ARCHITECTURES",
        "RUNNER_INTERNAL_TOKEN",
        "SSH_CREDENTIAL_ENCRYPTION_KEY",
        "MINIO_BUCKET",
        "MINIO_ACCESS_KEY",
        "MINIO_SECRET_KEY",
        "MINIO_ROOT_USER",
        "MINIO_ROOT_PASSWORD",
        "SURGEPILOT_MONITORING_INFLUXDB_USERNAME",
        "SURGEPILOT_MONITORING_INFLUXDB_PASSWORD",
        "SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT",
        "SURGEPILOT_MONITORING_INFLUXDB_TOKEN_FILE_HOST",
        "SURGEPILOT_MONITORING_INFLUXDB_ORG",
        "SURGEPILOT_MONITORING_INFLUXDB_BUCKET",
        "SURGEPILOT_GRAFANA_ADMIN_USER",
    }
)
RELEASE_PERSISTED_ENV_KEYS = PERSISTED_ENV_KEYS | {
    "SURGEPILOT_NODE_API_BASE_URL",
    "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL",
    "SESSION_COOKIE_SECURE",
}
RELEASE_NETWORK_KEYS = (
    "SURGEPILOT_HTTP_PORT",
    "SURGEPILOT_NODE_API_BASE_URL",
    "SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT",
    "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL",
)
INFLUXDB_INIT_CLI_ENV_KEYS = (
    "SURGEPILOT_MONITORING_INFLUXDB_USERNAME",
    "SURGEPILOT_MONITORING_INFLUXDB_PASSWORD",
    "SURGEPILOT_MONITORING_INFLUXDB_ORG",
    "SURGEPILOT_MONITORING_INFLUXDB_BUCKET",
)
SAFE_UNQUOTED_ENV_VALUE = re.compile(r"^[A-Za-z0-9_./:@%+,=\-]+$")
LOWERCASE_SHA256 = re.compile(r"^[0-9a-f]{64}$")
UNSUPPORTED_RECONFIGURATION_LINE_SEPARATORS = frozenset(
    {"\v", "\f", "\x1c", "\x1d", "\x1e", "\x85", "\u2028", "\u2029"}
)
TEMPLATE_PLACEHOLDERS = {
    "RUNNER_INTERNAL_TOKEN": "replace-with-random-runner-token",
    "SSH_CREDENTIAL_ENCRYPTION_KEY": "replace-with-base64-32-byte-key",
    "MINIO_SECRET_KEY": "replace-with-minio-password",
    "MINIO_ROOT_PASSWORD": "replace-with-minio-password",
    "SURGEPILOT_MONITORING_INFLUXDB_PASSWORD": "replace-with-influxdb-password",
    "SURGEPILOT_MONITORING_INFLUXDB_TOKEN_FILE_HOST": "./monitoring/influxdb-token.example",
}


class BootstrapError(RuntimeError):
    """Raised when first-run deployment configuration cannot be created safely."""


def _replace_exact(text: str, old: str, new: str, *, count: int) -> str:
    if text.count(old) != count:
        raise BootstrapError(f"{ENV_TEMPLATE_NAME} must contain {count} occurrence(s) of {old!r}")
    return text.replace(old, new)


def _decode_environment_value(value: str) -> str:
    if len(value) >= 2 and value.startswith("'") and value.endswith("'"):
        return re.sub(r"\\(['\\])", r"\1", value[1:-1])
    return value


def _encode_environment_value(key: str, value: str) -> str:
    if any(character in value for character in ("\x00", "\r", "\n")):
        raise BootstrapError(f"inherited {key} cannot contain NUL or newline characters")
    if not value:
        raise BootstrapError(f"inherited {key} must not be empty")
    if SAFE_UNQUOTED_ENV_VALUE.fullmatch(value) is not None:
        return value
    escaped = value.replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"


def _active_environment_values(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", maxsplit=1)
        values[key] = _decode_environment_value(value)
    return values


def _persist_inherited_environment(
    text: str, environ: Mapping[str, str], *, persisted_keys: frozenset[str] | set[str]
) -> str:
    lines: list[str] = []
    for line in text.splitlines(keepends=True):
        content = line.rstrip("\r\n")
        newline = line[len(content) :]
        if content and not content.startswith("#") and "=" in content:
            key, _value = content.split("=", maxsplit=1)
            if key in persisted_keys and key in environ:
                inherited = environ[key]
                content = f"{key}={_encode_environment_value(key, inherited)}"
        lines.append(f"{content}{newline}")
    rendered = "".join(lines)
    values = _active_environment_values(rendered)
    _validate_minio_pairs(values)
    _validate_influxdb_init_cli_values(values)
    return rendered


def _validate_reconfiguration_line_endings(text: str) -> None:
    for index, character in enumerate(text):
        if character == "\r":
            if index + 1 >= len(text) or text[index + 1] != "\n":
                raise BootstrapError("deployment .env reconfiguration supports LF or CRLF only")
        elif character in UNSUPPORTED_RECONFIGURATION_LINE_SEPARATORS:
            raise BootstrapError("deployment .env reconfiguration supports LF or CRLF only")


def _render_release_network_update(text: str, updates: Mapping[str, str]) -> str:
    if set(updates) != set(RELEASE_NETWORK_KEYS):
        raise BootstrapError(
            "release network updates must contain exactly the four allowed network keys"
        )
    _validate_reconfiguration_line_endings(text)

    counts = dict.fromkeys(RELEASE_NETWORK_KEYS, 0)
    lines: list[str] = []
    for line in text.splitlines(keepends=True):
        content = line.rstrip("\r\n")
        newline = line[len(content) :]
        if content and not content.startswith("#") and "=" in content:
            key, _value = content.split("=", maxsplit=1)
            if key in counts:
                counts[key] += 1
                content = f"{key}={_encode_environment_value(key, updates[key])}"
        lines.append(f"{content}{newline}")

    invalid_counts = [key for key, count in counts.items() if count != 1]
    if invalid_counts:
        raise BootstrapError(
            "deployment .env must contain exactly one active assignment for each release "
            "network key"
        )
    return "".join(lines)


def _required_environment_value(values: Mapping[str, str], key: str) -> str:
    try:
        return values[key]
    except KeyError as exc:
        raise BootstrapError(f"existing .env is missing required {key}") from exc


def _validate_minio_pairs(values: Mapping[str, str]) -> None:
    if _required_environment_value(values, "MINIO_ACCESS_KEY") != _required_environment_value(
        values, "MINIO_ROOT_USER"
    ):
        raise BootstrapError("MINIO_ACCESS_KEY must match MINIO_ROOT_USER")
    if _required_environment_value(values, "MINIO_SECRET_KEY") != _required_environment_value(
        values, "MINIO_ROOT_PASSWORD"
    ):
        raise BootstrapError("MINIO_SECRET_KEY must match MINIO_ROOT_PASSWORD")


def _validate_influxdb_init_cli_values(values: Mapping[str, str]) -> None:
    for key in INFLUXDB_INIT_CLI_ENV_KEYS:
        if _required_environment_value(values, key).startswith("-"):
            raise BootstrapError(
                f"{key} must not start with '-' because InfluxDB setup parses it as a CLI flag"
            )


def _strict_boolean(values: Mapping[str, str], key: str) -> bool:
    normalized = _required_environment_value(values, key).strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise BootstrapError(f"{key} must be true or false")


def _validate_no_template_placeholders(values: Mapping[str, str]) -> None:
    for key, placeholder in TEMPLATE_PLACEHOLDERS.items():
        if _required_environment_value(values, key) == placeholder:
            raise BootstrapError(f"{key} still uses a template placeholder")


def _requires_demo_state(*, is_release: bool, values: Mapping[str, str]) -> bool:
    if not is_release:
        return True
    return _strict_boolean(values, "SURGEPILOT_DEMO_LOAD_NODE_ENABLED")


def _render_environment(
    template: str,
    environ: Mapping[str, str],
    *,
    compose_token_path: str = COMPOSE_TOKEN_PATH,
    persisted_keys: frozenset[str] | set[str] = PERSISTED_ENV_KEYS,
) -> str:
    minio_password = secrets.token_hex(20)
    rendered = _replace_exact(
        template,
        "replace-with-random-runner-token",
        secrets.token_hex(32),
        count=1,
    )
    rendered = _replace_exact(
        rendered,
        "replace-with-base64-32-byte-key",
        base64.b64encode(secrets.token_bytes(32)).decode("ascii"),
        count=1,
    )
    rendered = _replace_exact(
        rendered,
        "replace-with-minio-password",
        minio_password,
        count=2,
    )
    rendered = _replace_exact(
        rendered,
        "replace-with-influxdb-password",
        secrets.token_hex(24),
        count=1,
    )
    rendered = _replace_exact(
        rendered,
        "./monitoring/influxdb-token.example",
        compose_token_path,
        count=1,
    )
    return _persist_inherited_environment(rendered, environ, persisted_keys=persisted_keys)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_private_file(
    path: Path,
    content: str,
    *,
    temporary_directory: Path,
) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".bootstrap-",
        dir=temporary_directory,
    )
    temporary_path = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            descriptor = -1
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary_path, path)
        _fsync_directory(path.parent)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        temporary_path.unlink(missing_ok=True)
        _fsync_directory(temporary_directory)


def _ensure_secret_directory(root: Path) -> Path:
    state_dir = root / ".surgepilot"
    secret_dir = state_dir / "secrets"
    state_dir.mkdir(mode=0o700, exist_ok=True)
    if state_dir.is_symlink() or not state_dir.is_dir():
        raise NotADirectoryError(f"private deployment state is not a directory: {state_dir}")
    _validate_owner_only(state_dir.stat(), label="private deployment state")
    secret_dir.mkdir(mode=0o700, exist_ok=True)
    if secret_dir.is_symlink() or not secret_dir.is_dir():
        raise NotADirectoryError(f"private secret state is not a directory: {secret_dir}")
    _validate_owner_only(secret_dir.stat(), label="private secret state")
    return secret_dir


def _validate_owner_only(metadata: os.stat_result, *, label: str) -> None:
    if metadata.st_uid != os.geteuid():
        raise BootstrapError(f"{label} must be owned by the current deployment user")
    if stat.S_IMODE(metadata.st_mode) & 0o077:
        raise BootstrapError(f"{label} must use owner-only permissions")


def _validate_private_text_file(path: Path, *, label: str) -> None:
    if path.is_symlink():
        raise BootstrapError(f"{label} must not be a symbolic link: {path}")
    try:
        metadata = path.stat()
    except OSError as exc:
        raise BootstrapError(f"cannot inspect {label}: {exc}") from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise BootstrapError(f"{label} is not a regular file: {path}")
    _validate_owner_only(metadata, label=label)
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise BootstrapError(f"cannot read {label}: {exc}") from exc
    if not content.strip():
        raise BootstrapError(f"{label} is empty: {path}")


def _validate_monitoring_token(path: Path) -> None:
    _validate_private_text_file(path, label="Monitoring token file")


def _validate_demo_identity(directory: Path) -> None:
    if directory.is_symlink() or not directory.is_dir():
        raise BootstrapError(f"Demo Load Node SSH identity path is unsafe: {directory}")
    _validate_owner_only(directory.stat(), label="Demo Load Node SSH identity directory")
    private_key = directory / DEMO_PRIVATE_KEY_NAME
    public_key = directory / DEMO_PUBLIC_KEY_NAME
    if private_key.exists() != public_key.exists():
        raise BootstrapError("Demo Load Node SSH identity is incomplete; refusing automatic repair")
    if not private_key.exists():
        raise BootstrapError("Demo Load Node SSH identity is missing")
    _validate_private_text_file(private_key, label="Demo Load Node SSH private key")
    _validate_private_text_file(public_key, label="Demo Load Node SSH public key")
    if not private_key.read_text(encoding="utf-8").startswith("-----BEGIN OPENSSH"):
        raise BootstrapError("Demo Load Node SSH private key is not OpenSSH format")
    if not public_key.read_text(encoding="utf-8").startswith("ssh-ed25519 "):
        raise BootstrapError("Demo Load Node SSH public key is not Ed25519 OpenSSH format")


def _ensure_demo_identity(root: Path) -> Path:
    state_dir = root / ".surgepilot"
    final_directory = root / DEMO_KEY_DIRECTORY_RELATIVE_PATH
    if final_directory.exists():
        _validate_demo_identity(final_directory)
        return final_directory

    temporary_directory = Path(tempfile.mkdtemp(prefix=".demo-load-node-", dir=state_dir))
    os.chmod(temporary_directory, 0o700)
    private_key = temporary_directory / DEMO_PRIVATE_KEY_NAME
    try:
        result = subprocess.run(
            [
                "ssh-keygen",
                "-q",
                "-t",
                "ed25519",
                "-N",
                "",
                "-C",
                "surgepilot-demo-node",
                "-f",
                str(private_key),
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode != 0:
            raise BootstrapError(
                "cannot generate Demo Load Node SSH identity with ssh-keygen: "
                f"{result.stderr.strip() or 'unknown error'}"
            )
        os.chmod(private_key, 0o600)
        os.chmod(temporary_directory / DEMO_PUBLIC_KEY_NAME, 0o600)
        for path in (private_key, temporary_directory / DEMO_PUBLIC_KEY_NAME):
            with path.open("rb") as handle:
                os.fsync(handle.fileno())
        _fsync_directory(temporary_directory)
        try:
            os.rename(temporary_directory, final_directory)
        except OSError as exc:
            if exc.errno not in {errno.EEXIST, errno.ENOTEMPTY}:
                raise
        _fsync_directory(state_dir)
    finally:
        if temporary_directory.exists():
            for path in temporary_directory.iterdir():
                path.unlink(missing_ok=True)
            temporary_directory.rmdir()
            _fsync_directory(state_dir)
    _validate_demo_identity(final_directory)
    return final_directory


def _ensure_demo_state(root: Path, secret_directory: Path) -> None:
    password_path = root / DEMO_PASSWORD_RELATIVE_PATH
    if not password_path.exists():
        try:
            _write_private_file(
                password_path,
                f"{secrets.token_urlsafe(32)}\n",
                temporary_directory=secret_directory,
            )
        except FileExistsError:
            pass
        except OSError as exc:
            raise BootstrapError(f"cannot create Demo Load Node password file: {exc}") from exc
    _validate_private_text_file(password_path, label="Demo Load Node password file")
    try:
        _ensure_demo_identity(root)
    except OSError as exc:
        raise BootstrapError(f"cannot prepare Demo Load Node SSH identity: {exc}") from exc


def _validate_existing_environment(
    *,
    root: Path,
    env_path: Path,
    environ: Mapping[str, str],
    persisted_keys: frozenset[str] | set[str],
) -> None:
    _validate_private_text_file(env_path, label="deployment .env")
    try:
        values = _active_environment_values(env_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise BootstrapError(f"cannot read existing {env_path}: {exc}") from exc
    _validate_minio_pairs(values)
    _validate_influxdb_init_cli_values(values)
    _validate_no_template_placeholders(values)
    for key in sorted(persisted_keys.intersection(environ)):
        persisted = _required_environment_value(values, key)
        if persisted != environ[key]:
            raise BootstrapError(
                f"inherited {key} conflicts with existing .env; update .env or unset {key}"
            )
    token_source = _required_environment_value(
        values, "SURGEPILOT_MONITORING_INFLUXDB_TOKEN_FILE_HOST"
    )
    if token_source in {COMPOSE_TOKEN_PATH, RELEASE_COMPOSE_TOKEN_PATH}:
        _validate_monitoring_token(root / TOKEN_RELATIVE_PATH)


def _validate_complete_release_environment(
    values: Mapping[str, str], *, daemon_arch: str, forced_platform: str
) -> None:
    from scripts.release_preflight import ReleasePreflightError, validate_release_environment

    try:
        validate_release_environment(
            values,
            daemon_arch=daemon_arch,
            forced_platform=forced_platform,
        )
    except ReleasePreflightError as exc:
        raise BootstrapError(f"release environment validation failed: {exc}") from exc


def _validate_reconfiguration_candidate(path: Path, *, expected_bytes: bytes) -> None:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise BootstrapError(f"cannot inspect replacement candidate: {exc}") from exc
    if not stat.S_ISREG(metadata.st_mode) or path.is_symlink():
        raise BootstrapError("replacement candidate must be a regular non-symlink file")
    if metadata.st_uid != os.geteuid():
        raise BootstrapError("replacement candidate must be owned by the deployment user")
    if stat.S_IMODE(metadata.st_mode) != 0o600:
        raise BootstrapError("replacement candidate must use mode 0600")
    try:
        candidate_bytes = path.read_bytes()
        candidate_bytes.decode("utf-8")
    except (OSError, UnicodeError) as exc:
        raise BootstrapError(f"cannot read replacement candidate: {exc}") from exc
    if candidate_bytes != expected_bytes:
        raise BootstrapError("replacement candidate bytes do not match the validated proposal")


def reconfigure_release_network(
    root: Path,
    *,
    deployment_root: Path | None = None,
    expected_sha256: str,
    updates: Mapping[str, str],
    daemon_arch: str,
    forced_platform: str,
) -> bool:
    """Replace the four existing direct-LAN release network assignments."""

    release_root = root.resolve()
    state_root = (deployment_root or release_root).resolve()
    manifest_path = release_root / "release-manifest.json"
    env_path = state_root / ENV_NAME
    if not manifest_path.is_file():
        raise BootstrapError(f"release-manifest.json is missing: {manifest_path}")
    if not env_path.exists():
        raise BootstrapError(f"existing .env is missing: {env_path}")
    if LOWERCASE_SHA256.fullmatch(expected_sha256) is None:
        raise BootstrapError(
            "expected .env SHA-256 must be exactly 64 lowercase hexadecimal digits"
        )

    _validate_private_text_file(env_path, label="deployment .env")
    _validate_existing_environment(
        root=state_root,
        env_path=env_path,
        environ={},
        persisted_keys=RELEASE_PERSISTED_ENV_KEYS,
    )
    try:
        original_bytes = env_path.read_bytes()
        original_text = original_bytes.decode("utf-8")
    except (OSError, UnicodeError) as exc:
        raise BootstrapError(f"cannot read existing {env_path}: {exc}") from exc
    if hashlib.sha256(original_bytes).hexdigest() != expected_sha256:
        raise BootstrapError("existing .env SHA-256 does not match the reviewed content")

    current_values = _active_environment_values(original_text)
    _validate_complete_release_environment(
        current_values,
        daemon_arch=daemon_arch,
        forced_platform=forced_platform,
    )
    if _strict_boolean(current_values, "SESSION_COOKIE_SECURE"):
        raise BootstrapError(
            "advanced HTTPS release configuration requires explicit manual .env editing"
        )

    rendered = _render_release_network_update(original_text, updates)
    proposed_values = _active_environment_values(rendered)
    _validate_complete_release_environment(
        proposed_values,
        daemon_arch=daemon_arch,
        forced_platform=forced_platform,
    )
    rendered_bytes = rendered.encode("utf-8")
    if rendered_bytes == original_bytes:
        return False

    descriptor = -1
    temporary_path: Path | None = None
    try:
        try:
            descriptor, temporary_name = tempfile.mkstemp(prefix=".reconfigure-", dir=state_root)
            temporary_path = Path(temporary_name)
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                descriptor = -1
                handle.write(rendered_bytes)
                handle.flush()
                os.fsync(handle.fileno())
        except OSError as exc:
            raise BootstrapError(
                f"cannot prepare private replacement for deployment .env: {exc}"
            ) from exc

        _validate_reconfiguration_candidate(temporary_path, expected_bytes=rendered_bytes)

        _validate_private_text_file(env_path, label="deployment .env")
        try:
            current_bytes = env_path.read_bytes()
        except OSError as exc:
            raise BootstrapError(
                f"cannot re-read deployment .env before replacement: {exc}"
            ) from exc
        if (
            current_bytes != original_bytes
            or hashlib.sha256(current_bytes).hexdigest() != expected_sha256
        ):
            raise BootstrapError(
                "deployment .env changed before replacement; review the current configuration"
            )

        try:
            os.replace(temporary_path, env_path)
            temporary_path = None
        except OSError as exc:
            raise BootstrapError(f"cannot replace deployment .env: {exc}") from exc
        try:
            _fsync_directory(state_root)
        except OSError as exc:
            raise BootstrapError(
                "deployment .env was updated but durability could not be confirmed; inspect "
                f".env: {exc}"
            ) from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

    return True


def bootstrap(
    root: Path,
    *,
    deployment_root: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> bool:
    """Create first-run deployment files and return whether `.env` was created."""

    release_root = root.resolve()
    state_root = (deployment_root or release_root).resolve()
    env_path = state_root / ENV_NAME
    effective_environ = os.environ if environ is None else environ
    is_release = (release_root / "release-manifest.json").is_file()
    persisted_keys = RELEASE_PERSISTED_ENV_KEYS if is_release else PERSISTED_ENV_KEYS
    if env_path.exists():
        _validate_private_text_file(env_path, label="deployment .env")
        try:
            secret_directory = _ensure_secret_directory(state_root)
        except OSError as exc:
            raise BootstrapError(f"cannot prepare private deployment state: {exc}") from exc
        values = _active_environment_values(env_path.read_text(encoding="utf-8"))
        _validate_existing_environment(
            root=state_root,
            env_path=env_path,
            environ=effective_environ,
            persisted_keys=persisted_keys,
        )
        if _requires_demo_state(is_release=is_release, values=values):
            _ensure_demo_state(state_root, secret_directory)
        print("Existing .env found; deployment configuration remains unchanged.")
        return False

    template_path = release_root / ENV_TEMPLATE_NAME
    try:
        template = template_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise BootstrapError(f"cannot read {template_path}: {exc}") from exc
    compose_token_path = RELEASE_COMPOSE_TOKEN_PATH if is_release else COMPOSE_TOKEN_PATH
    rendered = _render_environment(
        template,
        effective_environ,
        compose_token_path=compose_token_path,
        persisted_keys=persisted_keys,
    )
    rendered_values = _active_environment_values(rendered)

    try:
        secret_directory = _ensure_secret_directory(state_root)
        token_path = secret_directory / TOKEN_RELATIVE_PATH.name
    except OSError as exc:
        raise BootstrapError(f"cannot prepare private deployment state: {exc}") from exc
    manages_default_token = rendered_values["SURGEPILOT_MONITORING_INFLUXDB_TOKEN_FILE_HOST"] in {
        COMPOSE_TOKEN_PATH,
        RELEASE_COMPOSE_TOKEN_PATH,
    }
    if manages_default_token and not token_path.exists():
        try:
            _write_private_file(
                token_path,
                f"{secrets.token_hex(32)}\n",
                temporary_directory=secret_directory,
            )
        except FileExistsError:
            pass
        except OSError as exc:
            raise BootstrapError(f"cannot create Monitoring token file: {exc}") from exc
    if manages_default_token:
        _validate_monitoring_token(token_path)
    if _requires_demo_state(is_release=is_release, values=rendered_values):
        _ensure_demo_state(state_root, secret_directory)

    try:
        _write_private_file(
            env_path,
            rendered,
            temporary_directory=secret_directory,
        )
    except FileExistsError:
        _validate_existing_environment(
            root=state_root,
            env_path=env_path,
            environ=effective_environ,
            persisted_keys=persisted_keys,
        )
        print("Existing .env found; deployment configuration remains unchanged.")
        return False
    except OSError as exc:
        raise BootstrapError(f"cannot create {env_path}: {exc}") from exc

    print("Created secure first-run deployment configuration in .env.")
    return True


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root containing .env.example (default: script repository root)",
    )
    parser.add_argument(
        "--deployment-root",
        type=Path,
        help="Directory containing mutable deployment state (default: --root)",
    )
    parser.add_argument("--reconfigure-release-network", action="store_true")
    parser.add_argument("--expected-env-sha256")
    parser.add_argument("--daemon-arch")
    parser.add_argument("--forced-platform")
    parser.add_argument("--release-http-port")
    parser.add_argument("--release-node-api-base-url")
    parser.add_argument("--release-influxdb-host-port")
    parser.add_argument("--release-influxdb-node-write-url")
    parser.add_argument("--release-demo-enabled")
    parser.add_argument("--release-runtime-architectures")
    parser.add_argument("--session-cookie-secure")
    return parser.parse_args(argv)


def _release_environment_from_args(args: argparse.Namespace) -> dict[str, str]:
    if args.daemon_arch is not None or args.forced_platform is not None:
        raise BootstrapError(
            "--daemon-arch and --forced-platform require --reconfigure-release-network"
        )
    values = {
        "SURGEPILOT_HTTP_PORT": args.release_http_port,
        "SURGEPILOT_NODE_API_BASE_URL": args.release_node_api_base_url,
        "SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT": args.release_influxdb_host_port,
        "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL": args.release_influxdb_node_write_url,
        "SURGEPILOT_DEMO_LOAD_NODE_ENABLED": args.release_demo_enabled,
        "SURGEPILOT_RUNTIME_ARCHITECTURES": args.release_runtime_architectures,
        "SESSION_COOKIE_SECURE": args.session_cookie_secure,
    }
    supplied = {key: value for key, value in values.items() if value is not None}
    if supplied and len(supplied) != len(values):
        raise BootstrapError("release bootstrap arguments must be supplied together")
    return supplied


def _release_network_reconfiguration_from_args(args: argparse.Namespace) -> dict[str, str]:
    network_values = {
        "SURGEPILOT_HTTP_PORT": args.release_http_port,
        "SURGEPILOT_NODE_API_BASE_URL": args.release_node_api_base_url,
        "SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT": args.release_influxdb_host_port,
        "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL": args.release_influxdb_node_write_url,
    }
    bootstrap_only_values = (
        args.release_demo_enabled,
        args.release_runtime_architectures,
        args.session_cookie_secure,
    )
    if any(value is not None for value in bootstrap_only_values):
        raise BootstrapError(
            "release bootstrap and network reconfiguration arguments must not be mixed"
        )
    if args.expected_env_sha256 is None or any(value is None for value in network_values.values()):
        raise BootstrapError(
            "release network reconfiguration requires the expected digest and all four network "
            "arguments"
        )
    if args.daemon_arch is None or args.forced_platform is None:
        raise BootstrapError(
            "release network reconfiguration requires actual daemon architecture and forced "
            "platform inputs"
        )
    return {key: value for key, value in network_values.items() if value is not None}


def main(
    argv: list[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> int:
    args = parse_args(argv)
    try:
        if args.reconfigure_release_network:
            updates = _release_network_reconfiguration_from_args(args)
            changed = reconfigure_release_network(
                args.root,
                deployment_root=args.deployment_root,
                expected_sha256=args.expected_env_sha256,
                updates=updates,
                daemon_arch=args.daemon_arch,
                forced_platform=args.forced_platform,
            )
            if changed:
                print("Updated release network configuration in .env.")
            else:
                print("Release network configuration is unchanged.")
            return 0
        if args.expected_env_sha256 is not None:
            raise BootstrapError("--expected-env-sha256 requires --reconfigure-release-network")
        effective_environ = dict(os.environ if environ is None else environ)
        effective_environ.update(_release_environment_from_args(args))
        bootstrap(args.root, deployment_root=args.deployment_root, environ=effective_environ)
    except BootstrapError as exc:
        print(f"Deployment bootstrap failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
