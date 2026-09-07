from dataclasses import dataclass
import base64
import binascii
import os


def _normalize_database_url(value: str) -> str:
    if value.startswith("postgresql://"):
        return value.replace("postgresql://", "postgresql+psycopg://", 1)
    return value


def _bool_from_env(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _session_cookie_secure_from_env(*, app_env: str) -> bool:
    value = os.environ.get("SESSION_COOKIE_SECURE")
    if value is None:
        return app_env == "production"
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ValueError("SESSION_COOKIE_SECURE must be true or false.")


@dataclass(frozen=True)
class Settings:
    app_env: str
    session_cookie_secure: bool
    app_base_url: str
    surgepilot_node_api_base_url: str | None
    database_url: str
    allow_signup: bool
    default_workspace_name: str
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket: str
    minio_region: str | None
    minio_secure: bool
    dependency_file_max_bytes: int
    dependency_file_allowed_extensions: str
    ssh_credential_encryption_key: str | None
    load_node_default_runner_home: str
    load_node_ssh_connect_timeout_seconds: int
    load_node_init_command_timeout_seconds: int
    load_node_init_timeout_seconds: int
    load_node_init_log_tail_bytes: int
    load_node_generated_key_type: str
    runner_internal_token: str | None
    enable_protocol_smoke_runs: bool
    runner_heartbeat_timeout_seconds: int
    runner_accepted_timeout_seconds: int
    runner_stop_grace_seconds: int
    node_cooldown_seconds: int
    runner_callback_retention_days: int
    runner_force_kill_ssh_timeout_seconds: int
    run_control_stale_seconds: int
    run_artifact_max_bytes: int
    run_terminal_late_artifact_max_bytes: int
    run_terminal_late_artifact_seconds: int


def get_settings() -> Settings:
    app_env = os.environ.get("APP_ENV", "development")
    return Settings(
        app_env=app_env,
        session_cookie_secure=_session_cookie_secure_from_env(app_env=app_env),
        app_base_url=os.environ.get("APP_BASE_URL", "http://localhost:8000"),
        surgepilot_node_api_base_url=os.environ.get("SURGEPILOT_NODE_API_BASE_URL") or None,
        database_url=_normalize_database_url(
            os.environ.get(
                "DATABASE_URL", "postgresql://surgepilot:surgepilot@localhost:5432/surgepilot"
            )
        ),
        allow_signup=_bool_from_env(os.environ.get("ALLOW_SIGNUP"), True),
        default_workspace_name=os.environ.get("DEFAULT_WORKSPACE_NAME", "Default Workspace"),
        minio_endpoint=os.environ.get("MINIO_ENDPOINT", "http://localhost:9000"),
        minio_access_key=os.environ.get("MINIO_ACCESS_KEY", "minioadmin"),
        minio_secret_key=os.environ.get("MINIO_SECRET_KEY", "minioadmin"),
        minio_bucket=os.environ.get("MINIO_BUCKET", "surgepilot"),
        minio_region=os.environ.get("MINIO_REGION") or None,
        minio_secure=_bool_from_env(os.environ.get("MINIO_SECURE"), False),
        dependency_file_max_bytes=int(
            os.environ.get("DEPENDENCY_FILE_MAX_BYTES", str(100 * 1024 * 1024))
        ),
        dependency_file_allowed_extensions=os.environ.get("DEPENDENCY_FILE_ALLOWED_EXTENSIONS", ""),
        ssh_credential_encryption_key=os.environ.get("SSH_CREDENTIAL_ENCRYPTION_KEY") or None,
        load_node_default_runner_home=os.environ.get(
            "LOAD_NODE_DEFAULT_RUNNER_HOME", "/opt/surgepilot/runner"
        ),
        load_node_ssh_connect_timeout_seconds=int(
            os.environ.get("LOAD_NODE_SSH_CONNECT_TIMEOUT_SECONDS", "15")
        ),
        load_node_init_command_timeout_seconds=int(
            os.environ.get("LOAD_NODE_INIT_COMMAND_TIMEOUT_SECONDS", "30")
        ),
        load_node_init_timeout_seconds=int(os.environ.get("LOAD_NODE_INIT_TIMEOUT_SECONDS", "120")),
        load_node_init_log_tail_bytes=int(os.environ.get("LOAD_NODE_INIT_LOG_TAIL_BYTES", "65536")),
        load_node_generated_key_type=os.environ.get("LOAD_NODE_GENERATED_KEY_TYPE", "ed25519"),
        runner_internal_token=os.environ.get("RUNNER_INTERNAL_TOKEN") or None,
        enable_protocol_smoke_runs=_bool_from_env(
            os.environ.get("SURGEPILOT_ENABLE_PROTOCOL_SMOKE_RUNS"), False
        ),
        runner_heartbeat_timeout_seconds=int(
            os.environ.get("SURGEPILOT_RUN_HEARTBEAT_TIMEOUT_SECONDS", "60")
        ),
        runner_accepted_timeout_seconds=int(
            os.environ.get("SURGEPILOT_RUN_ACCEPTED_TIMEOUT_SECONDS", "120")
        ),
        runner_stop_grace_seconds=int(
            os.environ.get("SURGEPILOT_RUN_STOP_GRACE_SECONDS", "60")
        ),
        node_cooldown_seconds=int(os.environ.get("SURGEPILOT_NODE_COOLDOWN_SECONDS", "300")),
        runner_callback_retention_days=int(
            os.environ.get("SURGEPILOT_RUNNER_CALLBACK_RETENTION_DAYS", "30")
        ),
        runner_force_kill_ssh_timeout_seconds=int(
            os.environ.get("SURGEPILOT_RUN_FORCE_KILL_SSH_TIMEOUT_SECONDS", "30")
        ),
        run_control_stale_seconds=int(
            os.environ.get("SURGEPILOT_RUN_CONTROL_STALE_SECONDS", "120")
        ),
        run_artifact_max_bytes=int(
            os.environ.get("SURGEPILOT_RUN_ARTIFACT_MAX_BYTES", str(200 * 1024 * 1024))
        ),
        run_terminal_late_artifact_max_bytes=int(
            os.environ.get(
                "SURGEPILOT_RUN_TERMINAL_LATE_ARTIFACT_MAX_BYTES", str(1024 * 1024)
            )
        ),
        run_terminal_late_artifact_seconds=int(
            os.environ.get("SURGEPILOT_RUN_TERMINAL_LATE_ARTIFACT_SECONDS", "300")
        ),
    )


def decode_ssh_credential_encryption_key(value: str | None) -> bytes:
    if not value:
        raise ValueError(
            "SSH_CREDENTIAL_ENCRYPTION_KEY is required and must be base64-encoded 32 bytes."
        )
    try:
        decoded = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError(
            "SSH_CREDENTIAL_ENCRYPTION_KEY must be valid base64 encoding for 32 bytes."
        ) from exc
    if len(decoded) != 32:
        raise ValueError("SSH_CREDENTIAL_ENCRYPTION_KEY must decode to exactly 32 bytes.")
    return decoded


def validate_ssh_credential_encryption_key() -> None:
    decode_ssh_credential_encryption_key(get_settings().ssh_credential_encryption_key)
