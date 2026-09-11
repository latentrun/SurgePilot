from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import json
import re
from threading import Lock
from typing import Any

import yaml
from openapi_spec_validator import (
    OpenAPIV2SpecValidator,
    OpenAPIV30SpecValidator,
    OpenAPIV31SpecValidator,
)
from openapi_spec_validator.validation.exceptions import OpenAPISpecValidatorError
from referencing.exceptions import (
    CannotDetermineSpecification,
    InvalidAnchor,
    NoInternalID,
    NoSuchAnchor,
    NoSuchResource,
    PointerToNowhere,
    Unresolvable,
    Unretrievable,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.api_catalog import ApiCatalogSpec
from app.schemas.scenarios import (
    OpenApiGeneratedBodyDraft,
    OpenApiGeneratedNamedValueDraft,
    OpenApiGeneratedStepDraft,
    OpenApiGeneratedStepDraftItem,
    OpenApiGeneratedStepSettingsDraft,
    OpenApiGeneratedStepSource,
    OpenApiOperationListResponse,
    OpenApiOperationRef,
    OpenApiOperationSummary,
    OpenApiSpecSourceListResponse,
    OpenApiSpecSourceSummary,
    OpenApiStepDraftPreviewResponse,
    OpenApiStepGenerationWarning,
    OpenApiStepInsertPlan,
)
from app.services.api_catalog import get_api_catalog_spec
from app.services.storage import StorageClient

HTTP_METHOD_ORDER = ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS")
HTTP_METHODS = set(HTTP_METHOD_ORDER)
OPENAPI_METHOD_ORDER = tuple(method.lower() for method in HTTP_METHOD_ORDER)
MAX_RAW_BODY_CHARS = 262_144
MAX_SCHEMA_SAMPLE_DEPTH = 20
AUTH_HEADER_NAMES = {
    "authorization",
    "cookie",
    "proxy-authorization",
    "x-api-key",
    "api-key",
    "apikey",
    "x-auth-token",
    "x-csrf-token",
}
COMMON_HEADER_NAMES = {
    "accept",
    "accept-encoding",
    "connection",
    "content-length",
    "content-type",
    "host",
    "user-agent",
}
PATH_PARAMETER_PATTERN = re.compile(r"\{([^{}]+)\}")
NO_REMOTE_RESOLVER_HANDLERS: dict[str, Any] = {}
PARSED_DOCUMENT_CACHE_CAPACITY = 8


class NoRemoteOpenAPIV2SpecValidator(OpenAPIV2SpecValidator):
    resolver_handlers = NO_REMOTE_RESOLVER_HANDLERS


class NoRemoteOpenAPIV30SpecValidator(OpenAPIV30SpecValidator):
    resolver_handlers = NO_REMOTE_RESOLVER_HANDLERS


class NoRemoteOpenAPIV31SpecValidator(OpenAPIV31SpecValidator):
    resolver_handlers = NO_REMOTE_RESOLVER_HANDLERS


@dataclass(frozen=True)
class ParsedOpenApiDocument:
    document: dict[str, Any]
    version: str
    root_kind: str


ParsedOpenApiDocumentCacheKey = tuple[str, str, str, str]


class ParsedOpenApiDocumentCache:
    def __init__(self, *, capacity: int) -> None:
        self._capacity = capacity
        self._items: OrderedDict[ParsedOpenApiDocumentCacheKey, ParsedOpenApiDocument] = (
            OrderedDict()
        )
        self._lock = Lock()

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)

    def get(self, key: ParsedOpenApiDocumentCacheKey) -> ParsedOpenApiDocument | None:
        with self._lock:
            parsed = self._items.get(key)
            if parsed is not None:
                self._items.move_to_end(key)
            return parsed

    def put(self, key: ParsedOpenApiDocumentCacheKey, parsed: ParsedOpenApiDocument) -> None:
        with self._lock:
            self._items[key] = parsed
            self._items.move_to_end(key)
            while len(self._items) > self._capacity:
                self._items.popitem(last=False)


