#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping
from dataclasses import dataclass
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import re
import sys
from typing import Any
import uuid
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from jsonschema import Draft202012Validator


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT_PATH = PACKAGE_ROOT / "references/public-api.openapi.json"
DEFAULT_TIMEOUT_SECONDS = 30

ALLOWED_OPERATION_IDS = frozenset(
    {
        "publicCopyEnvGroup",
        "publicCreateEnvGroup",
        "publicCreateRun",
        "publicCreateScenario",
        "publicCreateTestPlan",
        "publicDeleteEnvGroup",
        "publicDeleteScenario",
        "publicDeleteTestPlan",
        "publicGetRun",
        "publicGetRunReport",
        "publicGetScenario",
        "publicGetTestPlan",
        "publicListLoadNodes",
        "publicListDependencyFiles",
        "publicUploadDependencyFile",
        "publicDeleteDependencyFile",
        "publicListRuns",
        "publicListScenarios",
        "publicListTestPlans",
        "publicPatchEnvGroup",
        "publicPatchScenario",
        "publicPatchTestPlan",
        "publicStopRun",
    }
)

FORBIDDEN_FIELD_NAMES = frozenset(
    {
        "authorization",
        "displayvalue",
        "hasvalue",
        "objectkey",
        "plaintext",
        "runnertoken",
        "secrethash",
        "serverpath",
    }
)
HTTP_METHODS = frozenset({"delete", "get", "patch", "post", "put"})
PATH_PARAMETER_PATTERN = re.compile(r"\{([^{}]+)\}")


class LocalInputError(ValueError):
    """The local invocation is incomplete or does not match the public contract."""


class ContractSafetyError(RuntimeError):
    """The bundled contract or payload violates the governed public boundary."""


class PublicApiError(RuntimeError):
    def __init__(
        self,
        *,
        status: int,
        code: str,
        message: str,
        details: Any = None,
    ) -> None:
        super().__init__(f"{status} {code}: {message}")
        self.status = status
        self.code = code
        self.message = message
        self.details = details


class NetworkRequestError(RuntimeError):
    """The single public API request failed before receiving a response."""


@dataclass(frozen=True)
class PreparedFileUpload:
    path: Path
    filename: str
    content_type: str
    size_bytes: int
    sha256: str


@dataclass(frozen=True)
class PreparedRequest:
    operation_id: str
    method: str
    url: str
    headers: dict[str, str]
    body: bytes | None
    workspace_id: str
    path_params: dict[str, Any]
    query_params: dict[str, Any]
    body_value: Any
    file_upload: PreparedFileUpload | None
    response_schemas: dict[int, dict[str, Any] | None]
    contract: dict[str, Any]


class _FailClosedRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, *_args: Any, **_kwargs: Any) -> None:
        return None


def _open_without_redirects(request: Request, *, timeout: int) -> Any:
    return build_opener(_FailClosedRedirectHandler()).open(request, timeout=timeout)


def _operation_index(document: dict[str, Any]) -> dict[str, tuple[str, str, dict[str, Any]]]:
    operations: dict[str, tuple[str, str, dict[str, Any]]] = {}
    for path, path_item in document.get("paths", {}).items():
        if not isinstance(path, str) or not path.startswith("/public/v1/"):
            raise ContractSafetyError(f"non-public path in bundled contract: {path}")
        if not isinstance(path_item, dict):
            raise ContractSafetyError(f"invalid path item for {path}")
        for method, operation in path_item.items():
            if method.lower() not in HTTP_METHODS or not isinstance(operation, dict):
                continue
            operation_id = operation.get("operationId")
            if not isinstance(operation_id, str) or not operation_id:
                raise ContractSafetyError(f"missing operationId for {method.upper()} {path}")
            if operation_id in operations:
                raise ContractSafetyError(
                    f"duplicate operationId in bundled contract: {operation_id}"
                )
            operations[operation_id] = (method.upper(), path, operation)
    return operations


