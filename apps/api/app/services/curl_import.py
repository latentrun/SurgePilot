from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
import shlex
from urllib.parse import parse_qsl, urlparse

from pydantic import ValidationError

from app.core.errors import AppError
from app.core.ids import new_ulid
from app.schemas.scenarios import (
    CurlImportBodyDraft,
    CurlImportNamedValueDraft,
    CurlImportParseResponse,
    CurlImportStepDraft,
    CurlImportStepSettingsDraft,
    CurlImportUnsupportedOption,
    CurlImportWarning,
)
from app.services.scenarios import HTTP_TOKEN_PATTERN, validate_scenario_content

SUPPORTED_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
RAW_CURL_MAX_LENGTH = 300_000
SHELL_OPERATOR_TOKENS = {"|", ">", ">>", "<", "<<", ";", "&&", "||"}
SENSITIVE_NAME_PATTERN = re.compile(
    r"(authorization|cookie|set-cookie|api-key|token|password|secret|key)", re.I
)
JSON_CONTENT_TYPE_PREFIX = "application/json"
FORM_CONTENT_TYPE = "application/x-www-form-urlencoded"


@dataclass
class WarningCollector:
    warnings: list[CurlImportWarning] = field(default_factory=list)

    def add(self, code: str, message: str, field: str | None = None) -> None:
        if any(item.code == code and item.field == field for item in self.warnings):
            return
        self.warnings.append(CurlImportWarning(code=code, message=message, field=field))


@dataclass
class ParseState:
    url_values: list[str] = field(default_factory=list)
    method: str | None = None
    method_explicit: bool = False
    headers: list[dict[str, str | bool]] = field(default_factory=list)
    data_values: list[tuple[str, str]] = field(default_factory=list)
    data_urlencode_values: list[str] = field(default_factory=list)
    use_get: bool = False
    follow_redirects: bool | None = None
    timeout_ms: int | None = None
    unsupported: list[CurlImportUnsupportedOption] = field(default_factory=list)
    warnings: WarningCollector = field(default_factory=WarningCollector)

    def unsupported_option(self, option: str, reason_code: str, message: str) -> None:
        if any(
            item.option == option and item.reason_code == reason_code for item in self.unsupported
        ):
            return
        self.unsupported.append(
            CurlImportUnsupportedOption(option=option, reason_code=reason_code, message=message)
        )


def _field_error(field: str, message: str, code: str = "invalid_field") -> dict[str, str]:
    return {"field": field, "code": code, "message": message}


def _validation_error(field: str, message: str, code: str = "invalid_field") -> AppError:
    return AppError(
        "VALIDATION_ERROR", "Validation failed.", 422, [_field_error(field, message, code)]
    )


def _preview_limit_error() -> AppError:
    return _validation_error(
        "rawCurl",
        "Imported Step preview exceeds Scenario limits.",
        "scenario_limit_exceeded",
    )


def _named_value_draft(item: dict[str, str | bool]) -> CurlImportNamedValueDraft:
    try:
        return CurlImportNamedValueDraft(**item)
    except ValidationError as exc:
        raise _preview_limit_error() from exc


def _normalize(raw_curl: str) -> str:
    if len(raw_curl) > RAW_CURL_MAX_LENGTH:
        raise _validation_error("rawCurl", "cURL command is too long.", "too_long")
    normalized = raw_curl.replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"\\[ \t]*\n", " ", normalized)
    if not normalized.strip():
        raise _validation_error("rawCurl", "cURL command is required.", "required_field")
    return normalized


def _tokenize(raw_curl: str) -> list[str]:
    try:
        tokens = shlex.split(raw_curl, comments=True, posix=True)
    except ValueError as exc:
        raise _validation_error(
            "rawCurl", "Unable to parse cURL shell syntax.", "invalid_shell"
        ) from exc
    if not tokens:
        raise _validation_error("rawCurl", "cURL command is required.", "required_field")
    lowered = tokens[0].lower()
    if lowered == "curl":
        tokens = tokens[1:]
    elif lowered.endswith("/curl"):
        tokens = tokens[1:]
    for token in tokens:
        if token in SHELL_OPERATOR_TOKENS or "$(" in token or "`" in token:
            raise _validation_error(
                "rawCurl", "Shell operators are not supported.", "unsupported_shell"
            )
    return tokens


def _split_long_option(token: str) -> tuple[str, str | None]:
    if token.startswith("--") and "=" in token:
        option, value = token.split("=", 1)
        return option, value
    return token, None


