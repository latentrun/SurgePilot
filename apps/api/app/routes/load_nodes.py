from typing import Any
import logging

from fastapi import APIRouter, Request, Response, status
from sqlalchemy import func, or_, select

from app.api.deps import CsrfDep, CurrentUserDep, CurrentWorkspaceDep, DbDep
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.ids import is_ulid
from app.core.time import utc_now
from app.models.load_nodes import LoadNode, LoadNodeCredential, LoadNodeInitializationAttempt
from app.schemas.common import ErrorResponse
from app.schemas.load_nodes import (
    DisableLoadNodeRequest,
    InitializeLoadNodeRequest,
    LoadNodeCreateRequest,
    LoadNodeCredentialUpdateRequest,
    LoadNodeDetail,
    LoadNodeInitAttemptDetail,
    LoadNodeInitAttemptListResponse,
    LoadNodeInitAttemptSummary,
    LoadNodeInitializeAttemptStatus,
    LoadNodeInitializeNodeStatus,
    LoadNodeInitializeResponse,
    LoadNodeLatestInitAttempt,
    LoadNodeListResponse,
    LoadNodePatchRequest,
    LoadNodeSshHostKeyInput,
    LoadNodeSshHostKeyResponse,
    LoadNodeSshHostKeyScanRequest,
    LoadNodeSshHostKeyScanResponse,
    LoadNodeSummary,
)
from app.services.load_nodes import (
    archive_load_node,
    audit_details,
    create_load_node,
    disable_load_node,
    enable_load_node,
    get_visible_load_node,
    known_hosts_line_for_node,
    normalize_host,
    normalize_ssh_port,
    request_initialization,
    require_admin_for_public,
    safe_write_load_node_audit,
    scan_ssh_host_key,
    trust_load_node_ssh_host_key,
    update_load_node,
    update_load_node_credentials,
    visible_node_filters,
)

router = APIRouter(prefix="/api/v1/load-nodes", tags=["load-nodes"])
logger = logging.getLogger(__name__)
ERROR_RESPONSE = {"model": ErrorResponse}
ALLOWED_LIST_QUERY_PARAMS = {"scope", "status", "q", "includeArchived", "limit", "offset", "sort"}
ALLOWED_SORTS = {"createdAt", "-createdAt", "host", "status", "lastCheckedAt", "-lastCheckedAt"}
STATUSES = {"uninitialized", "initializing", "idle", "busy", "offline", "quarantined", "disabled"}
SCOPES = {"public", "workspace"}

INIT_ATTEMPT_LIST_QUERY_OPENAPI_PARAMETERS = [
    {
        "name": "limit",
        "in": "query",
        "required": False,
        "schema": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
    },
    {
        "name": "offset",
        "in": "query",
        "required": False,
        "schema": {"type": "integer", "minimum": 0, "default": 0},
    },
]
LIST_QUERY_OPENAPI_PARAMETERS = [
    {
        "name": "scope",
        "in": "query",
        "required": False,
        "schema": {"type": "string", "enum": sorted(SCOPES)},
    },
    {
        "name": "status",
        "in": "query",
        "required": False,
        "schema": {"type": "string", "enum": sorted(STATUSES)},
    },
    {
        "name": "q",
        "in": "query",
        "required": False,
        "schema": {"anyOf": [{"type": "string", "maxLength": 120}, {"type": "null"}]},
    },
    {
        "name": "includeArchived",
        "in": "query",
        "required": False,
        "schema": {"type": "boolean", "default": False},
    },
    {
        "name": "limit",
        "in": "query",
        "required": False,
        "schema": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
    },
    {
        "name": "offset",
        "in": "query",
        "required": False,
        "schema": {"type": "integer", "minimum": 0, "default": 0},
    },
    {
        "name": "sort",
        "in": "query",
        "required": False,
        "schema": {"type": "string", "default": "-createdAt"},
    },
]


def iso_z(value) -> str | None:
    if value is None:
        return None
    return value.isoformat().replace("+00:00", "Z")


def attach_workspace_header(response: Response, workspace_id: str) -> None:
    response.headers["x-workspace-id"] = workspace_id


def validate_load_node_id(load_node_id: str, field: str = "loadNodeId") -> None:
    if not is_ulid(load_node_id):
        raise AppError(
            "VALIDATION_ERROR",
            "Validation failed.",
            422,
            [{"field": field, "code": "INVALID_FIELD", "message": "Invalid Load Node ID."}],
        )


