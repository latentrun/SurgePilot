from dataclasses import dataclass
from datetime import timedelta
import base64
import hashlib
import logging
import re
import secrets

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import decode_ssh_credential_encryption_key, get_settings
from app.core.errors import AppError
from app.core.ids import new_ulid
from app.core.time import utc_now
from app.models.auth import User
from app.models.load_nodes import (
    LOAD_NODE_AUTH_TYPES,
    LOAD_NODE_SCOPES,
    LoadNode,
    LoadNodeCredential,
    LoadNodeInitializationAttempt,
)
from app.services.audit import write_audit_event

logger = logging.getLogger(__name__)

DEFAULT_RUNNER_HOME = "/opt/surgepilot/runner"
MAX_HOST_LENGTH = 255
MAX_TEXT_LENGTH = 500
MAX_REASON_LENGTH = 240
SSH_USER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9._-]{0,31}$")
HOST_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,255}$")
SHELL_UNSAFE_PATTERN = re.compile(r"[\s\\\x00\n\r;&|`$<>]")
SECRET_PATTERNS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S),
    re.compile(r"(?i)(password|passphrase|token|secret|csrf|credential)=\S+"),
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/-]+=*"),
]
LOAD_NODE_HOST_KEY_ERROR_CODES = {
    "LOAD_NODE_SSH_HOST_KEY_UNTRUSTED",
    "LOAD_NODE_SSH_HOST_KEY_CHANGED",
}


@dataclass(frozen=True)
class CredentialPlaintext:
    auth_type: str
    password: str | None = None
    private_key: str | None = None
    private_key_passphrase: str | None = None


@dataclass(frozen=True)
class PreparedCredential:
    auth_type: str
    password_ciphertext: str | None
    private_key_ciphertext: str | None
    private_key_passphrase_ciphertext: str | None
    generated_public_key: str | None
    credential_fingerprint: str | None


@dataclass(frozen=True)
class TrustedSshHostKey:
    algorithm: str
    public_key: str
    fingerprint_sha256: str


@dataclass(frozen=True)
class InitResult:
    ok: bool
    log: str
    error_code: str | None = None
    message: str | None = None
    runner_version: str | None = None
    bundle_version: str | None = None


class LoadNodeInitializer:
    def initialize(self, node: LoadNode, credential: CredentialPlaintext) -> InitResult:
        _ = node, credential
        raise NotImplementedError("Load Node initializer must be provided.")


class DeterministicLoadNodeInitializer(LoadNodeInitializer):
    def initialize(self, node: LoadNode, credential: CredentialPlaintext) -> InitResult:
        _ = credential
        return InitResult(
            ok=True,
            log=(
                "[info] Connection verified.\n"
                f"[info] Agent home prepared at {node.runner_home}.\n"
                "[info] Engine checks passed.\n"
                "[info] Agent bundle verified.\n"
            ),
            message="Initialization succeeded.",
            runner_version="0.1.0",
            bundle_version="p0-03",
        )


class FailingInitializer(LoadNodeInitializer):
    def __init__(self, error_code: str, log: str = "setup failed password=secret-token") -> None:
        self.error_code = error_code
        self.log = log

    def initialize(self, node: LoadNode, credential: CredentialPlaintext) -> InitResult:
        _ = node, credential
        return InitResult(
            ok=False, error_code=self.error_code, message="Initialization failed.", log=self.log
        )


def field_error(field: str, message: str, code: str = "INVALID_FIELD") -> dict[str, str]:
    return {"field": field, "code": code, "message": message}


def validation_error(details: list[dict[str, str]]) -> AppError:
    return AppError("VALIDATION_ERROR", "Validation failed.", 422, details)


def _load_master_key() -> bytes:
    try:
        return decode_ssh_credential_encryption_key(get_settings().ssh_credential_encryption_key)
    except ValueError as exc:
        raise AppError(
            "CREDENTIAL_DECRYPT_FAILED", "Credential encryption is not configured.", 500
        ) from exc


def encrypt_secret(value: str, *, node_id: str) -> str:
    key = _load_master_key()
    nonce = secrets.token_bytes(12)
    aad = f"load-node-credential:v1:{node_id}".encode()
    ciphertext = AESGCM(key).encrypt(nonce, value.encode(), aad)
    return base64.b64encode(nonce + ciphertext).decode()


