from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, and_, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


LOAD_NODE_STATUSES = (
    "uninitialized",
    "initializing",
    "idle",
    "busy",
    "offline",
    "quarantined",
    "disabled",
)
LOAD_NODE_SCOPES = ("public", "workspace")
LOAD_NODE_AUTH_TYPES = ("password", "private_key", "generated_key")
INIT_ATTEMPT_STATUSES = ("queued", "running", "succeeded", "failed")


class LoadNode(Base):
    __tablename__ = "load_nodes"
    __table_args__ = (
        CheckConstraint("length(id) = 26", name="ck_load_nodes_id_len"),
        CheckConstraint("scope in ('public', 'workspace')", name="ck_load_nodes_scope"),
        CheckConstraint(
            "(scope = 'public' and workspace_id is null) or "
            "(scope = 'workspace' and workspace_id is not null)",
            name="ck_load_nodes_scope_workspace",
        ),
        CheckConstraint(
            "status in ('uninitialized', 'initializing', 'idle', 'busy', 'offline', "
            "'quarantined', 'disabled')",
            name="ck_load_nodes_status",
        ),
        CheckConstraint(
            "auth_type in ('password', 'private_key', 'generated_key')",
            name="ck_load_nodes_auth_type",
        ),
        CheckConstraint("ssh_port >= 1 and ssh_port <= 65535", name="ck_load_nodes_ssh_port"),
        CheckConstraint(
            "workspace_id is null or length(workspace_id) = 26",
            name="ck_load_nodes_workspace_id_len",
        ),
        CheckConstraint("length(created_by) = 26", name="ck_load_nodes_created_by_len"),
        CheckConstraint(
            "updated_by is null or length(updated_by) = 26", name="ck_load_nodes_updated_by_len"
        ),
        CheckConstraint(
            "archived_by is null or length(archived_by) = 26",
            name="ck_load_nodes_archived_by_len",
        ),
        CheckConstraint(
            "current_run_id is null or length(current_run_id) = 26",
            name="ck_load_nodes_current_run_id_len",
        ),
        CheckConstraint(
            "last_init_attempt_id is null or length(last_init_attempt_id) = 26",
            name="ck_load_nodes_last_init_attempt_id_len",
        ),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    workspace_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("workspaces.id", ondelete="CASCADE")
    )
    host: Mapped[str] = mapped_column(Text, nullable=False)
    ssh_port: Mapped[int] = mapped_column(nullable=False)
    ssh_user: Mapped[str] = mapped_column(Text, nullable=False)
    runner_home: Mapped[str] = mapped_column(Text, nullable=False)
    ssh_host_key_algorithm: Mapped[str | None] = mapped_column(Text)
    ssh_host_key_public_key: Mapped[str | None] = mapped_column(Text)
    ssh_host_key_fingerprint_sha256: Mapped[str | None] = mapped_column(Text)
    ssh_host_key_trusted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    ssh_host_key_trusted_by: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("users.id", ondelete="RESTRICT")
    )
    auth_type: Mapped[str] = mapped_column(Text, nullable=False)
    maintainer: Mapped[str | None] = mapped_column(Text)
    remark: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    last_status_reason: Mapped[str | None] = mapped_column(Text)
    runner_version: Mapped[str | None] = mapped_column(Text)
    bundle_version: Mapped[str | None] = mapped_column(Text)
    last_initialized_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_force_kill_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(nullable=True)
    current_run_id: Mapped[str | None] = mapped_column(
        String(26),
        ForeignKey(
            "runs.id", ondelete="SET NULL", use_alter=True, name="fk_load_nodes_current_run_id"
        ),
    )
    last_init_attempt_id: Mapped[str | None] = mapped_column(
        String(26),
        ForeignKey(
            "load_node_initialization_attempts.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_load_nodes_last_init_attempt_id",
        ),
    )
    created_by: Mapped[str] = mapped_column(
        String(26), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    updated_by: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("users.id", ondelete="RESTRICT")
    )
    archived_by: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("users.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(nullable=False)
    updated_at: Mapped[datetime] = mapped_column(nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(nullable=True)

    credential: Mapped["LoadNodeCredential"] = relationship(back_populates="node")


Index(
    "uq_load_nodes_public_active_endpoint",
    func.lower(LoadNode.host),
    LoadNode.ssh_port,
    func.lower(LoadNode.ssh_user),
    unique=True,
    sqlite_where=and_(LoadNode.scope == "public", LoadNode.archived_at.is_(None)),
    postgresql_where=and_(LoadNode.scope == "public", LoadNode.archived_at.is_(None)),
)
Index(
    "uq_load_nodes_workspace_active_endpoint",
    LoadNode.workspace_id,
    func.lower(LoadNode.host),
    LoadNode.ssh_port,
    func.lower(LoadNode.ssh_user),
    unique=True,
    sqlite_where=and_(LoadNode.scope == "workspace", LoadNode.archived_at.is_(None)),
    postgresql_where=and_(LoadNode.scope == "workspace", LoadNode.archived_at.is_(None)),
)
Index(
    "ix_load_nodes_scope_status_created",
    LoadNode.scope,
    LoadNode.status,
    LoadNode.created_at.desc(),
    LoadNode.id.desc(),
)
Index(
    "ix_load_nodes_workspace_status_created",
    LoadNode.workspace_id,
    LoadNode.status,
    LoadNode.created_at.desc(),
    LoadNode.id.desc(),
)
Index("ix_load_nodes_archived_at", LoadNode.archived_at)


class LoadNodeCredential(Base):
    __tablename__ = "load_node_credentials"
    __table_args__ = (
        CheckConstraint("length(node_id) = 26", name="ck_load_node_credentials_node_id_len"),
        CheckConstraint(
            "auth_type in ('password', 'private_key', 'generated_key')",
            name="ck_load_node_credentials_auth_type",
        ),
        CheckConstraint(
            "(auth_type = 'password' and password_ciphertext is not null and "
            "private_key_ciphertext is null and generated_public_key is null) or "
            "(auth_type = 'private_key' and password_ciphertext is null and "
            "private_key_ciphertext is not null and generated_public_key is null) or "
            "(auth_type = 'generated_key' and password_ciphertext is null and "
            "private_key_ciphertext is not null and generated_public_key is not null)",
            name="ck_load_node_credentials_material",
        ),
        CheckConstraint("length(updated_by) = 26", name="ck_load_node_credentials_updated_by_len"),
    )

    node_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("load_nodes.id", ondelete="RESTRICT"), primary_key=True
    )
    auth_type: Mapped[str] = mapped_column(Text, nullable=False)
    password_ciphertext: Mapped[str | None] = mapped_column(Text)
    private_key_ciphertext: Mapped[str | None] = mapped_column(Text)
    private_key_passphrase_ciphertext: Mapped[str | None] = mapped_column(Text)
    generated_public_key: Mapped[str | None] = mapped_column(Text)
    credential_fingerprint: Mapped[str | None] = mapped_column(Text)
    encryption_key_version: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(nullable=False)
    updated_at: Mapped[datetime] = mapped_column(nullable=False)
    updated_by: Mapped[str] = mapped_column(
        String(26), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    node: Mapped[LoadNode] = relationship(back_populates="credential")


class LoadNodeInitializationAttempt(Base):
    __tablename__ = "load_node_initialization_attempts"
    __table_args__ = (
        CheckConstraint("length(id) = 26", name="ck_load_node_init_attempts_id_len"),
        CheckConstraint("length(node_id) = 26", name="ck_load_node_init_attempts_node_id_len"),
        CheckConstraint(
            "length(requested_by) = 26", name="ck_load_node_init_attempts_requested_by_len"
        ),
        CheckConstraint(
            "status in ('queued', 'running', 'succeeded', 'failed')",
            name="ck_load_node_init_attempts_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    node_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("load_nodes.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    requested_by: Mapped[str] = mapped_column(
        String(26), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)
    error_code: Mapped[str | None] = mapped_column(Text)
    message: Mapped[str | None] = mapped_column(Text)
    sanitized_log_tail: Mapped[str | None] = mapped_column(Text)
    runner_version: Mapped[str | None] = mapped_column(Text)
    bundle_version: Mapped[str | None] = mapped_column(Text)
    request_id: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(nullable=False)
    updated_at: Mapped[datetime] = mapped_column(nullable=False)


Index(
    "ix_load_node_init_attempts_node_created",
    LoadNodeInitializationAttempt.node_id,
    LoadNodeInitializationAttempt.created_at.desc(),
    LoadNodeInitializationAttempt.id.desc(),
)
Index(
    "ix_load_node_init_attempts_status_created",
    LoadNodeInitializationAttempt.status,
    LoadNodeInitializationAttempt.created_at,
)
