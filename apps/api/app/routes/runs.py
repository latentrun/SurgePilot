from collections.abc import Iterator
from typing import Annotated, Literal

from fastapi import APIRouter, Path, Query, Request, Response, status
from fastapi.responses import StreamingResponse

from app.api.deps import CsrfDep, CurrentUserDep, CurrentWorkspaceDep, DbDep
from app.core.errors import AppError
from app.core.ids import is_ulid
from app.schemas.common import ErrorResponse
from app.schemas.runs import (RunArtifactListResponse, RunArtifactType, RunCreateRequest, RunCreateResponse, RunListResponse, RunReportDetail, RunState, RunStopResponse, RunType, RunSourceType, RunValidity, RunValidityPatchRequest, RunValidityPatchResponse)
from app.services.run_reports import get_run_artifact_download, get_run_report, list_run_artifacts_report, list_runs_report, update_run_validity
from app.services.storage import StoredObjectStream
from app.services.runs import request_stop_by_id
from app.services.scenarios import create_debug_run
from app.services.test_plans import create_test_plan_run

router = APIRouter(prefix="/api/v1/runs", tags=["runs"])
ERROR_RESPONSE = {"model": ErrorResponse}
RunIdPath = Annotated[str, Path(alias="runId")]
ArtifactIdPath = Annotated[str, Path(alias="artifactId")]
LimitQuery = Annotated[int, Query(ge=1, le=100)]


def iso_z(value) -> str | None:
    if value is None:
        return None
    return value.isoformat().replace("+00:00", "Z")


def validate_run_id(run_id: str) -> None:
    if not is_ulid(run_id):
        raise AppError(
            "VALIDATION_ERROR",
            "Validation failed.",
            422,
            [{"field": "runId", "code": "INVALID_FIELD", "message": "Invalid Run ID."}],
        )


def attach_workspace_header(response: Response, workspace_id: str) -> None:
    response.headers["x-workspace-id"] = workspace_id


def validate_artifact_id(artifact_id: str) -> None:
    if not is_ulid(artifact_id):
        raise AppError("VALIDATION_ERROR", "Validation failed.", 422, [{"field": "artifactId", "code": "INVALID_FIELD", "message": "Invalid Artifact ID."}])


@router.get("", operation_id="listRuns", response_model=RunListResponse, response_model_by_alias=True, responses={400: ERROR_RESPONSE, 401: ERROR_RESPONSE, 403: ERROR_RESPONSE, 422: ERROR_RESPONSE})
def list_runs(response: Response, db: DbDep, workspace: CurrentWorkspaceDep, state: Annotated[RunState | None, Query()] = None, validity: Annotated[RunValidity | None, Query()] = None, run_type: Annotated[RunType | None, Query(alias="runType")] = None, source_type: Annotated[RunSourceType | None, Query(alias="sourceType")] = None, q: Annotated[str | None, Query(max_length=120)] = None, tag: Annotated[str | None, Query(max_length=50)] = None, recent_hours: Annotated[int | None, Query(alias="recentHours", gt=0)] = None, cursor: Annotated[str | None, Query()] = None, limit: LimitQuery = 20, sort: Annotated[Literal["-createdAt"], Query()] = "-createdAt") -> RunListResponse:
    attach_workspace_header(response, workspace.id)
    return list_runs_report(db, workspace_id=workspace.id, state=state.value if state else None, validity=validity.value if validity else None, run_type=run_type.value if run_type else None, source_type=source_type.value if source_type else None, q=q, tag=tag, recent_hours=recent_hours, cursor=cursor, limit=limit, sort=sort)


@router.get("/{runId}", operation_id="getRunReport", response_model=RunReportDetail, response_model_by_alias=True, responses={400: ERROR_RESPONSE, 401: ERROR_RESPONSE, 403: ERROR_RESPONSE, 404: ERROR_RESPONSE, 422: ERROR_RESPONSE})
def get_run_report_route(run_id: RunIdPath, response: Response, db: DbDep, workspace: CurrentWorkspaceDep) -> RunReportDetail:
    validate_run_id(run_id)
    attach_workspace_header(response, workspace.id)
    result = get_run_report(db, workspace_id=workspace.id, run_id=run_id)
    db.commit()
    return result


