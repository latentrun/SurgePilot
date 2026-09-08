from datetime import UTC, datetime
from io import BytesIO

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models.auth import DEFAULT_WORKSPACE_ID, User
from app.models.load_nodes import LoadNode
from app.models.runs import Run, RunArtifact, RunReportSummary
from app.services.run_reports import (
    FINAL_STATS_TOTAL_ROW_MISSING,
    create_pending_final_stats_summary,
    parse_and_store_final_stats_summary,
    parse_final_stats_csv,
)
from app.services.storage import StoredObjectStream
from app.worker import run_once


def user() -> User:
    now = datetime.now(UTC)
    return User(
        id="01HZX3Y9M0E9W7Z6M5QK9S8P7A",
        email="report@example.com",
        display_name="Report User",
        password_hash="hash",
        role="user",
        status="active",
        failed_login_count=0,
        created_at=now,
        updated_at=now,
    )


def node(actor: User) -> LoadNode:
    now = datetime.now(UTC)
    return LoadNode(
        id="01HZX3Y9M0E9W7Z6M5QK9S8P7N",
        scope="workspace",
        workspace_id=DEFAULT_WORKSPACE_ID,
        host="load-01.internal",
        ssh_port=22,
        ssh_user="surgepilot",
        runner_home="/opt/surgepilot/runner",
        auth_type="password",
        status="idle",
        last_status_reason=None,
        created_by=actor.id,
        created_at=now,
        updated_at=now,
    )


def run(actor: User, selected_node: LoadNode, *, state: str = "finished") -> Run:
    now = datetime.now(UTC)
    return Run(
        id="01HZX3Y9M0E9W7Z6M5QK9S8P7R",
        workspace_id=DEFAULT_WORKSPACE_ID,
        run_type="standard",
        state=state,
        source_type="test_plan",
        source_id="01HZX3Y9M0E9W7Z6M5QK9S8P7P",
        selected_node_id=selected_node.id,
        triggered_by_user_id=actor.id,
        started_at=now,
        ended_at=now,
        forced_convergence=False,
        validity="valid",
        sla_result="failed",
        sla_result_reason=None,
        created_at=now,
        updated_at=now,
    )


def artifact(created_run: Run) -> RunArtifact:
    now = datetime.now(UTC)
    return RunArtifact(
        id="01HZX3Y9M0E9W7Z6M5QK9S8P7F",
        workspace_id=created_run.workspace_id,
        run_id=created_run.id,
        node_id=created_run.selected_node_id,
        event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7E",
        artifact_type="final_stats_csv",
        relative_path="artifacts/final_stats.csv",
        display_filename="final_stats.csv",
        size_bytes=128,
        sha256="a" * 64,
        content_type="text/csv",
        storage_key="run-artifacts/ws/run/artifacts/final_stats.csv",
        status="available",
        terminal_late=False,
        created_at=now,
    )


class FakeStorage:
    def __init__(self, objects: dict[str, bytes]) -> None:
        self.objects = objects

    def get_stream(self, *, bucket: str, object_key: str) -> StoredObjectStream:
        assert bucket == "surgepilot"
        return StoredObjectStream(
            "text/csv", len(self.objects[object_key]), BytesIO(self.objects[object_key])
        )


def csv_bytes(text: str) -> BytesIO:
    return BytesIO(text.encode("utf-8"))


def test_final_stats_parser_maps_taurus_fields_and_treats_throughput_as_total_count() -> None:
    result = parse_final_stats_csv(
        csv_bytes(
            "label,concurrency,throughput,succ,fail,avg_rt,perc_90.0,perc_95.0,perc_99.0,rc_200,rc_500\n"
            ",1,1200,1188,12,0.1532,0.420,0.610,0.950,1188,12\n"
            "GET /checkout,1,400,396,4,0.1884,0.500,0.700,0.980,396,4\n"
        )
    )

    assert result.parse_status == "parsed"
    assert result.truncated is False
    total = result.summary_json["total"]
    assert total["label"] is None
    assert total["totalRequests"] == 1200
    assert total["successRequests"] == 1188
    assert total["failedRequests"] == 12
    assert total["errorRate"] == 0.01
    assert total["averageResponseTimeMs"] == 153.2
    assert total["p90Ms"] == 420.0
    assert total["p95Ms"] == 610.0
    assert total["p99Ms"] == 950.0
    assert total["responseCodeCounts"] == {"200": 1188, "500": 12}
    assert "throughputPerSecond" not in total
    assert result.summary_json["rows"][0]["label"] == "GET /checkout"


