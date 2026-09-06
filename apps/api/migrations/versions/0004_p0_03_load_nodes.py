"""P0-03 load nodes."""

from alembic import op
import sqlalchemy as sa

revision = "0004_p0_03"
down_revision = "0003_p0_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "load_nodes",
        sa.Column("id", sa.String(length=26), primary_key=True, nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("workspace_id", sa.String(length=26), nullable=True),
        sa.Column("host", sa.Text(), nullable=False),
        sa.Column("ssh_port", sa.Integer(), nullable=False),
        sa.Column("ssh_user", sa.Text(), nullable=False),
        sa.Column("runner_home", sa.Text(), nullable=False),
        sa.Column("auth_type", sa.Text(), nullable=False),
        sa.Column("maintainer", sa.Text(), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("last_status_reason", sa.Text(), nullable=True),
        sa.Column("runner_version", sa.Text(), nullable=True),
        sa.Column("bundle_version", sa.Text(), nullable=True),
        sa.Column("last_initialized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_run_id", sa.String(length=26), nullable=True),
        sa.Column("last_init_attempt_id", sa.String(length=26), nullable=True),
        sa.Column("created_by", sa.String(length=26), nullable=False),
        sa.Column("updated_by", sa.String(length=26), nullable=True),
        sa.Column("archived_by", sa.String(length=26), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("length(id) = 26", name="ck_load_nodes_id_len"),
        sa.CheckConstraint("scope in ('public', 'workspace')", name="ck_load_nodes_scope"),
        sa.CheckConstraint(
            "(scope = 'public' and workspace_id is null) or "
            "(scope = 'workspace' and workspace_id is not null)",
            name="ck_load_nodes_scope_workspace",
        ),
        sa.CheckConstraint(
            "status in ('uninitialized', 'initializing', 'idle', 'busy', 'offline', "
            "'quarantined', 'disabled')",
            name="ck_load_nodes_status",
        ),
        sa.CheckConstraint(
            "auth_type in ('password', 'private_key', 'generated_key')",
            name="ck_load_nodes_auth_type",
        ),
        sa.CheckConstraint("ssh_port >= 1 and ssh_port <= 65535", name="ck_load_nodes_ssh_port"),
        sa.CheckConstraint(
            "workspace_id is null or length(workspace_id) = 26",
            name="ck_load_nodes_workspace_id_len",
        ),
        sa.CheckConstraint("length(created_by) = 26", name="ck_load_nodes_created_by_len"),
        sa.CheckConstraint(
            "updated_by is null or length(updated_by) = 26", name="ck_load_nodes_updated_by_len"
        ),
        sa.CheckConstraint(
            "archived_by is null or length(archived_by) = 26",
            name="ck_load_nodes_archived_by_len",
        ),
        sa.CheckConstraint(
            "current_run_id is null or length(current_run_id) = 26",
            name="ck_load_nodes_current_run_id_len",
        ),
        sa.CheckConstraint(
            "last_init_attempt_id is null or length(last_init_attempt_id) = 26",
            name="ck_load_nodes_last_init_attempt_id_len",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["archived_by"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        "uq_load_nodes_public_active_endpoint",
        "load_nodes",
        [sa.text("lower(host)"), "ssh_port", sa.text("lower(ssh_user)")],
        unique=True,
        postgresql_where=sa.text("scope = 'public' and archived_at is null"),
    )
    op.create_index(
        "uq_load_nodes_workspace_active_endpoint",
        "load_nodes",
        ["workspace_id", sa.text("lower(host)"), "ssh_port", sa.text("lower(ssh_user)")],
        unique=True,
        postgresql_where=sa.text("scope = 'workspace' and archived_at is null"),
    )
    op.create_index(
        "ix_load_nodes_scope_status_created",
        "load_nodes",
        ["scope", "status", sa.text("created_at DESC"), sa.text("id DESC")],
    )
    op.create_index(
        "ix_load_nodes_workspace_status_created",
        "load_nodes",
        ["workspace_id", "status", sa.text("created_at DESC"), sa.text("id DESC")],
    )
    op.create_index("ix_load_nodes_archived_at", "load_nodes", ["archived_at"])

    op.create_table(
        "load_node_credentials",
        sa.Column("node_id", sa.String(length=26), primary_key=True, nullable=False),
        sa.Column("auth_type", sa.Text(), nullable=False),
        sa.Column("password_ciphertext", sa.Text(), nullable=True),
        sa.Column("private_key_ciphertext", sa.Text(), nullable=True),
        sa.Column("private_key_passphrase_ciphertext", sa.Text(), nullable=True),
        sa.Column("generated_public_key", sa.Text(), nullable=True),
        sa.Column("credential_fingerprint", sa.Text(), nullable=True),
        sa.Column("encryption_key_version", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.String(length=26), nullable=False),
        sa.CheckConstraint("length(node_id) = 26", name="ck_load_node_credentials_node_id_len"),
        sa.CheckConstraint(
            "auth_type in ('password', 'private_key', 'generated_key')",
            name="ck_load_node_credentials_auth_type",
        ),
        sa.CheckConstraint(
            "(auth_type = 'password' and password_ciphertext is not null and "
            "private_key_ciphertext is null and generated_public_key is null) or "
            "(auth_type = 'private_key' and password_ciphertext is null and "
            "private_key_ciphertext is not null and generated_public_key is null) or "
            "(auth_type = 'generated_key' and password_ciphertext is null and "
            "private_key_ciphertext is not null and generated_public_key is not null)",
            name="ck_load_node_credentials_material",
        ),
        sa.CheckConstraint(
            "length(updated_by) = 26", name="ck_load_node_credentials_updated_by_len"
        ),
        sa.ForeignKeyConstraint(["node_id"], ["load_nodes.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="RESTRICT"),
    )

    op.create_table(
        "load_node_initialization_attempts",
        sa.Column("id", sa.String(length=26), primary_key=True, nullable=False),
        sa.Column("node_id", sa.String(length=26), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("requested_by", sa.String(length=26), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("sanitized_log_tail", sa.Text(), nullable=True),
        sa.Column("runner_version", sa.Text(), nullable=True),
        sa.Column("bundle_version", sa.Text(), nullable=True),
        sa.Column("request_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("length(id) = 26", name="ck_load_node_init_attempts_id_len"),
        sa.CheckConstraint("length(node_id) = 26", name="ck_load_node_init_attempts_node_id_len"),
        sa.CheckConstraint(
            "length(requested_by) = 26", name="ck_load_node_init_attempts_requested_by_len"
        ),
        sa.CheckConstraint(
            "status in ('queued', 'running', 'succeeded', 'failed')",
            name="ck_load_node_init_attempts_status",
        ),
        sa.ForeignKeyConstraint(["node_id"], ["load_nodes.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        "ix_load_node_init_attempts_node_created",
        "load_node_initialization_attempts",
        ["node_id", sa.text("created_at DESC"), sa.text("id DESC")],
    )
    op.create_index(
        "ix_load_node_init_attempts_status_created",
        "load_node_initialization_attempts",
        ["status", "created_at"],
    )
    op.create_foreign_key(
        "fk_load_nodes_last_init_attempt_id",
        "load_nodes",
        "load_node_initialization_attempts",
        ["last_init_attempt_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_load_nodes_last_init_attempt_id", "load_nodes", type_="foreignkey")
    op.drop_index(
        "ix_load_node_init_attempts_status_created",
        table_name="load_node_initialization_attempts",
    )
    op.drop_index(
        "ix_load_node_init_attempts_node_created",
        table_name="load_node_initialization_attempts",
    )
    op.drop_table("load_node_initialization_attempts")
    op.drop_table("load_node_credentials")
    op.drop_index("ix_load_nodes_archived_at", table_name="load_nodes")
    op.drop_index("ix_load_nodes_workspace_status_created", table_name="load_nodes")
    op.drop_index("ix_load_nodes_scope_status_created", table_name="load_nodes")
    op.drop_index("uq_load_nodes_workspace_active_endpoint", table_name="load_nodes")
    op.drop_index("uq_load_nodes_public_active_endpoint", table_name="load_nodes")
    op.drop_table("load_nodes")