def decrypt_secret(value: str, *, node_id: str) -> str:
    key = _load_master_key()
    try:
        raw = base64.b64decode(value, validate=True)
        nonce, ciphertext = raw[:12], raw[12:]
        aad = f"load-node-credential:v1:{node_id}".encode()
        return AESGCM(key).decrypt(nonce, ciphertext, aad).decode()
    except (ValueError, InvalidTag) as exc:
        raise AppError(
            "CREDENTIAL_DECRYPT_FAILED", "Credential material could not be decrypted.", 500
        ) from exc


def fingerprint(value: str) -> str:
    digest = hashlib.sha256(value.encode()).digest()
    return "SHA256:" + base64.b64encode(digest).decode().rstrip("=")[:32]


def generated_keypair() -> tuple[str, str]:
    key = ed25519.Ed25519PrivateKey.generate()
    private_key = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.OpenSSH,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_key = (
        key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.OpenSSH,
            format=serialization.PublicFormat.OpenSSH,
        )
        .decode()
    )
    return private_key, f"{public_key} surgepilot-generated"


def normalize_host(value: str | None) -> str:
    host = (value or "").strip().lower()
    if not host or len(host) > MAX_HOST_LENGTH or not HOST_PATTERN.fullmatch(host):
        raise AppError("LOAD_NODE_HOST_INVALID", "Load Node host is invalid.", 422)
    if (
        "://" in host
        or "/" in host
        or "?" in host
        or "#" in host
        or SHELL_UNSAFE_PATTERN.search(host)
    ):
        raise AppError("LOAD_NODE_HOST_INVALID", "Load Node host is invalid.", 422)
    return host


def scan_ssh_host_key(host: str, port: int, timeout_seconds: int):
    from app.services.ssh_remote import scan_ssh_host_key as scan

    return scan(host=host, port=port, timeout_seconds=timeout_seconds)


def _value_from_host_key(input_host_key, field: str) -> str:
    aliases = {
        "public_key": "publicKey",
        "fingerprint_sha256": "fingerprintSha256",
    }
    if isinstance(input_host_key, dict):
        value = input_host_key.get(field)
        if value is None and field in aliases:
            value = input_host_key.get(aliases[field])
    else:
        value = getattr(input_host_key, field, None)
    text = (value or "").strip()
    if not text:
        raise validation_error(
            [field_error(f"sshHostKey.{field}", "SSH host key confirmation is required.")]
        )
    return text


def normalize_ssh_host_key(input_host_key) -> TrustedSshHostKey:
    return TrustedSshHostKey(
        algorithm=_value_from_host_key(input_host_key, "algorithm"),
        public_key=_value_from_host_key(input_host_key, "public_key"),
        fingerprint_sha256=_value_from_host_key(input_host_key, "fingerprint_sha256"),
    )


def known_hosts_line_for_node(node: LoadNode) -> str | None:
    if not (
        node.ssh_host_key_algorithm
        and node.ssh_host_key_public_key
        and node.ssh_host_key_fingerprint_sha256
    ):
        return None
    from app.services.ssh_remote import trusted_known_hosts_line

    return trusted_known_hosts_line(
        host=node.host,
        algorithm=node.ssh_host_key_algorithm,
        public_key=node.ssh_host_key_public_key,
        port=node.ssh_port,
    )


def require_trusted_ssh_host_key(node: LoadNode) -> None:
    if not (
        node.ssh_host_key_algorithm
        and node.ssh_host_key_public_key
        and node.ssh_host_key_fingerprint_sha256
    ):
        raise AppError(
            "LOAD_NODE_SSH_HOST_KEY_UNTRUSTED",
            "SSH host key must be scanned and trusted before this operation.",
            409,
        )


def clear_ssh_host_key_trust(node: LoadNode) -> None:
    node.ssh_host_key_algorithm = None
    node.ssh_host_key_public_key = None
    node.ssh_host_key_fingerprint_sha256 = None
    node.ssh_host_key_trusted_at = None
    node.ssh_host_key_trusted_by = None