@router.get("/{runId}/artifacts", operation_id="listRunArtifacts", response_model=RunArtifactListResponse, response_model_by_alias=True, responses={400: ERROR_RESPONSE, 401: ERROR_RESPONSE, 403: ERROR_RESPONSE, 404: ERROR_RESPONSE, 422: ERROR_RESPONSE})
def list_run_artifacts(run_id: RunIdPath, response: Response, db: DbDep, workspace: CurrentWorkspaceDep, artifact_type: Annotated[RunArtifactType | None, Query(alias="artifactType")] = None, cursor: Annotated[str | None, Query()] = None, limit: LimitQuery = 50, sort: Annotated[Literal["createdAt", "-createdAt"], Query()] = "createdAt") -> RunArtifactListResponse:
    validate_run_id(run_id)
    attach_workspace_header(response, workspace.id)
    return list_run_artifacts_report(db, workspace_id=workspace.id, run_id=run_id, artifact_type=artifact_type.value if artifact_type else None, cursor=cursor, limit=limit, sort=sort)


def stream_iterator(stored: StoredObjectStream) -> Iterator[bytes]:
    try:
        while chunk := stored.stream.read(1024 * 1024):
            yield chunk
    finally:
        close = getattr(stored.stream, "close", None)
        if callable(close): close()


@router.get("/{runId}/artifacts/{artifactId}/download", operation_id="downloadRunArtifact", response_class=StreamingResponse, responses={200: {"description": "Run artifact bytes."}, 400: ERROR_RESPONSE, 401: ERROR_RESPONSE, 403: ERROR_RESPONSE, 404: ERROR_RESPONSE, 409: ERROR_RESPONSE, 422: ERROR_RESPONSE, 503: ERROR_RESPONSE})
def download_run_artifact(run_id: RunIdPath, artifact_id: ArtifactIdPath, db: DbDep, workspace: CurrentWorkspaceDep) -> StreamingResponse:
    validate_run_id(run_id)
    validate_artifact_id(artifact_id)
    result = get_run_artifact_download(db, workspace_id=workspace.id, run_id=run_id, artifact_id=artifact_id)
    db.commit()
    return StreamingResponse(stream_iterator(result.stored), media_type=result.artifact.content_type or "application/octet-stream", headers={"Content-Disposition": f'attachment; filename="{result.artifact.display_filename}"', "Cache-Control": "private, no-store", "x-workspace-id": workspace.id})


@router.patch("/{runId}/validity", operation_id="patchRunValidity", response_model=RunValidityPatchResponse, response_model_by_alias=True, responses={400: ERROR_RESPONSE, 401: ERROR_RESPONSE, 403: ERROR_RESPONSE, 404: ERROR_RESPONSE, 422: ERROR_RESPONSE})
def patch_run_validity(run_id: RunIdPath, payload: RunValidityPatchRequest, request: Request, response: Response, db: DbDep, user: CurrentUserDep, workspace: CurrentWorkspaceDep, _csrf: CsrfDep) -> RunValidityPatchResponse:
    validate_run_id(run_id)
    result = update_run_validity(db, workspace_id=workspace.id, run_id=run_id, validity=payload.validity.value, actor=user, request=request)
    db.commit()
    attach_workspace_header(response, workspace.id)
    return result


