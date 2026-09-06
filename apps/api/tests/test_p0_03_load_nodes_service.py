from datetime import UTC, datetime, timedelta

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
import pytest
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.auth import DEFAULT_WORKSPACE_ID, User
from app.models.load_nodes import LoadNodeInitializationAttempt
from app.services.load_nodes import (
    DeterministicLoadNodeInitializer,
    FailingInitializer,
    LoadNodeInitializer,
    archive_load_node,
    claim_next_initialization_attempt,
    complete_initialization_attempt,
    create_load_node,
    decrypt_credential,
    disable_load_node,
    enable_load_node,
    encrypt_secret,
    recover_stale_initializing_nodes_without_active_attempts,
    recover_stale_running_attempts,
    request_initialization,
    sanitize_log,
    trust_load_node_ssh_host_key,
    update_load_node,
    update_load_node_credentials,
    validate_scope,
    normalize_host,
    normalize_runner_home,
    normalize_ssh_user,
)
from app.schemas.load_nodes import LoadNodeCredentialInput


def user(role: str = "user") -> User:
    now = datetime.now(UTC)
    return User(
        id="01HZX3Y9M0E9W7Z6M5QK9S8P7B" if role == "user" else "01HZX3Y9M0E9W7Z6M5QK9S8P7C",
        email=f"{role}@example.com",
        display_name=role.title(),
        password_hash="hash",
        role=role,
        status="active",
        failed_login_count=0,
        created_at=now,
        updated_at=now,
    )


def trusted_host_key() -> dict[str, str]:
    return {
        "algorithm": "ssh-ed25519",
        "publicKey": "AAAAC3NzaC1lZDI1NTE5AAAAIF6W/+2uAKbK71edPOwIYEGmhaggGtRy5wu0lXPVysEC",
        "fingerprintSha256": "SHA256:SurgePilotTrustedHostKey",
    }


def credential(auth_type: str = "password") -> LoadNodeCredentialInput:
    if auth_type == "password":
        return LoadNodeCredentialInput(authType="password", password="secret-password")
    if auth_type == "private_key":
        private_key = (
            ed25519.Ed25519PrivateKey.generate()
            .private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.OpenSSH,
                encryption_algorithm=serialization.BestAvailableEncryption(b"secret-passphrase"),
            )
            .decode()
        )
        return LoadNodeCredentialInput(
            authType="private_key",
            privateKey=private_key,
            privateKeyPassphrase="secret-passphrase",
        )
    return LoadNodeCredentialInput(authType="generated_key")


def create_private_node(db_session: Session, actor: User | None = None):
    actor = actor or user()
    db_session.add(actor)
    db_session.flush()
    return create_load_node(
        db_session,
        actor=actor,
        workspace_id=DEFAULT_WORKSPACE_ID,
        scope="workspace",
        host="load-node-01.internal",
        ssh_port=22,
        ssh_user="surgepilot",
        runner_home="/opt/surgepilot/runner",
        credential=credential(),
        ssh_host_key=trusted_host_key(),
        maintainer="Team",
        remark="Remark",
    )


def test_validation_rejects_host_user_runner_home_and_scope() -> None:
    assert normalize_host("node-01.internal") == "node-01.internal"
    assert normalize_ssh_user("surgepilot_1") == "surgepilot_1"
    assert normalize_runner_home("/opt/surgepilot/runner") == "/opt/surgepilot/runner"
    assert validate_scope("workspace") == "workspace"

    for value in ["http://node", "node/path", "bad node", "node;rm"]:
        with pytest.raises(AppError) as exc:
            normalize_host(value)
        assert exc.value.code == "LOAD_NODE_HOST_INVALID"

    for value in ["1bad", "bad user", "bad$user", "a" * 33]:
        with pytest.raises(AppError):
            normalize_ssh_user(value)

    for value in ["/", "relative/path", "/opt/../tmp", "/opt/load pilot", "/opt/x;y"]:
        with pytest.raises(AppError) as exc:
            normalize_runner_home(value)
        assert exc.value.code == "LOAD_NODE_RUNNER_HOME_INVALID"

    with pytest.raises(AppError):
        validate_scope("global")


def test_base_load_node_initializer_must_be_overridden() -> None:
    with pytest.raises(NotImplementedError):
        LoadNodeInitializer().initialize(create_private_node, None)  # type: ignore[arg-type]