def invalid_query(field: str, message: str) -> AppError:
    return AppError(
        "INVALID_QUERY_PARAMETER",
        "Invalid query parameter.",
        400,
        [{"field": field, "code": "INVALID_QUERY_PARAMETER", "message": message}],
    )


def parse_int(
    raw_value: str | None, *, field: str, default: int, minimum: int, maximum: int | None = None
) -> int:
    if raw_value is None:
        return default
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise invalid_query(field, f"{field} must be an integer.") from exc
    if value < minimum:
        raise invalid_query(field, f"{field} must be greater than or equal to {minimum}.")
    if maximum is not None and value > maximum:
        raise invalid_query(field, f"{field} must be less than or equal to {maximum}.")
    return value


def parse_bool(raw_value: str | None, *, field: str, default: bool) -> bool:
    if raw_value is None:
        return default
    lowered = raw_value.lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    raise invalid_query(field, f"{field} must be a boolean.")


def parse_list_query(
    request: Request,
) -> tuple[str | None, str | None, str | None, bool, int, int, str]:
    unknown = set(request.query_params) - ALLOWED_LIST_QUERY_PARAMS
    if unknown:
        raise invalid_query(sorted(unknown)[0], "Unknown query parameter.")
    scope = request.query_params.get("scope")
    if scope is not None and scope not in SCOPES:
        raise invalid_query("scope", "Unsupported scope filter.")
    node_status = request.query_params.get("status")
    if node_status is not None and node_status not in STATUSES:
        raise invalid_query("status", "Unsupported status filter.")
    q = request.query_params.get("q")
    trimmed_q = q.strip() if q is not None else None
    if trimmed_q is not None and len(trimmed_q) > 120:
        raise invalid_query("q", "q must be 120 characters or less.")
    include_archived = parse_bool(
        request.query_params.get("includeArchived"), field="includeArchived", default=False
    )
    limit = parse_int(
        request.query_params.get("limit"), field="limit", default=20, minimum=1, maximum=100
    )
    offset = parse_int(request.query_params.get("offset"), field="offset", default=0, minimum=0)
    sort = request.query_params.get("sort", "-createdAt")
    if sort not in ALLOWED_SORTS:
        raise invalid_query("sort", "Unsupported sort parameter.")
    return scope, node_status, trimmed_q, include_archived, limit, offset, sort


def credential_for(
    node: LoadNode, credential: LoadNodeCredential | None
) -> tuple[bool, str | None, str | None]:
    if credential is None:
        return False, None, None
    return True, credential.credential_fingerprint, credential.generated_public_key


def ssh_host_key_response(node: LoadNode) -> LoadNodeSshHostKeyResponse | None:
    known_hosts_line = known_hosts_line_for_node(node)
    if known_hosts_line is None:
        return None
    return LoadNodeSshHostKeyResponse(
        algorithm=node.ssh_host_key_algorithm or "",
        public_key=node.ssh_host_key_public_key or "",
        fingerprint_sha256=node.ssh_host_key_fingerprint_sha256 or "",
        known_hosts_line=known_hosts_line,
    )


def latest_attempt(db: DbDep, node_id: str) -> LoadNodeInitializationAttempt | None:
    return db.scalar(
        select(LoadNodeInitializationAttempt)
        .where(LoadNodeInitializationAttempt.node_id == node_id)
        .order_by(
            LoadNodeInitializationAttempt.created_at.desc(), LoadNodeInitializationAttempt.id.desc()
        )
    )


def summary_response(
    node: LoadNode, credential: LoadNodeCredential | None = None
) -> LoadNodeSummary:
    configured, credential_fingerprint, generated_public_key = credential_for(node, credential)
    return LoadNodeSummary(
        id=node.id,
        scope=node.scope,  # type: ignore[arg-type]
        workspace_id=node.workspace_id,
        host=node.host,
        ssh_port=node.ssh_port,
        ssh_user=node.ssh_user,
        runner_home=node.runner_home,
        auth_type=node.auth_type,  # type: ignore[arg-type]
        credential_configured=configured,
        credential_fingerprint=credential_fingerprint,
        generated_public_key=generated_public_key if node.auth_type == "generated_key" else None,
        ssh_host_key=ssh_host_key_response(node),
        maintainer=node.maintainer,
        remark=node.remark,
        status=node.status,  # type: ignore[arg-type]
        last_status_reason=node.last_status_reason,
        runner_version=node.runner_version,
        bundle_version=node.bundle_version,
        last_initialized_at=iso_z(node.last_initialized_at),
        last_checked_at=iso_z(node.last_checked_at),
        last_heartbeat_at=iso_z(node.last_heartbeat_at),
        current_run_id=node.current_run_id,
        last_init_attempt_id=node.last_init_attempt_id,
        created_at=iso_z(node.created_at) or "",
        updated_at=iso_z(node.updated_at) or "",
    )


