from datetime import UTC, datetime, timedelta
from io import BytesIO

import pytest
from httpx import AsyncClient
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.models.auth import AuditEvent, DEFAULT_WORKSPACE_ID, User, Workspace, WorkspaceMember
from app.models.load_nodes import LoadNode
from app.models.runs import Run, RunArtifact, RunReportSummary, RunSnapshot
from app.core.ids import new_ulid
from app.services.storage import StoredObjectStream
from app.services.run_reports import get_run_report, list_runs_report

OTHER_WORKSPACE_ID = "01HZX3Y9M0E9W7Z6M5QK9S8P7W"


class QueryCounter:
    def __init__(self, session: Session) -> None:
        self._engine = session.get_bind()
        self.count = 0

    def __enter__(self) -> "QueryCounter":
        event.listen(self._engine, "before_cursor_execute", self._before_cursor_execute)
        return self

    def __exit__(self, *args: object) -> None:
        event.remove(self._engine, "before_cursor_execute", self._before_cursor_execute)

    def _before_cursor_execute(self, *args: object) -> None:
        self.count += 1


async def register(client: AsyncClient, email: str) -> tuple[str, str, str]:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "displayName": "Report User", "password": "password123"},
    )
    assert response.status_code == 201
    body = response.json()
    return body["csrfToken"], body["defaultWorkspace"]["id"], body["user"]["id"]


def seed_node(db: Session, user_id: str, *, node_id: str, workspace_id: str) -> LoadNode:
    now = datetime(2030, 6, 3, 8, 0, tzinfo=UTC)
    node = LoadNode(
        id=node_id,
        scope="workspace",
        workspace_id=workspace_id,
        host=f"{node_id[-4:].lower()}.internal",
        ssh_port=22,
        ssh_user="surgepilot",
        runner_home="/opt/surgepilot/runner",
        auth_type="password",
        status="idle",
        runtime_version="runtime-test-v1",
        last_status_reason=None,
        last_heartbeat_at=now,
        created_by=user_id,
        created_at=now,
        updated_at=now,
    )
    db.add(node)
    return node


def seed_run(
    db: Session,
    *,
    user_id: str,
    run_id: str,
    node: LoadNode,
    workspace_id: str = DEFAULT_WORKSPACE_ID,
    state: str = "finished",
    validity: str | None = "valid",
    sla_result: str = "failed",
    run_type: str = "standard",
    source_name: str = "Checkout Load Test",
    tags: list[str] | None = None,
    created_at: datetime | None = None,
) -> Run:
    created_at = created_at or datetime(2030, 6, 3, 8, 0, tzinfo=UTC)
    run = Run(
        id=run_id,
        workspace_id=workspace_id,
        run_type=run_type,
        state=state,
        source_type="test_plan",
        source_id="01HZX3Y9M0E9W7Z6M5QK9S8P7P",
        selected_node_id=node.id,
        triggered_by_user_id=user_id,
        accepted_at=created_at + timedelta(seconds=2),
        started_at=created_at + timedelta(seconds=5),
        ended_at=(created_at + timedelta(minutes=5, seconds=10)) if state == "finished" else None,
        last_heartbeat_at=created_at + timedelta(minutes=5),
        failure_reason=None,
        failure_message=None,
        forced_convergence=False,
        validity=validity,
        sla_result=sla_result,
        sla_result_reason=None,
        created_at=created_at,
        updated_at=created_at,
    )
    db.add(run)
    db.flush()
    db.add(
        RunSnapshot(
            id=f"{run_id[:-2]}{run_id[-1]}S",
            workspace_id=workspace_id,
            run_id=run.id,
            snapshot_version=1,
            snapshot_hash="0" * 64,
            snapshot_json={
                "schemaVersion": 1,
                "runType": run.run_type,
                "sourceType": "test_plan",
                "sourceId": run.source_id,
                "sourceRevision": 4,
                "validityDefault": "valid",
                "slaEvaluationMode": "passfail",
                "testPlan": {
                    "id": run.source_id,
                    "name": source_name,
                    "tags": tags if tags is not None else ["checkout"],
                    "revision": 4,
                    "runMode": "sequential",
                },
                "envGroup": {
                    "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7E",
                    "name": "Staging",
                    "variables": {
                        "BASE_URL": "https://staging.example.test",
                        "API_TOKEN": "secret-token",
                    },
                },
                "resourceRequest": {
                    "mode": "manual",
                    "poolType": "workspace",
                    "selectedNodeId": node.id,
                    "expectedConcurrencyPerNode": 10,
                },
                "scenarioItems": [
                    {
                        "scenarioName": "Checkout scenario",
                        "loadSettings": {
                            "concurrencyPerNode": 10,
                            "rampUpSeconds": 30,
                            "holdForSeconds": 300,
                            "iterations": None,
                            "targetRps": 50,
                            "steps": 5,
                            "delaySeconds": 7,
                        },
                    }
                ],
                "dependencyFiles": [{"filename": "users.csv"}],
                "slaRules": [
                    {
                        "subject": "p95",
                        "condition": "lte",
                        "threshold": {"value": 500, "unit": "ms"},
                    }
                ],
                "generatedYaml": {
                    "artifactRelativePath": "execution/generated.yml",
                    "sha256": "b" * 64,
                },
            },
            created_at=created_at,
        )
    )
    return run