def test_credential_encryption_round_trip_and_generated_key(db_session: Session) -> None:
    actor = user()
    node = create_private_node(db_session, actor)
    encrypted = encrypt_secret("plain-secret", node_id=node.id)
    assert "plain-secret" not in encrypted
    assert decrypt_credential(node.credential).password == "secret-password"
    assert node.credential.credential_fingerprint is None
    from app.services.load_nodes import decrypt_secret

    assert decrypt_secret(encrypted, node_id=node.id) == "plain-secret"

    update_load_node_credentials(
        db_session, node=node, actor=actor, credential=credential("generated_key")
    )
    assert node.auth_type == "generated_key"
    assert node.credential.generated_public_key is not None
    assert node.credential.credential_fingerprint is not None
    assert node.credential.credential_fingerprint.startswith("SHA256:")
    assert node.credential.private_key_ciphertext is not None
    assert "OPENSSH PRIVATE KEY" not in node.credential.private_key_ciphertext


def test_malformed_private_key_is_rejected_even_when_marker_is_present(db_session: Session) -> None:
    actor = user()
    node = create_private_node(db_session, actor)

    with pytest.raises(AppError) as exc:
        update_load_node_credentials(
            db_session,
            node=node,
            actor=actor,
            credential=LoadNodeCredentialInput(
                authType="private_key",
                privateKey=(
                    "-----BEGIN OPENSSH PRIVATE KEY-----\n"
                    "not-a-real-key\n"
                    "-----END OPENSSH PRIVATE KEY-----"
                ),
            ),
        )

    assert exc.value.code == "LOAD_NODE_CREDENTIAL_INVALID"


def test_missing_or_malformed_encryption_key_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SSH_CREDENTIAL_ENCRYPTION_KEY", "not-base64")
    with pytest.raises(AppError) as exc:
        encrypt_secret("secret", node_id="01HZX3Y9M0E9W7Z6M5QK9S8P7A")
    assert exc.value.code == "CREDENTIAL_DECRYPT_FAILED"


def test_duplicate_active_node_conflict_and_archive_re_registration(db_session: Session) -> None:
    actor = user()
    first = create_private_node(db_session, actor)
    db_session.commit()
    with pytest.raises(AppError) as conflict:
        create_load_node(
            db_session,
            actor=actor,
            workspace_id=DEFAULT_WORKSPACE_ID,
            scope="workspace",
            host="LOAD-node-01.internal",
            ssh_port=22,
            ssh_user="SurgePilot",
            runner_home="/opt/surgepilot/runner",
            credential=credential(),
            ssh_host_key=trusted_host_key(),
            maintainer=None,
            remark=None,
        )
    assert conflict.value.code == "LOAD_NODE_CONFLICT"
    db_session.rollback()
    first = db_session.get(type(first), first.id)
    assert first is not None
    first.archived_at = datetime.now(UTC)
    db_session.commit()
    second = create_load_node(
        db_session,
        actor=actor,
        workspace_id=DEFAULT_WORKSPACE_ID,
        scope="workspace",
        host="LOAD-node-01.internal",
        ssh_port=22,
        ssh_user="SurgePilot",
        runner_home="/opt/surgepilot/runner",
        credential=credential(),
        ssh_host_key=trusted_host_key(),
        maintainer=None,
        remark=None,
    )
    assert second.id != first.id


def test_admin_required_for_public_node(db_session: Session) -> None:
    actor = user()
    db_session.add(actor)
    db_session.flush()
    with pytest.raises(AppError) as exc:
        create_load_node(
            db_session,
            actor=actor,
            workspace_id=DEFAULT_WORKSPACE_ID,
            scope="public",
            host="public-node.internal",
            ssh_port=22,
            ssh_user="surgepilot",
            runner_home="/opt/surgepilot/runner",
            credential=credential(),
            ssh_host_key=trusted_host_key(),
            maintainer=None,
            remark=None,
        )
    assert exc.value.code == "LOAD_NODE_PUBLIC_ADMIN_REQUIRED"


