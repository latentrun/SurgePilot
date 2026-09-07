from typing import Literal

from pydantic import ConfigDict, Field, field_validator

from app.schemas.common import ApiSchema

ScenarioType = Literal["visual"]
HttpMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]
BodyType = Literal["none", "raw", "form"]
ExtractorType = Literal["jsonpath", "regexp"]
AssertionType = Literal["status_code", "body_contains", "jsonpath_exists", "jsonpath_equals"]
ScriptExecute = Literal["before", "after"]
ScriptLanguage = Literal["groovy"]

# Unit: characters. This Scenario content limit is intentionally separate from
# Env Group variable values, which keep their P0 UTF-8 bytes limit.
SCENARIO_NAMED_VALUE_MAX_LENGTH = 65_536
SCENARIO_MODEL_CONFIG = ConfigDict(
    alias_generator=ApiSchema.model_config["alias_generator"],
    populate_by_name=True,
    extra="forbid",
)


class ScenarioDefaultSettings(ApiSchema):
    model_config = SCENARIO_MODEL_CONFIG

    think_time_ms: int = Field(default=0, ge=0, le=600_000)
    timeout_ms: int = Field(default=30_000, ge=100, le=300_000)
    follow_redirects: bool = True
    keep_alive: bool = True
    store_cache: bool = True
    store_cookie: bool = True
    retrieve_resources: bool = False


class ScenarioDataSource(ApiSchema):
    model_config = SCENARIO_MODEL_CONFIG

    id: str = Field(min_length=26, max_length=26)
    dependency_file_id: str = Field(min_length=26, max_length=26)
    display_name: str = Field(min_length=1, max_length=255)
    delimiter: str | None = Field(default=None, max_length=3, pattern=r"^(tab|.)$")
    quoted: bool | None = None
    loop: bool = True
    variable_names: list[str] = Field(default_factory=list, max_length=100)
    random_order: bool = False
    enabled: bool = True


class ScenarioNamedValue(ApiSchema):
    model_config = SCENARIO_MODEL_CONFIG

    id: str = Field(min_length=26, max_length=26)
    name: str = Field(min_length=1, max_length=255)
    value: str = Field(default="", max_length=SCENARIO_NAMED_VALUE_MAX_LENGTH)
    enabled: bool = True


class ScenarioFormField(ScenarioNamedValue):
    pass


class ScenarioBody(ApiSchema):
    model_config = SCENARIO_MODEL_CONFIG

    type: BodyType = "none"
    content_type: str | None = Field(default=None, max_length=120)
    raw_text: str | None = Field(default=None, max_length=262_144)
    form_fields: list[ScenarioFormField] = Field(default_factory=list, max_length=200)


class ScenarioUploadFile(ApiSchema):
    model_config = SCENARIO_MODEL_CONFIG

    id: str = Field(min_length=26, max_length=26)
    field_name: str = Field(min_length=1, max_length=120)
    dependency_file_id: str = Field(min_length=26, max_length=26)
    mime_type: str | None = Field(default=None, max_length=120)
    enabled: bool = True


class ScenarioExtractor(ApiSchema):
    model_config = SCENARIO_MODEL_CONFIG

    id: str = Field(min_length=26, max_length=26)
    type: ExtractorType
    variable_name: str = Field(min_length=1, max_length=64)
    expression: str = Field(min_length=1, max_length=2048)
    default_value: str | None = Field(default="", max_length=4096)
    match_no: int = Field(default=1, ge=0, le=1000)
    subject: str | None = Field(default="body", max_length=64)
    template: str | None = Field(default=None, max_length=120)
    enabled: bool = True


class ScenarioAssertion(ApiSchema):
    model_config = SCENARIO_MODEL_CONFIG

    id: str = Field(min_length=26, max_length=26)
    type: AssertionType
    expected_status: int | None = Field(default=None, ge=100, le=599)
    contains: str | None = Field(default=None, max_length=4096)
    jsonpath: str | None = Field(default=None, max_length=2048)
    expected_value: str | None = Field(default=None, max_length=4096)
    regexp: bool = False
    not_: bool = Field(default=False, alias="not")
    enabled: bool = True


class ScenarioScript(ApiSchema):
    model_config = SCENARIO_MODEL_CONFIG

    id: str = Field(min_length=26, max_length=26)
    execute: ScriptExecute
    language: ScriptLanguage = "groovy"
    script_text: str | None = Field(default=None, max_length=262_144)
    enabled: bool = True


class ScenarioStepSettings(ApiSchema):
    model_config = SCENARIO_MODEL_CONFIG

    think_time_ms: int | None = Field(default=None, ge=0, le=600_000)
    timeout_ms: int | None = Field(default=None, ge=100, le=300_000)
    follow_redirects: bool | None = None
    keep_alive: bool | None = None


class ScenarioStep(ApiSchema):
    model_config = SCENARIO_MODEL_CONFIG

    id: str = Field(min_length=26, max_length=26)
    enabled: bool = True
    name: str = Field(min_length=1, max_length=120)
    method: HttpMethod
    path: str = Field(min_length=1, max_length=2048)
    query_params: list[ScenarioNamedValue] = Field(default_factory=list, max_length=200)
    headers: list[ScenarioNamedValue] = Field(default_factory=list, max_length=200)
    body: ScenarioBody = Field(default_factory=ScenarioBody)
    upload_files: list[ScenarioUploadFile] = Field(default_factory=list, max_length=20)
    extractors: list[ScenarioExtractor] = Field(default_factory=list, max_length=50)
    assertions: list[ScenarioAssertion] = Field(default_factory=list, max_length=50)
    scripts: list[ScenarioScript] = Field(default_factory=list, max_length=20)
    settings: ScenarioStepSettings = Field(default_factory=ScenarioStepSettings)

    @field_validator("path")
    @classmethod
    def path_starts_with_slash(cls, value: str) -> str:
        if not value.startswith("/"):
            raise ValueError("Path must start with /.")
        return value


class ScenarioEditableContent(ApiSchema):
    model_config = SCENARIO_MODEL_CONFIG

    name: str = Field(min_length=1, max_length=120, pattern=r".*\S.*")
    description: str | None = Field(default=None, max_length=2000)
    tags: list[str] = Field(default_factory=list, max_length=10)
    base_url_expression: str = Field(default="${base_url}", min_length=1, max_length=2048)
    default_settings: ScenarioDefaultSettings = Field(default_factory=ScenarioDefaultSettings)
    data_sources: list[ScenarioDataSource] = Field(default_factory=list, max_length=50)
    steps: list[ScenarioStep] = Field(default_factory=list, max_length=200)


class ScenarioCreateRequest(ScenarioEditableContent):
    pass


class ScenarioPatchRequest(ScenarioEditableContent):
    expected_revision: int = Field(ge=1)


class ScenarioSummary(ApiSchema):
    id: str
    name: str
    description: str | None = None
    tags: list[str]
    scenario_type: ScenarioType
    step_count: int
    enabled_step_count: int
    dependency_file_count: int
    revision: int
    created_at: str
    updated_at: str


class ScenarioDetail(ScenarioSummary):
    base_url_expression: str
    default_settings: ScenarioDefaultSettings
    data_sources: list[ScenarioDataSource]
    steps: list[ScenarioStep]


class ScenarioListResponse(ApiSchema):
    items: list[ScenarioSummary]
    page: int
    page_size: int
    total: int
