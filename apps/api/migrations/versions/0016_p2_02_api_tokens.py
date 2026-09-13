"""P2-02 API tokens for public API substrate."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0016_p2_02"
down_revision = "0015_p2_00"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_tokens",
        sa.Column("id", sa.String(length=26), primary_key=True, nullable=False),
        sa.Column("public_id", sa.String(length=26), nullable=False),
        sa.Column("secret_hash", sa.Text(), nullable=False),
        sa.Column("actor_user_id", sa.String(length=26), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "scopes",
            postgresql.JSONB().with_variant(sa.JSON(), "sqlite"),
            nullable=False,
        ),
        sa.Column(
            "workspace_allowlist",
            postgresql.JSONB().with_variant(sa.JSON(), "sqlite"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("length(id) = 26", name="ck_api_tokens_id_len"),
        sa.CheckConstraint("length(public_id) = 26", name="ck_api_tokens_public_id_len"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("public_id", name="uq_api_tokens_public_id"),
    )
    op.create_index(
        "ix_api_tokens_actor_user", "api_tokens", ["actor_user_id", "revoked_at", "expires_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_api_tokens_actor_user", table_name="api_tokens")
    op.drop_table("api_tokens")
