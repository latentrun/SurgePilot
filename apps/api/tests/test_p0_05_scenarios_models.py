from sqlalchemy import inspect

from app.models.scenarios import Scenario
from sqlalchemy.orm import Session


def test_p0_05_tables_exist_with_expected_indexes(db_session: Session) -> None:
    inspector = inspect(db_session.bind)

    assert "scenarios" in inspector.get_table_names()
    assert "scenario_dependency_file_refs" in inspector.get_table_names()
    assert "run_creation_dedup_keys" in inspector.get_table_names()

    scenario_columns = {column["name"] for column in inspector.get_columns("scenarios")}
    assert {
        "id",
        "workspace_id",
        "scenario_type",
        "name",
        "tags_json",
        "base_url_expression",
        "default_settings_json",
        "data_sources_json",
        "steps_json",
        "visual_schema_version",
        "revision",
        "deleted_at",
    }.issubset(scenario_columns)

    scenario_index_names = {index.name for index in Scenario.__table__.indexes}
    assert "ix_scenarios_workspace_deleted_updated" in scenario_index_names
    assert "ix_scenarios_workspace_name_lower" in scenario_index_names

    ref_index_names = {
        index["name"] for index in inspector.get_indexes("scenario_dependency_file_refs")
    }
    assert "ix_scenario_dependency_file_refs_workspace_file" in ref_index_names
    assert "ix_scenario_dependency_file_refs_workspace_scenario" in ref_index_names

    dedup_index_names = {
        index["name"] for index in inspector.get_indexes("run_creation_dedup_keys")
    }
    assert "uq_run_creation_dedup_keys_workspace_hash" in dedup_index_names
    assert "ix_run_creation_dedup_keys_expires" in dedup_index_names