def _next_value(tokens: list[str], index: int, option: str, inline: str | None) -> tuple[str, int]:
    if inline is not None:
        return inline, index
    if index + 1 >= len(tokens):
        raise _validation_error("rawCurl", f"{option} requires a value.", "missing_option_value")
    return tokens[index + 1], index + 1


def _add_header(state: ParseState, raw_header: str, *, option: str = "-H") -> None:
    if ":" not in raw_header:
        raise _validation_error(
            "headers[0].name", "Header must use Name: value syntax.", "invalid_header"
        )
    name, value = raw_header.split(":", 1)
    name = name.strip()
    if not name or not HTTP_TOKEN_PATTERN.fullmatch(name):
        raise _validation_error("headers[0].name", "Header name is invalid.", "invalid_header_name")
    state.headers.append({"name": name, "value": value.lstrip(), "enabled": True})
    if SENSITIVE_NAME_PATTERN.search(name):
        state.warnings.add(
            "SENSITIVE_HEADER_PRESENT",
            "A sensitive header may be saved into the Scenario if you confirm and save.",
            f"headers[{len(state.headers) - 1}].name",
        )


def _looks_like_cookie_text(value: str) -> bool:
    return "=" in value or ";" in value


def _is_local_reference(value: str) -> bool:
    return value.startswith("@") or value.startswith("<")


def _local_file_warning(state: ParseState) -> None:
    state.warnings.add(
        "LOCAL_FILE_REFERENCE_UNSUPPORTED",
        "Local file references are not read or imported in this preview.",
        None,
    )


def _parse_timeout_ms(value: str) -> int:
    try:
        seconds = float(value)
    except ValueError as exc:
        raise _validation_error(
            "settings.timeoutMs", "Timeout must be a number of seconds."
        ) from exc
    milliseconds = round(seconds * 1000)
    if milliseconds < 100 or milliseconds > 300_000:
        raise _validation_error(
            "settings.timeoutMs", "Timeout must be between 0.1 and 300 seconds.", "out_of_range"
        )
    return milliseconds


def _parse_tokens(tokens: list[str], raw_curl: str) -> ParseState:
    state = ParseState()
    if "^" in raw_curl:
        state.warnings.add(
            "WINDOWS_CARET_CONTINUATION_UNSUPPORTED",
            "Windows caret line continuation may not be fully interpreted.",
        )
    index = 0
    while index < len(tokens):
        token = tokens[index]
        option, inline = _split_long_option(token)
        if option in {"--url"}:
            value, index = _next_value(tokens, index, option, inline)
            state.url_values.append(value)
        elif option in {"-X", "--request"}:
            value, index = _next_value(tokens, index, option, inline)
            method = value.upper()
            if method not in SUPPORTED_METHODS:
                raise _validation_error(
                    "method", "HTTP method is not supported.", "unsupported_method"
                )
            state.method = method
            state.method_explicit = True
        elif option in {"-H", "--header"}:
            value, index = _next_value(tokens, index, option, inline)
            _add_header(state, value, option=option)
        elif option in {"-A", "--user-agent"}:
            value, index = _next_value(tokens, index, option, inline)
            _add_header(state, f"User-Agent: {value}", option=option)
        elif option in {"-b", "--cookie"}:
            value, index = _next_value(tokens, index, option, inline)
            if _looks_like_cookie_text(value) and not _is_local_reference(value):
                _add_header(state, f"Cookie: {value}", option=option)
            else:
                state.unsupported_option(
                    option, "local_file_reference", "Cookie jar files are not imported."
                )
                _local_file_warning(state)
        elif option in {"-I", "--head"}:
            state.method = "HEAD"
            state.method_explicit = True
        elif option in {"--data", "--data-raw", "--data-binary", "-d"}:
            value, index = _next_value(tokens, index, option, inline)
            if _is_local_reference(value):
                state.unsupported_option(
                    option, "local_file_reference", "Local file bodies are not imported."
                )
                _local_file_warning(state)
            else:
                state.data_values.append((option, value))
        elif option == "--data-urlencode":
            value, index = _next_value(tokens, index, option, inline)
            if _is_local_reference(value):
                state.unsupported_option(
                    option, "local_file_reference", "Local file bodies are not imported."
                )
                _local_file_warning(state)
            else:
                state.data_urlencode_values.append(value)
        elif option in {"-G", "--get"}:
            state.use_get = True
        elif option in {"-L", "--location"}:
            state.follow_redirects = True
        elif option == "--max-time":
            value, index = _next_value(tokens, index, option, inline)
            state.timeout_ms = _parse_timeout_ms(value)
        elif option in {"-F", "--form", "--form-string", "--upload-file"}:
            value, index = _next_value(tokens, index, option, inline)
            state.unsupported_option(
                option, "multipart_unsupported", "Multipart and upload options are not imported."
            )
            if "@" in value:
                _local_file_warning(state)
        elif option.startswith("-"):
            # Consume a likely value for known value-taking unsupported options, without echoing it.
            value_taking = {
                "--connect-timeout",
                "--user",
                "-u",
                "--cacert",
                "--cert",
                "-E",
                "--key",
                "--retry",
                "--cookie-jar",
                "--proxy",
                "-x",
                "--config",
                "-K",
            }
            if option in value_taking and inline is None and index + 1 < len(tokens):
                index += 1
            state.unsupported_option(
                option, "unsupported_option", "This cURL option was not imported."
            )
            state.warnings.add(
                "UNSUPPORTED_OPTION_IGNORED",
                "One or more cURL options were not imported into the Step preview.",
            )
        else:
            state.url_values.append(token)
        index += 1
    return state