def seed_artifact(
    db: Session,
    *,
    run: Run,
    artifact_id: str,
    artifact_type: str,
    relative_path: str,
    status: str = "available",
) -> RunArtifact:
    created_at = datetime(2030, 6, 3, 8, 5, 18, tzinfo=UTC)
    artifact = RunArtifact(
        id=artifact_id,
        workspace_id=run.workspace_id,
        run_id=run.id,
        node_id=run.selected_node_id,
        event_id=f"{artifact_id[:-2]}{artifact_id[-1]}E",
        artifact_type=artifact_type,
        relative_path=relative_path,
        display_filename=relative_path.rsplit("/", 1)[-1],
        size_bytes=2048,
        sha256="a" * 64,
        content_type="application/zip" if artifact_type == "artifacts_zip" else "text/csv",
        storage_key=(
            f"run-artifacts/{run.workspace_id}/{run.id}/nodes/{run.selected_node_id}/{relative_path}"
        ),
        status=status,
        terminal_late=False,
        created_at=created_at,
    )
    db.add(artifact)
    return artifact


def seed_summary(db: Session, *, run: Run, artifact: RunArtifact) -> None:
    now = datetime(2030, 6, 3, 8, 5, 20, tzinfo=UTC)
    db.add(
        RunReportSummary(
            id="01HZX3Y9M0E9W7Z6M5QK9S8P7Y",
            workspace_id=run.workspace_id,
            run_id=run.id,
            source_artifact_id=artifact.id,
            summary_type="final_stats",
            summary_json={
                "schemaVersion": 1,
                "total": {
                    "label": None,
                    "totalRequests": 1200,
                    "successRequests": 1188,
                    "failedRequests": 12,
                    "errorRate": 0.01,
                    "averageResponseTimeMs": 153.2,
                    "p90Ms": 420.0,
                    "p95Ms": 610.0,
                    "p99Ms": 950.0,
                    "responseCodeCounts": {"200": 1188, "500": 12},
                },
                "rows": [
                    {
                        "label": "GET /checkout",
                        "totalRequests": 400,
                        "successRequests": 396,
                        "failedRequests": 4,
                        "errorRate": 0.01,
                        "averageResponseTimeMs": 188.4,
                        "p90Ms": 500.0,
                        "p95Ms": 700.0,
                        "p99Ms": 980.0,
                        "responseCodeCounts": {"200": 396, "500": 4},
                    }
                ],
                "warnings": [],
            },
            truncated=False,
            parse_status="parsed",
            parse_error_code=None,
            created_at=now,
            updated_at=now,
        )
    )