def attempt_latest_response(
    attempt: LoadNodeInitializationAttempt | None,
) -> LoadNodeLatestInitAttempt | None:
    if attempt is None:
        return None
    return LoadNodeLatestInitAttempt(
        id=attempt.id,
        status=attempt.status,  # type: ignore[arg-type]
        started_at=iso_z(attempt.started_at),
        finished_at=iso_z(attempt.finished_at),
        error_code=attempt.error_code,
        message=attempt.message,
    )


def detail_response(db: DbDep, node: LoadNode) -> LoadNodeDetail:
    credential = db.get(LoadNodeCredential, node.id)
    latest = latest_attempt(db, node.id)
    return LoadNodeDetail(
        **summary_response(node, credential).model_dump(),
        latest_init_attempt=attempt_latest_response(latest),
    )


def attempt_summary_response(attempt: LoadNodeInitializationAttempt) -> LoadNodeInitAttemptSummary:
    return LoadNodeInitAttemptSummary(
        id=attempt.id,
        node_id=attempt.node_id,
        status=attempt.status,  # type: ignore[arg-type]
        started_at=iso_z(attempt.started_at),
        finished_at=iso_z(attempt.finished_at),
        error_code=attempt.error_code,
        message=attempt.message,
        created_at=iso_z(attempt.created_at) or "",
    )


def attempt_detail_response(attempt: LoadNodeInitializationAttempt) -> LoadNodeInitAttemptDetail:
    return LoadNodeInitAttemptDetail(
        **attempt_summary_response(attempt).model_dump(),
        sanitized_log_tail=attempt.sanitized_log_tail,
        runner_version=attempt.runner_version,
        bundle_version=attempt.bundle_version,
        updated_at=iso_z(attempt.updated_at) or "",
    )


def write_audit(
    request: Request,
    db: DbDep,
    event_type: str,
    user_id: str,
    node: LoadNode,
    attempt_id: str | None = None,
) -> None:
    safe_write_load_node_audit(
        db,
        event_type=event_type,
        request=request,
        actor_user_id=user_id,
        workspace_id=node.workspace_id,
        target_type="load_node",
        target_id=node.id,
        details=audit_details(node, attempt_id=attempt_id),
    )


@router.post(
    "/ssh-host-key/scan",
    operation_id="scanLoadNodeSshHostKey",
    response_model=LoadNodeSshHostKeyScanResponse,
    response_model_by_alias=True,
    responses={400: ERROR_RESPONSE, 401: ERROR_RESPONSE, 403: ERROR_RESPONSE, 422: ERROR_RESPONSE},
)
def scan_load_node_ssh_host_key_route(
    request: Request,
    response: Response,
    db: DbDep,
    user: CurrentUserDep,
    workspace: CurrentWorkspaceDep,
    _csrf: CsrfDep,
    payload: LoadNodeSshHostKeyScanRequest,
) -> LoadNodeSshHostKeyScanResponse:
    _ = db
    attach_workspace_header(response, workspace.id)
    require_admin_for_public(user, payload.scope)
    host = normalize_host(payload.host)
    ssh_port = normalize_ssh_port(payload.ssh_port)
    try:
        scanned = scan_ssh_host_key(
            host, ssh_port, get_settings().load_node_ssh_connect_timeout_seconds
        )
    except Exception as exc:
        logger.warning(
            "SSH host key scan failed.",
            extra={"host": host, "ssh_port": ssh_port, "workspace_id": workspace.id},
            exc_info=True,
        )
        raise AppError(
            "LOAD_NODE_SSH_HOST_KEY_SCAN_FAILED", "SSH host key scan failed.", 400
        ) from exc
    safe_write_load_node_audit(
        db,
        event_type="load_node.ssh_host_key_scanned",
        request=request,
        actor_user_id=user.id,
        workspace_id=workspace.id,
        target_type="load_node",
        target_id=None,
        details={
            "scope": payload.scope,
            "host": host,
            "sshPort": ssh_port,
            "algorithm": scanned.algorithm,
        },
    )
    db.commit()
    from app.services.ssh_remote import trusted_known_hosts_line

    return LoadNodeSshHostKeyScanResponse(
        host=host,
        ssh_port=ssh_port,
        algorithm=scanned.algorithm,
        public_key=scanned.public_key,
        fingerprint_sha256=scanned.fingerprint_sha256,
        known_hosts_line=trusted_known_hosts_line(
            host=host, algorithm=scanned.algorithm, public_key=scanned.public_key, port=ssh_port
        ),
        scanned_at=iso_z(utc_now()) or "",
    )


