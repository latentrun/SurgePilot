from enum import Enum
from typing import Literal

from pydantic import ConfigDict, Field

from app.schemas.common import ApiSchema


class RunState(str, Enum):
    initializing = "initializing"
    running = "running"
    stopping = "stopping"
    finished = "finished"
    failed = "failed"
    aborted = "aborted"


CallbackEventType = Literal[
    "accepted", "running", "heartbeat", "artifact", "finished", "failed", "aborted"
]

RunCreateType = Literal["debug"]
RunCreateSourceType = Literal["debug_scenario"]


class RunCreateRequest(ApiSchema):
    """Public ``POST /api/v1/runs`` payload for a Scenario Debug Run.

    P0-05 activates public Run creation for ``runType=debug`` with
    ``sourceType=debug_scenario`` only; other Run sources are rejected until a
    later slice extends public Run creation.
    """

    model_config = ConfigDict(
        alias_generator=ApiSchema.model_config["alias_generator"],
        populate_by_name=True,
        extra="forbid",
    )

    run_type: RunCreateType
    source_type: RunCreateSourceType
    source_id: str = Field(min_length=26, max_length=26)
    expected_source_revision: int = Field(ge=1)
    env_group_id: str | None = Field(default=None, min_length=26, max_length=26)
    selected_node_id: str | None = Field(default=None, min_length=26, max_length=26)


class RunCreateResponse(ApiSchema):
    id: str
    state: RunState
    run_type: RunCreateType
    source_type: RunCreateSourceType
    source_id: str | None = None
    selected_node_id: str
    created_at: str
    deduplicated: bool


class RunStopResponse(ApiSchema):
    id: str
    state: RunState
    stop_requested_at: str | None = None
    duplicate: bool


class RunnerCallbackRequest(ApiSchema):
    model_config = ConfigDict(
        alias_generator=ApiSchema.model_config["alias_generator"],
        populate_by_name=True,
        extra="forbid",
    )

    schema_version: Literal["1"]
    event_id: str = Field(min_length=26, max_length=26)
    run_id: str = Field(min_length=26, max_length=26)
    node_id: str = Field(min_length=26, max_length=26)
    runtime_version: str = Field(min_length=1, max_length=200)
    event_type: CallbackEventType
    seq: int = Field(ge=0)
    event_time: str
    message: str | None = Field(default=None, max_length=500)
    runner_pid: int | None = Field(default=None, ge=1)
    details: dict = Field(default_factory=dict)


class RunnerCallbackResponse(ApiSchema):
    accepted: bool
    duplicate: bool
    state_changed: bool
    current_state: RunState
    ignored_reason: str | None = None


class RunnerArtifactResponse(ApiSchema):
    artifact_id: str
    duplicate: bool