def verify_live_ssh_host_key(*, host: str, ssh_port: int, trusted: TrustedSshHostKey) -> None:
    try:
        live = scan_ssh_host_key(
            host, ssh_port, get_settings().load_node_ssh_connect_timeout_seconds
        )
    except Exception as exc:
        logger.warning(
            "SSH host key scan failed during trust verification.",
            extra={"host": host, "ssh_port": ssh_port},
            exc_info=True,
        )
        raise AppError(
            "LOAD_NODE_SSH_HOST_KEY_SCAN_FAILED",
            "SSH host key scan failed.",
            400,
        ) from exc
    if (
        live.algorithm != trusted.algorithm
        or live.public_key != trusted.public_key
        or live.fingerprint_sha256 != trusted.fingerprint_sha256
    ):
        raise AppError(
            "LOAD_NODE_SSH_HOST_KEY_MISMATCH",
            "SSH host key changed before trust could be saved.",
            409,
        )


def normalize_ssh_port(value: int | None) -> int:
    if value is None or value < 1 or value > 65535:
        raise validation_error([field_error("sshPort", "SSH port must be between 1 and 65535.")])
    return value


def normalize_ssh_user(value: str | None) -> str:
    user = (value or "").strip()
    if not SSH_USER_PATTERN.fullmatch(user):
        raise validation_error([field_error("sshUser", "SSH user is invalid.")])
    return user


def normalize_runner_home(value: str | None) -> str:
    path = (value or get_settings().load_node_default_runner_home or DEFAULT_RUNNER_HOME).strip()
    if (
        not path.startswith("/")
        or path == "/"
        or ".." in path.split("/")
        or SHELL_UNSAFE_PATTERN.search(path)
        or "//" in path
    ):
        raise AppError("LOAD_NODE_RUNNER_HOME_INVALID", "Runner home is invalid.", 422)
    return path


def normalize_optional_text(
    value: str | None, *, field: str, max_length: int = MAX_TEXT_LENGTH
) -> str | None:
    if value is None:
        return None
    text = sanitize_log(value.strip(), max_bytes=max_length * 4)
    if len(text) > max_length:
        raise validation_error(
            [field_error(field, f"{field} must be {max_length} characters or less.")]
        )
    return text or None


def validate_scope(value: str) -> str:
    if value not in LOAD_NODE_SCOPES:
        raise validation_error([field_error("scope", "Scope is invalid.")])
    return value


def require_admin_for_public(actor: User, node_or_scope: LoadNode | str) -> None:
    scope = node_or_scope.scope if isinstance(node_or_scope, LoadNode) else node_or_scope
    if scope == "public" and actor.role != "admin":
        raise AppError(
            "LOAD_NODE_PUBLIC_ADMIN_REQUIRED",
            "Public Load Node operation requires Admin.",
            403,
        )


def validate_private_key_material(private_key: str, passphrase: str | None) -> None:
    password = passphrase.encode() if passphrase else None
    loaders = (serialization.load_ssh_private_key, serialization.load_pem_private_key)
    last_error: Exception | None = None
    for loader in loaders:
        try:
            loader(private_key.encode(), password=password)
            return
        except (TypeError, ValueError) as exc:
            last_error = exc
    raise AppError(
        "LOAD_NODE_CREDENTIAL_INVALID", "Credential material is invalid.", 422
    ) from last_error


def prepare_credential(input_credential, *, node_id: str) -> PreparedCredential:
    auth_type = input_credential.auth_type
    if auth_type not in LOAD_NODE_AUTH_TYPES:
        raise validation_error([field_error("credential.authType", "Auth type is invalid.")])
    password_ciphertext = None
    private_key_ciphertext = None
    passphrase_ciphertext = None
    public_key = None
    credential_fingerprint = None
    if auth_type == "password":
        password = (input_credential.password or "").strip()
        if not password:
            raise AppError("LOAD_NODE_CREDENTIAL_REQUIRED", "Credential material is required.", 422)
        password_ciphertext = encrypt_secret(password, node_id=node_id)
    elif auth_type == "private_key":
        private_key = (input_credential.private_key or "").strip()
        if not private_key:
            raise AppError("LOAD_NODE_CREDENTIAL_REQUIRED", "Credential material is required.", 422)
        private_key_passphrase = input_credential.private_key_passphrase
        validate_private_key_material(private_key, private_key_passphrase)
        private_key_ciphertext = encrypt_secret(private_key, node_id=node_id)
        if private_key_passphrase:
            passphrase_ciphertext = encrypt_secret(private_key_passphrase, node_id=node_id)
    else:
        private_key, public_key = generated_keypair()
        private_key_ciphertext = encrypt_secret(private_key, node_id=node_id)
        credential_fingerprint = fingerprint(public_key)
    return PreparedCredential(
        auth_type=auth_type,
        password_ciphertext=password_ciphertext,
        private_key_ciphertext=private_key_ciphertext,
        private_key_passphrase_ciphertext=passphrase_ciphertext,
        generated_public_key=public_key,
        credential_fingerprint=credential_fingerprint,
    )