@router.get(
    "",
    operation_id="listLoadNodes",
    response_model=LoadNodeListResponse,
    response_model_by_alias=True,
    responses={400: ERROR_RESPONSE, 401: ERROR_RESPONSE, 403: ERROR_RESPONSE, 422: ERROR_RESPONSE},
    openapi_extra={"parameters": LIST_QUERY_OPENAPI_PARAMETERS},
)
def list_load_nodes(
    request: Request,
    response: Response,
    db: DbDep,
    workspace: CurrentWorkspaceDep,
    user: CurrentUserDep,
) -> LoadNodeListResponse:
    scope, node_status, q, include_archived, limit, offset, sort = parse_list_query(request)
    attach_workspace_header(response, workspace.id)
    if include_archived and scope == "public" and user.role != "admin":
        raise AppError(
            "LOAD_NODE_PUBLIC_ADMIN_REQUIRED", "Public Load Node operation requires Admin.", 403
        )
    filters: list[Any] = [visible_node_filters(workspace_id=workspace.id)]
    if not include_archived:
        filters.append(LoadNode.archived_at.is_(None))
    elif user.role != "admin":
        filters.append(or_(LoadNode.scope == "workspace", LoadNode.archived_at.is_(None)))
    if scope:
        filters.append(LoadNode.scope == scope)
    if node_status:
        filters.append(LoadNode.status == node_status)
    if q:
        pattern = f"%{q.lower()}%"
        filters.append(
            or_(
                func.lower(LoadNode.host).like(pattern),
                func.lower(LoadNode.ssh_user).like(pattern),
                func.lower(LoadNode.maintainer).like(pattern),
                func.lower(LoadNode.remark).like(pattern),
            )
        )
    statement = select(LoadNode).where(*filters)
    count_statement = select(func.count(LoadNode.id)).where(*filters)
    if sort == "createdAt":
        statement = statement.order_by(LoadNode.created_at.asc(), LoadNode.id.asc())
    elif sort == "host":
        statement = statement.order_by(func.lower(LoadNode.host).asc(), LoadNode.id.asc())
    elif sort == "status":
        statement = statement.order_by(LoadNode.status.asc(), LoadNode.id.asc())
    elif sort == "lastCheckedAt":
        statement = statement.order_by(
            LoadNode.last_checked_at.asc().nulls_last(), LoadNode.id.asc()
        )
    elif sort == "-lastCheckedAt":
        statement = statement.order_by(
            LoadNode.last_checked_at.desc().nulls_last(), LoadNode.id.desc()
        )
    else:
        statement = statement.order_by(LoadNode.created_at.desc(), LoadNode.id.desc())
    total = db.scalar(count_statement) or 0
    nodes = db.scalars(statement.offset(offset).limit(limit)).all()
    credentials = (
        {
            c.node_id: c
            for c in db.scalars(
                select(LoadNodeCredential).where(
                    LoadNodeCredential.node_id.in_([n.id for n in nodes])
                )
            ).all()
        }
        if nodes
        else {}
    )
    db.commit()
    return LoadNodeListResponse(
        items=[summary_response(node, credentials.get(node.id)) for node in nodes],
        limit=limit,
        offset=offset,
        total=total,
    )


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    operation_id="createLoadNode",
    response_model=LoadNodeDetail,
    response_model_by_alias=True,
    responses={
        400: ERROR_RESPONSE,
        401: ERROR_RESPONSE,
        403: ERROR_RESPONSE,
        409: ERROR_RESPONSE,
        422: ERROR_RESPONSE,
        500: ERROR_RESPONSE,
    },
)
def create_load_node_route(
    request: Request,
    response: Response,
    db: DbDep,
    user: CurrentUserDep,
    workspace: CurrentWorkspaceDep,
    _csrf: CsrfDep,
    payload: LoadNodeCreateRequest,
) -> LoadNodeDetail:
    node = create_load_node(
        db,
        actor=user,
        workspace_id=workspace.id,
        scope=payload.scope,
        host=payload.host,
        ssh_port=payload.ssh_port,
        ssh_user=payload.ssh_user,
        runner_home=payload.runner_home,
        credential=payload.credential,
        ssh_host_key=payload.ssh_host_key,
        maintainer=payload.maintainer,
        remark=payload.remark,
    )
    write_audit(request, db, "load_node.created", user.id, node)
    write_audit(request, db, "load_node.credential_updated", user.id, node)
    db.commit()
    attach_workspace_header(response, workspace.id)
    return detail_response(db, node)


