from dataclasses import dataclass
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


def get_settings() -> Settings:
    app_env = os.environ.get("APP_ENV", "development")
    return Settings(
        app_env=app_env,
        session_cookie_secure=_session_cookie_secure_from_env(app_env=app_env),
        app_base_url=os.environ.get("APP_BASE_URL", "http://localhost:8000"),
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
    )