def load_contract(path: Path = DEFAULT_CONTRACT_PATH) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise ContractSafetyError(f"unable to load bundled public OpenAPI: {error}") from error

    if document.get("servers") != [{"url": "/api"}]:
        raise ContractSafetyError("bundled public OpenAPI must use the fixed /api server base")
    security_schemes = document.get("components", {}).get("securitySchemes", {})
    if security_schemes.get("HTTPBearer") != {"scheme": "bearer", "type": "http"}:
        raise ContractSafetyError("bundled public OpenAPI must use HTTP Bearer authentication")

    operations = _operation_index(document)
    operation_ids = frozenset(operations)
    if operation_ids != ALLOWED_OPERATION_IDS:
        missing = sorted(ALLOWED_OPERATION_IDS - operation_ids)
        unexpected = sorted(operation_ids - ALLOWED_OPERATION_IDS)
        raise ContractSafetyError(
            f"public operation allowlist drift; missing={missing}, unexpected={unexpected}"
        )
    return document


def _validate_origin(base_url: str) -> str:
    value = base_url.strip()
    if not value:
        raise LocalInputError("SURGEPILOT_PUBLIC_API_BASE is required")
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise LocalInputError("SURGEPILOT_PUBLIC_API_BASE must be an absolute http(s) origin")
    if parsed.username is not None or parsed.password is not None:
        raise LocalInputError("SURGEPILOT_PUBLIC_API_BASE must not contain credentials")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise LocalInputError(
            "SURGEPILOT_PUBLIC_API_BASE must be an origin without path/query/fragment"
        )
    return f"{parsed.scheme}://{parsed.netloc}"