@router.get(
    "/{loadNodeId}",
    operation_id="getLoadNode",
    response_model=LoadNodeDetail,
    response_model_by_alias=True,
    responses={
        400: ERROR_RESPONSE,
        401: ERROR_RESPONSE,
        403: ERROR_RESPONSE,
        404: ERROR_RESPONSE,
        422: ERROR_RESPONSE,
    },
)
def get_load_node_route(
    loadNodeId: str, response: Response, db: DbDep, workspace: CurrentWorkspaceDep
) -> LoadNodeDetail:
    validate_load_node_id(loadNodeId)
    attach_workspace_header(response, workspace.id)
    node = get_visible_load_node(db, workspace_id=workspace.id, load_node_id=loadNodeId)
    db.commit()
    return detail_response(db, node)


@router.patch(
    "/{loadNodeId}",
    operation_id="patchLoadNode",
    response_model=LoadNodeDetail,
    response_model_by_alias=True,
    responses={
        400: ERROR_RESPONSE,
        401: ERROR_RESPONSE,
        403: ERROR_RESPONSE,
        404: ERROR_RESPONSE,
        409: ERROR_RESPONSE,
        422: ERROR_RESPONSE,
    },
)
def patch_load_node_route(
    loadNodeId: str,
    request: Request,
    response: Response,
    db: DbDep,
    user: CurrentUserDep,
    workspace: CurrentWorkspaceDep,
    _csrf: CsrfDep,
    payload: LoadNodePatchRequest,
) -> LoadNodeDetail:
    validate_load_node_id(loadNodeId)
    attach_workspace_header(response, workspace.id)
    node = get_visible_load_node(db, workspace_id=workspace.id, load_node_id=loadNodeId)
    updated = update_load_node(
        db, node=node, actor=user, fields=payload.model_dump(exclude_unset=True, by_alias=False)
    )
    write_audit(request, db, "load_node.updated", user.id, updated)
    db.commit()
    return detail_response(db, updated)


@router.delete(
    "/{loadNodeId}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="deleteLoadNode",
    response_model=None,
    responses={
        400: ERROR_RESPONSE,
        401: ERROR_RESPONSE,
        403: ERROR_RESPONSE,
        404: ERROR_RESPONSE,
        409: ERROR_RESPONSE,
        422: ERROR_RESPONSE,
    },
)
def delete_load_node_route(
    loadNodeId: str,
    request: Request,
    db: DbDep,
    user: CurrentUserDep,
    workspace: CurrentWorkspaceDep,
    _csrf: CsrfDep,
) -> Response:
    validate_load_node_id(loadNodeId)
    node = get_visible_load_node(db, workspace_id=workspace.id, load_node_id=loadNodeId)
    archive_load_node(db, node=node, actor=user)
    write_audit(request, db, "load_node.archived", user.id, node)
    db.commit()
    return Response(
        status_code=status.HTTP_204_NO_CONTENT, headers={"x-workspace-id": workspace.id}
    )