def test_status_transitions_patch_credentials_init_and_worker(db_session: Session) -> None:
    actor = user()
    node = create_private_node(db_session, actor)
    node.status = "idle"
    updated = update_load_node(
        db_session, node=node, actor=actor, fields={"host": "load-node-02.internal"}
    )
    assert updated.status == "uninitialized"
    assert updated.ssh_host_key_algorithm is None
    trust_load_node_ssh_host_key(
        db_session, node=node, actor=actor, ssh_host_key=trusted_host_key()
    )
    update_load_node_credentials(
        db_session, node=node, actor=actor, credential=credential("private_key")
    )
    assert node.auth_type == "private_key"
    assert node.credential.credential_fingerprint is None
    assert node.status == "uninitialized"

    attempt = request_initialization(
        db_session, node=node, actor=actor, force=False, request_id="req_test"
    )
    assert node.status == "initializing"
    duplicate = request_initialization(
        db_session, node=node, actor=actor, force=True, request_id="req_test_2"
    )
    assert duplicate.id == attempt.id

    claimed = claim_next_initialization_attempt(db_session)
    assert claimed is not None
    assert claimed.id == attempt.id
    complete_initialization_attempt(
        db_session, attempt=claimed, initializer=DeterministicLoadNodeInitializer()
    )
    assert claimed.status == "succeeded"
    assert node.status == "idle"

    with pytest.raises(AppError) as no_force:
        request_initialization(db_session, node=node, actor=actor, force=False, request_id=None)
    assert no_force.value.code == "LOAD_NODE_ACTION_NOT_ALLOWED"

    forced = request_initialization(db_session, node=node, actor=actor, force=True, request_id=None)
    claimed = claim_next_initialization_attempt(db_session)
    assert claimed is not None and claimed.id == forced.id
    complete_initialization_attempt(
        db_session, attempt=claimed, initializer=FailingInitializer("LOAD_NODE_PYTHON_MISSING")
    )
    assert claimed.status == "failed"
    assert claimed.error_code == "LOAD_NODE_PYTHON_MISSING"
    assert node.status == "offline"

    host_key_attempt = request_initialization(
        db_session, node=node, actor=actor, force=True, request_id=None
    )
    claimed = claim_next_initialization_attempt(db_session)
    assert claimed is not None and claimed.id == host_key_attempt.id
    complete_initialization_attempt(
        db_session,
        attempt=claimed,
        initializer=FailingInitializer("LOAD_NODE_SSH_HOST_KEY_CHANGED"),
    )
    assert claimed.status == "failed"
    assert claimed.error_code == "LOAD_NODE_SSH_HOST_KEY_CHANGED"
    assert node.status == "uninitialized"
    assert node.last_status_reason == "LOAD_NODE_SSH_HOST_KEY_CHANGED"