def _require_non_empty(value: str, environment_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise LocalInputError(f"{environment_name} is required")
    return normalized


def _schema_root(schema: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "allOf": [schema],
        "components": contract.get("components", {}),
    }


def _validate_schema(
    value: Any,
    schema: dict[str, Any],
    contract: dict[str, Any],
    label: str,
) -> None:
    validator = Draft202012Validator(_schema_root(schema, contract))
    error = next(iter(validator.iter_errors(value)), None)
    if error is not None:
        raise LocalInputError(f"{label} is invalid: {error.message}")


def _find_forbidden_field(value: Any, path: str = "$") -> tuple[str, str] | None:
    if isinstance(value, dict):
        if value.get("type") == "secret":
            return path, "type=secret"
        for key, child in value.items():
            key_text = str(key)
            if key_text.casefold() in FORBIDDEN_FIELD_NAMES:
                return f"{path}.*", key_text
            match = _find_forbidden_field(child, f"{path}.*")
            if match is not None:
                return match
    elif isinstance(value, list):
        for index, child in enumerate(value):
            match = _find_forbidden_field(child, f"{path}[{index}]")
            if match is not None:
                return match
    return None


def _find_credential_value(
    value: Any,
    *,
    token: str,
    path: str = "$",
) -> str | None:
    if isinstance(value, str):
        if token and token in value:
            return path
        if "surgepilot_pat_" in value.casefold():
            return path
    elif isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            if (token and token in key_text) or "surgepilot_pat_" in key_text.casefold():
                return f"{path}.*"
            match = _find_credential_value(child, token=token, path=f"{path}.*")
            if match is not None:
                return match
    elif isinstance(value, list):
        for index, child in enumerate(value):
            match = _find_credential_value(child, token=token, path=f"{path}[{index}]")
            if match is not None:
                return match
    return None


def _assert_safe_payload(value: Any, *, token: str) -> None:
    match = _find_forbidden_field(value)
    if match is not None:
        path, field = match
        if field == "type=secret":
            raise ContractSafetyError(f"secret-bearing public payload is forbidden at {path}")
        raise ContractSafetyError(f"forbidden public field {field} at {path}")
    credential_path = _find_credential_value(value, token=token)
    if credential_path is not None:
        raise ContractSafetyError(f"credential-like value is forbidden at {credential_path}")


def _parameters_by_location(
    operation: dict[str, Any],
    location: str,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for parameter in operation.get("parameters", []):
        if not isinstance(parameter, dict):
            continue
        parameter_location = parameter.get("in")
        name = parameter.get("name")
        if parameter_location == "header":
            if name != "x-workspace-id":
                raise ContractSafetyError(f"unexpected public header parameter: {name}")
            continue
        if parameter_location == location and isinstance(name, str):
            result[name] = parameter
    return result


def _validate_parameter_group(
    *,
    values: Mapping[str, Any],
    parameters: dict[str, dict[str, Any]],
    location: str,
    contract: dict[str, Any],
) -> None:
    unknown = sorted(set(values) - set(parameters))
    if unknown:
        raise LocalInputError(f"unknown {location} parameter: {unknown[0]}")
    for name, parameter in parameters.items():
        if parameter.get("required") and name not in values:
            raise LocalInputError(f"required {location} parameter {name} is missing")
        if name in values:
            _validate_schema(
                values[name],
                parameter.get("schema", {}),
                contract,
                f"{location} parameter {name}",
            )


def _encode_path(path_template: str, path_params: Mapping[str, Any]) -> str:
    path = path_template
    for name in PATH_PARAMETER_PATTERN.findall(path_template):
        if name not in path_params:
            raise LocalInputError(f"required path parameter {name} is missing")
        path = path.replace(f"{{{name}}}", quote(str(path_params[name]), safe=""))
    if PATH_PARAMETER_PATTERN.search(path):
        raise LocalInputError("not all path parameters were resolved")
    return path


def _encode_query(
    query_params: Mapping[str, Any],
    parameters: dict[str, dict[str, Any]],
) -> str:
    pairs: list[tuple[str, Any]] = []
    for name in parameters:
        if name not in query_params or query_params[name] is None:
            continue
        value = query_params[name]
        if isinstance(value, list):
            pairs.extend((name, item) for item in value)
        else:
            pairs.append((name, value))
    return urlencode(pairs)


def _prepare_file_upload(path: Path) -> PreparedFileUpload:
    if not path.is_file():
        raise LocalInputError(f"--file must reference an existing regular file: {path}")
    filename = path.name
    if not filename or any(character in filename for character in ("\r", "\n", '"')):
        raise LocalInputError("--file filename contains unsupported characters")
    digest = hashlib.sha256()
    size_bytes = 0
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                size_bytes += len(chunk)
                digest.update(chunk)
    except OSError as error:
        raise LocalInputError(f"unable to read --file: {error}") from error
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return PreparedFileUpload(
        path=path,
        filename=filename,
        content_type=content_type,
        size_bytes=size_bytes,
        sha256=digest.hexdigest(),
    )


def _resolve_component_schema(schema: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    reference = schema.get("$ref")
    if not isinstance(reference, str):
        return schema
    prefix = "#/components/schemas/"
    if not reference.startswith(prefix):
        raise ContractSafetyError("public upload contract contains an unsupported schema reference")
    name = reference.removeprefix(prefix)
    resolved = contract.get("components", {}).get("schemas", {}).get(name)
    if not isinstance(resolved, dict):
        raise ContractSafetyError("public upload contract references a missing schema")
    return resolved


def _validate_upload_contract(operation: dict[str, Any], contract: dict[str, Any]) -> None:
    content = operation.get("requestBody", {}).get("content", {})
    schema = content.get("multipart/form-data", {}).get("schema")
    if not isinstance(schema, dict):
        raise ContractSafetyError(
            "publicUploadDependencyFile must expose a multipart/form-data request schema"
        )
    schema = _resolve_component_schema(schema, contract)
    properties = schema.get("properties")
    file_schema = properties.get("file") if isinstance(properties, dict) else None
    if not isinstance(file_schema, dict):
        raise ContractSafetyError(
            "publicUploadDependencyFile multipart contract must contain one binary file field"
        )
    file_schema = _resolve_component_schema(file_schema, contract)
    binary_marker = (
        file_schema.get("format") == "binary"
        or file_schema.get("contentMediaType") == "application/octet-stream"
    )
    if (
        file_schema.get("type") != "string"
        or not binary_marker
        or "file" not in schema.get("required", [])
    ):
        raise ContractSafetyError(
            "publicUploadDependencyFile multipart contract must contain one binary file field"
        )


def _multipart_file_body(upload: PreparedFileUpload) -> tuple[bytes, str]:
    boundary = f"surgepilot-{uuid.uuid4().hex}"
    try:
        content = upload.path.read_bytes()
    except OSError as error:
        raise LocalInputError(f"unable to read --file: {error}") from error
    if len(content) != upload.size_bytes or hashlib.sha256(content).hexdigest() != upload.sha256:
        raise LocalInputError(
            "--file changed after confirmation preview; prepare the operation again"
        )
    prefix = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{upload.filename}"\r\n'
        f"Content-Type: {upload.content_type}\r\n\r\n"
    ).encode()
    suffix = f"\r\n--{boundary}--\r\n".encode()
    return prefix + content + suffix, f"multipart/form-data; boundary={boundary}"


def _response_schemas(operation: dict[str, Any]) -> dict[int, dict[str, Any] | None]:
    result: dict[int, dict[str, Any] | None] = {}
    for status_text, response in operation.get("responses", {}).items():
        if not isinstance(status_text, str) or not status_text.isdigit():
            continue
        if not isinstance(response, dict):
            raise ContractSafetyError(f"invalid response contract for status {status_text}")
        content = response.get("content")
        if not content:
            result[int(status_text)] = None
            continue
        schema = content.get("application/json", {}).get("schema")
        if not isinstance(schema, dict):
            raise ContractSafetyError(
                f"response status {status_text} must expose an application/json schema"
            )
        result[int(status_text)] = schema
    if not result:
        raise ContractSafetyError("public operation must declare response schemas")
    return result


def build_request(
    operation_id: str,
    *,
    base_url: str,
    token: str,
    workspace_id: str,
    path_params: Mapping[str, Any] | None = None,
    query_params: Mapping[str, Any] | None = None,
    body: Any = None,
    file_path: Path | None = None,
    contract: dict[str, Any] | None = None,
) -> PreparedRequest:
    if operation_id not in ALLOWED_OPERATION_IDS:
        raise LocalInputError(f"operationId is not allowlisted: {operation_id}")

    document = contract or load_contract()
    operations = _operation_index(document)
    if operation_id not in operations:
        raise ContractSafetyError(
            f"allowlisted operation missing from bundled contract: {operation_id}"
        )
    method, path_template, operation = operations[operation_id]

    origin = _validate_origin(base_url)
    bearer_token = _require_non_empty(token, "SURGEPILOT_PAT")
    explicit_workspace_id = _require_non_empty(workspace_id, "SURGEPILOT_WORKSPACE_ID")
    provided_path = dict(path_params or {})
    provided_query = dict(query_params or {})

    path_parameters = _parameters_by_location(operation, "path")
    query_parameters = _parameters_by_location(operation, "query")
    _validate_parameter_group(
        values=provided_path,
        parameters=path_parameters,
        location="path",
        contract=document,
    )
    _validate_parameter_group(
        values=provided_query,
        parameters=query_parameters,
        location="query",
        contract=document,
    )

    request_body = operation.get("requestBody")
    body_bytes: bytes | None = None
    file_upload: PreparedFileUpload | None = None
    if operation_id == "publicUploadDependencyFile":
        if body is not None:
            raise LocalInputError("publicUploadDependencyFile accepts --file, not --body-json")
        if file_path is None:
            raise LocalInputError("--file is required for publicUploadDependencyFile")
        _validate_upload_contract(operation, document)
        file_upload = _prepare_file_upload(file_path)
    elif file_path is not None:
        raise LocalInputError("--file is supported only for publicUploadDependencyFile")

    if request_body is None:
        if body is not None or file_upload is not None:
            raise LocalInputError(f"{operation_id} does not accept a request body")
    elif file_upload is None:
        if request_body.get("required") and body is None:
            raise LocalInputError(f"request body is required for {operation_id}")
        if body is not None:
            content = request_body.get("content", {})
            schema = content.get("application/json", {}).get("schema")
            if not isinstance(schema, dict):
                raise ContractSafetyError(
                    f"{operation_id} does not expose an application/json request schema"
                )
            _assert_safe_payload(body, token=bearer_token)
            _validate_schema(body, schema, document, "request body")
            body_bytes = json.dumps(body, separators=(",", ":")).encode()

    encoded_path = _encode_path(path_template, provided_path)
    query_string = _encode_query(provided_query, query_parameters)
    server_base = document["servers"][0]["url"]
    url = f"{origin}{server_base}{encoded_path}"
    if query_string:
        url = f"{url}?{query_string}"

    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {bearer_token}",
        "x-workspace-id": explicit_workspace_id,
    }
    if body_bytes is not None:
        headers["Content-Type"] = "application/json"

    return PreparedRequest(
        operation_id=operation_id,
        method=method,
        url=url,
        headers=headers,
        body=body_bytes,
        workspace_id=explicit_workspace_id,
        path_params=provided_path,
        query_params=provided_query,
        body_value=body,
        file_upload=file_upload,
        response_schemas=_response_schemas(operation),
        contract=document,
    )


def _summarize_value(key: str, value: Any) -> Any:
    key_folded = key.casefold()
    if key_folded in FORBIDDEN_FIELD_NAMES or key_folded in {"body", "rawtext"}:
        return "[REDACTED]"
    if key_folded in {"variables", "headers", "globalheaders"}:
        if isinstance(value, dict):
            return {"keys": sorted(str(item) for item in value)}
        if isinstance(value, list):
            return {"count": len(value)}
        return "[REDACTED]"
    if isinstance(value, dict):
        return {"keys": sorted(str(item) for item in value)}
    if isinstance(value, list):
        return {"count": len(value)}
    return value


def _target_resource(request: PreparedRequest) -> str:
    if request.file_upload is not None:
        return request.file_upload.filename
    for value in request.path_params.values():
        return str(value)
    if isinstance(request.body_value, dict):
        for key in ("name", "displayName", "sourceId", "scenarioId", "testPlanId"):
            value = request.body_value.get(key)
            if isinstance(value, str) and value:
                return value
    return request.url.split("?", 1)[0]


def summarize_confirmation(request: PreparedRequest) -> dict[str, Any]:
    key_parameters: dict[str, Any] = {}
    for key, value in request.path_params.items():
        key_parameters[key] = _summarize_value(key, value)
    for key, value in request.query_params.items():
        key_parameters[key] = _summarize_value(key, value)
    if isinstance(request.body_value, dict):
        for key, value in request.body_value.items():
            key_parameters[key] = _summarize_value(key, value)
    if request.file_upload is not None:
        key_parameters["file"] = {
            "filename": request.file_upload.filename,
            "sizeBytes": request.file_upload.size_bytes,
            "sha256": request.file_upload.sha256,
        }

    return {
        "confirmationRequired": request.method != "GET",
        "workspaceId": request.workspace_id,
        "operationId": request.operation_id,
        "method": request.method,
        "targetResource": _target_resource(request),
        "keyParameters": key_parameters,
    }


def _decode_json(payload: bytes) -> Any:
    if not payload:
        return None
    try:
        return json.loads(payload)
    except json.JSONDecodeError as error:
        raise ContractSafetyError("public API returned a non-JSON response") from error


def _assert_safe_response(value: Any, *, token: str) -> None:
    match = _find_forbidden_field(value)
    if match is not None:
        path, field = match
        raise ContractSafetyError(f"forbidden public response field {field} at {path}")
    credential_path = _find_credential_value(value, token=token)
    if credential_path is not None:
        raise ContractSafetyError(f"credential-like value in public response at {credential_path}")


def _validate_response_contract(
    request: PreparedRequest,
    *,
    status: int,
    data: Any,
) -> None:
    if status not in request.response_schemas:
        raise ContractSafetyError(
            f"public API returned undeclared status {status} for {request.operation_id}"
        )
    schema = request.response_schemas[status]
    if schema is None:
        if data is not None:
            raise ContractSafetyError(
                f"public API response status {status} must not contain a JSON body"
            )
        return
    validator = Draft202012Validator(_schema_root(schema, request.contract))
    if next(iter(validator.iter_errors(data)), None) is not None:
        raise ContractSafetyError(
            f"public API response does not match status {status} schema for {request.operation_id}"
        )


def execute_request(
    request: PreparedRequest,
    *,
    opener: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    headers = dict(request.headers)
    body = request.body
    if request.file_upload is not None:
        body, content_type = _multipart_file_body(request.file_upload)
        headers["Content-Type"] = content_type
    http_request = Request(
        request.url,
        data=body,
        headers=headers,
        method=request.method,
    )
    actual_opener = _open_without_redirects if opener is None else opener
    token = request.headers["Authorization"].removeprefix("Bearer ").strip()
    try:
        with actual_opener(http_request, timeout=DEFAULT_TIMEOUT_SECONDS) as response:
            status = int(getattr(response, "status", 200))
            data = _decode_json(response.read())
    except HTTPError as error:
        payload = _decode_json(error.read())
        _assert_safe_response(payload, token=token)
        _validate_response_contract(request, status=error.code, data=payload)
        if isinstance(payload, dict):
            code = payload.get("code")
            message = payload.get("message")
            details = payload.get("details")
        else:
            code = None
            message = None
            details = None
        raise PublicApiError(
            status=error.code,
            code=code if isinstance(code, str) else "PUBLIC_API_ERROR",
            message=message if isinstance(message, str) else "Public API request failed.",
            details=details,
        ) from None
    except (URLError, OSError) as error:
        raise NetworkRequestError("public API request failed without retry or fallback") from error

    _assert_safe_response(data, token=token)
    _validate_response_contract(request, status=status, data=data)
    return {"status": status, "data": data}


def _json_object(value: str, label: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as error:
        raise LocalInputError(f"{label} must be valid JSON: {error.msg}") from error
    if not isinstance(parsed, dict):
        raise LocalInputError(f"{label} must be a JSON object")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Call an allowlisted SurgePilot public API operation by operationId."
    )
    parser.add_argument("operation_id", choices=sorted(ALLOWED_OPERATION_IDS))
    parser.add_argument("--path-json", default="{}", help="JSON object of path parameters")
    parser.add_argument("--query-json", default="{}", help="JSON object of query parameters")
    parser.add_argument("--body-json", help="JSON object request body")
    parser.add_argument(
        "--file",
        type=Path,
        help="Dependency File path; supported only by publicUploadDependencyFile",
    )
    parser.add_argument(
        "--expected-file-sha256",
        help="SHA256 shown in the confirmed upload plan; required with --confirm for file upload",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Execute a non-GET operation after explicit user confirmation",
    )
    return parser


def _print_json(value: Any, *, stream: Any = None) -> None:
    print(
        json.dumps(value, indent=2, sort_keys=True), file=sys.stdout if stream is None else stream
    )


def run_cli(
    argv: list[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    opener: Callable[..., Any] | None = None,
) -> int:
    args = build_parser().parse_args(argv)
    environment = os.environ if environ is None else environ
    try:
        path_params = _json_object(args.path_json, "--path-json")
        query_params = _json_object(args.query_json, "--query-json")
        body = None if args.body_json is None else _json_object(args.body_json, "--body-json")
        prepared = build_request(
            args.operation_id,
            base_url=environment.get("SURGEPILOT_PUBLIC_API_BASE", ""),
            token=environment.get("SURGEPILOT_PAT", ""),
            workspace_id=environment.get("SURGEPILOT_WORKSPACE_ID", ""),
            path_params=path_params,
            query_params=query_params,
            body=body,
            file_path=args.file,
        )
        if prepared.file_upload is None and args.expected_file_sha256 is not None:
            raise LocalInputError(
                "--expected-file-sha256 is supported only for publicUploadDependencyFile"
            )
        if prepared.file_upload is not None and args.confirm:
            expected_sha256 = (args.expected_file_sha256 or "").strip().lower()
            if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
                raise LocalInputError(
                    "--expected-file-sha256 is required with --confirm for file upload"
                )
            if expected_sha256 != prepared.file_upload.sha256:
                raise LocalInputError(
                    "--file SHA256 changed after confirmation preview; prepare and confirm the upload again"
                )
        if prepared.method != "GET" and not args.confirm:
            _print_json(summarize_confirmation(prepared))
            return 2
        result = execute_request(prepared, opener=opener)
        _print_json(result)
        return 0
    except LocalInputError as error:
        _print_json({"error": "LOCAL_INPUT_ERROR", "message": str(error)}, stream=sys.stderr)
        return 2
    except PublicApiError as error:
        _print_json(
            {
                "error": error.code,
                "status": error.status,
                "message": error.message,
                "details": error.details,
            },
            stream=sys.stderr,
        )
        return 3
    except NetworkRequestError as error:
        _print_json({"error": "NETWORK_ERROR", "message": str(error)}, stream=sys.stderr)
        return 3
    except ContractSafetyError as error:
        _print_json({"error": "CONTRACT_SAFETY_ERROR", "message": str(error)}, stream=sys.stderr)
        return 4


def main() -> None:
    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