def seed_final_stats_summary(
    db: Session,
    *,
    run: Run,
    artifact: RunArtifact,
    total_requests: int | None,
    failed_requests: int | None,
    average_response_time_ms: float | None,
    response_code_counts: dict[str, int] | None = None,
    parse_status: str = "parsed",
    warnings: list[str] | None = None,
) -> RunReportSummary:
    now = datetime(2030, 6, 3, 8, 5, 20, tzinfo=UTC)
    summary = RunReportSummary(
        id=new_ulid(),
        workspace_id=run.workspace_id,
        run_id=run.id,
        source_artifact_id=artifact.id,
        summary_type="final_stats",
        summary_json={
            "schemaVersion": 1,
            "total": {
                "label": None,
                "totalRequests": total_requests,
                "successRequests": None
                if total_requests is None or failed_requests is None
                else total_requests - failed_requests,
                "failedRequests": failed_requests,
                "errorRate": None
                if total_requests in (None, 0) or failed_requests is None
                else failed_requests / total_requests,
                "averageResponseTimeMs": average_response_time_ms,
                "p90Ms": 123.0,
                "p95Ms": 234.0,
                "p99Ms": 345.0,
                "responseCodeCounts": response_code_counts or {},
            },
            "rows": [
                {
                    "label": "GET /checkout",
                    "totalRequests": total_requests,
                    "successRequests": None
                    if total_requests is None or failed_requests is None
                    else total_requests - failed_requests,
                    "failedRequests": failed_requests,
                    "errorRate": None
                    if total_requests in (None, 0) or failed_requests is None
                    else failed_requests / total_requests,
                    "averageResponseTimeMs": average_response_time_ms,
                    "p90Ms": 123.0,
                    "p95Ms": 234.0,
                    "p99Ms": 345.0,
                    "responseCodeCounts": response_code_counts or {},
                }
            ],
            "warnings": warnings or [],
        },
        truncated=False,
        parse_status=parse_status,
        parse_error_code="FINAL_STATS_PARSE_FAILED" if parse_status == "failed" else None,
        created_at=now,
        updated_at=now,
    )
    db.add(summary)
    return summary


class FakeStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def get_stream(self, *, bucket: str, object_key: str) -> StoredObjectStream:
        assert bucket == "surgepilot"
        if object_key not in self.objects:
            raise AssertionError("test storage object missing")
        return StoredObjectStream(
            "application/octet-stream",
            len(self.objects[object_key]),
            BytesIO(self.objects[object_key]),
        )


@pytest.mark.anyio
async def test_run_report_detail_tolerates_malformed_snapshot_summary_values(
    client: AsyncClient, db_session: Session
) -> None:
    _csrf, workspace_id, user_id = await register(client, "runs-malformed-snapshot@example.com")
    node = seed_node(
        db_session, user_id, node_id="01HZX3Y9M0E9W7Z6M5QK9S8P7N", workspace_id=workspace_id
    )
    created_run = seed_run(
        db_session,
        user_id=user_id,
        run_id="01HZX3Y9M0E9W7Z6M5QK9S8P7R",
        node=node,
        sla_result="not_evaluated",
    )
    db_session.flush()
    snapshot = db_session.scalar(select(RunSnapshot).where(RunSnapshot.run_id == created_run.id))
    assert snapshot is not None
    snapshot.snapshot_json["scenarioItems"] = [
        {
            "scenarioName": "Malformed scenario",
            "loadSettings": {
                "concurrencyPerNode": {},
                "rampUpSeconds": "not-a-number",
                "holdForSeconds": ["bad"],
                "iterations": True,
                "targetRps": "NaN",
                "steps": None,
                "delaySeconds": {"bad": "value"},
            },
        }
    ]
    snapshot.snapshot_json["slaRules"] = [
        {"metric": {"bad": "metric"}, "condition": {"bad": "condition"}, "threshold": "bad"},
        {"metric": "payload", "condition": "gt", "threshold": {"value": 1, "unit": "mb"}},
    ]
    snapshot.snapshot_json["envGroup"] = {"name": "Broken Env", "variables": ["not", "a", "dict"]}
    db_session.commit()

    report = await client.get(
        f"/api/v1/runs/{created_run.id}", headers={"x-workspace-id": workspace_id}
    )

    assert report.status_code == 200
    body = report.json()
    assert body["snapshot"]["scenarioItems"][0]["loadSettings"] == {
        "concurrencyPerNode": None,
        "rampUpSeconds": None,
        "holdForSeconds": None,
        "iterations": None,
        "targetRps": None,
        "steps": None,
        "delaySeconds": None,
    }
    assert body["snapshot"]["slaRules"] == [
        {"metric": None, "condition": None, "thresholdText": None},
        {"metric": "payload", "condition": "gt", "thresholdText": "1MB"},
    ]
    assert body["snapshot"]["envGroupVariableKeys"] == []