@router.post(
    "",
    operation_id="createRun",
    response_model=RunCreateResponse,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
    responses={
        200: {"model": RunCreateResponse},
        400: ERROR_RESPONSE,
        401: ERROR_RESPONSE,
        403: ERROR_RESPONSE,
        404: ERROR_RESPONSE,
        409: ERROR_RESPONSE,
        422: ERROR_RESPONSE,
    },
)
def create_run(
    payload: RunCreateRequest,
    request: Request,
    response: Response,
    db: DbDep,
    user: CurrentUserDep,
    workspace: CurrentWorkspaceDep,
    _csrf: CsrfDep,
) -> RunCreateResponse:
    """Create a Scenario Debug Run or a Test Plan Run Now / Debug Run.

    P0-05 accepts ``runType=debug`` with ``sourceType=debug_scenario`` only.
    P0-06 extends public Run creation to ``runType=standard|debug`` with
    ``sourceType=test_plan``. Test Plan Runs use the saved Env Group and Load
    Node settings and reject overrides. A short-window dedup hit returns the
    already-created Run with ``deduplicated: true`` and status 200 instead of
    201.
    """
    if payload.source_type == "debug_scenario":
        if payload.run_type != "debug" or payload.selected_node_id is None:
            raise AppError(
                "VALIDATION_ERROR",
                "Validation failed.",
                422,
                [
                    {
                        "field": "sourceType",
                        "code": "unsupported_run_source",
                        "message": "Only Scenario Debug Runs are supported for this source.",
                    }
                ],
            )
        result = create_debug_run(
            db,
            workspace_id=workspace.id,
            actor=user,
            request=request,
            source_id=payload.source_id,
            expected_source_revision=payload.expected_source_revision,
            env_group_id=payload.env_group_id,
            selected_node_id=payload.selected_node_id,
        )
    elif payload.source_type == "test_plan":
        if payload.env_group_id is not None or payload.selected_node_id is not None:
            raise AppError(
                "VALIDATION_ERROR",
                "Validation failed.",
                422,
                [
                    {
                        "field": "sourceType",
                        "code": "unsupported_run_override",
                        "message": "Test Plan Runs use saved Env Group and Load Node settings.",
                    }
                ],
            )
        result = create_test_plan_run(
            db,
            workspace_id=workspace.id,
            actor=user,
            request=request,
            source_id=payload.source_id,
            expected_source_revision=payload.expected_source_revision,
            run_type=payload.run_type,
            confirm_high_concurrency=payload.confirm_high_concurrency,
        )
    else:
        raise AppError(
            "VALIDATION_ERROR",
            "Validation failed.",
            422,
            [
                {
                    "field": "sourceType",
                    "code": "unsupported_run_source",
                    "message": "Run source is not supported in this release.",
                }
            ],
        )
    db.commit()
    response.status_code = result.status_code
    response.headers["x-workspace-id"] = workspace.id
    return RunCreateResponse(
        id=result.run.id,
        state=result.run.state,  # type: ignore[arg-type]
        run_type=result.run.run_type,  # type: ignore[arg-type]
        source_type=result.run.source_type,  # type: ignore[arg-type]
        source_id=result.run.source_id,
        selected_node_id=result.run.selected_node_id,
        validity=result.run.validity,
        created_at=iso_z(result.run.created_at) or "",
        deduplicated=result.deduplicated,
    )


@router.post(
    "/{runId}/stop",
    operation_id="stopRun",
    response_model=RunStopResponse,
    response_model_by_alias=True,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        200: {"model": RunStopResponse},
        400: ERROR_RESPONSE,
        401: ERROR_RESPONSE,
        403: ERROR_RESPONSE,
        404: ERROR_RESPONSE,
        409: ERROR_RESPONSE,
        422: ERROR_RESPONSE,
    },
)
def stop_run(
    run_id: RunIdPath,
    response: Response,
    db: DbDep,
    user: CurrentUserDep,
    workspace: CurrentWorkspaceDep,
    _csrf: CsrfDep,
) -> RunStopResponse:
    validate_run_id(run_id)
    result = request_stop_by_id(db, run_id=run_id, workspace_id=workspace.id, actor=user)
    db.commit()
    response.status_code = result.status_code
    response.headers["x-workspace-id"] = workspace.id
    return RunStopResponse(
        id=result.run_id,
        state=result.state,  # type: ignore[arg-type]
        stop_requested_at=iso_z(result.stop_requested_at),
        duplicate=result.duplicate,
    )
