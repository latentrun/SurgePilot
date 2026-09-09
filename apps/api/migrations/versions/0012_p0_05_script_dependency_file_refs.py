"""P0-05 script dependency file refs.

Revision ID: 0012_p0_05_script_refs
Revises: 0011_p1_03
"""

from alembic import op

revision = "0012_p0_05_script_refs"
down_revision = "0011_p1_03"
branch_labels = None
depends_on = None


CONSTRAINT_NAME = "ck_scenario_dependency_file_refs_type"
TABLE_NAME = "scenario_dependency_file_refs"


def upgrade() -> None:
    with op.batch_alter_table(TABLE_NAME) as batch_op:
        batch_op.drop_constraint(CONSTRAINT_NAME, type_="check")
        batch_op.create_check_constraint(
            CONSTRAINT_NAME,
            "ref_type in ('data_source', 'upload_file', 'script')",
        )


def downgrade() -> None:
    with op.batch_alter_table(TABLE_NAME) as batch_op:
        batch_op.drop_constraint(CONSTRAINT_NAME, type_="check")
        batch_op.create_check_constraint(
            CONSTRAINT_NAME,
            "ref_type in ('data_source', 'upload_file')",
        )