@pytest.mark.anyio
async def test_run_list_filters_workspace_and_cursor_paginates(
    client: AsyncClient, db_session: Session
) -> None:
    _csrf, workspace_id, user_id = await register(client, "runs-list@example.com")
    actor = db_session.get(User, user_id)
    assert actor is not None
    first_node = seed_node(
        db_session, user_id, node_id="01HZX3Y9M0E9W7Z6M5QK9S8P7N", workspace_id=workspace_id
    )
    second_node = seed_node(
        db_session, user_id, node_id="01HZX3Y9M0E9W7Z6M5QK9S8P7M", workspace_id=workspace_id
    )
    other = Workspace(
        id=OTHER_WORKSPACE_ID,
        name="Other",
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(other)
    db_session.add(
        WorkspaceMember(
            workspace_id=OTHER_WORKSPACE_ID, user_id=user_id, joined_at=datetime.now(UTC)
        )
    )
    other_node = seed_node(
        db_session, user_id, node_id="01HZX3Y9M0E9W7Z6M5QK9S8P7O", workspace_id=OTHER_WORKSPACE_ID
    )
    newest = seed_run(
        db_session,
        user_id=user_id,
        run_id="01HZX3Y9M0E9W7Z6M5QK9S8P7R",
        node=first_node,
        created_at=datetime(2030, 6, 3, 9, 0, tzinfo=UTC),
    )
    older = seed_run(
        db_session,
        user_id=user_id,
        run_id="01HZX3Y9M0E9W7Z6M5QK9S8P7Q",
        node=second_node,
        validity="invalid",
        created_at=datetime(2030, 6, 3, 8, 0, tzinfo=UTC),
    )
    seed_run(
        db_session,
        user_id=user_id,
        run_id="01HZX3Y9M0E9W7Z6M5QK9S8P7Z",
        node=other_node,
        workspace_id=OTHER_WORKSPACE_ID,
        created_at=datetime(2030, 6, 3, 10, 0, tzinfo=UTC),
    )
    seed_artifact(
        db_session,
        run=newest,
        artifact_id="01HZX3Y9M0E9W7Z6M5QK9S8P7F",
        artifact_type="final_stats_csv",
        relative_path="artifacts/final_stats.csv",
    )
    seed_artifact(
        db_session,
        run=newest,
        artifact_id="01HZX3Y9M0E9W7Z6M5QK9S8P7G",
        artifact_type="artifacts_zip",
        relative_path="artifacts/artifacts.zip",
    )
    db_session.flush()

    first_page = await client.get(
        "/api/v1/runs?limit=1&sort=-createdAt",
        headers={"x-workspace-id": workspace_id},
    )
    assert first_page.status_code == 200
    assert [item["id"] for item in first_page.json()["items"]] == [newest.id]
    assert first_page.json()["items"][0]["sourceName"] == "Checkout Load Test"
    assert first_page.json()["items"][0]["artifactCount"] == 2
    assert first_page.json()["items"][0]["hasArtifactsZip"] is True
    assert first_page.json()["nextCursor"] is not None
    assert OTHER_WORKSPACE_ID not in first_page.text

    second_page = await client.get(
        f"/api/v1/runs?limit=1&sort=-createdAt&cursor={first_page.json()['nextCursor']}",
        headers={"x-workspace-id": workspace_id},
    )
    assert second_page.status_code == 200
    assert [item["id"] for item in second_page.json()["items"]] == [older.id]

    filtered = await client.get(
        "/api/v1/runs?validity=invalid&runType=standard&sourceType=test_plan&q=checkout&tag=checkout",
        headers={"x-workspace-id": workspace_id},
    )
    assert filtered.status_code == 200
    assert [item["id"] for item in filtered.json()["items"]] == [older.id]


def test_run_list_batches_page_supplemental_data(db_session: Session) -> None:
    user = User(
        id=new_ulid(),
        email="runs-batched-list@example.com",
        display_name="Batched List User",
        password_hash="hash",
        role="admin",
        status="active",
        failed_login_count=0,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(user)
    runs: list[Run] = []
    for index in range(4):
        node = seed_node(
            db_session,
            user.id,
            node_id=new_ulid(),
            workspace_id=DEFAULT_WORKSPACE_ID,
        )
        run = seed_run(
            db_session,
            user_id=user.id,
            run_id=new_ulid(),
            node=node,
            source_name=f"Checkout Load Test {index}",
            created_at=datetime(2030, 6, 3, 9, 0, tzinfo=UTC) - timedelta(minutes=index),
        )
        seed_artifact(
            db_session,
            run=run,
            artifact_id=new_ulid(),
            artifact_type="artifacts_zip" if index == 0 else "final_stats_csv",
            relative_path=(
                "artifacts/artifacts.zip" if index == 0 else "artifacts/final_stats.csv"
            ),
        )
        runs.append(run)
    db_session.flush()

    with QueryCounter(db_session) as counter:
        response = list_runs_report(
            db_session,
            workspace_id=DEFAULT_WORKSPACE_ID,
            limit=4,
            sort="-createdAt",
        )

    assert [item.id for item in response.items] == [run.id for run in runs]
    assert response.items[0].source_name == "Checkout Load Test 0"
    assert response.items[0].triggered_by.email == user.email
    assert response.items[0].artifact_count == 1
    assert response.items[0].has_artifacts_zip is True
    assert all(
        item.selected_node.id == run.selected_node_id for item, run in zip(response.items, runs)
    )
    assert counter.count <= 6


@pytest.mark.anyio
async def test_run_list_search_and_tag_filters_page_past_newer_nonmatches(
    client: AsyncClient, db_session: Session
) -> None:
    _csrf, workspace_id, user_id = await register(client, "runs-filter-window@example.com")
    node = seed_node(
        db_session, user_id, node_id="01HZX3Y9M0E9W7Z6M5QK9S8P7N", workspace_id=workspace_id
    )
    for index in range(501):
        seed_run(
            db_session,
            user_id=user_id,
            run_id=new_ulid(),
            node=node,
            source_name="Payment Load Test",
            tags=["payment"],
            created_at=datetime(2030, 6, 4, 10, 0, tzinfo=UTC) - timedelta(seconds=index),
        )
    older_match = seed_run(
        db_session,
        user_id=user_id,
        run_id="01HZX3Y9M0E9W7Z6M5QK9S8P7R",
        node=node,
        source_name="Checkout Load Test",
        tags=["checkout"],
        created_at=datetime(2030, 6, 3, 8, 0, tzinfo=UTC),
    )
    db_session.flush()

    response = await client.get(
        "/api/v1/runs?q=checkout&tag=checkout",
        headers={"x-workspace-id": workspace_id},
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [older_match.id]


@pytest.mark.anyio
async def test_run_list_validity_filter_matches_legacy_default_validity(
    client: AsyncClient, db_session: Session
) -> None:
    _csrf, workspace_id, user_id = await register(client, "runs-legacy-validity@example.com")
    node = seed_node(
        db_session, user_id, node_id="01HZX3Y9M0E9W7Z6M5QK9S8P7N", workspace_id=workspace_id
    )
    legacy_standard = seed_run(
        db_session,
        user_id=user_id,
        run_id="01HZX3Y9M0E9W7Z6M5QK9S8P7R",
        node=node,
        validity=None,
        run_type="standard",
        created_at=datetime(2030, 6, 3, 9, 0, tzinfo=UTC),
    )
    legacy_debug = seed_run(
        db_session,
        user_id=user_id,
        run_id="01HZX3Y9M0E9W7Z6M5QK9S8P7Q",
        node=node,
        validity=None,
        run_type="debug",
        created_at=datetime(2030, 6, 3, 8, 0, tzinfo=UTC),
    )
    db_session.flush()

    valid = await client.get(
        "/api/v1/runs?validity=valid", headers={"x-workspace-id": workspace_id}
    )
    invalid = await client.get(
        "/api/v1/runs?validity=invalid", headers={"x-workspace-id": workspace_id}
    )

    assert valid.status_code == 200
    assert [item["id"] for item in valid.json()["items"]] == [legacy_standard.id]
    assert valid.json()["items"][0]["validity"] == "valid"
    assert invalid.status_code == 200
    assert [item["id"] for item in invalid.json()["items"]] == [legacy_debug.id]
    assert invalid.json()["items"][0]["validity"] == "invalid"


@pytest.mark.anyio
async def test_run_list_search_and_tag_filters_escape_wildcards_and_keep_semantics(
    client: AsyncClient, db_session: Session
) -> None:
    _csrf, workspace_id, user_id = await register(client, "runs-filter-semantics@example.com")
    node = seed_node(
        db_session, user_id, node_id="01HZX3Y9M0E9W7Z6M5QK9S8P7N", workspace_id=workspace_id
    )
    seed_run(
        db_session,
        user_id=user_id,
        run_id="01HZX3Y9M0E9W7Z6M5QK9S8P7R",
        node=node,
        source_name="Checkout Load Test",
        tags=["checkout"],
        created_at=datetime(2030, 6, 3, 9, 0, tzinfo=UTC),
    )
    seed_run(
        db_session,
        user_id=user_id,
        run_id="01HZX3Y9M0E9W7Z6M5QK9S8P7Q",
        node=node,
        source_name="Payment Load Test",
        tags=["payment"],
        created_at=datetime(2030, 6, 3, 8, 0, tzinfo=UTC),
    )
    db_session.flush()

    wildcard_search = await client.get("/api/v1/runs?q=%", headers={"x-workspace-id": workspace_id})
    tag_outside_tags = await client.get(
        "/api/v1/runs?tag=Checkout%20Load%20Test", headers={"x-workspace-id": workspace_id}
    )

    assert wildcard_search.status_code == 200
    assert wildcard_search.json()["items"] == []
    assert tag_outside_tags.status_code == 200
    assert tag_outside_tags.json()["items"] == []


@pytest.mark.anyio
async def test_run_report_detail_artifacts_download_and_validity(
    client: AsyncClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    csrf, workspace_id, user_id = await register(client, "runs-report@example.com")
    first_node = seed_node(
        db_session, user_id, node_id="01HZX3Y9M0E9W7Z6M5QK9S8P7N", workspace_id=workspace_id
    )
    created_run = seed_run(
        db_session,
        user_id=user_id,
        run_id="01HZX3Y9M0E9W7Z6M5QK9S8P7R",
        node=first_node,
        sla_result="failed",
    )
    final_stats = seed_artifact(
        db_session,
        run=created_run,
        artifact_id="01HZX3Y9M0E9W7Z6M5QK9S8P7F",
        artifact_type="final_stats_csv",
        relative_path="artifacts/final_stats.csv",
    )
    zip_artifact = seed_artifact(
        db_session,
        run=created_run,
        artifact_id="01HZX3Y9M0E9W7Z6M5QK9S8P7G",
        artifact_type="artifacts_zip",
        relative_path="artifacts/artifacts.zip",
    )
    unavailable = seed_artifact(
        db_session,
        run=created_run,
        artifact_id="01HZX3Y9M0E9W7Z6M5QK9S8P7H",
        artifact_type="run_log",
        relative_path="logs/runner.log",
        status="failed",
    )
    seed_summary(db_session, run=created_run, artifact=final_stats)
    db_session.flush()
    storage = FakeStorage()
    storage.objects[final_stats.storage_key] = b"csv-bytes"
    storage.objects[zip_artifact.storage_key] = b"zip-bytes"
    monkeypatch.setattr("app.services.run_reports.get_storage_client", lambda: storage)

    report = await client.get(
        f"/api/v1/runs/{created_run.id}", headers={"x-workspace-id": workspace_id}
    )
    assert report.status_code == 200
    body = report.json()
    assert body["verdict"]["state"] == "finished"
    assert body["verdict"]["slaResult"] == "failed"
    assert body["verdict"]["validity"] == "valid"
    assert body["kpiSummary"]["status"] == "parsed"
    assert body["kpiSummary"]["throughputPerSecond"] is None
    assert body["failureDiagnostics"]["hasFailedRequestsPreview"] is False
    assert body["snapshot"]["sourceName"] == "Checkout Load Test"
    assert body["snapshot"]["resourceRequest"]["selectedNodeId"] == created_run.selected_node_id
    assert [node["id"] for node in body["nodes"]] == [created_run.selected_node_id]
    assert body["snapshot"]["scenarioItems"] == [
        {
            "scenarioName": "Checkout scenario",
            "loadSettings": {
                "concurrencyPerNode": 10,
                "rampUpSeconds": 30,
                "holdForSeconds": 300,
                "iterations": None,
                "targetRps": 50,
                "steps": 5,
                "delaySeconds": 7,
            },
        }
    ]
    assert body["snapshot"]["slaRules"] == [
        {"metric": "p95", "condition": "lte", "thresholdText": "500ms"}
    ]
    assert body["snapshot"]["dependencyFileNames"] == ["users.csv"]
    assert body["snapshot"]["envGroupVariableKeys"] == ["API_TOKEN", "BASE_URL"]
    assert body["artifactsSummary"]["hasArtifactsZip"] is True
    assert "secret-token" not in report.text
    assert first_node.host not in report.text
    assert "generatedYaml" not in report.text
    assert "execution/generated.yml" not in report.text
    assert "storage_key" not in report.text and "run-artifacts/" not in report.text

    artifacts = await client.get(
        f"/api/v1/runs/{created_run.id}/artifacts",
        headers={"x-workspace-id": workspace_id},
    )
    assert artifacts.status_code == 200
    assert {item["artifactType"] for item in artifacts.json()["items"]} == {
        "final_stats_csv",
        "artifacts_zip",
    }
    assert "storage" not in artifacts.text.lower()

    rejected_filter = await client.get(
        f"/api/v1/runs/{created_run.id}/artifacts?artifactType=failed_requests_csv",
        headers={"x-workspace-id": workspace_id},
    )
    assert rejected_filter.status_code == 422
    assert rejected_filter.json()["code"] == "VALIDATION_ERROR"

    download = await client.get(
        f"/api/v1/runs/{created_run.id}/artifacts/{zip_artifact.id}/download",
        headers={"x-workspace-id": workspace_id},
    )
    assert download.status_code == 200
    assert download.content == b"zip-bytes"
    assert download.headers["content-disposition"] == 'attachment; filename="artifacts.zip"'
    assert download.headers["cache-control"] == "private, no-store"
    assert "accept-ranges" not in {key.lower() for key in download.headers}
    assert "run-artifacts/" not in str(download.headers)

    not_ready = await client.get(
        f"/api/v1/runs/{created_run.id}/artifacts/{unavailable.id}/download",
        headers={"x-workspace-id": workspace_id},
    )
    assert not_ready.status_code == 409
    assert not_ready.json()["code"] == "ARTIFACT_NOT_READY"

    missing_csrf = await client.patch(
        f"/api/v1/runs/{created_run.id}/validity",
        headers={"x-workspace-id": workspace_id},
        json={"validity": "invalid"},
    )
    assert missing_csrf.status_code == 403
    assert missing_csrf.json()["code"] == "CSRF_TOKEN_REQUIRED"

    changed = await client.patch(
        f"/api/v1/runs/{created_run.id}/validity",
        headers={"x-workspace-id": workspace_id, "x-csrf-token": csrf},
        json={"validity": "invalid"},
    )
    assert changed.status_code == 200
    assert changed.json()["validity"] == "invalid"
    assert changed.json()["validityUpdatedBy"]["id"] == user_id
    db_session.refresh(created_run)
    assert created_run.state == "finished"
    assert created_run.sla_result == "failed"
    assert created_run.validity == "invalid"
    assert created_run.validity_updated_by_user_id == user_id
    events = db_session.scalars(
        select(AuditEvent).where(AuditEvent.event_type == "run.validity_changed")
    ).all()
    assert len(events) == 1
    assert events[0].details_json["oldValidity"] == "valid"
    assert events[0].details_json["newValidity"] == "invalid"

    same = await client.patch(
        f"/api/v1/runs/{created_run.id}/validity",
        headers={"x-workspace-id": workspace_id, "x-csrf-token": csrf},
        json={"validity": "invalid"},
    )
    assert same.status_code == 200
    events_after_idempotent = db_session.scalars(
        select(AuditEvent).where(AuditEvent.event_type == "run.validity_changed")
    ).all()
    assert len(events_after_idempotent) == 1


@pytest.mark.anyio
async def test_run_report_routes_hide_cross_workspace_runs(
    client: AsyncClient, db_session: Session
) -> None:
    csrf, workspace_id, user_id = await register(client, "runs-cross-workspace@example.com")
    other = Workspace(
        id=OTHER_WORKSPACE_ID,
        name="Other",
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(other)
    other_node = seed_node(
        db_session, user_id, node_id="01HZX3Y9M0E9W7Z6M5QK9S8P7O", workspace_id=OTHER_WORKSPACE_ID
    )
    hidden_run = seed_run(
        db_session,
        user_id=user_id,
        run_id="01HZX3Y9M0E9W7Z6M5QK9S8P7Z",
        node=other_node,
        workspace_id=OTHER_WORKSPACE_ID,
    )
    hidden_artifact = seed_artifact(
        db_session,
        run=hidden_run,
        artifact_id="01HZX3Y9M0E9W7Z6M5QK9S8P7G",
        artifact_type="artifacts_zip",
        relative_path="artifacts/artifacts.zip",
    )
    db_session.flush()

    headers = {"x-workspace-id": workspace_id}
    for path in (
        f"/api/v1/runs/{hidden_run.id}",
        f"/api/v1/runs/{hidden_run.id}/artifacts",
        f"/api/v1/runs/{hidden_run.id}/artifacts/{hidden_artifact.id}/download",
    ):
        response = await client.get(path, headers=headers)
        assert response.status_code == 404
        assert response.json()["code"] == "RESOURCE_NOT_FOUND"

    validity = await client.patch(
        f"/api/v1/runs/{hidden_run.id}/validity",
        headers={**headers, "x-csrf-token": csrf},
        json={"validity": "invalid"},
    )
    assert validity.status_code == 404
    assert validity.json()["code"] == "RESOURCE_NOT_FOUND"


@pytest.mark.anyio
async def test_active_run_report_returns_pending_sections_without_mutating_state(
    client: AsyncClient, db_session: Session
) -> None:
    _csrf, workspace_id, user_id = await register(client, "runs-active@example.com")
    first_node = seed_node(
        db_session, user_id, node_id="01HZX3Y9M0E9W7Z6M5QK9S8P7N", workspace_id=workspace_id
    )
    active = seed_run(
        db_session,
        user_id=user_id,
        run_id="01HZX3Y9M0E9W7Z6M5QK9S8P7R",
        node=first_node,
        state="running",
        sla_result="not_evaluated",
    )
    db_session.flush()

    report = await client.get(f"/api/v1/runs/{active.id}", headers={"x-workspace-id": workspace_id})

    assert report.status_code == 200
    assert report.json()["verdict"]["state"] == "running"
    assert report.json()["kpiSummary"]["status"] == "pending"
    assert report.json()["kpiSummary"]["missingReasons"] == ["summary_pending"]
    assert report.json()["finalStatsPreview"]["status"] == "pending"
    db_session.refresh(active)
    assert active.state == "running"
    assert active.ended_at is None
