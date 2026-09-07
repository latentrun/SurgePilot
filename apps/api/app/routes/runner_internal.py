from datetime import datetime
from functools import lru_cache
import json
import os
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Header, Request
from jsonschema import (
    Draft202012Validator,
    FormatChecker,
    ValidationError as JsonSchemaValidationError,
)
from pydantic import ValidationError
from starlette.datastructures import UploadFile

from app.api.deps import DbDep, request_id
from app.core.config import get_settings
from app.core.errors import AppError
from app.schemas.runs import (
    RunnerArtifactResponse,
    RunnerCallbackRequest,
    RunnerCallbackResponse,
)
from app.services.runs import (
    RunnerCallbackInput,
    apply_runner_callback,
    ingest_run_artifact,
    validate_runner_token,
)

router = APIRouter(
    prefix="/api/internal/v1/runner", tags=["internal-runner"], include_in_schema=False
)
RunnerTokenHeader = Annotated[str | None, Header(alias="x-runner-token")]
ARTIFACT_MULTIPART_OVERHEAD_BYTES = 8192


def runner_callback_schema_candidates(source_file: Path | None = None) -> list[Path]:
    source = (source_file or Path(__file__)).resolve()
    candidates: list[Path] = []
    configured = os.environ.get("SURGEPILOT_RUNNER_CALLBACK_SCHEMA_PATH")
    if configured:
        candidates.append(Path(configured))
    for parent in source.parents:
        candidates.append(
            parent / "packages" / "contracts" / "runner" / "runner-callback.schema.json"
        )
    candidates.append(Path("/opt/surgepilot/contracts/runner/runner-callback.schema.json"))
    deduped: list[Path] = []
    for candidate in candidates:
        if candidate not in deduped:
            deduped.append(candidate)
    return deduped


@lru_cache(maxsize=1)
def runner_callback_validator() -> Draft202012Validator:
    schema_path = next(path for path in runner_callback_schema_candidates() if path.exists())
    return Draft202012Validator(json.loads(schema_path.read_text()), format_checker=FormatChecker())


def parse_event_time(value: str) -> datetime:
    if not value.endswith("Z"):
        raise AppError("RUNNER_CALLBACK_INVALID", "Runner callback is invalid.", 422)
    try:
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise AppError("RUNNER_CALLBACK_INVALID", "Runner callback is invalid.", 422) from exc


def validate_callback_payload(payload: RunnerCallbackRequest) -> None:
    if payload.schema_version != "1":
        raise AppError("RUNNER_CALLBACK_INVALID", "Runner callback is invalid.", 422)
    if payload.event_type == "accepted" and payload.runner_pid is None:
        raise AppError("RUNNER_CALLBACK_INVALID", "Runner callback is invalid.", 422)
    if payload.event_type in {"finished", "failed", "aborted"} and not isinstance(
        payload.details.get("processGroupExited"), bool
    ):
        raise AppError("RUNNER_CALLBACK_INVALID", "Runner callback is invalid.", 422)
    sla_result = payload.details.get("slaResult")
    if sla_result is not None and sla_result not in {"passed", "failed"}:
        raise AppError("RUNNER_CALLBACK_INVALID", "Runner callback is invalid.", 422)


@router.post("/callbacks", response_model=RunnerCallbackResponse, response_model_by_alias=True)
async def runner_callback(
    request: Request,
    db: DbDep,
    x_runner_token: RunnerTokenHeader = None,
) -> RunnerCallbackResponse:
    body = await request.body()
    if len(body) > 8192:
        raise AppError("RUNNER_CALLBACK_INVALID", "Runner callback is invalid.", 422)
    try:
        raw_payload = json.loads(body)
        if not isinstance(raw_payload, dict):
            raise ValueError("Callback payload must be a JSON object.")
        runner_callback_validator().validate(raw_payload)
        payload = RunnerCallbackRequest.model_validate(raw_payload)
    except (ValueError, JsonSchemaValidationError, ValidationError) as exc:
        raise AppError("RUNNER_CALLBACK_INVALID", "Runner callback is invalid.", 422) from exc
    validate_callback_payload(payload)
    result = apply_runner_callback(
        db,
        callback=RunnerCallbackInput(
            schema_version=payload.schema_version,
            event_id=payload.event_id,
            run_id=payload.run_id,
            node_id=payload.node_id,
            runtime_version=payload.runtime_version,
            event_type=payload.event_type,
            seq=payload.seq,
            event_time=parse_event_time(payload.event_time),
            message=payload.message,
            runner_pid=payload.runner_pid,
            details=payload.details,
            raw_payload=payload.model_dump(by_alias=True),
        ),
        request_id=request_id(request),
        authenticated_node_id=validate_runner_token(x_runner_token, node_id=payload.node_id),
    )
    db.commit()
    return RunnerCallbackResponse(
        accepted=result.accepted,
        duplicate=result.duplicate,
        state_changed=result.state_changed,
        current_state=result.current_state,  # type: ignore[arg-type]
        ignored_reason=result.ignored_reason,
    )


def _form_text(form: dict[str, object], field_name: str) -> str:
    value = form.get(field_name)
    if not isinstance(value, str) or value == "":
        raise AppError("INVALID_REQUEST", "Invalid request.", 400)
    return value


def _reject_oversized_artifact_content_length(request: Request) -> None:
    content_length = request.headers.get("content-length")
    if content_length is None:
        return
    try:
        length = int(content_length)
    except ValueError:
        return
    limit = get_settings().run_artifact_max_bytes + ARTIFACT_MULTIPART_OVERHEAD_BYTES
    if length > limit:
        raise AppError("PAYLOAD_TOO_LARGE", "Uploaded file is too large.", 413)


@router.post("/artifacts", response_model=RunnerArtifactResponse, response_model_by_alias=True)
async def runner_artifact(
    request: Request,
    db: DbDep,
    x_runner_token: RunnerTokenHeader = None,
) -> RunnerArtifactResponse:
    _reject_oversized_artifact_content_length(request)
    # Restricted exception to the P0 "authenticate before parse" rule: multipart
    # artifact nodeId is a form field, so node-bound token validation happens
    # immediately after parsing that field. The security boundary remains the
    # Content-Length preflight above plus the same token-node allocation check as
    # callbacks; do not use this as a generic parse-before-auth pattern.
    form = await request.form()
    schema_version = _form_text(form, "schemaVersion")
    if schema_version != "1":
        raise AppError("INVALID_REQUEST", "Invalid request.", 400)
    uploaded_file = form.get("file")
    if not isinstance(uploaded_file, UploadFile):
        raise AppError("INVALID_REQUEST", "Invalid request.", 400)
    try:
        size_bytes = int(_form_text(form, "sizeBytes"))
    except ValueError as exc:
        raise AppError("INVALID_REQUEST", "Invalid request.", 400) from exc
    node_id = _form_text(form, "nodeId")
    result = ingest_run_artifact(
        db,
        event_id=_form_text(form, "eventId"),
        run_id=_form_text(form, "runId"),
        node_id=node_id,
        authenticated_node_id=validate_runner_token(x_runner_token, node_id=node_id),
        artifact_type=_form_text(form, "artifactType"),
        relative_path=_form_text(form, "relativePath"),
        declared_sha256=_form_text(form, "sha256"),
        declared_size_bytes=size_bytes,
        file=uploaded_file.file,
        content_type=uploaded_file.content_type,
    )
    db.commit()
    return RunnerArtifactResponse(artifact_id=result.artifact_id, duplicate=result.duplicate)