def _parse_url(values: list[str]) -> tuple[str, str, list[dict[str, str | bool]]]:
    if not values:
        raise _validation_error("url", "Exactly one HTTP or HTTPS URL is required.", "missing_url")
    if len(values) > 1:
        raise _validation_error("url", "Only one URL can be imported at a time.", "multiple_urls")
    parsed = urlparse(values[0])
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise _validation_error(
            "url", "Only HTTP and HTTPS URLs can be imported.", "unsupported_url"
        )
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    path = parsed.path or "/"
    query_params = [
        {"name": name, "value": value, "enabled": True}
        for name, value in parse_qsl(parsed.query, keep_blank_values=True)
    ]
    return base_url, path, query_params


def _content_type(headers: list[dict[str, str | bool]]) -> str | None:
    for header in headers:
        if str(header["name"]).lower() == "content-type":
            return str(header["value"]).split(";", 1)[0].strip().lower()
    return None


def _form_fields_from_text(value: str) -> list[dict[str, str | bool]] | None:
    if "=" not in value:
        return None
    pairs = parse_qsl(value, keep_blank_values=True)
    if not pairs:
        return None
    names: set[str] = set()
    fields: list[dict[str, str | bool]] = []
    for name, field_value in pairs:
        if not name or name in names:
            return None
        names.add(name)
        fields.append({"name": name, "value": field_value, "enabled": True})
    return fields


def _body_from_state(state: ParseState) -> CurlImportBodyDraft:
    data_chunks = [value for _, value in state.data_values]
    if state.data_urlencode_values and not state.use_get:
        data_chunks.extend(state.data_urlencode_values)
    if not data_chunks:
        return CurlImportBodyDraft()
    body_text = "&".join(data_chunks)
    if len(body_text) > 262_144:
        raise _validation_error("body.rawText", "Request body is too large.", "too_long")
    content_type = _content_type(state.headers)
    form_fields = _form_fields_from_text(body_text)
    if form_fields is not None and (content_type in {None, FORM_CONTENT_TYPE}):
        _add_sensitive_body_warnings(state, form_fields)
        try:
            return CurlImportBodyDraft(
                type="form", content_type=FORM_CONTENT_TYPE, raw_text=None, form_fields=form_fields
            )
        except ValidationError as exc:
            raise _preview_limit_error() from exc
    inferred_content_type = content_type
    stripped = body_text.strip()
    if inferred_content_type is None and (
        (stripped.startswith("{") and stripped.endswith("}"))
        or (stripped.startswith("[") and stripped.endswith("]"))
    ):
        inferred_content_type = JSON_CONTENT_TYPE_PREFIX
    _add_json_sensitive_warnings(state, body_text)
    return CurlImportBodyDraft(
        type="raw",
        content_type=inferred_content_type,
        raw_text=body_text,
        form_fields=[],
    )


def _data_urlencode_query_params(values: list[str]) -> list[dict[str, str | bool]]:
    params: list[dict[str, str | bool]] = []
    for value in values:
        if "=" in value:
            name, field_value = value.split("=", 1)
            params.append({"name": name, "value": field_value, "enabled": True})
        else:
            # Keep a safe field name and preserve value when curl syntax cannot infer a pair.
            params.append({"name": value, "value": "", "enabled": True})
    return params


def _add_sensitive_body_warnings(state: ParseState, fields: list[dict[str, str | bool]]) -> None:
    for index, item in enumerate(fields):
        if SENSITIVE_NAME_PATTERN.search(str(item["name"])):
            state.warnings.add(
                "SENSITIVE_BODY_FIELD_PRESENT",
                "A sensitive body field may be saved into the Scenario if you confirm and save.",
                f"body.formFields[{index}].name",
            )


