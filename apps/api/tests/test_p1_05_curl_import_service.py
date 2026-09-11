import pytest
from pydantic import BaseModel, Field, ValidationError

from app.core.errors import AppError
from app.services.curl_import import parse_curl_import


def test_parse_simple_get_url_splits_base_path_and_query() -> None:
    result = parse_curl_import("curl https://example.test/v1/orders?region=sg")

    assert result.base_url_suggestion == "https://example.test"
    assert result.step.method == "GET"
    assert result.step.path == "/v1/orders"
    assert [item.model_dump() for item in result.step.query_params] == [
        {"name": "region", "value": "sg", "enabled": True}
    ]
    assert result.step.body.type == "none"
    assert any(warning.code == "BASE_URL_SUGGESTED" for warning in result.warnings)


def test_parse_post_json_body_and_content_type_header() -> None:
    result = parse_curl_import(
        "curl -X POST -H 'Content-Type: application/json' "
        '--data \'{"sku":"A1"}\' https://example.test/v1/orders'
    )

    assert result.step.method == "POST"
    assert result.step.path == "/v1/orders"
    assert [item.model_dump() for item in result.step.headers] == [
        {"name": "Content-Type", "value": "application/json", "enabled": True}
    ]
    assert result.step.body.type == "raw"
    assert result.step.body.content_type == "application/json"
    assert result.step.body.raw_text == '{"sku":"A1"}'


def test_parse_data_infers_post_and_form_body() -> None:
    result = parse_curl_import("curl -d 'a=1&b=2' https://example.test/form")

    assert result.step.method == "POST"
    assert result.step.body.type == "form"
    assert result.step.body.content_type == "application/x-www-form-urlencoded"
    assert [item.model_dump() for item in result.step.body.form_fields] == [
        {"name": "a", "value": "1", "enabled": True},
        {"name": "b", "value": "2", "enabled": True},
    ]
    assert any(warning.code == "METHOD_INFERRED_FROM_BODY" for warning in result.warnings)


def test_parse_data_urlencode_get_moves_data_to_query() -> None:
    result = parse_curl_import(
        "curl --data-urlencode 'q=hello world' -G https://example.test/search"
    )

    assert result.step.method == "GET"
    assert result.step.path == "/search"
    assert [item.model_dump() for item in result.step.query_params] == [
        {"name": "q", "value": "hello world", "enabled": True}
    ]
    assert result.step.body.type == "none"


def test_sensitive_headers_emit_safe_warnings() -> None:
    result = parse_curl_import(
        "curl -H 'Authorization: Bearer token' -H 'x-api-key: key' https://example.test/secure"
    )

    warning_fields = {
        warning.field for warning in result.warnings if warning.code == "SENSITIVE_HEADER_PRESENT"
    }
    assert warning_fields == {"headers[0].name", "headers[1].name"}
    assert "Bearer token" not in {warning.message for warning in result.warnings}


def test_cookie_shorthand_accepts_browser_sized_cookie_value() -> None:
    cookie = "session=" + ("x" * 5_200)

    result = parse_curl_import(f"curl -b '{cookie}' https://example.test/secure")

    assert result.step.path == "/secure"
    assert [item.model_dump() for item in result.step.headers] == [
        {"name": "Cookie", "value": cookie, "enabled": True}
    ]
    assert any(warning.code == "SENSITIVE_HEADER_PRESENT" for warning in result.warnings)


def test_cookie_header_accepts_browser_sized_cookie_value() -> None:
    cookie = "session=" + ("x" * 5_200)

    result = parse_curl_import(f"curl -H 'Cookie: {cookie}' https://example.test/secure")

    assert [item.model_dump() for item in result.step.headers] == [
        {"name": "Cookie", "value": cookie, "enabled": True}
    ]
    assert any(warning.code == "SENSITIVE_HEADER_PRESENT" for warning in result.warnings)


def test_cookie_header_over_named_value_limit_returns_safe_validation_error() -> None:
    cookie = "session=" + ("x" * 65_537)

    with pytest.raises(AppError) as exc_info:
        parse_curl_import(f"curl -H 'Cookie: {cookie}' https://example.test/secure")

    assert exc_info.value.code == "VALIDATION_ERROR"
    assert exc_info.value.status_code == 422
    assert any(detail["field"] == "rawCurl" for detail in exc_info.value.details or [])
    assert "x" * 100 not in str(exc_info.value.details)


def test_form_field_over_named_value_limit_returns_safe_validation_error() -> None:
    form_value = "x" * 65_537

    with pytest.raises(AppError) as exc_info:
        parse_curl_import(f"curl -d 'token={form_value}' https://example.test/form")

    assert exc_info.value.code == "VALIDATION_ERROR"
    assert exc_info.value.status_code == 422
    assert exc_info.value.details == [
        {
            "field": "rawCurl",
            "code": "scenario_limit_exceeded",
            "message": "Imported Step preview exceeds Scenario limits.",
        }
    ]
    assert "x" * 100 not in str(exc_info.value.details)