def apply_credential(
    db: Session, *, node: LoadNode, input_credential, actor_user_id: str
) -> LoadNodeCredential:
    now = utc_now()
    prepared = prepare_credential(input_credential, node_id=node.id)
    credential = db.get(LoadNodeCredential, node.id)
    if credential is None:
        credential = LoadNodeCredential(
            node_id=node.id,
            auth_type=prepared.auth_type,
            password_ciphertext=prepared.password_ciphertext,
            private_key_ciphertext=prepared.private_key_ciphertext,
            private_key_passphrase_ciphertext=prepared.private_key_passphrase_ciphertext,
            generated_public_key=prepared.generated_public_key,
            credential_fingerprint=prepared.credential_fingerprint,
            encryption_key_version="v1",
            created_at=now,
            updated_at=now,
            updated_by=actor_user_id,
        )
        db.add(credential)
    else:
        credential.auth_type = prepared.auth_type
        credential.password_ciphertext = prepared.password_ciphertext
        credential.private_key_ciphertext = prepared.private_key_ciphertext
        credential.private_key_passphrase_ciphertext = prepared.private_key_passphrase_ciphertext
        credential.generated_public_key = prepared.generated_public_key
        credential.credential_fingerprint = prepared.credential_fingerprint
        credential.encryption_key_version = credential.encryption_key_version or "v1"
        credential.updated_at = now
        credential.updated_by = actor_user_id
    node.auth_type = prepared.auth_type
    node.status = "uninitialized"
    node.updated_by = actor_user_id
    node.updated_at = now
    db.flush()
    return credential


def visible_node_filters(*, workspace_id: str):
    return or_(
        LoadNode.scope == "public",
        and_(LoadNode.scope == "workspace", LoadNode.workspace_id == workspace_id),
    )


def get_visible_load_node(db: Session, *, workspace_id: str, load_node_id: str) -> LoadNode:
    node = db.scalar(
        select(LoadNode).where(
            LoadNode.id == load_node_id,
            LoadNode.archived_at.is_(None),
            visible_node_filters(workspace_id=workspace_id),
        )
    )
    if node is None:
        raise AppError("RESOURCE_NOT_FOUND", "Resource was not found.", 404)
    return node


def ensure_not_archived(node: LoadNode) -> None:
    if node.archived_at is not None:
        raise AppError("RESOURCE_NOT_FOUND", "Resource was not found.", 404)


def ensure_status_allows_change(node: LoadNode, *, action: str) -> None:
    ensure_not_archived(node)
    if node.status == "busy":
        raise AppError("LOAD_NODE_BUSY", "Load Node is busy.", 409)
    allowed = {"uninitialized", "idle", "offline"}
    if node.status not in allowed:
        raise AppError("LOAD_NODE_ACTION_NOT_ALLOWED", f"Load Node cannot be {action}.", 409)


