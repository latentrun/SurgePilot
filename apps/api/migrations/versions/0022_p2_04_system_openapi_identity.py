"""Mark the single historical SurgePilot OpenAPI Catalog asset when unambiguous.

Revision ID: 0022_p2_04_system_openapi
Revises: 0021_p0_run_allocation_runtime
"""

from collections.abc import Sequence
import logging

from alembic import op
import sqlalchemy as sa


revision: str = "0022_p2_04_system_openapi"
down_revision: str | None = "0021_p0_run_allocation_runtime"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

logger = logging.getLogger(__name__)


def upgrade() -> None:
    op.add_column("api_catalog_specs", sa.Column("system_key", sa.Text(), nullable=True))

    specs = sa.table(
        "api_catalog_specs",
        sa.column("id", sa.Text()),
        sa.column("workspace_id", sa.Text()),
        sa.column("status", sa.Text()),
        sa.column("name", sa.Text()),
        sa.column("filename", sa.Text()),
        sa.column("document_title", sa.Text()),
        sa.column("source_format", sa.Text()),
        sa.column("created_by", sa.Text()),
        sa.column("system_key", sa.Text()),
    )
    users = sa.table("users", sa.column("id", sa.Text()), sa.column("created_at", sa.DateTime()))
    audits = sa.table(
        "audit_events",
        sa.column("event_type", sa.Text()),
        sa.column("target_type", sa.Text()),
        sa.column("target_id", sa.Text()),
    )
    first_user_id = sa.select(users.c.id).order_by(users.c.created_at, users.c.id).limit(1)
    uploaded_audit = sa.exists(
        sa.select(1).where(
            audits.c.event_type == "api_catalog_spec.uploaded",
            audits.c.target_type == "api_catalog_spec",
            audits.c.target_id == specs.c.id,
        )
    )
    candidate_ids = (
        op.get_bind()
        .execute(
            sa.select(specs.c.id).where(
                specs.c.system_key.is_(None),
                specs.c.workspace_id == "01HZW000000000000000000000",
                specs.c.status != "deleted",
                specs.c.name == "SurgePilot API",
                specs.c.filename == "surgepilot-api.openapi.json",
                specs.c.document_title == "SurgePilot API",
                specs.c.source_format == "openapi_json",
                specs.c.created_by == first_user_id.scalar_subquery(),
                ~uploaded_audit,
            )
        )
        .scalars()
        .all()
    )
    if len(candidate_ids) == 1:
        op.execute(
            specs.update().where(specs.c.id == candidate_ids[0]).values(system_key="surgepilot_api")
        )
    elif len(candidate_ids) > 1:
        logger.warning("System OpenAPI migration found multiple canonical candidates; none adopted")


def downgrade() -> None:
    op.drop_column("api_catalog_specs", "system_key")
