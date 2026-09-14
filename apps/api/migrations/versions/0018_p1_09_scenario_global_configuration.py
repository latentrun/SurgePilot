"""P1-09 Scenario global configuration fields."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0018_p1_09"
down_revision = "0017_p2_03"
branch_labels = None
depends_on = None


def json_type() -> sa.types.TypeEngine:
    return postgresql.JSONB().with_variant(sa.JSON(), "sqlite")


def upgrade() -> None:
    op.add_column(
        "scenarios",
        sa.Column(
            "global_headers_json",
            json_type(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )
    op.add_column(
        "scenarios",
        sa.Column(
            "variables_json",
            json_type(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )
    op.alter_column("scenarios", "global_headers_json", server_default=None)
    op.alter_column("scenarios", "variables_json", server_default=None)


def downgrade() -> None:
    op.drop_column("scenarios", "variables_json")
    op.drop_column("scenarios", "global_headers_json")
