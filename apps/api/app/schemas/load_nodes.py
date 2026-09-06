from typing import Literal

from pydantic import ConfigDict, Field

from app.core.config import get_settings
from app.schemas.common import ApiSchema

LoadNodeScope = Literal["public", "workspace"]
LoadNodeStatus = Literal[
    "uninitialized",
    "initializing",
    "idle",
    "busy",
    "offline",
    "quarantined",
    "disabled",
]
LoadNodeAuthType = Literal["password", "private_key", "generated_key"]
InitAttemptStatus = Literal["queued", "running", "succeeded", "failed"]


class LoadNodeCredentialInput(ApiSchema):
    model_config = ConfigDict(
        alias_generator=ApiSchema.model_config["alias_generator"],
        populate_by_name=True,
        extra="forbid",
    )

    auth_type: LoadNodeAuthType
    password: str | None = Field(default=None, json_schema_extra={"writeOnly": True})
    private_key: str | None = Field(default=None, json_schema_extra={"writeOnly": True})
    private_key_passphrase: str | None = Field(default=None, json_schema_extra={"writeOnly": True})


class LoadNodeSshHostKeyInput(ApiSchema):
    model_config = ConfigDict(
        alias_generator=ApiSchema.model_config["alias_generator"],
        populate_by_name=True,
        extra="forbid",
    )

    algorithm: str
    public_key: str
    fingerprint_sha256: str


class LoadNodeSshHostKeyScanRequest(ApiSchema):
    model_config = ConfigDict(
        alias_generator=ApiSchema.model_config["alias_generator"],
        populate_by_name=True,
        extra="forbid",
    )

    scope: LoadNodeScope
    host: str
    ssh_port: int = 22


class LoadNodeSshHostKeyResponse(ApiSchema):
    algorithm: str
    public_key: str
    fingerprint_sha256: str
    known_hosts_line: str


class LoadNodeSshHostKeyScanResponse(LoadNodeSshHostKeyResponse):
    host: str
    ssh_port: int
    scanned_at: str


class LoadNodeCreateRequest(ApiSchema):
    model_config = ConfigDict(
        alias_generator=ApiSchema.model_config["alias_generator"],
        populate_by_name=True,
        extra="forbid",
    )

    scope: LoadNodeScope
    host: str
    ssh_port: int = 22
    ssh_user: str
    runner_home: str = Field(default_factory=lambda: get_settings().load_node_default_runner_home)
    ssh_host_key: LoadNodeSshHostKeyInput
    credential: LoadNodeCredentialInput
    maintainer: str | None = None
    remark: str | None = None


class LoadNodePatchRequest(ApiSchema):
    model_config = ConfigDict(
        alias_generator=ApiSchema.model_config["alias_generator"],
        populate_by_name=True,
        extra="forbid",
    )

    host: str | None = None
    ssh_port: int | None = None
    ssh_user: str | None = None
    runner_home: str | None = None
    maintainer: str | None = None
    remark: str | None = None


class LoadNodeCredentialUpdateRequest(ApiSchema):
    model_config = ConfigDict(
        alias_generator=ApiSchema.model_config["alias_generator"],
        populate_by_name=True,
        extra="forbid",
    )

    credential: LoadNodeCredentialInput


class InitializeLoadNodeRequest(ApiSchema):
    force: bool = False


class DisableLoadNodeRequest(ApiSchema):
    reason: str | None = None


class LoadNodeSummary(ApiSchema):
    id: str
    scope: LoadNodeScope
    workspace_id: str | None = None
    host: str
    ssh_port: int
    ssh_user: str
    runner_home: str
    auth_type: LoadNodeAuthType
    credential_configured: bool
    credential_fingerprint: str | None = None
    generated_public_key: str | None = None
    ssh_host_key: LoadNodeSshHostKeyResponse | None = None
    maintainer: str | None = None
    remark: str | None = None
    status: LoadNodeStatus
    last_status_reason: str | None = None
    runner_version: str | None = None
    bundle_version: str | None = None
    last_initialized_at: str | None = None
    last_checked_at: str | None = None
    last_heartbeat_at: str | None = None
    current_run_id: str | None = None
    last_init_attempt_id: str | None = None
    created_at: str
    updated_at: str


class LoadNodeInitAttemptSummary(ApiSchema):
    id: str
    node_id: str
    status: InitAttemptStatus
    started_at: str | None = None
    finished_at: str | None = None
    error_code: str | None = None
    message: str | None = None
    created_at: str


class LoadNodeLatestInitAttempt(ApiSchema):
    id: str
    status: InitAttemptStatus
    started_at: str | None = None
    finished_at: str | None = None
    error_code: str | None = None
    message: str | None = None


class LoadNodeDetail(LoadNodeSummary):
    latest_init_attempt: LoadNodeLatestInitAttempt | None = None


class LoadNodeListResponse(ApiSchema):
    items: list[LoadNodeSummary]
    limit: int
    offset: int
    total: int


class LoadNodeInitializeNodeStatus(ApiSchema):
    id: str
    status: LoadNodeStatus


class LoadNodeInitializeAttemptStatus(ApiSchema):
    id: str
    status: InitAttemptStatus
    message: str | None = None


class LoadNodeInitializeResponse(ApiSchema):
    node: LoadNodeInitializeNodeStatus
    attempt: LoadNodeInitializeAttemptStatus


class LoadNodeInitAttemptListResponse(ApiSchema):
    items: list[LoadNodeInitAttemptSummary]
    limit: int
    offset: int
    total: int


class LoadNodeInitAttemptDetail(LoadNodeInitAttemptSummary):
    sanitized_log_tail: str | None = None
    runner_version: str | None = None
    bundle_version: str | None = None
    updated_at: str