def test_final_stats_parser_fails_safely_when_total_row_is_missing() -> None:
    result = parse_final_stats_csv(
        csv_bytes("label,throughput,succ,fail,avg_rt,perc_95.0\nGET /checkout,10,10,0,0.1,0.2\n")
    )

    assert result.parse_status == "failed"
    assert result.parse_error_code == FINAL_STATS_TOTAL_ROW_MISSING
    assert result.summary_json["warnings"] == [FINAL_STATS_TOTAL_ROW_MISSING]


def test_final_stats_parser_keeps_partial_data_and_bounds_preview_rows() -> None:
    rows = ["label,throughput,succ,fail,avg_rt,perc_90.0,perc_95.0,perc_99.0"]
    rows.append(",5,4,1,not-a-number,,bad,0.9")
    rows.extend(f"label-{index},1,1,0,0.1,0.2,0.3,0.4" for index in range(5))

    result = parse_final_stats_csv(csv_bytes("\n".join(rows)), max_rows=2)

    assert result.parse_status == "parsed"
    assert result.truncated is True
    assert result.summary_json["total"]["averageResponseTimeMs"] is None
    assert result.summary_json["total"]["p90Ms"] is None
    assert result.summary_json["total"]["p95Ms"] is None
    assert result.summary_json["total"]["p99Ms"] == 900.0
    assert len(result.summary_json["rows"]) == 2
    assert set(result.summary_json["warnings"]) >= {
        "average_response_time_invalid",
        "percentile_column_missing",
        "percentile_value_invalid",
    }


def test_final_stats_parser_rejects_non_finite_numbers_without_raising() -> None:
    result = parse_final_stats_csv(
        csv_bytes(
            "label,throughput,succ,fail,avg_rt,perc_90.0,perc_95.0,perc_99.0,rc_200\n"
            ",NaN,Inf,-Inf,NaN,Inf,-Inf,0.9,NaN\n"
        )
    )

    assert result.parse_status == "parsed"
    total = result.summary_json["total"]
    assert total["totalRequests"] is None
    assert total["successRequests"] is None
    assert total["failedRequests"] is None
    assert total["averageResponseTimeMs"] is None
    assert total["p90Ms"] is None
    assert total["p95Ms"] is None
    assert total["p99Ms"] == 900.0
    assert total["responseCodeCounts"] == {}
    assert set(result.summary_json["warnings"]) >= {
        "total_requests_invalid",
        "success_requests_invalid",
        "failed_requests_invalid",
        "average_response_time_invalid",
        "percentile_value_invalid",
        "response_code_count_invalid",
    }


def test_final_stats_parse_failure_is_stored_without_mutating_run_state(
    db_session: Session,
) -> None:
    actor = user()
    selected_node = node(actor)
    created_run = run(actor, selected_node)
    final_stats = artifact(created_run)
    db_session.add_all([actor, selected_node, created_run, final_stats])
    db_session.flush()

    parse_and_store_final_stats_summary(
        db_session,
        artifact=final_stats,
        stream=csv_bytes("label,throughput,succ,fail\nGET /only,1,1,0\n"),
    )

    db_session.flush()
    stored_run = db_session.get(Run, created_run.id)
    assert stored_run is not None
    assert stored_run.state == "finished"
    assert stored_run.sla_result == "failed"
    summary = db_session.scalar(
        select(RunReportSummary).where(RunReportSummary.run_id == created_run.id)
    )
    assert summary is not None
    assert summary.parse_status == "failed"
    assert summary.parse_error_code == FINAL_STATS_TOTAL_ROW_MISSING


def test_api_worker_processes_pending_final_stats_summary(db_session: Session, monkeypatch) -> None:
    actor = user()
    selected_node = node(actor)
    created_run = run(actor, selected_node)
    final_stats = artifact(created_run)
    db_session.add_all([actor, selected_node, created_run, final_stats])
    db_session.flush()
    create_pending_final_stats_summary(db_session, artifact=final_stats)
    db_session.commit()
    monkeypatch.setattr(
        "app.services.run_reports.get_storage_client",
        lambda: FakeStorage(
            {
                final_stats.storage_key: (
                    b"label,throughput,succ,fail,avg_rt,perc_90.0,perc_95.0,perc_99.0\n"
                    b",10,9,1,0.12,0.20,0.30,0.40\n"
                )
            }
        ),
    )
    factory = sessionmaker(
        bind=db_session.get_bind(), autoflush=False, expire_on_commit=False, future=True
    )

    assert run_once(factory) >= 1

    db_session.expire_all()
    stored_run = db_session.get(Run, created_run.id)
    assert stored_run is not None
    assert stored_run.state == "finished"
    summary = db_session.scalar(
        select(RunReportSummary).where(RunReportSummary.run_id == created_run.id)
    )
    assert summary is not None
    assert summary.parse_status == "parsed"
    assert summary.summary_json["total"]["totalRequests"] == 10
    assert summary.summary_json["total"]["averageResponseTimeMs"] == 120.0
