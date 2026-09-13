"""P2-03 Env Group typed secret variables."""

from alembic import op

revision = "0017_p2_03"
down_revision = "0016_p2_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE env_groups
        SET variables = COALESCE(
            (
                SELECT jsonb_object_agg(
                    key,
                    CASE
                        WHEN jsonb_typeof(value) = 'string'
                            THEN jsonb_build_object('type', 'plain', 'value', value #>> '{}')
                        ELSE value
                    END
                )
                FROM jsonb_each(env_groups.variables)
            ),
            '{}'::jsonb
        )
        WHERE variables <> '{}'::jsonb
          AND EXISTS (
              SELECT 1
              FROM jsonb_each(env_groups.variables) AS item(key, value)
              WHERE jsonb_typeof(item.value) = 'string'
          )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE env_groups
        SET variables = COALESCE(
            (
                SELECT jsonb_object_agg(key, COALESCE(value ->> 'value', ''))
                FROM jsonb_each(env_groups.variables)
            ),
            '{}'::jsonb
        )
        WHERE variables <> '{}'::jsonb
          AND EXISTS (
              SELECT 1
              FROM jsonb_each(env_groups.variables) AS item(key, value)
              WHERE jsonb_typeof(item.value) = 'object'
          )
        """
    )