@router.post(
    "/{loadNodeId}/credentials",
    operation_id="updateLoadNodeCredentials",
    response_model=LoadNodeDetail,
    response_model_by_alias=True,
    responses={
        400: ERROR_RESPONSE,
        401: ERROR_RESPONSE,
        403: ERROR_RESPONSE,
        404: ERROR_RESPONSE,
        409: ERROR_RESPONSE,
        422: ERROR_RESPONSE,
        500: ERROR_RESPONSE,
    },
)
def update_load_node_credentials_route(
    loadNodeId: str,
    request: Request,
    response: Response,
    db: DbDep,
    user: CurrentUserDep,
    workspace: CurrentWorkspaceDep,
    _csrf: CsrfDep,
    payload: LoadNodeCredentialUpdateRequest,
) -> LoadNodeDetail:
    validate_load_node_id(loadNodeId)
    attach_workspace_header(response, workspace.id)
    node = get_visible_load_node(db, workspace_id=workspace.id, load_node_id=loadNodeId)
    updated = update_load_node_credentials(db, node=node, actor=user, credential=payload.credential)
    write_audit(request, db, "load_node.credential_updated", user.id, updated)
    db.commit()
    return detail_response(db, updated)


@router.post(
    "/{loadNodeId}/ssh-host-key/trust",
    operation_id="trustLoadNodeSshHostKey",
    response_model=LoadNodeDetail,
    response_model_by_alias=True,
    responses={
        400: ERROR_RESPONSE,
        401: ERROR_RESPONSE,
        403: ERROR_RESPONSE,
        404: ERROR_RESPONSE,
        409: ERROR_RESPONSE,
        422: ERROR_RESPONSE,
    },
)
def trust_load_node_ssh_host_key_route(
    loadNodeId: str,
    request: Request,
    response: Response,
    db: DbDep,
    user: CurrentUserDep,
    workspace: CurrentWorkspaceDep,
    _csrf: CsrfDep,
    payload: LoadNodeSshHostKeyInput,
) -> LoadNodeDetail:
    validate_load_node_id(loadNodeId)
    attach_workspace_header(response, workspace.id)
    node = get_visible_load_node(db, workspace_id=workspace.id, load_node_id=loadNodeId)
    updated = trust_load_node_ssh_host_key(db, node=node, actor=user, ssh_host_key=payload)
    write_audit(request, db, "load_node.ssh_host_key_trusted", user.id, updated)
    db.commit()
    return detail_response(db, updated)


@router.post(
    "/{loadNodeId}/initialize",
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="initializeLoadNode",
    response_model=LoadNodeInitializeResponse,
    response_model_by_alias=True,
    responses={
        400: ERROR_RESPONSE,
        401: ERROR_RESPONSE,
        403: ERROR_RESPONSE,
        404: ERROR_RESPONSE,
        409: ERROR_RESPONSE,
        422: ERROR_RESPONSE,
    },
)
def initialize_load_node_route(
    loadNodeId: str,
    request: Request,
    response: Response,
    db: DbDep,
    user: CurrentUserDep,
    workspace: CurrentWorkspaceDep,
    _csrf: CsrfDep,
    payload: InitializeLoadNodeRequest,
) -> LoadNodeInitializeResponse:
    validate_load_node_id(loadNodeId)
    attach_workspace_header(response, workspace.id)
    node = get_visible_load_node(db, workspace_id=workspace.id, load_node_id=loadNodeId)
    attempt = request_initialization(
        db,
        node=node,
        actor=user,
        force=payload.force,
        request_id=getattr(request.state, "request_id", None),
    )
    write_audit(request, db, "load_node.initialization_requested", user.id, node, attempt.id)
    db.commit()
    return LoadNodeInitializeResponse(
        node=LoadNodeInitializeNodeStatus(id=node.id, status=node.status),
        attempt=LoadNodeInitializeAttemptStatus(
            id=attempt.id, status=attempt.status, message=attempt.message
        ),
    )  # type: ignore[arg-type]


@router.get(
    "/{loadNodeId}/init-attempts",
    operation_id="listLoadNodeInitAttempts",
    response_model=LoadNodeInitAttemptListResponse,
    response_model_by_alias=True,
    responses={
        400: ERROR_RESPONSE,
        401: ERROR_RESPONSE,
        403: ERROR_RESPONSE,
        404: ERROR_RESPONSE,
        422: ERROR_RESPONSE,
    },
    openapi_extra={"parameters": INIT_ATTEMPT_LIST_QUERY_OPENAPI_PARAMETERS},
)
def list_init_attempts_route(
    loadNodeId: str, request: Request, response: Response, db: DbDep, workspace: CurrentWorkspaceDep
) -> LoadNodeInitAttemptListResponse:
    validate_load_node_id(loadNodeId)
    attach_workspace_header(response, workspace.id)
    node = get_visible_load_node(db, workspace_id=workspace.id, load_node_id=loadNodeId)
    limit = parse_int(
        request.query_params.get("limit"), field="limit", default=20, minimum=1, maximum=100
    )
    offset = parse_int(request.query_params.get("offset"), field="offset", default=0, minimum=0)
    filters = [LoadNodeInitializationAttempt.node_id == node.id]
    total = db.scalar(select(func.count(LoadNodeInitializationAttempt.id)).where(*filters)) or 0
    attempts = db.scalars(
        select(LoadNodeInitializationAttempt)
        .where(*filters)
        .order_by(
            LoadNodeInitializationAttempt.created_at.desc(), LoadNodeInitializationAttempt.id.desc()
        )
        .offset(offset)
        .limit(limit)
    ).all()
    db.commit()
    return LoadNodeInitAttemptListResponse(
        items=[attempt_summary_response(attempt) for attempt in attempts],
        limit=limit,
        offset=offset,
        total=total,
    )