def create_load_node(
    db: Session,
    *,
    actor: User,
    workspace_id: str,
    scope: str,
    host: str,
    ssh_port: int,
    ssh_user: str,
    runner_home: str,
    credential,
    ssh_host_key,
    maintainer: str | None,
    remark: str | None,
) -> LoadNode:
    scope = validate_scope(scope)
    require_admin_for_public(actor, scope)
    normalized_host = normalize_host(host)
    normalized_port = normalize_ssh_port(ssh_port)
    trusted_host_key = normalize_ssh_host_key(ssh_host_key)
    verify_live_ssh_host_key(
        host=normalized_host, ssh_port=normalized_port, trusted=trusted_host_key
    )
    node_id = new_ulid()
    now = utc_now()
    node = LoadNode(
        id=node_id,
        scope=scope,
        workspace_id=None if scope == "public" else workspace_id,
        host=normalized_host,
        ssh_port=normalized_port,
        ssh_user=normalize_ssh_user(ssh_user),
        runner_home=normalize_runner_home(runner_home),
        ssh_host_key_algorithm=trusted_host_key.algorithm,
        ssh_host_key_public_key=trusted_host_key.public_key,
        ssh_host_key_fingerprint_sha256=trusted_host_key.fingerprint_sha256,
        ssh_host_key_trusted_at=now,
        ssh_host_key_trusted_by=actor.id,
        auth_type=credential.auth_type,
        maintainer=normalize_optional_text(maintainer, field="maintainer"),
        remark=normalize_optional_text(remark, field="remark"),
        status="uninitialized",
        last_status_reason=None,
        created_by=actor.id,
        updated_by=actor.id,
        created_at=now,
        updated_at=now,
    )
    db.add(node)
    try:
        db.flush()
        apply_credential(db, node=node, input_credential=credential, actor_user_id=actor.id)
    except IntegrityError as exc:
        raise AppError("LOAD_NODE_CONFLICT", "Load Node already exists.", 409) from exc
    return node


def update_load_node(
    db: Session, *, node: LoadNode, actor: User, fields: dict[str, object]
) -> LoadNode:
    require_admin_for_public(actor, node)
    ensure_status_allows_change(node, action="updated")
    endpoint_changed = False
    if "host" in fields and fields["host"] is not None:
        next_host = normalize_host(str(fields["host"]))
        endpoint_changed = endpoint_changed or next_host != node.host
        node.host = next_host
    elif "host" in fields:
        raise validation_error([field_error("host", "Host cannot be null.")])
    if "ssh_port" in fields and fields["ssh_port"] is not None:
        next_port = normalize_ssh_port(int(fields["ssh_port"]))
        endpoint_changed = endpoint_changed or next_port != node.ssh_port
        node.ssh_port = next_port
    elif "ssh_port" in fields:
        raise validation_error([field_error("sshPort", "SSH port cannot be null.")])
    if "ssh_user" in fields and fields["ssh_user"] is not None:
        node.ssh_user = normalize_ssh_user(str(fields["ssh_user"]))
    elif "ssh_user" in fields:
        raise validation_error([field_error("sshUser", "SSH user cannot be null.")])
    if "runner_home" in fields and fields["runner_home"] is not None:
        node.runner_home = normalize_runner_home(str(fields["runner_home"]))
    elif "runner_home" in fields:
        raise validation_error([field_error("runnerHome", "Runner home cannot be null.")])
    if "maintainer" in fields:
        node.maintainer = normalize_optional_text(fields["maintainer"], field="maintainer")  # type: ignore[arg-type]
    if "remark" in fields:
        node.remark = normalize_optional_text(fields["remark"], field="remark")  # type: ignore[arg-type]
    if endpoint_changed:
        clear_ssh_host_key_trust(node)
    node.status = "uninitialized"
    node.last_status_reason = None
    node.updated_by = actor.id
    node.updated_at = utc_now()
    try:
        db.flush()
    except IntegrityError as exc:
        raise AppError("LOAD_NODE_CONFLICT", "Load Node already exists.", 409) from exc
    return node


def trust_load_node_ssh_host_key(
    db: Session, *, node: LoadNode, actor: User, ssh_host_key
) -> LoadNode:
    require_admin_for_public(actor, node)
    ensure_status_allows_change(node, action="trusted")
    trusted_host_key = normalize_ssh_host_key(ssh_host_key)
    verify_live_ssh_host_key(host=node.host, ssh_port=node.ssh_port, trusted=trusted_host_key)
    now = utc_now()
    node.ssh_host_key_algorithm = trusted_host_key.algorithm
    node.ssh_host_key_public_key = trusted_host_key.public_key
    node.ssh_host_key_fingerprint_sha256 = trusted_host_key.fingerprint_sha256
    node.ssh_host_key_trusted_at = now
    node.ssh_host_key_trusted_by = actor.id
    node.status = "uninitialized"
    node.last_status_reason = None
    node.updated_by = actor.id
    node.updated_at = now
    db.flush()
    return node