def _add_json_sensitive_warnings(state: ParseState, raw_text: str) -> None:
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        return
    if isinstance(parsed, dict):
        for key in parsed:
            if SENSITIVE_NAME_PATTERN.search(str(key)):
                state.warnings.add(
                    "SENSITIVE_BODY_FIELD_PRESENT",
                    "A sensitive JSON field may be saved into the Scenario if you confirm and save.",
                    "body.rawText",
                )


def _validate_duplicate_headers(headers: list[dict[str, str | bool]]) -> None:
    seen: set[str] = set()
    details: list[dict[str, str]] = []
    for index, header in enumerate(headers):
        lower_name = str(header["name"]).lower()
        if lower_name in seen:
            details.append(
                _field_error(
                    f"headers[{index}].name",
                    "Header names must be unique within a Step.",
                    "duplicate_header",
                )
            )
        seen.add(lower_name)
    if details:
        raise AppError("VALIDATION_ERROR", "Validation failed.", 422, details)


def _temporary_scenario_step(step: CurlImportStepDraft) -> dict:
    dumped = step.model_dump(by_alias=True, mode="json")
    return {
        "id": new_ulid(),
        **dumped,
        "queryParams": [{**item, "id": new_ulid()} for item in dumped["queryParams"]],
        "headers": [{**item, "id": new_ulid()} for item in dumped["headers"]],
        "body": {
            **dumped["body"],
            "formFields": [
                {**item, "id": new_ulid()} for item in dumped["body"].get("formFields", [])
            ],
        },
        "uploadFiles": [],
        "extractors": [],
        "assertions": [],
        "scripts": [],
    }


def _validate_preview(step: CurlImportStepDraft) -> None:
    try:
        validate_scenario_content(
            {
                "name": "cURL import preview",
                "description": None,
                "tags": [],
                "baseUrlExpression": "${base_url}",
                "defaultSettings": {
                    "thinkTimeMs": 0,
                    "timeoutMs": 30000,
                    "followRedirects": True,
                    "keepAlive": True,
                    "storeCache": True,
                    "storeCookie": True,
                    "retrieveResources": False,
                },
                "dataSources": [],
                "steps": [_temporary_scenario_step(step)],
            }
        )
    except ValidationError as exc:
        raise _validation_error(
            "rawCurl",
            "Imported Step preview exceeds Scenario limits.",
            "scenario_limit_exceeded",
        ) from exc


def parse_curl_import(raw_curl: str) -> CurlImportParseResponse:
    normalized = _normalize(raw_curl)
    tokens = _tokenize(normalized)
    state = _parse_tokens(tokens, normalized)
    base_url, path, query_params = _parse_url(state.url_values)
    if state.use_get:
        query_params.extend(
            [
                {"name": name, "value": value, "enabled": True}
                for value in [chunk for _, chunk in state.data_values]
                for name, value in parse_qsl(value, keep_blank_values=True)
            ]
        )
        query_params.extend(_data_urlencode_query_params(state.data_urlencode_values))
        body = CurlImportBodyDraft()
    else:
        body = _body_from_state(state)
    method = state.method or "GET"
    if body.type != "none" and not state.method_explicit:
        method = "POST"
        state.warnings.add(
            "METHOD_INFERRED_FROM_BODY",
            "POST was inferred because the command includes a body.",
        )
    if method in {"GET", "HEAD"} and body.type != "none":
        raise _validation_error(
            "body.type", "GET and HEAD requests cannot have a body.", "body_not_allowed"
        )
    _validate_duplicate_headers(state.headers)
    step = CurlImportStepDraft(
        enabled=True,
        name=f"{method} {path}"[:120],
        method=method,
        path=path,
        query_params=[_named_value_draft(item) for item in query_params],
        headers=[_named_value_draft(item) for item in state.headers],
        body=body,
        settings=CurlImportStepSettingsDraft(
            timeout_ms=state.timeout_ms,
            follow_redirects=state.follow_redirects,
            keep_alive=None,
            think_time_ms=None,
        ),
    )
    _validate_preview(step)
    state.warnings.add(
        "BASE_URL_SUGGESTED",
        "A base URL suggestion is available and can be applied to Global Config.",
    )
    return CurlImportParseResponse(
        step=step,
        base_url_suggestion=base_url,
        warnings=state.warnings.warnings,
        unsupported_options=state.unsupported,
    )