@router.get(
    "/{loadNodeId}/init-attempts/{attemptId}",
    operation_id="getLoadNodeInitAttempt",
    response_model=LoadNodeInitAttemptDetail,
    response_model_by_alias=True,
    responses={
        400: ERROR_RESPONSE,
        401: ERROR_RESPONSE,
        403: ERROR_RESPONSE,
        404: ERROR_RESPONSE,
        422: ERROR_RESPONSE,
    },
)
def get_init_attempt_route(
    loadNodeId: str, attemptId: str, response: Response, db: DbDep, workspace: CurrentWorkspaceDep
) -> LoadNodeInitAttemptDetail:
    validate_load_node_id(loadNodeId)
    validate_load_node_id(attemptId, field="attemptId")
    attach_workspace_header(response, workspace.id)
    node = get_visible_load_node(db, workspace_id=workspace.id, load_node_id=loadNodeId)
    attempt = db.scalar(
        select(LoadNodeInitializationAttempt).where(
            LoadNodeInitializationAttempt.id == attemptId,
            LoadNodeInitializationAttempt.node_id == node.id,
        )
    )
    if attempt is None:
        raise AppError("RESOURCE_NOT_FOUND", "Resource was not found.", 404)
    db.commit()
    return attempt_detail_response(attempt)


@router.post(
    "/{loadNodeId}/disable",
    operation_id="disableLoadNode",
    response_model=LoadNodeDetail,
    response_model_by_alias=True,
    responses={
        400: ERROR_RESPONSE,
        401: ERROR_RESPONSE,
        403: ERROR_RESPONSE,
        404: ERROR_RESPONSE,
        409: ERROR_RESPONSE,
        422: ERROR_RESPONSE,
    },
)
def disable_load_node_route(
    loadNodeId: str,
    request: Request,
    response: Response,
    db: DbDep,
    user: CurrentUserDep,
    workspace: CurrentWorkspaceDep,
    _csrf: CsrfDep,
    payload: DisableLoadNodeRequest,
) -> LoadNodeDetail:
    validate_load_node_id(loadNodeId)
    attach_workspace_header(response, workspace.id)
    node = get_visible_load_node(db, workspace_id=workspace.id, load_node_id=loadNodeId)
    updated = disable_load_node(db, node=node, actor=user, reason=payload.reason)
    write_audit(request, db, "load_node.disabled", user.id, updated)
    db.commit()
    return detail_response(db, updated)


@router.post(
    "/{loadNodeId}/enable",
    operation_id="enableLoadNode",
    response_model=LoadNodeDetail,
    response_model_by_alias=True,
    responses={
        400: ERROR_RESPONSE,
        401: ERROR_RESPONSE,
        403: ERROR_RESPONSE,
        404: ERROR_RESPONSE,
        409: ERROR_RESPONSE,
        422: ERROR_RESPONSE,
    },
)
def enable_load_node_route(
    loadNodeId: str,
    request: Request,
    response: Response,
    db: DbDep,
    user: CurrentUserDep,
    workspace: CurrentWorkspaceDep,
    _csrf: CsrfDep,
) -> LoadNodeDetail:
    validate_load_node_id(loadNodeId)
    attach_workspace_header(response, workspace.id)
    node = get_visible_load_node(db, workspace_id=workspace.id, load_node_id=loadNodeId)
    updated = enable_load_node(db, node=node, actor=user)
    write_audit(request, db, "load_node.enabled", user.id, updated)
    db.commit()
    return detail_response(db, updated)