def test_complete_initialization_uses_default_real_initializer_when_not_injected(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.services.load_node_initializer as initializer_module

    actor = user()
    node = create_private_node(db_session, actor)
    attempt = request_initialization(
        db_session, node=node, actor=actor, force=False, request_id="req_default_initializer"
    )
    claimed = claim_next_initialization_attempt(db_session)
    assert claimed is not None and claimed.id == attempt.id
    monkeypatch.setattr(
        initializer_module,
        "RealLoadNodeInitializer",
        lambda: DeterministicLoadNodeInitializer(),
    )

    complete_initialization_attempt(db_session, attempt=claimed)

    assert attempt.status == "succeeded"
    assert node.status == "idle"


def test_busy_and_quarantined_actions_are_guarded(db_session: Session) -> None:
    actor = user()
    node = create_private_node(db_session, actor)
    node.status = "busy"
    with pytest.raises(AppError) as busy:
        update_load_node(db_session, node=node, actor=actor, fields={"host": "other.internal"})
    assert busy.value.code == "LOAD_NODE_BUSY"
    with pytest.raises(AppError) as init_busy:
        request_initialization(db_session, node=node, actor=actor, force=True, request_id=None)
    assert init_busy.value.code == "LOAD_NODE_BUSY"
    with pytest.raises(AppError) as enable_busy:
        enable_load_node(db_session, node=node, actor=actor)
    assert enable_busy.value.code == "LOAD_NODE_BUSY"
    node.status = "quarantined"
    with pytest.raises(AppError) as quarantined:
        update_load_node_credentials(db_session, node=node, actor=actor, credential=credential())
    assert quarantined.value.code == "LOAD_NODE_ACTION_NOT_ALLOWED"
    with pytest.raises(AppError) as enable_quarantined:
        enable_load_node(db_session, node=node, actor=actor)
    assert enable_quarantined.value.code == "LOAD_NODE_ACTION_NOT_ALLOWED"


def test_disable_enable_archive_reject_invalid_states(db_session: Session) -> None:
    actor = user()
    node = create_private_node(db_session, actor)

    node.status = "initializing"
    for action in (
        lambda: disable_load_node(db_session, node=node, actor=actor, reason="Maintenance"),
        lambda: archive_load_node(db_session, node=node, actor=actor),
        lambda: enable_load_node(db_session, node=node, actor=actor),
    ):
        with pytest.raises(AppError) as exc:
            action()
        assert exc.value.code == "LOAD_NODE_ACTION_NOT_ALLOWED"
    assert node.status == "initializing"

    node.status = "idle"
    with pytest.raises(AppError) as enable_idle:
        enable_load_node(db_session, node=node, actor=actor)
    assert enable_idle.value.code == "LOAD_NODE_ACTION_NOT_ALLOWED"
    assert node.status == "idle"

    node.status = "disabled"
    enabled = enable_load_node(db_session, node=node, actor=actor)
    assert enabled.status == "uninitialized"


def test_archived_node_mutations_are_rejected(db_session: Session) -> None:
    actor = user()
    node = create_private_node(db_session, actor)
    node.archived_at = datetime.now(UTC)
    db_session.flush()

    mutations = [
        lambda: update_load_node(
            db_session, node=node, actor=actor, fields={"host": "archived-node.internal"}
        ),
        lambda: update_load_node_credentials(
            db_session, node=node, actor=actor, credential=credential()
        ),
        lambda: request_initialization(
            db_session, node=node, actor=actor, force=True, request_id=None
        ),
        lambda: disable_load_node(db_session, node=node, actor=actor, reason="Maintenance"),
        lambda: enable_load_node(db_session, node=node, actor=actor),
        lambda: archive_load_node(db_session, node=node, actor=actor),
    ]
    for mutation in mutations:
        with pytest.raises(AppError) as exc:
            mutation()
        assert exc.value.code == "RESOURCE_NOT_FOUND"


def test_log_redaction_tail_and_stale_attempt_recovery(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    actor = user()
    node = create_private_node(db_session, actor)
    redacted = sanitize_log(
        "password=hunter2 token=abc -----BEGIN OPENSSH PRIVATE KEY-----x-----END OPENSSH PRIVATE KEY-----",
        max_bytes=80,
    )
    assert "hunter2" not in redacted
    assert "abc" not in redacted
    assert "PRIVATE KEY" not in redacted

    attempt = LoadNodeInitializationAttempt(
        id="01HZX3Y9M0E9W7Z6M5QK9S8P7D",
        node_id=node.id,
        status="running",
        requested_by=actor.id,
        started_at=datetime.now(UTC) - timedelta(seconds=300),
        created_at=datetime.now(UTC) - timedelta(seconds=300),
        updated_at=datetime.now(UTC) - timedelta(seconds=300),
    )
    db_session.add(attempt)
    node.status = "initializing"
    monkeypatch.setenv("LOAD_NODE_INIT_TIMEOUT_SECONDS", "1")
    db_session.flush()
    assert recover_stale_running_attempts(db_session) == 1
    assert attempt.status == "failed"
    assert attempt.error_code == "LOAD_NODE_INIT_FAILED"
    assert node.status == "offline"


def test_stale_orphan_initialization_attempt_does_not_mark_newer_healthy_node_offline(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    actor = user()
    node = create_private_node(db_session, actor)
    stale_attempt = LoadNodeInitializationAttempt(
        id="01HZX3Y9M0E9W7Z6M5QK9S8P7D",
        node_id=node.id,
        status="running",
        requested_by=actor.id,
        started_at=datetime.now(UTC) - timedelta(seconds=300),
        created_at=datetime.now(UTC) - timedelta(seconds=300),
        updated_at=datetime.now(UTC) - timedelta(seconds=300),
    )
    db_session.add(stale_attempt)
    node.status = "idle"
    node.last_init_attempt_id = "01HZX3Y9M0E9W7Z6M5QK9S8P7E"
    monkeypatch.setenv("LOAD_NODE_INIT_TIMEOUT_SECONDS", "1")
    db_session.flush()

    assert recover_stale_running_attempts(db_session) == 1
    assert stale_attempt.status == "failed"
    assert stale_attempt.error_code == "LOAD_NODE_INIT_FAILED"
    assert node.status == "idle"
    assert node.last_init_attempt_id == "01HZX3Y9M0E9W7Z6M5QK9S8P7E"


def test_stale_initializing_node_without_active_attempt_recovers_to_offline(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    actor = user()
    node = create_private_node(db_session, actor)
    node.status = "initializing"
    node.last_init_attempt_id = "01HZX3Y9M0E9W7Z6M5QK9S8P7F"
    node.updated_at = datetime.now(UTC) - timedelta(seconds=300)
    monkeypatch.setenv("LOAD_NODE_INIT_TIMEOUT_SECONDS", "1")
    db_session.flush()

    assert recover_stale_initializing_nodes_without_active_attempts(db_session) == 1
    assert node.status == "offline"
    assert node.last_status_reason == "LOAD_NODE_INIT_FAILED"


def test_late_success_does_not_revive_timed_out_attempt(db_session: Session) -> None:
    actor = user()
    node = create_private_node(db_session, actor)
    attempt = request_initialization(
        db_session, node=node, actor=actor, force=False, request_id="req_late"
    )
    claimed = claim_next_initialization_attempt(db_session)
    assert claimed is not None
    assert claimed.id == attempt.id

    class TimeoutDuringInitialize(LoadNodeInitializer):
        def initialize(self, node, credential):  # noqa: ANN001
            attempt.status = "failed"
            attempt.error_code = "LOAD_NODE_INIT_FAILED"
            attempt.message = "Initialization failed."
            node.status = "offline"
            node.last_status_reason = "LOAD_NODE_INIT_FAILED"
            db_session.flush()
            return DeterministicLoadNodeInitializer().initialize(node, credential)

    complete_initialization_attempt(
        db_session, attempt=claimed, initializer=TimeoutDuringInitialize()
    )

    assert attempt.status == "failed"
    assert attempt.error_code == "LOAD_NODE_INIT_FAILED"
    assert node.status == "offline"


def test_completion_refreshes_external_timeout_before_succeeding(db_session: Session) -> None:
    actor = user()
    node = create_private_node(db_session, actor)
    attempt = request_initialization(
        db_session, node=node, actor=actor, force=False, request_id="req_external_timeout"
    )
    claimed = claim_next_initialization_attempt(db_session)
    assert claimed is not None
    assert claimed.id == attempt.id
    db_session.commit()

    with Session(db_session.get_bind()) as external_session:
        external_attempt = external_session.get(LoadNodeInitializationAttempt, attempt.id)
        external_node = external_session.get(type(node), node.id)
        assert external_attempt is not None
        assert external_node is not None
        external_attempt.status = "failed"
        external_attempt.error_code = "LOAD_NODE_INIT_FAILED"
        external_attempt.message = "Initialization failed."
        external_node.status = "offline"
        external_node.last_status_reason = "LOAD_NODE_INIT_FAILED"
        external_session.commit()

    assert claimed.status == "running"
    assert node.status == "initializing"

    complete_initialization_attempt(
        db_session, attempt=claimed, initializer=DeterministicLoadNodeInitializer()
    )

    db_session.expire_all()
    refreshed_attempt = db_session.get(LoadNodeInitializationAttempt, attempt.id)
    refreshed_node = db_session.get(type(node), node.id)
    assert refreshed_attempt is not None
    assert refreshed_node is not None
    assert refreshed_attempt.status == "failed"
    assert refreshed_attempt.error_code == "LOAD_NODE_INIT_FAILED"
    assert refreshed_node.status == "offline"


def test_completion_requires_current_active_attempt(db_session: Session) -> None:
    actor = user()
    node = create_private_node(db_session, actor)
    stale_attempt = request_initialization(
        db_session, node=node, actor=actor, force=False, request_id="req_stale"
    )
    claimed = claim_next_initialization_attempt(db_session)
    assert claimed is not None
    node.last_init_attempt_id = "01HZX3Y9M0E9W7Z6M5QK9S8P7F"
    db_session.flush()

    complete_initialization_attempt(
        db_session, attempt=claimed, initializer=DeterministicLoadNodeInitializer()
    )

    assert stale_attempt.status == "running"
    assert node.status == "initializing"
    assert node.last_init_attempt_id == "01HZX3Y9M0E9W7Z6M5QK9S8P7F"


def test_initializer_error_paths_fail_only_active_attempt(db_session: Session) -> None:
    actor = user()
    node = create_private_node(db_session, actor)
    attempt = request_initialization(
        db_session, node=node, actor=actor, force=False, request_id="req_error"
    )
    claimed = claim_next_initialization_attempt(db_session)
    assert claimed is not None

    class RaisesAppError(LoadNodeInitializer):
        def initialize(self, node, credential):  # noqa: ANN001
            raise AppError("LOAD_NODE_SSH_AUTH_FAILED", "Initialization failed.", 409)

    complete_initialization_attempt(db_session, attempt=claimed, initializer=RaisesAppError())
    assert attempt.status == "failed"
    assert attempt.error_code == "LOAD_NODE_SSH_AUTH_FAILED"
    assert node.status == "offline"

    retry = request_initialization(
        db_session, node=node, actor=actor, force=False, request_id="req_exception"
    )
    claimed_retry = claim_next_initialization_attempt(db_session)
    assert claimed_retry is not None and claimed_retry.id == retry.id

    class RaisesUnexpected(LoadNodeInitializer):
        def initialize(self, node, credential):  # noqa: ANN001
            raise RuntimeError("boom")

    complete_initialization_attempt(
        db_session, attempt=claimed_retry, initializer=RaisesUnexpected()
    )
    assert retry.status == "failed"
    assert retry.error_code == "LOAD_NODE_INIT_FAILED"
    assert node.status == "offline"


def test_late_initializer_errors_do_not_overwrite_timed_out_attempt(db_session: Session) -> None:
    actor = user()
    node = create_private_node(db_session, actor)
    attempt = request_initialization(
        db_session, node=node, actor=actor, force=False, request_id="req_late_error"
    )
    claimed = claim_next_initialization_attempt(db_session)
    assert claimed is not None

    class TimeoutThenAppError(LoadNodeInitializer):
        def initialize(self, node, credential):  # noqa: ANN001
            attempt.status = "failed"
            attempt.error_code = "LOAD_NODE_INIT_FAILED"
            node.status = "offline"
            db_session.flush()
            raise AppError("LOAD_NODE_SSH_AUTH_FAILED", "Initialization failed.", 409)

    complete_initialization_attempt(db_session, attempt=claimed, initializer=TimeoutThenAppError())
    assert attempt.status == "failed"
    assert attempt.error_code == "LOAD_NODE_INIT_FAILED"
    assert node.status == "offline"

    retry = request_initialization(
        db_session, node=node, actor=actor, force=False, request_id="req_late_unexpected"
    )
    claimed_retry = claim_next_initialization_attempt(db_session)
    assert claimed_retry is not None and claimed_retry.id == retry.id

    class TimeoutThenUnexpected(LoadNodeInitializer):
        def initialize(self, node, credential):  # noqa: ANN001
            retry.status = "failed"
            retry.error_code = "LOAD_NODE_INIT_FAILED"
            node.status = "offline"
            db_session.flush()
            raise RuntimeError("boom")

    complete_initialization_attempt(
        db_session, attempt=claimed_retry, initializer=TimeoutThenUnexpected()
    )
    assert retry.status == "failed"
    assert retry.error_code == "LOAD_NODE_INIT_FAILED"
    assert node.status == "offline"


def test_request_initialization_flushes_attempt_before_node_fk_update(monkeypatch) -> None:
    from types import SimpleNamespace

    import app.services.load_nodes as load_node_services

    class RecordingSession:
        def __init__(self) -> None:
            self.added = []
            self.flush_snapshots = []

        def add(self, value):  # noqa: ANN001
            self.added.append(value)

        def flush(self) -> None:
            self.flush_snapshots.append(
                {
                    "added_count": len(self.added),
                    "node_last_init_attempt_id": node.last_init_attempt_id,
                }
            )

    node = SimpleNamespace(
        id="01HZX3Y9M0E9W7Z6M5QK9S8P7N",
        scope="workspace",
        status="uninitialized",
        archived_at=None,
        last_init_attempt_id=None,
        last_status_reason="not ready",
        ssh_host_key_algorithm="ssh-ed25519",
        ssh_host_key_public_key="AAAAC3NzaC1lZDI1NTE5AAAAIF6W/+2uAKbK71edPOwIYEGmhaggGtRy5wu0lXPVysEC",
        ssh_host_key_fingerprint_sha256="SHA256:SurgePilotTrustedHostKey",
        updated_by=None,
        updated_at=None,
    )
    actor = user()
    db = RecordingSession()
    monkeypatch.setattr(load_node_services, "credential_for_node", lambda _db, *, node: object())

    attempt = request_initialization(db, node=node, actor=actor, force=False, request_id="req_1")

    assert attempt.id == node.last_init_attempt_id
    assert db.flush_snapshots[0] == {"added_count": 1, "node_last_init_attempt_id": None}
    assert db.flush_snapshots[-1]["node_last_init_attempt_id"] == attempt.id