def update_load_node_credentials(
    db: Session, *, node: LoadNode, actor: User, credential
) -> LoadNode:
    require_admin_for_public(actor, node)
    ensure_status_allows_change(node, action="credential-updated")
    apply_credential(db, node=node, input_credential=credential, actor_user_id=actor.id)
    return node


def archive_load_node(db: Session, *, node: LoadNode, actor: User) -> None:
    ensure_not_archived(node)
    require_admin_for_public(actor, node)
    if node.status == "busy":
        raise AppError("LOAD_NODE_BUSY", "Busy Load Node cannot be archived.", 409)
    if node.status == "initializing":
        raise AppError("LOAD_NODE_ACTION_NOT_ALLOWED", "Load Node cannot be archived.", 409)
    node.archived_at = utc_now()
    node.archived_by = actor.id
    node.updated_by = actor.id
    node.updated_at = node.archived_at
    db.flush()


def disable_load_node(db: Session, *, node: LoadNode, actor: User, reason: str | None) -> LoadNode:
    ensure_not_archived(node)
    require_admin_for_public(actor, node)
    if node.status == "busy":
        raise AppError("LOAD_NODE_BUSY", "Busy Load Node cannot be disabled.", 409)
    if node.status == "initializing":
        raise AppError("LOAD_NODE_ACTION_NOT_ALLOWED", "Load Node cannot be disabled.", 409)
    node.status = "disabled"
    node.last_status_reason = normalize_optional_text(
        reason, field="reason", max_length=MAX_REASON_LENGTH
    )
    node.updated_by = actor.id
    node.updated_at = utc_now()
    db.flush()
    return node


def enable_load_node(db: Session, *, node: LoadNode, actor: User) -> LoadNode:
    ensure_not_archived(node)
    require_admin_for_public(actor, node)
    if node.status == "busy":
        raise AppError("LOAD_NODE_BUSY", "Busy Load Node cannot be enabled.", 409)
    if node.status != "disabled":
        raise AppError("LOAD_NODE_ACTION_NOT_ALLOWED", "Load Node cannot be enabled.", 409)
    node.status = "uninitialized"
    node.last_status_reason = None
    node.updated_by = actor.id
    node.updated_at = utc_now()
    db.flush()
    return node


def credential_for_node(db: Session, *, node: LoadNode) -> LoadNodeCredential:
    credential = db.get(LoadNodeCredential, node.id)
    if credential is None:
        raise AppError("LOAD_NODE_CREDENTIAL_REQUIRED", "Credential material is required.", 422)
    return credential


def decrypt_credential(credential: LoadNodeCredential) -> CredentialPlaintext:
    try:
        if credential.auth_type == "password":
            return CredentialPlaintext(
                auth_type="password",
                password=decrypt_secret(
                    credential.password_ciphertext or "", node_id=credential.node_id
                ),
            )
        private_key = decrypt_secret(
            credential.private_key_ciphertext or "", node_id=credential.node_id
        )
        passphrase = (
            decrypt_secret(credential.private_key_passphrase_ciphertext, node_id=credential.node_id)
            if credential.private_key_passphrase_ciphertext
            else None
        )
        return CredentialPlaintext(
            auth_type=credential.auth_type,
            private_key=private_key,
            private_key_passphrase=passphrase,
        )
    except AppError:
        raise
    except Exception as exc:
        raise AppError(
            "CREDENTIAL_DECRYPT_FAILED", "Credential material could not be decrypted.", 500
        ) from exc


def request_initialization(
    db: Session, *, node: LoadNode, actor: User, force: bool, request_id: str | None
) -> LoadNodeInitializationAttempt:
    ensure_not_archived(node)
    require_admin_for_public(actor, node)
    credential_for_node(db, node=node)
    require_trusted_ssh_host_key(node)
    if node.status == "busy":
        raise AppError("LOAD_NODE_BUSY", "Busy Load Node cannot be initialized.", 409)
    if node.status == "initializing":
        attempt = latest_active_attempt(db, node_id=node.id)
        if attempt is not None:
            return attempt
    elif node.status in {"uninitialized", "offline"}:
        pass
    elif node.status == "idle" and force:
        pass
    else:
        raise AppError("LOAD_NODE_ACTION_NOT_ALLOWED", "Load Node cannot be initialized.", 409)
    now = utc_now()
    attempt = LoadNodeInitializationAttempt(
        id=new_ulid(),
        node_id=node.id,
        status="queued",
        requested_by=actor.id,
        message="Initialization queued.",
        request_id=request_id,
        created_at=now,
        updated_at=now,
    )
    db.add(attempt)
    db.flush()
    node.status = "initializing"
    node.last_init_attempt_id = attempt.id
    node.last_status_reason = None
    node.updated_by = actor.id
    node.updated_at = now
    db.flush()
    return attempt