def test_preview_validation_error_returns_safe_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class PreviewLimitProbe(BaseModel):
        value: int = Field(gt=0)

    try:
        PreviewLimitProbe(value=0)
    except ValidationError as exc:
        preview_validation_error = exc

    def fail_preview_validation(_content: dict) -> dict:
        raise preview_validation_error

    monkeypatch.setattr(
        "app.services.curl_import.validate_scenario_content",
        fail_preview_validation,
    )

    with pytest.raises(AppError) as exc_info:
        parse_curl_import("curl https://example.test/secure")

    assert exc_info.value.code == "VALIDATION_ERROR"
    assert exc_info.value.status_code == 422
    assert exc_info.value.details == [
        {
            "field": "rawCurl",
            "code": "scenario_limit_exceeded",
            "message": "Imported Step preview exceeds Scenario limits.",
        }
    ]
    assert "example.test" not in str(exc_info.value.details)


def test_duplicate_header_names_raise_validation_error() -> None:
    with pytest.raises(AppError) as exc_info:
        parse_curl_import("curl -H 'Accept: json' -H 'accept: text' https://example.test")

    assert exc_info.value.code == "VALIDATION_ERROR"
    assert {detail["code"] for detail in exc_info.value.details} == {"duplicate_header"}


def test_location_and_max_time_map_to_step_settings() -> None:
    result = parse_curl_import("curl --location --max-time 2.5 https://example.test/ping")

    assert result.step.settings.follow_redirects is True
    assert result.step.settings.timeout_ms == 2500
    assert result.step.settings.keep_alive is None
    assert result.step.settings.think_time_ms is None


def test_local_file_references_are_not_read_and_are_reported() -> None:
    result = parse_curl_import(
        "curl -F file=@local.png --data-binary @payload.json https://example.test/upload"
    )

    assert result.step.method == "GET"
    assert result.step.body.type == "none"
    assert {item.option for item in result.unsupported_options} == {"-F", "--data-binary"}
    assert any(warning.code == "LOCAL_FILE_REFERENCE_UNSUPPORTED" for warning in result.warnings)


@pytest.mark.parametrize(
    ("raw", "expected_field"),
    [
        ("curl", "url"),
        ("curl https://one.test https://two.test", "url"),
        ("curl ftp://example.test/file", "url"),
        ("curl -H 'broken' https://example.test", "headers[0].name"),
        ("curl --request TRACE https://example.test", "method"),
        ("curl --request GET --data 'a=1' https://example.test", "body.type"),
        ("curl 'https://example.test", "rawCurl"),
    ],
)
def test_invalid_commands_raise_safe_validation_errors(raw: str, expected_field: str) -> None:
    with pytest.raises(AppError) as exc_info:
        parse_curl_import(raw)

    assert exc_info.value.code == "VALIDATION_ERROR"
    assert any(detail["field"] == expected_field for detail in exc_info.value.details)
    assert "example.test" not in str(exc_info.value.details)


def test_body_over_scenario_limit_raises_safe_validation_error() -> None:
    body = "a" * 262_145

    with pytest.raises(AppError) as exc_info:
        parse_curl_import("curl --data '" + body + "' https://example.test/large")

    assert exc_info.value.code == "VALIDATION_ERROR"
    assert "a" * 100 not in str(exc_info.value.details)


def test_large_command_with_body_under_scenario_limit_is_accepted() -> None:
    body = "a" * 262_000
    raw = "curl --data '" + body + "' https://example.test/large #" + ("x" * 20_000)

    result = parse_curl_import(raw)

    assert len(raw) > 262_144
    assert len(raw) < 300_000
    assert result.step.method == "POST"
    assert result.step.body.raw_text == body


def test_basic_auth_short_option_is_unsupported_without_becoming_url() -> None:
    result = parse_curl_import("curl -u user:pass https://example.test/secure")

    assert result.step.method == "GET"
    assert result.step.path == "/secure"
    assert result.base_url_suggestion == "https://example.test"
    assert [(item.option, item.reason_code) for item in result.unsupported_options] == [
        ("-u", "unsupported_option")
    ]
    assert any(warning.code == "UNSUPPORTED_OPTION_IGNORED" for warning in result.warnings)
    assert "user:pass" not in str(result.unsupported_options)
    assert "user:pass" not in " ".join(warning.message for warning in result.warnings)


@pytest.mark.parametrize(
    ("option", "value"),
    [
        ("-x", "http://proxy.example.test:8080"),
        ("-E", "client.pem"),
        ("-K", "curl.conf"),
    ],
)
def test_connection_auth_short_options_are_consumed_as_unsupported(option: str, value: str) -> None:
    result = parse_curl_import(f"curl {option} {value} https://example.test/secure")

    assert result.step.path == "/secure"
    assert [(item.option, item.reason_code) for item in result.unsupported_options] == [
        (option, "unsupported_option")
    ]
    assert value not in str(result.unsupported_options)