_PARSED_DOCUMENT_CACHE = ParsedOpenApiDocumentCache(capacity=PARSED_DOCUMENT_CACHE_CAPACITY)


@dataclass(frozen=True)
class LocatedOperation:
    ref: OpenApiOperationRef
    operation: dict[str, Any]
    path_item: dict[str, Any]


def iso_z(value) -> str:
    return value.isoformat().replace("+00:00", "Z")


def warning(code: str, message: str, field: str | None = None) -> OpenApiStepGenerationWarning:
    return OpenApiStepGenerationWarning(code=code, message=message, field=field)


def spec_source_summary(spec: ApiCatalogSpec) -> OpenApiSpecSourceSummary:
    return OpenApiSpecSourceSummary(
        id=spec.id,
        name=spec.name,
        filename=spec.filename,
        source_format=spec.source_format,
        document_title=spec.document_title,
        document_version=spec.document_version,
        status=spec.status,
        updated_at=iso_z(spec.updated_at),
    )


def list_openapi_spec_sources(
    db: Session, *, workspace_id: str, limit: int, offset: int
) -> OpenApiSpecSourceListResponse:
    filters = [
        ApiCatalogSpec.workspace_id == workspace_id,
        ApiCatalogSpec.status == "available",
    ]
    total = db.scalar(select(func.count(ApiCatalogSpec.id)).where(*filters)) or 0
    items = db.scalars(
        select(ApiCatalogSpec)
        .where(*filters)
        .order_by(ApiCatalogSpec.created_at.desc(), ApiCatalogSpec.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return OpenApiSpecSourceListResponse(
        items=[spec_source_summary(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


def read_stored_spec(spec: ApiCatalogSpec, *, storage: StorageClient) -> bytes:
    stored = storage.get_stream(bucket=spec.storage_bucket, object_key=spec.storage_object_key)
    stream = stored.stream
    try:
        return stream.read()
    finally:
        close = getattr(stream, "close", None)
        if callable(close):
            close()
        release_conn = getattr(stream, "release_conn", None)
        if callable(release_conn):
            release_conn()


def load_payload(payload: bytes, *, spec: ApiCatalogSpec) -> dict[str, Any]:
    try:
        if spec.source_format.endswith("_json"):
            document = json.loads(payload.decode("utf-8"))
        else:
            document = yaml.safe_load(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, yaml.YAMLError) as exc:
        raise AppError("API_SPEC_PARSE_FAILED", "The API spec could not be parsed.", 422) from exc
    if not isinstance(document, dict):
        raise AppError("UNSUPPORTED_API_SPEC_FORMAT", "The API spec root is unsupported.", 422)
    return document


def validate_document(document: dict[str, Any]) -> ParsedOpenApiDocument:
    root_kind: str
    version: Any
    if "openapi" in document:
        root_kind = "openapi"
        version = document.get("openapi")
    elif "swagger" in document:
        root_kind = "swagger"
        version = document.get("swagger")
    else:
        raise AppError("UNSUPPORTED_API_SPEC_FORMAT", "The API spec root is unsupported.", 422)
    if not isinstance(version, str):
        raise AppError("UNSUPPORTED_API_SPEC_FORMAT", "The API spec version is unsupported.", 422)
    if root_kind == "swagger" and version.strip() == "2.0":
        validator_cls = NoRemoteOpenAPIV2SpecValidator
    elif root_kind == "openapi" and version.startswith("3.0"):
        validator_cls = NoRemoteOpenAPIV30SpecValidator
    elif root_kind == "openapi" and version.startswith("3.1"):
        validator_cls = NoRemoteOpenAPIV31SpecValidator
    else:
        raise AppError("UNSUPPORTED_API_SPEC_FORMAT", "The API spec version is unsupported.", 422)
    try:
        errors = list(validator_cls(document).iter_errors())
    except (
        OpenAPISpecValidatorError,
        CannotDetermineSpecification,
        InvalidAnchor,
        NoInternalID,
        NoSuchAnchor,
        NoSuchResource,
        PointerToNowhere,
        Unresolvable,
        Unretrievable,
    ) as exc:
        raise AppError(
            "API_SPEC_PARSE_FAILED", "The API spec could not be validated.", 422
        ) from exc
    if errors:
        raise AppError("API_SPEC_PARSE_FAILED", "The API spec could not be validated.", 422)
    return ParsedOpenApiDocument(document=document, version=version.strip(), root_kind=root_kind)


def parsed_document_cache_key(spec: ApiCatalogSpec) -> ParsedOpenApiDocumentCacheKey:
    return (spec.workspace_id, spec.id, spec.sha256, spec.status)


def parse_authorized_spec(
    spec: ApiCatalogSpec,
    *,
    storage: StorageClient,
    cache: ParsedOpenApiDocumentCache | None = None,
) -> ParsedOpenApiDocument:
    if spec.status != "available":
        raise AppError("API_SPEC_NOT_AVAILABLE", "API spec is not available for generation.", 422)
    document_cache = cache if cache is not None else _PARSED_DOCUMENT_CACHE
    cache_key = parsed_document_cache_key(spec)
    cached = document_cache.get(cache_key)
    if cached is not None:
        return cached
    parsed = validate_document(load_payload(read_stored_spec(spec, storage=storage), spec=spec))
    document_cache.put(cache_key, parsed)
    return parsed


def safe_text(value: Any, *, max_length: int = 120) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    if not isinstance(value, str):
        value = str(value)
    compact = re.sub(r"\s+", " ", value).strip()
    return compact[:max_length] if compact else None


def operation_ref(method: str, path: str, operation: dict[str, Any]) -> OpenApiOperationRef:
    return OpenApiOperationRef(
        method=method,
        path=path,
        operation_id=safe_text(operation.get("operationId"), max_length=160),
    )


def has_request_body(parsed: ParsedOpenApiDocument, operation: dict[str, Any]) -> bool:
    if parsed.root_kind == "swagger":
        return any(
            isinstance(parameter, dict) and parameter.get("in") == "body"
            for parameter in operation.get("parameters", [])
        )
    return isinstance(operation.get("requestBody"), dict)


def enumerate_operations(
    parsed: ParsedOpenApiDocument,
) -> tuple[list[OpenApiOperationSummary], list[OpenApiStepGenerationWarning]]:
    items: list[OpenApiOperationSummary] = []
    paths = parsed.document.get("paths")
    if not isinstance(paths, dict):
        return [], []
    for path, path_item in paths.items():
        if not isinstance(path, str) or not isinstance(path_item, dict):
            continue
        for method_name in OPENAPI_METHOD_ORDER:
            operation = path_item.get(method_name)
            if not isinstance(operation, dict):
                continue
            method = method_name.upper()
            summary = safe_text(operation.get("summary"))
            operation_id = safe_text(operation.get("operationId"), max_length=160)
            tags = [tag for tag in operation.get("tags", []) if isinstance(tag, str)]
            items.append(
                OpenApiOperationSummary(
                    ref=operation_ref(method, path, operation),
                    method=method,
                    path=path,
                    operation_id=operation_id,
                    summary=summary,
                    tags=tags[:20],
                    display_name=summary or operation_id or f"{method} {path}",
                    has_request_body=has_request_body(parsed, operation),
                    supported_for_generation=path.startswith("/"),
                    warning_codes=[] if path.startswith("/") else ["OPENAPI_OPERATION_UNSUPPORTED"],
                )
            )
    return items, []


def resolve_local_ref(document: dict[str, Any], value: Any) -> Any:
    if not isinstance(value, dict) or "$ref" not in value:
        return value
    ref = value.get("$ref")
    if not isinstance(ref, str) or not ref.startswith("#/"):
        return value
    current: Any = document
    for part in ref[2:].split("/"):
        key = part.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, dict) or key not in current:
            return value
        current = current[key]
    return current


def parameters(parsed: ParsedOpenApiDocument, located: LocatedOperation) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for source in (
        located.path_item.get("parameters", []),
        located.operation.get("parameters", []),
    ):
        if not isinstance(source, list):
            continue
        for parameter in source:
            resolved = resolve_local_ref(parsed.document, parameter)
            if isinstance(resolved, dict):
                values.append(resolved)
    return values


def parameter_schema(parameter: dict[str, Any]) -> dict[str, Any]:
    schema = parameter.get("schema")
    if isinstance(schema, dict):
        return schema
    swagger_schema: dict[str, Any] = {}
    for key in ("type", "format", "items", "enum", "default", "minimum", "maximum"):
        if key in parameter:
            swagger_schema[key] = parameter[key]
    return swagger_schema


def parameter_value(parameter: dict[str, Any]) -> tuple[str | None, bool]:
    if "example" in parameter:
        return str(parameter.get("example")), True
    schema = parameter_schema(parameter)
    if schema:
        if "example" in schema:
            return str(schema.get("example")), True
        if "default" in schema:
            return str(schema.get("default")), True
        if "minimum" in schema:
            return str(schema.get("minimum")), True
    return None, False


def schema_type(schema: dict[str, Any]) -> str | None:
    schema_type_value = schema.get("type")
    return schema_type_value if isinstance(schema_type_value, str) else None


def has_unsupported_parameter_serialization(parameter: dict[str, Any]) -> bool:
    location = parameter.get("in")
    if location not in {"query", "header"}:
        return False
    schema = parameter_schema(parameter)
    current_schema_type = schema_type(schema)
    if current_schema_type in {"array", "object"} or isinstance(schema.get("properties"), dict):
        return True

    style = parameter.get("style")
    if location == "query":
        if style is not None and style != "form":
            return True
        return False

    if style is not None and style != "simple":
        return True
    return False


def unsupported_parameter_style_warning(
    parameter_name: str, location: str
) -> OpenApiStepGenerationWarning:
    field = "step.queryParams" if location == "query" else "step.headers"
    return warning(
        "UNSUPPORTED_PARAMETER_STYLE",
        f"Parameter {parameter_name} uses serialization that is not supported in this version.",
        field,
    )


def auth_warning(name: str, field: str = "step.headers") -> OpenApiStepGenerationWarning:
    return warning(
        "AUTH_HEADER_NOT_GENERATED",
        f"Auth value for {name} was not generated because credentials must be configured "
        "outside OpenAPI Step generation.",
        field,
    )


def path_with_placeholders(path: str, warnings: list[OpenApiStepGenerationWarning]) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group(1).strip()
        warnings.append(
            warning(
                "PATH_VARIABLE_PLACEHOLDER_REQUIRED",
                f"Fill {name} before running this Step.",
                "step.path",
            )
        )
        return "${" + name + "}"

    return PATH_PARAMETER_PATTERN.sub(replace, path)


def named_value(name: str, value: str) -> OpenApiGeneratedNamedValueDraft:
    return OpenApiGeneratedNamedValueDraft(name=name, value=value, enabled=True)


def map_query_and_headers(
    parsed: ParsedOpenApiDocument, located: LocatedOperation
) -> tuple[
    list[OpenApiGeneratedNamedValueDraft],
    list[OpenApiGeneratedNamedValueDraft],
    list[OpenApiStepGenerationWarning],
]:
    query: list[OpenApiGeneratedNamedValueDraft] = []
    headers: list[OpenApiGeneratedNamedValueDraft] = []
    warnings: list[OpenApiStepGenerationWarning] = []
    header_names: set[str] = set()
    for parameter in parameters(parsed, located):
        name = parameter.get("name")
        location = parameter.get("in")
        if not isinstance(name, str) or location not in {"query", "header"}:
            continue
        normalized = name.lower()
        if normalized in AUTH_HEADER_NAMES:
            field = "step.queryParams" if location == "query" else "step.headers"
            warnings.append(auth_warning(name, field))
            continue
        if has_unsupported_parameter_serialization(parameter):
            warnings.append(unsupported_parameter_style_warning(name, location))
            continue
        required = bool(parameter.get("required"))
        value, has_value = parameter_value(parameter)
        if location == "query":
            if required and not has_value:
                query.append(named_value(name, "${" + name + "}"))
                warnings.append(
                    warning(
                        "QUERY_PARAMETER_PLACEHOLDER_REQUIRED",
                        f"Fill query parameter {name} before running this Step.",
                        "step.queryParams",
                    )
                )
            elif has_value:
                query.append(named_value(name, value or ""))
            else:
                warnings.append(
                    warning(
                        "OPTIONAL_PARAMETER_SKIPPED",
                        f"Optional query parameter {name} was skipped because it has no "
                        "example or default.",
                        "step.queryParams",
                    )
                )
            continue
        if normalized in COMMON_HEADER_NAMES or normalized in header_names:
            continue
        if required and not has_value:
            headers.append(named_value(name, "${" + name + "}"))
            header_names.add(normalized)
            warnings.append(
                warning(
                    "HEADER_PARAMETER_PLACEHOLDER_REQUIRED",
                    f"Fill header {name} before running this Step.",
                    "step.headers",
                )
            )
        elif has_value:
            headers.append(named_value(name, value or ""))
            header_names.add(normalized)
        else:
            warnings.append(
                warning(
                    "OPTIONAL_PARAMETER_SKIPPED",
                    f"Optional header {name} was skipped because it has no example or default.",
                    "step.headers",
                )
            )
    return query, headers, warnings


def schema_sample(
    document: dict[str, Any],
    schema: Any,
    *,
    depth: int = 0,
    seen_refs: set[str] | None = None,
) -> Any:
    if depth > MAX_SCHEMA_SAMPLE_DEPTH:
        return None
    if isinstance(schema, dict):
        ref = schema.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/"):
            seen_refs = seen_refs or set()
            if ref in seen_refs:
                return None
            seen_refs = {*seen_refs, ref}
    schema = resolve_local_ref(document, schema)
    if not isinstance(schema, dict):
        return None
    if "example" in schema:
        return schema["example"]
    if "default" in schema:
        return schema["default"]
    if "enum" in schema and isinstance(schema["enum"], list) and schema["enum"]:
        return schema["enum"][0]
    schema_type = schema.get("type")
    if not isinstance(schema_type, str) and isinstance(schema.get("properties"), dict):
        schema_type = "object"
    if schema_type == "object":
        properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
        result: dict[str, Any] = {}
        for name, child in properties.items():
            sample = schema_sample(document, child, depth=depth + 1, seen_refs=seen_refs)
            if sample is not None:
                result[str(name)] = sample
        return result if result else None
    if schema_type == "array":
        item = schema_sample(document, schema.get("items"), depth=depth + 1, seen_refs=seen_refs)
        return [item] if item is not None else []
    if schema_type in {"integer", "number"}:
        return schema.get("minimum", 0)
    if schema_type == "boolean":
        return False
    if schema_type == "string":
        return "string"
    return None


def json_body_from_sample(sample: Any) -> str | None:
    if sample is None:
        return None
    text = json.dumps(sample, indent=2, ensure_ascii=False)
    return text if len(text) <= MAX_RAW_BODY_CHARS else None


def map_body(
    parsed: ParsedOpenApiDocument, located: LocatedOperation
) -> tuple[OpenApiGeneratedBodyDraft, list[OpenApiStepGenerationWarning]]:
    warnings: list[OpenApiStepGenerationWarning] = []
    body = OpenApiGeneratedBodyDraft(type="none", content_type=None, raw_text=None, form_fields=[])
    media: dict[str, Any] | None = None
    if parsed.root_kind == "swagger":
        consumes = located.operation.get("consumes", parsed.document.get("consumes"))
        if isinstance(consumes, list) and consumes and "application/json" not in consumes:
            warnings.append(
                warning(
                    "UNSUPPORTED_BODY_MEDIA_TYPE",
                    "Request body media type is not supported in this version.",
                    "step.body",
                )
            )
            return body, warnings
        for parameter in parameters(parsed, located):
            if parameter.get("in") == "body":
                media = {"schema": parameter.get("schema")}
                break
    else:
        request_body = resolve_local_ref(parsed.document, located.operation.get("requestBody"))
        content = request_body.get("content") if isinstance(request_body, dict) else None
        if isinstance(content, dict):
            value = content.get("application/json")
            if isinstance(value, dict):
                media = value
            elif content:
                warnings.append(
                    warning(
                        "UNSUPPORTED_BODY_MEDIA_TYPE",
                        "Request body media type is not supported in this version.",
                        "step.body",
                    )
                )
                return body, warnings
    if media is None:
        return body, warnings
    sample = None
    if "example" in media:
        sample = media["example"]
    elif isinstance(media.get("examples"), dict):
        first = next(iter(media["examples"].values()), None)
        if isinstance(first, dict):
            sample = first.get("value")
    if sample is None:
        sample = schema_sample(parsed.document, media.get("schema"))
    raw_text = json_body_from_sample(sample)
    if raw_text is None:
        warnings.append(
            warning(
                "JSON_BODY_EXAMPLE_MISSING",
                "JSON request body exists but no safe example could be generated.",
                "step.body.rawText",
            )
        )
        return body, warnings
    warnings.append(
        warning(
            "JSON_BODY_EXAMPLE_GENERATED",
            "A JSON body example was generated from the API spec.",
            "step.body.rawText",
        )
    )
    return (
        OpenApiGeneratedBodyDraft(
            type="raw", content_type="application/json", raw_text=raw_text, form_fields=[]
        ),
        warnings,
    )


def locate_operation(
    parsed: ParsedOpenApiDocument, ref: OpenApiOperationRef, index: int
) -> LocatedOperation:
    if ref.method not in HTTP_METHODS:
        raise AppError(
            "OPENAPI_OPERATION_UNSUPPORTED",
            "OpenAPI operation cannot be generated as an HTTP Step.",
            422,
            [
                {
                    "field": f"operationRefs[{index}].method",
                    "code": "unsupported_method",
                    "message": "HTTP method is unsupported.",
                }
            ],
        )
    paths = parsed.document.get("paths")
    path_item = paths.get(ref.path) if isinstance(paths, dict) else None
    operation = path_item.get(ref.method.lower()) if isinstance(path_item, dict) else None
    if not isinstance(path_item, dict) or not isinstance(operation, dict):
        raise AppError(
            "OPENAPI_OPERATION_NOT_FOUND",
            "OpenAPI operation was not found.",
            422,
            [
                {
                    "field": f"operationRefs[{index}]",
                    "code": "operation_not_found",
                    "message": "OpenAPI operation was not found.",
                }
            ],
        )
    operation_id = operation.get("operationId")
    if ref.operation_id and operation_id and ref.operation_id != operation_id:
        raise AppError(
            "OPENAPI_OPERATION_NOT_FOUND",
            "OpenAPI operation was not found.",
            422,
            [
                {
                    "field": f"operationRefs[{index}].operationId",
                    "code": "operation_not_found",
                    "message": "OpenAPI operationId did not match.",
                }
            ],
        )
    return LocatedOperation(ref=ref, operation=operation, path_item=path_item)


def ensure_unique_refs(refs: list[OpenApiOperationRef]) -> None:
    seen: set[tuple[str, str]] = set()
    for index, ref in enumerate(refs):
        key = (ref.method, ref.path)
        if key in seen:
            raise AppError(
                "VALIDATION_ERROR",
                "Validation failed.",
                422,
                [
                    {
                        "field": f"operationRefs[{index}]",
                        "code": "duplicate_operation_ref",
                        "message": "Duplicate operation refs are not allowed.",
                    }
                ],
            )
        seen.add(key)


def security_schemes(parsed: ParsedOpenApiDocument) -> dict[str, Any]:
    if parsed.root_kind == "swagger":
        value = parsed.document.get("securityDefinitions")
    else:
        components = parsed.document.get("components")
        value = components.get("securitySchemes") if isinstance(components, dict) else None
    return value if isinstance(value, dict) else {}


def operation_security_requirements(
    located: LocatedOperation, document: dict[str, Any]
) -> list[Any]:
    if "security" in located.operation:
        value = located.operation.get("security")
    else:
        value = document.get("security")
    return value if isinstance(value, list) else []


def security_scheme_requires_credential_header(scheme: Any) -> bool:
    if not isinstance(scheme, dict):
        return False
    scheme_type = scheme.get("type")
    if scheme_type == "apiKey":
        return scheme.get("in") in {"header", "query", "cookie"}
    if scheme_type == "basic":
        return True
    if scheme_type == "http":
        return str(scheme.get("scheme", "")).lower() in {"basic", "bearer"}
    if scheme_type in {"oauth2", "openIdConnect"}:
        return True
    return False


def security_scheme_field(scheme: Any) -> str:
    if isinstance(scheme, dict) and scheme.get("type") == "apiKey" and scheme.get("in") == "query":
        return "step.queryParams"
    return "step.headers"


def security_warnings(
    parsed: ParsedOpenApiDocument, located: LocatedOperation
) -> list[OpenApiStepGenerationWarning]:
    schemes = security_schemes(parsed)
    requirements = operation_security_requirements(located, parsed.document)
    warnings: list[OpenApiStepGenerationWarning] = []
    seen: set[tuple[str, str]] = set()
    for requirement in requirements:
        if not isinstance(requirement, dict):
            continue
        for name in requirement:
            if not isinstance(name, str):
                continue
            scheme = schemes.get(name)
            if not security_scheme_requires_credential_header(scheme):
                continue
            field = security_scheme_field(scheme)
            key = (name, field)
            if key in seen:
                continue
            seen.add(key)
            warnings.append(auth_warning(name, field))
    return warnings


def generate_drafts(
    *,
    spec: ApiCatalogSpec,
    parsed: ParsedOpenApiDocument,
    operation_refs: list[OpenApiOperationRef],
    insert: OpenApiStepInsertPlan,
) -> OpenApiStepDraftPreviewResponse:
    ensure_unique_refs(operation_refs)
    items: list[OpenApiGeneratedStepDraftItem] = []
    for index, ref in enumerate(operation_refs):
        located = locate_operation(parsed, ref, index)
        warnings: list[OpenApiStepGenerationWarning] = []
        path = path_with_placeholders(ref.path, warnings)
        query, headers, parameter_warnings = map_query_and_headers(parsed, located)
        body, body_warnings = map_body(parsed, located)
        warnings.extend(parameter_warnings)
        warnings.extend(security_warnings(parsed, located))
        warnings.extend(body_warnings)
        name = safe_text(located.operation.get("summary")) or safe_text(
            located.operation.get("operationId")
        )
        step = OpenApiGeneratedStepDraft(
            enabled=True,
            name=(name or f"{ref.method} {ref.path}")[:120],
            method=ref.method,
            path=path,
            query_params=query,
            headers=headers,
            body=body,
            settings=OpenApiGeneratedStepSettingsDraft(),
        )
        items.append(
            OpenApiGeneratedStepDraftItem(
                operation_ref=ref,
                step=step,
                source=OpenApiGeneratedStepSource(
                    operation_id=safe_text(located.operation.get("operationId"), max_length=160),
                    summary=safe_text(located.operation.get("summary")),
                ),
                warnings=warnings,
            )
        )
    return OpenApiStepDraftPreviewResponse(
        spec=spec_source_summary(spec), items=items, insert=insert, warnings=[]
    )


def operations_response(
    spec: ApiCatalogSpec, parsed: ParsedOpenApiDocument
) -> OpenApiOperationListResponse:
    items, warnings = enumerate_operations(parsed)
    return OpenApiOperationListResponse(
        spec=spec_source_summary(spec), items=items, warnings=warnings
    )


def get_authorized_spec(db: Session, *, workspace_id: str, spec_id: str) -> ApiCatalogSpec:
    return get_api_catalog_spec(db, workspace_id=workspace_id, spec_id=spec_id)