def latest_active_attempt(db: Session, *, node_id: str) -> LoadNodeInitializationAttempt | None:
    return db.scalar(
        select(LoadNodeInitializationAttempt)
        .where(
            LoadNodeInitializationAttempt.node_id == node_id,
            LoadNodeInitializationAttempt.status.in_(["queued", "running"]),
        )
        .order_by(
            LoadNodeInitializationAttempt.created_at.desc(), LoadNodeInitializationAttempt.id.desc()
        )
    )


def sanitize_log(value: str, *, max_bytes: int | None = None) -> str:
    redacted = value
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub(
            lambda m: f"{m.group(1)}[REDACTED]" if m.lastindex else "[REDACTED]", redacted
        )
    limit = max_bytes if max_bytes is not None else get_settings().load_node_init_log_tail_bytes
    raw = redacted.encode("utf-8")
    if len(raw) <= limit:
        return redacted
    tail = raw[-limit:].decode("utf-8", errors="ignore")
    return "[log truncated]\n" + tail


def claim_next_initialization_attempt(db: Session) -> LoadNodeInitializationAttempt | None:
    attempt = db.scalar(
        select(LoadNodeInitializationAttempt)
        .where(LoadNodeInitializationAttempt.status == "queued")
        .order_by(
            LoadNodeInitializationAttempt.created_at.asc(), LoadNodeInitializationAttempt.id.asc()
        )
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if attempt is None:
        return None
    attempt.status = "running"
    attempt.started_at = utc_now()
    attempt.updated_at = attempt.started_at
    db.flush()
    return attempt


def lock_active_running_attempt(
    db: Session, *, attempt_id: str
) -> tuple[LoadNodeInitializationAttempt | None, LoadNode | None]:
    attempt = db.scalar(
        select(LoadNodeInitializationAttempt)
        .where(LoadNodeInitializationAttempt.id == attempt_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if attempt is None or attempt.status != "running":
        return None, None
    node = db.scalar(
        select(LoadNode)
        .where(LoadNode.id == attempt.node_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if (
        node is None
        or node.archived_at is not None
        or node.status != "initializing"
        or node.last_init_attempt_id != attempt.id
    ):
        return None, None
    return attempt, node


def complete_initialization_attempt(
    db: Session,
    *,
    attempt: LoadNodeInitializationAttempt,
    initializer: LoadNodeInitializer | None = None,
) -> LoadNodeInitializationAttempt:
    active_attempt, node = lock_active_running_attempt(db, attempt_id=attempt.id)
    if active_attempt is None or node is None:
        return attempt
    try:
        credential = decrypt_credential(credential_for_node(db, node=node))
        if initializer is None:
            from app.services.load_node_initializer import RealLoadNodeInitializer

            initializer = RealLoadNodeInitializer()
        result = initializer.initialize(node, credential)
    except AppError as exc:
        active_attempt, node = lock_active_running_attempt(db, attempt_id=attempt.id)
        if active_attempt is not None and node is not None:
            fail_attempt(
                db, attempt=active_attempt, node=node, error_code=exc.code, log=exc.message
            )
        return attempt
    except Exception:
        logger.exception(
            "Load Node initialization failed", extra={"attempt_id": attempt.id, "node_id": node.id}
        )
        active_attempt, node = lock_active_running_attempt(db, attempt_id=attempt.id)
        if active_attempt is not None and node is not None:
            fail_attempt(
                db,
                attempt=active_attempt,
                node=node,
                error_code="LOAD_NODE_INIT_FAILED",
                log="Unexpected setup failure.",
            )
        return attempt
    active_attempt, node = lock_active_running_attempt(db, attempt_id=attempt.id)
    if active_attempt is None or node is None:
        return attempt
    if result.ok:
        succeed_attempt(db, attempt=active_attempt, node=node, result=result)
    else:
        fail_attempt(
            db,
            attempt=active_attempt,
            node=node,
            error_code=result.error_code or "LOAD_NODE_INIT_FAILED",
            log=result.log,
            message=result.message,
        )
    return attempt


def succeed_attempt(
    db: Session, *, attempt: LoadNodeInitializationAttempt, node: LoadNode, result: InitResult
) -> None:
    now = utc_now()
    attempt.status = "succeeded"
    attempt.finished_at = now
    attempt.message = result.message or "Initialization succeeded."
    attempt.sanitized_log_tail = sanitize_log(result.log)
    attempt.runner_version = result.runner_version
    attempt.bundle_version = result.bundle_version
    attempt.updated_at = now
    node.status = "idle"
    node.last_status_reason = None
    node.runner_version = result.runner_version
    node.bundle_version = result.bundle_version
    node.last_initialized_at = now
    node.last_checked_at = now
    node.updated_at = now
    db.flush()


def fail_attempt(
    db: Session,
    *,
    attempt: LoadNodeInitializationAttempt,
    node: LoadNode | None,
    error_code: str,
    log: str,
    message: str | None = None,
) -> None:
    now = utc_now()
    attempt.status = "failed"
    attempt.finished_at = now
    attempt.error_code = error_code
    attempt.message = message or "Initialization failed."
    attempt.sanitized_log_tail = sanitize_log(log)
    attempt.updated_at = now
    if node is not None and node.status != "busy":
        node.status = "uninitialized" if error_code in LOAD_NODE_HOST_KEY_ERROR_CODES else "offline"
        node.last_status_reason = error_code
        node.last_checked_at = now
        node.updated_at = now
    db.flush()


def recover_stale_running_attempts(db: Session) -> int:
    cutoff = utc_now() - timedelta(seconds=get_settings().load_node_init_timeout_seconds)
    attempts = db.scalars(
        select(LoadNodeInitializationAttempt)
        .where(
            LoadNodeInitializationAttempt.status == "running",
            LoadNodeInitializationAttempt.started_at.is_not(None),
            LoadNodeInitializationAttempt.started_at < cutoff,
        )
        .with_for_update(skip_locked=True)
    ).all()
    count = 0
    for attempt in attempts:
        node = db.get(LoadNode, attempt.node_id)
        active_for_node = (
            node is not None
            and node.status == "initializing"
            and node.last_init_attempt_id in {None, attempt.id}
        )
        if not active_for_node:
            fail_attempt(
                db,
                attempt=attempt,
                node=None,
                error_code="LOAD_NODE_INIT_FAILED",
                log="Initialization worker did not finish before timeout.",
            )
        else:
            fail_attempt(
                db,
                attempt=attempt,
                node=node,
                error_code="LOAD_NODE_INIT_FAILED",
                log="Initialization worker did not finish before timeout.",
            )
        count += 1
    return count


def recover_stale_initializing_nodes_without_active_attempts(db: Session) -> int:
    cutoff = utc_now() - timedelta(seconds=get_settings().load_node_init_timeout_seconds)
    nodes = db.scalars(
        select(LoadNode)
        .where(
            LoadNode.status == "initializing",
            LoadNode.archived_at.is_(None),
            LoadNode.updated_at < cutoff,
        )
        .with_for_update(skip_locked=True)
    ).all()
    count = 0
    for node in nodes:
        if latest_active_attempt(db, node_id=node.id) is not None:
            continue
        now = utc_now()
        node.status = "offline"
        node.last_status_reason = "LOAD_NODE_INIT_FAILED"
        node.last_checked_at = now
        node.updated_at = now
        count += 1
    if count:
        db.flush()
    return count


def audit_details(
    node: LoadNode, *, attempt_id: str | None = None, error_code: str | None = None
) -> dict[str, object | None]:
    return {
        "nodeId": node.id,
        "scope": node.scope,
        "workspaceId": node.workspace_id,
        "host": node.host,
        "sshPort": node.ssh_port,
        "status": node.status,
        "attemptId": attempt_id,
        "errorCode": error_code,
    }


def safe_write_load_node_audit(db: Session, **kwargs) -> None:
    try:
        write_audit_event(db, **kwargs)
    except Exception:
        logger.error("Failed to write load node audit event", exc_info=True)
