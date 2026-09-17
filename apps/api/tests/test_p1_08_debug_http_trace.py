from __future__ import annotations

from datetime import UTC, datetime, timedelta
from io import BytesIO
import hashlib
import json
from dataclasses import replace

import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session
import yaml

from app.core.config import get_settings
from app.models.auth import DEFAULT_WORKSPACE_ID
from app.models.runs import Run, RunArtifact, RunSnapshot
from app.services.execution_bundles import (
    build_debug_scenario_execution_bundle,
    build_test_plan_execution_bundle,
)
from app.services.runs import ingest_run_artifact
from app.services.storage import PutResult, StoredObjectStream

from test_p0_07_run_report_api import register, seed_node, seed_run


class MemoryStorage:
    def __init__(self, objects: dict[str, bytes] | None = None) -> None:
        self.objects = objects or {}
        self.puts: list[tuple[str, str, bytes, int, str | None]] = []
        self.last_stream: BytesIO | None = None

    def get_stream(self, *, bucket: str, object_key: str) -> StoredObjectStream:
        assert bucket == "surgepilot"
        self.last_stream = BytesIO(self.objects[object_key])
        return StoredObjectStream(
            "application/jsonl",
            len(self.objects[object_key]),
            self.last_stream,
        )

    def put_stream(self, *, bucket, object_key, stream, size_limit, content_type=None):  # noqa: ANN001
        data = stream.read()
        if len(data) > size_limit:
            from app.core.errors import AppError

            raise AppError("PAYLOAD_TOO_LARGE", "Uploaded file is too large.", 413)
        self.objects[object_key] = data
        self.puts.append((bucket, object_key, data, size_limit, content_type))
        return PutResult(size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest())

    def copy_object(self, *, bucket: str, source_key: str, destination_key: str) -> None:
        self.objects[destination_key] = self.objects[source_key]

    def delete_object_best_effort(self, *, bucket: str, object_key: str) -> None:
        self.objects.pop(object_key, None)


def jsonl(*rows: dict) -> bytes:
    return ("\n".join(json.dumps(row, separators=(",", ":")) for row in rows) + "\n").encode()


def trace_row(**overrides):  # noqa: ANN003
    row = {
        "schemaVersion": 1,
        "sequence": 1,
        "label": "Login",
        "url": "https://user:pass@api.example.test/login?api_key=query-secret&safe=ok",
        "method": "POST",
        "requestHeaders": {
            "Authorization": "Bearer secret-token",
            "X-Trace": "safe",
        },
        "requestBody": {
            "contentType": "application/json",
            "text": '{"username":"alice","password":"open-sesame"}',
        },
        "responseStatus": 401,
        "responseHeaders": {
            "Set-Cookie": "session=secret",
            "Content-Type": "application/json",
        },
        "responseBody": {"contentType": "application/json", "text": '{"token":"abc"}'},
        "durationMs": 123,
        "error": None,
    }
    row.update(overrides)
    return row


def test_debug_trace_parser_redacts_sensitive_headers_and_bodies() -> None:
    from app.services.debug_http_trace import parse_debug_http_trace_jsonl

    result = parse_debug_http_trace_jsonl(
        BytesIO(jsonl(trace_row())),
        source_artifact_id="01HZX3Y9M0E9W7Z6M5QK9S8P7A",
        max_requests=100,
        body_max_bytes=64 * 1024,
        artifact_max_bytes=10 * 1024 * 1024,
    )

    assert result.status == "available"
    assert result.entry_count == 1
    entry = result.entries[0]
    assert entry.request_headers == {"Authorization": "[REDACTED]", "X-Trace": "safe"}
    assert entry.url == "https://[REDACTED]@api.example.test/login?api_key=%5BREDACTED%5D&safe=ok"
    assert entry.response_headers["Set-Cookie"] == "[REDACTED]"
    assert "open-sesame" not in entry.request_body.text
    assert "[REDACTED]" in entry.request_body.text
    assert "abc" not in entry.response_body.text
    assert "query-secret" not in entry.url


def test_debug_trace_parser_sniffs_json_and_form_bodies_without_content_type() -> None:
    from app.services.debug_http_trace import parse_debug_http_trace_jsonl

    result = parse_debug_http_trace_jsonl(
        BytesIO(
            jsonl(
                trace_row(
                    requestBody={
                        "contentType": None,
                        "text": '{"password":"open-sesame","nested":{"token":"abc"}}',
                    },
                    responseBody={
                        "contentType": None,
                        "text": "token=abc&message=ok",
                    },
                )
            )
        ),
        source_artifact_id="01HZX3Y9M0E9W7Z6M5QK9S8P7A",
        max_requests=100,
        body_max_bytes=64 * 1024,
        artifact_max_bytes=10 * 1024 * 1024,
    )

    entry = result.entries[0]
    assert "open-sesame" not in entry.request_body.text
    assert "abc" not in entry.request_body.text
    assert entry.request_body.text == ('{"password":"[REDACTED]","nested":{"token":"[REDACTED]"}}')
    assert entry.response_body.text == "token=%5BREDACTED%5D&message=ok"


def test_debug_trace_parser_preserves_collector_observed_size_for_text_bodies() -> None:
    from app.services.debug_http_trace import parse_debug_http_trace_jsonl

    result = parse_debug_http_trace_jsonl(
        BytesIO(
            jsonl(
                trace_row(
                    requestBody={
                        "contentType": "text/plain",
                        "text": "short preview",
                        "bodyStorage": "inline",
                        "bodyTruncated": False,
                        "sizeBytes": 4096,
                        "sha256Prefix": "1234567890abcdef",
                    },
                    responseBody={
                        "contentType": "text/plain",
                        "text": "truncated preview",
                        "bodyStorage": "truncated",
                        "bodyTruncated": True,
                        "sizeBytes": 8192,
                        "sha256Prefix": "abcdef1234567890",
                    },
                )
            )
        ),
        source_artifact_id="01HZX3Y9M0E9W7Z6M5QK9S8P7A",
        max_requests=100,
        body_max_bytes=64 * 1024,
        artifact_max_bytes=10 * 1024 * 1024,
    )

    entry = result.entries[0]
    assert entry.request_body.body_storage == "inline"
    assert entry.request_body.size_bytes == 4096
    assert entry.request_body.sha256_prefix == "1234567890abcdef"
    assert entry.response_body.body_storage == "truncated"
    assert entry.response_body.body_truncated is True
    assert entry.response_body.size_bytes == 8192
    assert entry.response_body.sha256_prefix == "abcdef1234567890"


def test_debug_trace_parser_represents_binary_bodies_as_metadata_only() -> None:
    from app.services.debug_http_trace import parse_debug_http_trace_jsonl

    result = parse_debug_http_trace_jsonl(
        BytesIO(
            jsonl(
                trace_row(
                    requestBody={
                        "contentType": "application/octet-stream",
                        "sizeBytes": 1024,
                        "sha256Prefix": "abcdef123456",
                    }
                )
            )
        ),
        source_artifact_id="01HZX3Y9M0E9W7Z6M5QK9S8P7A",
        max_requests=100,
        body_max_bytes=64 * 1024,
        artifact_max_bytes=10 * 1024 * 1024,
    )

    body = result.entries[0].request_body
    assert body.content_type == "application/octet-stream"
    assert body.text is None
    assert body.size_bytes == 1024
    assert body.sha256_prefix == "abcdef123456"
    assert body.body_truncated is False


def test_debug_trace_parser_sniffs_missing_content_type_binary_body_as_metadata() -> None:
    from app.services.debug_http_trace import parse_debug_http_trace_jsonl

    opaque_text = "\x89PNG\r\n\x1a\n\x00\x00secret-looking-but-opaque"
    result = parse_debug_http_trace_jsonl(
        BytesIO(
            jsonl(
                trace_row(
                    requestBody={
                        "contentType": None,
                        "text": opaque_text,
                    },
                    responseBody={
                        "contentType": None,
                        "sizeBytes": 2048,
                        "sha256Prefix": "abcdef123456",
                    },
                )
            )
        ),
        source_artifact_id="01HZX3Y9M0E9W7Z6M5QK9S8P7A",
        max_requests=100,
        body_max_bytes=64 * 1024,
        artifact_max_bytes=10 * 1024 * 1024,
    )

    request_body = result.entries[0].request_body
    assert request_body.content_type is None
    assert request_body.text is None
    assert request_body.size_bytes == len(opaque_text.encode("utf-8"))
    assert request_body.sha256_prefix is not None
    response_body = result.entries[0].response_body
    assert response_body.content_type is None
    assert response_body.text is None
    assert response_body.size_bytes == 2048
    assert response_body.sha256_prefix == "abcdef123456"


def test_debug_trace_parser_maps_large_body_sidecar_and_dropped_states() -> None:
    from app.services.debug_http_trace import parse_debug_http_trace_jsonl

    result = parse_debug_http_trace_jsonl(
        BytesIO(
            jsonl(
                trace_row(
                    responseBody={
                        "contentType": "text/html",
                        "bodyStorage": "sidecar",
                        "text": "<html>preview</html>",
                        "sizeBytes": 3 * 1024 * 1024,
                        "sha256Prefix": "1234567890abcdef",
                        "downloadRelativePath": "artifacts/debug-http-body-blobs/1-response.bin",
                    },
                    requestBody={
                        "contentType": "application/pdf",
                        "bodyStorage": "dropped",
                        "sizeBytes": 8 * 1024 * 1024,
                        "sha256Prefix": "abcdef1234567890",
                        "dropReason": "body_too_large",
                    },
                )
            )
        ),
        source_artifact_id="01HZX3Y9M0E9W7Z6M5QK9S8P7A",
        max_requests=100,
        body_max_bytes=64 * 1024,
        artifact_max_bytes=10 * 1024 * 1024,
        record_max_bytes=128 * 1024,
        body_blob_artifact_ids_by_relative_path={
            "artifacts/debug-http-body-blobs/1-response.bin": "01HZX3Y9M0E9W7Z6M5QK9S8P7B"
        },
    )

    entry = result.entries[0]
    assert entry.response_body.body_storage == "sidecar"
    assert entry.response_body.body_truncated is True
    assert entry.response_body.inline_preview == "<html>preview</html>"
    assert entry.response_body.text == "<html>preview</html>"
    assert entry.response_body.size_bytes == 3 * 1024 * 1024
    assert entry.response_body.sha256_prefix == "1234567890abcdef"
    assert entry.response_body.download_artifact_id == "01HZX3Y9M0E9W7Z6M5QK9S8P7B"
    assert entry.response_body.download_relative_path is None
    assert entry.request_body.body_storage == "dropped"
    assert entry.request_body.text is None
    assert entry.request_body.inline_preview is None
    assert entry.request_body.drop_reason == "body_too_large"


def test_debug_trace_parser_skips_oversized_jsonl_line_without_reading_all() -> None:
    from app.services.debug_http_trace import parse_debug_http_trace_jsonl

    oversized = b'{"schemaVersion":1,"url":"' + (b"a" * 400) + b'","method":"GET"}\n'
    valid = jsonl(
        {
            "schemaVersion": 1,
            "sequence": 2,
            "url": "https://e.test",
            "method": "GET",
            "requestBody": {"contentType": "text/plain", "text": ""},
            "responseBody": {"contentType": "text/plain", "text": ""},
        }
    )

    result = parse_debug_http_trace_jsonl(
        BytesIO(oversized + valid),
        source_artifact_id="01HZX3Y9M0E9W7Z6M5QK9S8P7A",
        max_requests=100,
        body_max_bytes=64 * 1024,
        artifact_max_bytes=10 * 1024 * 1024,
        record_max_bytes=256,
    )

    assert result.status == "available"
    assert result.entry_count == 1
    assert result.entries[0].sequence == 2
    assert "debug_http_trace_line_too_large" in result.warnings


def test_debug_trace_parser_skips_oversized_jsonl_line_even_when_newline_terminated() -> None:
    from app.services.debug_http_trace import parse_debug_http_trace_jsonl

    oversized = b'{"schemaVersion":1,"url":"' + (b"a" * 400) + b'","method":"GET"}\n'
    valid = jsonl(
        {
            "schemaVersion": 1,
            "sequence": 2,
            "url": "https://e.test/next",
            "method": "GET",
            "requestBody": {"contentType": "text/plain", "text": ""},
            "responseBody": {"contentType": "text/plain", "text": ""},
        }
    )

    result = parse_debug_http_trace_jsonl(
        BytesIO(oversized + valid),
        source_artifact_id="01HZX3Y9M0E9W7Z6M5QK9S8P7A",
        max_requests=100,
        body_max_bytes=64 * 1024,
        artifact_max_bytes=10 * 1024 * 1024,
        record_max_bytes=256,
    )

    assert result.status == "available"
    assert result.entry_count == 1
    assert result.entries[0].url == "https://e.test/next"
    assert "debug_http_trace_line_too_large" in result.warnings


def test_debug_trace_parser_returns_unavailable_when_oversized_line_exceeds_total_limit() -> None:
    from app.services.debug_http_trace import parse_debug_http_trace_jsonl

    result = parse_debug_http_trace_jsonl(
        BytesIO(b'{"schemaVersion":1,"url":"' + (b"a" * 400) + b'"'),
        source_artifact_id="01HZX3Y9M0E9W7Z6M5QK9S8P7A",
        max_requests=100,
        body_max_bytes=64 * 1024,
        artifact_max_bytes=300,
        record_max_bytes=128,
    )

    assert result.model_dump(by_alias=True) == {
        "status": "unavailable",
        "sourceArtifactId": "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
        "entryCount": 0,
        "traceTruncated": True,
        "warnings": ["debug_http_trace_too_large"],
        "entries": [],
    }


def test_debug_trace_parser_redacts_sensitive_label_and_error_text() -> None:
    from app.services.debug_http_trace import parse_debug_http_trace_jsonl

    result = parse_debug_http_trace_jsonl(
        BytesIO(
            jsonl(
                trace_row(
                    label=(
                        "Login Authorization: Bearer label-secret Cookie: sid=cookie-secret "
                        '{"password":"json-secret"} apiKey is key-secret '
                        "https://user:pass@api.example.test/login?api_key=query-secret&safe=ok"
                    ),
                    error=(
                        "Failed Bearer abc password open-sesame token:abc "
                        "secret_key=query-secret X-Api-Key=header-secret Cookie=sid=cookie-secret"
                    ),
                )
            )
        ),
        source_artifact_id="01HZX3Y9M0E9W7Z6M5QK9S8P7A",
        max_requests=100,
        body_max_bytes=64 * 1024,
        artifact_max_bytes=10 * 1024 * 1024,
    )

    entry = result.entries[0]
    assert entry.label is not None
    assert entry.error is not None
    assert "https://[REDACTED]@api.example.test/login?api_key=[REDACTED]" in entry.label
    assert '{"password":"[REDACTED]"}' in entry.label
    assert "Authorization: [REDACTED]" in entry.label
    assert "Cookie: sid=[REDACTED]" in entry.label
    assert "apiKey" in entry.label and "key-secret" not in entry.label
    assert "Bearer [REDACTED]" in entry.error
    assert "password [REDACTED]" in entry.error
    assert "token:[REDACTED]" in entry.error
    assert "secret_key=[REDACTED]" in entry.error
    assert "X-Api-Key: [REDACTED]" in entry.error
    assert "Cookie=sid=[REDACTED]" in entry.error
    for secret in [
        "query-secret",
        "open-sesame",
        "label-secret",
        "cookie-secret",
        "json-secret",
        "key-secret",
        "header-secret",
        " abc",
    ]:
        assert secret not in entry.label
        assert secret not in entry.error


def test_debug_trace_parser_redacts_malformed_json_like_body_text() -> None:
    from app.services.debug_http_trace import parse_debug_http_trace_jsonl

    result = parse_debug_http_trace_jsonl(
        BytesIO(
            jsonl(
                trace_row(
                    requestBody={
                        "contentType": "application/json",
                        "text": '{"password":"open sesame","apiKey":"key secret"',
                    },
                    responseBody={
                        "contentType": "text/plain",
                        "text": "Cookie: sid=secret; refresh=secret2",
                    },
                )
            )
        ),
        source_artifact_id="01HZX3Y9M0E9W7Z6M5QK9S8P7A",
        max_requests=100,
        body_max_bytes=64 * 1024,
        artifact_max_bytes=10 * 1024 * 1024,
    )

    entry = result.entries[0]
    assert "open sesame" not in entry.request_body.text
    assert "key secret" not in entry.request_body.text
    assert "secret2" not in entry.response_body.text
    assert entry.response_body.text == "Cookie: sid=[REDACTED]; refresh=[REDACTED]"


def test_debug_trace_parser_redacts_header_values_and_url_fragments() -> None:
    from app.services.debug_http_trace import parse_debug_http_trace_jsonl

    result = parse_debug_http_trace_jsonl(
        BytesIO(
            jsonl(
                trace_row(
                    url=(
                        "https://api.example.test/callback?safe=ok"
                        "&redirect_uri=https%3A%2F%2Fidp.example.test%2Fcb%3Faccess_token%3Dnested-secret%26safe%3Dok"
                        "#next=https%3A%2F%2Fidp.example.test%2Fcb%3Fpassword%3Dfragment-nested&section=top"
                    ),
                    requestHeaders={
                        "Referer": (
                            "https://idp.example.test/cb?"
                            "redirect_uri=https%3A%2F%2Fapi.example.test%2Fcb%3Fapi_key%3Dquery-secret"
                        ),
                        "X-Trace": "Bearer trace-secret",
                    },
                    responseHeaders={
                        "Location": "https://api.example.test/next#password=fragment-password",
                        "Content-Type": "application/json",
                    },
                )
            )
        ),
        source_artifact_id="01HZX3Y9M0E9W7Z6M5QK9S8P7A",
        max_requests=100,
        body_max_bytes=64 * 1024,
        artifact_max_bytes=10 * 1024 * 1024,
    )

    entry = result.entries[0]
    assert "nested-secret" not in entry.url
    assert "fragment-nested" not in entry.url
    assert "access_token%3D%255BREDACTED%255D" in entry.url
    assert "password%3D%255BREDACTED%255D" in entry.url
    assert "query-secret" not in entry.request_headers["Referer"]
    assert "api_key%3D%255BREDACTED%255D" in entry.request_headers["Referer"]
    assert "trace-secret" not in entry.request_headers["X-Trace"]
    assert entry.request_headers["X-Trace"] == "Bearer [REDACTED]"
    assert "fragment-password" not in entry.response_headers["Location"]


def test_debug_trace_parser_redacts_nested_url_values_in_body_text() -> None:
    from app.services.debug_http_trace import parse_debug_http_trace_jsonl

    result = parse_debug_http_trace_jsonl(
        BytesIO(
            jsonl(
                trace_row(
                    requestBody={
                        "contentType": "application/json",
                        "text": json.dumps(
                            {
                                "redirectUri": (
                                    "https://idp.example.test/cb?"
                                    "access_token=json-nested-secret&safe=ok"
                                ),
                                "encodedRedirectUri": (
                                    "https%3A%2F%2Fidp.example.test%2Fcb%3Fpassword%3Dencoded-json-secret"
                                ),
                            }
                        ),
                    },
                    responseBody={
                        "contentType": "application/x-www-form-urlencoded",
                        "text": (
                            "redirect_uri=https%3A%2F%2Fidp.example.test%2Fcb"
                            "%3Ftoken%3Dform-nested-secret%26safe%3Dok&message=ok"
                        ),
                    },
                )
            )
        ),
        source_artifact_id="01HZX3Y9M0E9W7Z6M5QK9S8P7A",
        max_requests=100,
        body_max_bytes=64 * 1024,
        artifact_max_bytes=10 * 1024 * 1024,
    )

    entry = result.entries[0]
    assert "json-nested-secret" not in entry.request_body.text
    assert "encoded-json-secret" not in entry.request_body.text
    assert "form-nested-secret" not in entry.response_body.text
    assert "access_token=[REDACTED]" in entry.request_body.text
    assert "password=[REDACTED]" in entry.request_body.text
    assert "token%3D%5BREDACTED%5D" in entry.response_body.text


def test_debug_trace_parser_redacts_double_encoded_nested_url_values() -> None:
    from app.services.debug_http_trace import parse_debug_http_trace_jsonl

    result = parse_debug_http_trace_jsonl(
        BytesIO(
            jsonl(
                trace_row(
                    url=(
                        "https://api.example.test/callback?"
                        "redirect_uri=https%253A%252F%252Fidp.example.test%252Fcb"
                        "%253Fpassword%253Ddouble-url-secret%2526safe%253Dok"
                    ),
                    requestBody={
                        "contentType": "application/json",
                        "text": json.dumps(
                            {
                                "callback": (
                                    "https%253A%252F%252Fidp.example.test%252Fcb"
                                    "%253Ftoken%253Ddouble-json-secret%2526safe%253Dok"
                                )
                            }
                        ),
                    },
                    responseBody={
                        "contentType": "application/x-www-form-urlencoded",
                        "text": (
                            "redirect_uri=https%253A%252F%252Fidp.example.test%252Fcb"
                            "%253Fapi_key%253Ddouble-form-secret%2526safe%253Dok"
                        ),
                    },
                )
            )
        ),
        source_artifact_id="01HZX3Y9M0E9W7Z6M5QK9S8P7A",
        max_requests=100,
        body_max_bytes=64 * 1024,
        artifact_max_bytes=10 * 1024 * 1024,
    )

    entry = result.entries[0]
    encoded = json.dumps(entry.model_dump(mode="json"), default=str)
    assert "double-url-secret" not in encoded
    assert "double-json-secret" not in encoded
    assert "double-form-secret" not in encoded
    assert "password%3D%255BREDACTED%255D" in entry.url
    assert "token=[REDACTED]" in (entry.request_body.text or "")
    assert "api_key%3D%5BREDACTED%5D" in (entry.response_body.text or "")


def test_debug_trace_parser_redacts_double_encoded_free_text_and_headers() -> None:
    from app.services.debug_http_trace import parse_debug_http_trace_jsonl

    result = parse_debug_http_trace_jsonl(
        BytesIO(
            jsonl(
                trace_row(
                    requestHeaders={
                        "Referer": (
                            "https%253A%252F%252Fidp.example.test%252Fcb"
                            "%253Fpassword%253Ddouble-header-secret"
                        ),
                        "X-Trace": (
                            "callback=https%253A%252F%252Fidp.example.test%252Fcb"
                            "%253Ftoken%253Ddouble-custom-header-secret"
                        ),
                    },
                    requestBody={
                        "contentType": "text/plain",
                        "text": (
                            "callback=https%253A%252F%252Fidp.example.test%252Fcb"
                            "%253Ftoken%253Ddouble-text-body-secret"
                        ),
                    },
                    responseHeaders={
                        "Location": (
                            "https%253A%252F%252Fapi.example.test%252Fnext"
                            "%253Fsecret%253Ddouble-location-secret"
                        ),
                    },
                    responseBody={
                        "contentType": "text/plain",
                        "text": (
                            "next=https%253A%252F%252Fapi.example.test%252Fnext"
                            "%253Fapi_key%253Ddouble-response-body-secret"
                        ),
                    },
                )
            )
        ),
        source_artifact_id="01HZX3Y9M0E9W7Z6M5QK9S8P7A",
        max_requests=100,
        body_max_bytes=64 * 1024,
        artifact_max_bytes=10 * 1024 * 1024,
    )

    entry = result.entries[0]
    encoded = json.dumps(entry.model_dump(mode="json"), default=str)
    for secret in [
        "double-header-secret",
        "double-custom-header-secret",
        "double-text-body-secret",
        "double-location-secret",
        "double-response-body-secret",
    ]:
        assert secret not in encoded
    assert "password=[REDACTED]" in entry.request_headers["Referer"]
    assert "token=[REDACTED]" in entry.request_headers["X-Trace"]
    assert "token=[REDACTED]" in (entry.request_body.text or "")
    assert "secret=[REDACTED]" in entry.response_headers["Location"]
    assert "api_key=[REDACTED]" in (entry.response_body.text or "")


def test_debug_trace_parser_redacts_xml_sensitive_elements() -> None:
    from app.services.debug_http_trace import parse_debug_http_trace_jsonl

    result = parse_debug_http_trace_jsonl(
        BytesIO(
            jsonl(
                trace_row(
                    requestBody={
                        "contentType": "application/xml",
                        "text": (
                            "<request><password>xml-secret</password>"
                            "<callback>https://idp.example.test/cb?token=url-secret</callback>"
                            "</request>"
                        ),
                    }
                )
            )
        ),
        source_artifact_id="01HZX3Y9M0E9W7Z6M5QK9S8P7A",
        max_requests=100,
        body_max_bytes=64 * 1024,
        artifact_max_bytes=10 * 1024 * 1024,
    )

    body_text = result.entries[0].request_body.text
    assert body_text is not None
    assert "xml-secret" not in body_text
    assert "url-secret" not in body_text
    assert "<password>[REDACTED]</password>" in body_text
    assert "token=[REDACTED]" in body_text


def test_debug_trace_parser_marks_body_and_trace_truncation() -> None:
    from app.services.debug_http_trace import parse_debug_http_trace_jsonl

    result = parse_debug_http_trace_jsonl(
        BytesIO(
            jsonl(
                trace_row(sequence=1, requestBody={"contentType": "text/plain", "text": "abcdef"}),
                trace_row(sequence=2),
            )
        ),
        source_artifact_id="01HZX3Y9M0E9W7Z6M5QK9S8P7A",
        max_requests=1,
        body_max_bytes=3,
        artifact_max_bytes=10 * 1024 * 1024,
    )

    assert result.status == "available"
    assert result.entry_count == 1
    assert result.trace_truncated is True
    assert result.entries[0].request_body.text == "abc"
    assert result.entries[0].request_body.body_truncated is True


def test_debug_trace_parser_accepts_truncation_marker_without_fake_entry() -> None:
    from app.services.debug_http_trace import parse_debug_http_trace_jsonl

    result = parse_debug_http_trace_jsonl(
        BytesIO(jsonl(trace_row(sequence=1), {"schemaVersion": 1, "traceTruncated": True})),
        source_artifact_id="01HZX3Y9M0E9W7Z6M5QK9S8P7A",
        max_requests=100,
        body_max_bytes=64 * 1024,
        artifact_max_bytes=10 * 1024 * 1024,
    )

    assert result.status == "available"
    assert result.entry_count == 1
    assert result.trace_truncated is True
    assert result.entries[0].url == (
        "https://[REDACTED]@api.example.test/login?api_key=%5BREDACTED%5D&safe=ok"
    )


def test_debug_trace_parser_returns_unavailable_for_fully_malformed_jsonl() -> None:
    from app.services.debug_http_trace import parse_debug_http_trace_jsonl

    result = parse_debug_http_trace_jsonl(
        BytesIO(b"{not-json}\n[]\n"),
        source_artifact_id="01HZX3Y9M0E9W7Z6M5QK9S8P7A",
        max_requests=100,
        body_max_bytes=64 * 1024,
        artifact_max_bytes=10 * 1024 * 1024,
    )

    assert result.status == "unavailable"
    assert result.entry_count == 0
    assert result.warnings == [
        "debug_http_trace_line_invalid",
        "debug_http_trace_line_parse_failed",
    ]


@pytest.mark.anyio
async def test_run_report_returns_debug_http_trace_for_debug_run(
    client: AsyncClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _csrf, workspace_id, user_id = await register(client, "trace-report@example.com")
    node = seed_node(
        db_session, user_id, node_id="01HZX3Y9M0E9W7Z6M5QK9S8P7N", workspace_id=workspace_id
    )
    run = seed_run(
        db_session,
        user_id=user_id,
        run_id="01HZX3Y9M0E9W7Z6M5QK9S8P7R",
        node=node,
        workspace_id=workspace_id,
        run_type="debug",
        state="finished",
        validity="invalid",
    )
    artifact = RunArtifact(
        id="01HZX3Y9M0E9W7Z6M5QK9S8P7T",
        workspace_id=workspace_id,
        run_id=run.id,
        node_id=node.id,
        event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7E",
        artifact_type="debug_http_trace",
        relative_path="artifacts/debug-http-trace.jsonl",
        display_filename="debug-http-trace.jsonl",
        size_bytes=128,
        sha256="a" * 64,
        content_type="application/jsonl",
        storage_key="run-artifacts/object-key-must-not-leak",
        status="available",
        terminal_late=False,
        created_at=datetime(2030, 6, 3, 8, 5, tzinfo=UTC),
    )
    db_session.add(artifact)
    db_session.commit()
    storage = MemoryStorage(
        {
            artifact.storage_key: jsonl(
                trace_row(
                    label="Login https://user:pass@api.example.test/login?api_key=query-secret",
                    responseBody={
                        "contentType": "application/octet-stream",
                        "sizeBytes": 2048,
                        "sha256Prefix": "123456abcdef",
                    },
                    error="Failed password=open-sesame token:abc",
                )
            )
        }
    )
    monkeypatch.setattr("app.services.run_reports.get_storage_client", lambda: storage)

    response = await client.get(f"/api/v1/runs/{run.id}", headers={"x-workspace-id": workspace_id})

    assert response.status_code == 200
    body = response.json()
    assert body["debugHttpTrace"]["status"] == "available"
    assert body["artifactsSummary"]["count"] == 0
    assert body["debugHttpTrace"]["sourceArtifactId"] == artifact.id
    assert body["debugHttpTrace"]["entries"][0]["method"] == "POST"
    assert body["debugHttpTrace"]["entries"][0]["responseBody"] == {
        "contentType": "application/octet-stream",
        "text": None,
        "inlinePreview": None,
        "bodyStorage": "dropped",
        "bodyTruncated": False,
        "sizeBytes": 2048,
        "sha256Prefix": "123456abcdef",
        "downloadArtifactId": None,
        "dropReason": "binary_body",
    }
    assert "query-secret" not in body["debugHttpTrace"]["entries"][0]["label"]
    assert "open-sesame" not in body["debugHttpTrace"]["entries"][0]["error"]
    assert "abc" not in body["debugHttpTrace"]["entries"][0]["error"]
    assert "secret-token" not in response.text
    assert "object-key-must-not-leak" not in response.text
    assert storage.last_stream is not None
    assert storage.last_stream.closed is True

    artifacts = await client.get(
        f"/api/v1/runs/{run.id}/artifacts", headers={"x-workspace-id": workspace_id}
    )
    assert artifacts.status_code == 200
    assert artifacts.json()["items"] == []
    debug_filter = await client.get(
        f"/api/v1/runs/{run.id}/artifacts?artifactType=debug_http_trace",
        headers={"x-workspace-id": workspace_id},
    )
    assert debug_filter.status_code == 422
    download = await client.get(
        f"/api/v1/runs/{run.id}/artifacts/{artifact.id}/download",
        headers={"x-workspace-id": workspace_id},
    )
    assert download.status_code == 404
    assert "secret-token" not in download.text


@pytest.mark.anyio
async def test_debug_http_body_blob_download_is_internal_trace_only(
    client: AsyncClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _csrf, workspace_id, user_id = await register(client, "trace-body-blob@example.com")
    node = seed_node(
        db_session, user_id, node_id="01HZX3Y9M0E9W7Z6M5QK9S8P7N", workspace_id=workspace_id
    )
    run = seed_run(
        db_session,
        user_id=user_id,
        run_id="01HZX3Y9M0E9W7Z6M5QK9S8P7R",
        node=node,
        workspace_id=workspace_id,
        run_type="debug",
        state="finished",
        validity="invalid",
    )
    trace = RunArtifact(
        id="01HZX3Y9M0E9W7Z6M5QK9S8P7T",
        workspace_id=workspace_id,
        run_id=run.id,
        node_id=node.id,
        event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7E",
        artifact_type="debug_http_trace",
        relative_path="artifacts/debug-http-trace.jsonl",
        display_filename="debug-http-trace.jsonl",
        size_bytes=256,
        sha256="a" * 64,
        content_type="application/jsonl",
        storage_key="run-artifacts/trace-with-sidecar",
        status="available",
        terminal_late=False,
        created_at=datetime(2030, 6, 3, 8, 5, tzinfo=UTC),
    )
    blob = RunArtifact(
        id="01HZX3Y9M0E9W7Z6M5QK9S8P7B",
        workspace_id=workspace_id,
        run_id=run.id,
        node_id=node.id,
        event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7F",
        artifact_type="debug_http_body_blob",
        relative_path="artifacts/debug-http-body-blobs/1-response.bin",
        display_filename="1-response.bin",
        size_bytes=18,
        sha256="b" * 64,
        content_type="text/html",
        storage_key="run-artifacts/body-blob-object-key",
        status="available",
        terminal_late=False,
        created_at=datetime(2030, 6, 3, 8, 5, tzinfo=UTC),
    )
    db_session.add_all([trace, blob])
    db_session.commit()
    storage = MemoryStorage(
        {
            trace.storage_key: jsonl(
                trace_row(
                    responseBody={
                        "contentType": "text/html",
                        "bodyStorage": "sidecar",
                        "text": "<html>preview</html>",
                        "sizeBytes": 18,
                        "sha256Prefix": "bbbbbbbbbbbbbbbb",
                        "downloadRelativePath": blob.relative_path,
                    }
                )
            ),
            blob.storage_key: b"<html>sanitized-body</html>",
        }
    )
    monkeypatch.setattr("app.services.run_reports.get_storage_client", lambda: storage)

    report_response = await client.get(
        f"/api/v1/runs/{run.id}", headers={"x-workspace-id": workspace_id}
    )

    assert report_response.status_code == 200
    response_body = report_response.json()["debugHttpTrace"]["entries"][0]["responseBody"]
    assert response_body["bodyStorage"] == "sidecar"
    assert response_body["downloadArtifactId"] == blob.id
    assert "downloadRelativePath" not in response_body
    assert "body-blob-object-key" not in report_response.text

    public_filter = await client.get(
        f"/api/v1/runs/{run.id}/artifacts?artifactType=debug_http_body_blob",
        headers={"x-workspace-id": workspace_id},
    )
    assert public_filter.status_code == 422
    public_download = await client.get(
        f"/api/v1/runs/{run.id}/artifacts/{blob.id}/download",
        headers={"x-workspace-id": workspace_id},
    )
    assert public_download.status_code == 404

    blob_download = await client.get(
        f"/api/v1/runs/{run.id}/debug-http-body-blobs/{blob.id}/download",
        headers={"x-workspace-id": workspace_id},
    )
    assert blob_download.status_code == 200
    assert blob_download.content == b"<html>sanitized-body</html>"
    assert blob_download.headers["cache-control"] == "private, no-store"


@pytest.mark.anyio
async def test_run_report_returns_unavailable_for_oversized_debug_http_trace(
    client: AsyncClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _csrf, workspace_id, user_id = await register(client, "trace-oversize@example.com")
    node = seed_node(
        db_session, user_id, node_id="01HZX3Y9M0E9W7Z6M5QK9S8P7N", workspace_id=workspace_id
    )
    run = seed_run(
        db_session,
        user_id=user_id,
        run_id="01HZX3Y9M0E9W7Z6M5QK9S8P7R",
        node=node,
        workspace_id=workspace_id,
        run_type="debug",
        state="finished",
        validity="invalid",
    )
    artifact = RunArtifact(
        id="01HZX3Y9M0E9W7Z6M5QK9S8P7T",
        workspace_id=workspace_id,
        run_id=run.id,
        node_id=node.id,
        event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7E",
        artifact_type="debug_http_trace",
        relative_path="artifacts/debug-http-trace.jsonl",
        display_filename="debug-http-trace.jsonl",
        size_bytes=9,
        sha256="a" * 64,
        content_type="application/jsonl",
        storage_key="run-artifacts/oversized-debug-trace",
        status="available",
        terminal_late=False,
        created_at=datetime(2030, 6, 3, 8, 5, tzinfo=UTC),
    )
    db_session.add(artifact)
    db_session.commit()
    monkeypatch.setenv("SURGEPILOT_DEBUG_TRACE_ARTIFACT_MAX_BYTES", "8")
    storage = MemoryStorage({artifact.storage_key: b"123456789"})
    monkeypatch.setattr("app.services.run_reports.get_storage_client", lambda: storage)

    response = await client.get(f"/api/v1/runs/{run.id}", headers={"x-workspace-id": workspace_id})

    assert response.status_code == 200
    assert response.json()["debugHttpTrace"] == {
        "status": "unavailable",
        "sourceArtifactId": artifact.id,
        "entryCount": 0,
        "traceTruncated": True,
        "warnings": ["debug_http_trace_too_large"],
        "entries": [],
    }
    assert storage.last_stream is not None
    assert storage.last_stream.closed is True


@pytest.mark.anyio
async def test_standard_run_report_omits_debug_http_trace(
    client: AsyncClient, db_session: Session
) -> None:
    _csrf, workspace_id, user_id = await register(client, "trace-standard@example.com")
    node = seed_node(
        db_session, user_id, node_id="01HZX3Y9M0E9W7Z6M5QK9S8P7N", workspace_id=workspace_id
    )
    run = seed_run(
        db_session,
        user_id=user_id,
        run_id="01HZX3Y9M0E9W7Z6M5QK9S8P7R",
        node=node,
        workspace_id=workspace_id,
        run_type="standard",
    )
    db_session.commit()

    response = await client.get(f"/api/v1/runs/{run.id}", headers={"x-workspace-id": workspace_id})

    assert response.status_code == 200
    assert response.json()["debugHttpTrace"] is None


@pytest.mark.anyio
async def test_terminal_debug_run_without_trace_returns_unavailable_summary(
    client: AsyncClient, db_session: Session
) -> None:
    _csrf, workspace_id, user_id = await register(client, "trace-missing@example.com")
    node = seed_node(
        db_session, user_id, node_id="01HZX3Y9M0E9W7Z6M5QK9S8P7N", workspace_id=workspace_id
    )
    run = seed_run(
        db_session,
        user_id=user_id,
        run_id="01HZX3Y9M0E9W7Z6M5QK9S8P7R",
        node=node,
        workspace_id=workspace_id,
        run_type="debug",
        state="finished",
        validity="invalid",
    )
    db_session.commit()

    response = await client.get(f"/api/v1/runs/{run.id}", headers={"x-workspace-id": workspace_id})

    assert response.status_code == 200
    assert response.json()["debugHttpTrace"] == {
        "status": "unavailable",
        "sourceArtifactId": None,
        "entryCount": 0,
        "traceTruncated": False,
        "warnings": ["debug_http_trace_missing"],
        "entries": [],
    }


@pytest.mark.anyio
async def test_active_debug_run_without_trace_omits_debug_http_trace(
    client: AsyncClient, db_session: Session
) -> None:
    _csrf, workspace_id, user_id = await register(client, "trace-active@example.com")
    node = seed_node(
        db_session, user_id, node_id="01HZX3Y9M0E9W7Z6M5QK9S8P7N", workspace_id=workspace_id
    )
    run = seed_run(
        db_session,
        user_id=user_id,
        run_id="01HZX3Y9M0E9W7Z6M5QK9S8P7R",
        node=node,
        workspace_id=workspace_id,
        run_type="debug",
        state="running",
        validity="invalid",
    )
    db_session.commit()

    response = await client.get(f"/api/v1/runs/{run.id}", headers={"x-workspace-id": workspace_id})

    assert response.status_code == 200
    assert response.json()["debugHttpTrace"] is None


@pytest.mark.anyio
async def test_debug_trace_storage_read_failure_returns_safe_unavailable_summary(
    client: AsyncClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FailingStorage:
        def get_stream(self, *, bucket: str, object_key: str):  # noqa: ANN001, ARG002
            raise OSError("storage offline")

    _csrf, workspace_id, user_id = await register(client, "trace-read-fail@example.com")
    node = seed_node(
        db_session, user_id, node_id="01HZX3Y9M0E9W7Z6M5QK9S8P7N", workspace_id=workspace_id
    )
    run = seed_run(
        db_session,
        user_id=user_id,
        run_id="01HZX3Y9M0E9W7Z6M5QK9S8P7R",
        node=node,
        workspace_id=workspace_id,
        run_type="debug",
        state="finished",
        validity="invalid",
    )
    artifact = RunArtifact(
        id="01HZX3Y9M0E9W7Z6M5QK9S8P7T",
        workspace_id=workspace_id,
        run_id=run.id,
        node_id=node.id,
        event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7E",
        artifact_type="debug_http_trace",
        relative_path="artifacts/debug-http-trace.jsonl",
        display_filename="debug-http-trace.jsonl",
        size_bytes=128,
        sha256="a" * 64,
        content_type="application/jsonl",
        storage_key="run-artifacts/missing-debug-trace",
        status="available",
        terminal_late=False,
        created_at=datetime(2030, 6, 3, 8, 5, tzinfo=UTC),
    )
    db_session.add(artifact)
    db_session.commit()
    monkeypatch.setattr("app.services.run_reports.get_storage_client", lambda: FailingStorage())

    response = await client.get(f"/api/v1/runs/{run.id}", headers={"x-workspace-id": workspace_id})

    assert response.status_code == 200
    assert response.json()["debugHttpTrace"] == {
        "status": "unavailable",
        "sourceArtifactId": artifact.id,
        "entryCount": 0,
        "traceTruncated": False,
        "warnings": ["debug_http_trace_unavailable"],
        "entries": [],
    }


def test_debug_http_trace_artifact_is_pre_terminal_only(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user_id = "01HZX3Y9M0E9W7Z6M5QK9S8P7U"
    node = seed_node(
        db_session, user_id, node_id="01HZX3Y9M0E9W7Z6M5QK9S8P7N", workspace_id=DEFAULT_WORKSPACE_ID
    )
    active = seed_run(
        db_session,
        user_id=user_id,
        run_id="01HZX3Y9M0E9W7Z6M5QK9S8P7A",
        node=node,
        workspace_id=DEFAULT_WORKSPACE_ID,
        run_type="debug",
        state="running",
        validity="invalid",
    )
    terminal = seed_run(
        db_session,
        user_id=user_id,
        run_id="01HZX3Y9M0E9W7Z6M5QK9S8P7B",
        node=node,
        workspace_id=DEFAULT_WORKSPACE_ID,
        run_type="debug",
        state="finished",
        validity="invalid",
        created_at=datetime.now(UTC) - timedelta(minutes=2),
    )
    terminal.ended_at = datetime.now(UTC) - timedelta(seconds=30)
    db_session.commit()
    storage = MemoryStorage()
    monkeypatch.setattr("app.services.runs.get_storage_client", lambda: storage)
    payload = jsonl(trace_row())
    digest = hashlib.sha256(payload).hexdigest()

    result = ingest_run_artifact(
        db_session,
        event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7C",
        run_id=active.id,
        node_id=node.id,
        authenticated_node_id=node.id,
        artifact_type="debug_http_trace",
        relative_path="artifacts/debug-http-trace.jsonl",
        declared_sha256=digest,
        declared_size_bytes=len(payload),
        file=BytesIO(payload),
        content_type="application/jsonl",
    )

    assert result.duplicate is False
    assert f"/.tmp/{result.artifact_id}/" in storage.puts[0][1]
    assert storage.puts[0][1].endswith("/artifacts/debug-http-trace.jsonl")
    artifact = db_session.get(RunArtifact, result.artifact_id)
    assert artifact is not None
    assert artifact.storage_key.startswith(
        f"run-artifacts/{DEFAULT_WORKSPACE_ID}/{active.id}/nodes/{node.id}/allocations/"
    )
    assert artifact.storage_key.endswith("/artifacts/debug-http-trace.jsonl")
    assert result.artifact_id not in artifact.storage_key
    active.state = "finished"
    active.ended_at = datetime.now(UTC)
    db_session.commit()
    duplicate = ingest_run_artifact(
        db_session,
        event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7C",
        run_id=active.id,
        node_id=node.id,
        authenticated_node_id=node.id,
        artifact_type="debug_http_trace",
        relative_path="artifacts/debug-http-trace.jsonl",
        declared_sha256=digest,
        declared_size_bytes=len(payload),
        file=BytesIO(payload),
        content_type="application/jsonl",
    )
    assert duplicate.artifact_id == result.artifact_id
    assert duplicate.duplicate is True
    assert len(storage.puts) == 1
    with pytest.raises(Exception) as exc_info:
        ingest_run_artifact(
            db_session,
            event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7D",
            run_id=terminal.id,
            node_id=node.id,
            authenticated_node_id=node.id,
            artifact_type="debug_http_trace",
            relative_path="artifacts/debug-http-trace.jsonl",
            declared_sha256=digest,
            declared_size_bytes=len(payload),
            file=BytesIO(payload),
            content_type="application/jsonl",
        )
    assert getattr(exc_info.value, "code", None) == "RUN_TERMINAL_STATE"


def test_debug_http_body_blob_artifact_is_debug_only_pre_terminal_and_path_scoped(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user_id = "01HZX3Y9M0E9W7Z6M5QK9S8P7U"
    node = seed_node(
        db_session, user_id, node_id="01HZX3Y9M0E9W7Z6M5QK9S8P7N", workspace_id=DEFAULT_WORKSPACE_ID
    )
    active = seed_run(
        db_session,
        user_id=user_id,
        run_id="01HZX3Y9M0E9W7Z6M5QK9S8P7A",
        node=node,
        workspace_id=DEFAULT_WORKSPACE_ID,
        run_type="debug",
        state="running",
        validity="invalid",
    )
    terminal = seed_run(
        db_session,
        user_id=user_id,
        run_id="01HZX3Y9M0E9W7Z6M5QK9S8P7B",
        node=node,
        workspace_id=DEFAULT_WORKSPACE_ID,
        run_type="debug",
        state="finished",
        validity="invalid",
        created_at=datetime.now(UTC) - timedelta(minutes=2),
    )
    terminal.ended_at = datetime.now(UTC) - timedelta(seconds=30)
    standard = seed_run(
        db_session,
        user_id=user_id,
        run_id="01HZX3Y9M0E9W7Z6M5QK9S8P7C",
        node=node,
        workspace_id=DEFAULT_WORKSPACE_ID,
        run_type="standard",
        state="running",
        created_at=datetime.now(UTC) - timedelta(minutes=3),
    )
    db_session.commit()
    storage = MemoryStorage()
    monkeypatch.setattr("app.services.runs.get_storage_client", lambda: storage)
    payload = b"large-body-sidecar"
    digest = hashlib.sha256(payload).hexdigest()

    result = ingest_run_artifact(
        db_session,
        event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7D",
        run_id=active.id,
        node_id=node.id,
        authenticated_node_id=node.id,
        artifact_type="debug_http_body_blob",
        relative_path="artifacts/debug-http-body-blobs/1-response.bin",
        declared_sha256=digest,
        declared_size_bytes=len(payload),
        file=BytesIO(payload),
        content_type="text/html",
    )

    artifact = db_session.get(RunArtifact, result.artifact_id)
    assert artifact is not None
    assert artifact.artifact_type == "debug_http_body_blob"
    assert artifact.storage_key.startswith(
        f"run-artifacts/{DEFAULT_WORKSPACE_ID}/{active.id}/nodes/{node.id}/allocations/"
    )
    assert artifact.storage_key.endswith("/artifacts/debug-http-body-blobs/1-response.bin")
    assert storage.puts[0][3] == get_settings().debug_trace_body_blob_max_bytes

    invalid_cases = [
        (active.id, "artifacts/debug-http-body-blobs/not-bin.txt", "INVALID_ARTIFACT_PATH"),
        (active.id, "artifacts/debug-http-body-blobs/nested/1.bin", "INVALID_ARTIFACT_PATH"),
        (terminal.id, "artifacts/debug-http-body-blobs/2-response.bin", "RUN_TERMINAL_STATE"),
        (standard.id, "artifacts/debug-http-body-blobs/3-response.bin", "RUNNER_FORBIDDEN"),
    ]
    for index, (run_id, relative_path, code) in enumerate(invalid_cases):
        with pytest.raises(Exception) as exc_info:
            ingest_run_artifact(
                db_session,
                event_id=f"01HZX3Y9M0E9W7Z6M5QK9S8P{index}E",
                run_id=run_id,
                node_id=node.id,
                authenticated_node_id=node.id,
                artifact_type="debug_http_body_blob",
                relative_path=relative_path,
                declared_sha256=digest,
                declared_size_bytes=len(payload),
                file=BytesIO(payload),
                content_type="application/octet-stream",
            )
        assert getattr(exc_info.value, "code", None) == code


def test_debug_http_body_blob_artifact_enforces_total_upload_budget(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user_id = "01HZX3Y9M0E9W7Z6M5QK9S8P7U"
    node = seed_node(
        db_session, user_id, node_id="01HZX3Y9M0E9W7Z6M5QK9S8P7N", workspace_id=DEFAULT_WORKSPACE_ID
    )
    run = seed_run(
        db_session,
        user_id=user_id,
        run_id="01HZX3Y9M0E9W7Z6M5QK9S8P7A",
        node=node,
        workspace_id=DEFAULT_WORKSPACE_ID,
        run_type="debug",
        state="running",
        validity="invalid",
    )
    db_session.commit()
    monkeypatch.setenv("SURGEPILOT_DEBUG_TRACE_BODY_BLOB_TOTAL_MAX_BYTES", "10")
    storage = MemoryStorage()
    monkeypatch.setattr("app.services.runs.get_storage_client", lambda: storage)
    first_payload = b"123456"
    second_payload = b"abcdef"

    first = ingest_run_artifact(
        db_session,
        event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7D",
        run_id=run.id,
        node_id=node.id,
        authenticated_node_id=node.id,
        artifact_type="debug_http_body_blob",
        relative_path="artifacts/debug-http-body-blobs/1-response.bin",
        declared_sha256=hashlib.sha256(first_payload).hexdigest(),
        declared_size_bytes=len(first_payload),
        file=BytesIO(first_payload),
        content_type="text/html",
    )

    assert first.duplicate is False
    with pytest.raises(Exception) as exc_info:
        ingest_run_artifact(
            db_session,
            event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7E",
            run_id=run.id,
            node_id=node.id,
            authenticated_node_id=node.id,
            artifact_type="debug_http_body_blob",
            relative_path="artifacts/debug-http-body-blobs/2-response.bin",
            declared_sha256=hashlib.sha256(second_payload).hexdigest(),
            declared_size_bytes=len(second_payload),
            file=BytesIO(second_payload),
            content_type="text/html",
        )

    assert getattr(exc_info.value, "code", None) == "PAYLOAD_TOO_LARGE"
    assert len(storage.puts) == 1


def test_debug_http_trace_artifact_uses_debug_trace_upload_size_limit(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user_id = "01HZX3Y9M0E9W7Z6M5QK9S8P7U"
    node = seed_node(
        db_session, user_id, node_id="01HZX3Y9M0E9W7Z6M5QK9S8P7N", workspace_id=DEFAULT_WORKSPACE_ID
    )
    run = seed_run(
        db_session,
        user_id=user_id,
        run_id="01HZX3Y9M0E9W7Z6M5QK9S8P7A",
        node=node,
        workspace_id=DEFAULT_WORKSPACE_ID,
        run_type="debug",
        state="running",
        validity="invalid",
    )
    db_session.commit()
    monkeypatch.setenv("SURGEPILOT_DEBUG_TRACE_ARTIFACT_MAX_BYTES", "8")
    storage = MemoryStorage()
    monkeypatch.setattr("app.services.runs.get_storage_client", lambda: storage)
    payload = b"123456789"
    digest = hashlib.sha256(payload).hexdigest()

    with pytest.raises(Exception) as exc_info:
        ingest_run_artifact(
            db_session,
            event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7C",
            run_id=run.id,
            node_id=node.id,
            authenticated_node_id=node.id,
            artifact_type="debug_http_trace",
            relative_path="artifacts/debug-http-trace.jsonl",
            declared_sha256=digest,
            declared_size_bytes=len(payload),
            file=BytesIO(payload),
            content_type="application/jsonl",
        )

    assert getattr(exc_info.value, "code", None) == "PAYLOAD_TOO_LARGE"
    assert storage.puts == []
    assert storage.objects == {}


def test_debug_http_trace_artifact_rejects_standard_or_unsupported_source_runs(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user_id = "01HZX3Y9M0E9W7Z6M5QK9S8P7U"
    node = seed_node(
        db_session, user_id, node_id="01HZX3Y9M0E9W7Z6M5QK9S8P7N", workspace_id=DEFAULT_WORKSPACE_ID
    )
    standard = seed_run(
        db_session,
        user_id=user_id,
        run_id="01HZX3Y9M0E9W7Z6M5QK9S8P7A",
        node=node,
        workspace_id=DEFAULT_WORKSPACE_ID,
        run_type="standard",
        state="running",
    )
    unsupported = seed_run(
        db_session,
        user_id=user_id,
        run_id="01HZX3Y9M0E9W7Z6M5QK9S8P7B",
        node=node,
        workspace_id=DEFAULT_WORKSPACE_ID,
        run_type="debug",
        state="running",
        validity="invalid",
        created_at=datetime.now(UTC) - timedelta(minutes=2),
    )
    unsupported.source_type = "protocol_smoke"
    unsupported.source_id = None
    db_session.commit()
    storage = MemoryStorage()
    monkeypatch.setattr("app.services.runs.get_storage_client", lambda: storage)
    payload = jsonl(trace_row())
    digest = hashlib.sha256(payload).hexdigest()

    for run in [standard, unsupported]:
        with pytest.raises(Exception) as exc_info:
            ingest_run_artifact(
                db_session,
                event_id=f"{run.id[:-1]}C",
                run_id=run.id,
                node_id=node.id,
                artifact_type="debug_http_trace",
                relative_path="artifacts/debug-http-trace.jsonl",
                declared_sha256=digest,
                declared_size_bytes=len(payload),
                file=BytesIO(payload),
                content_type="application/jsonl",
            )
        assert getattr(exc_info.value, "code", None) == "RUNNER_FORBIDDEN"

    assert storage.objects == {}


def test_debug_http_trace_artifact_requires_documented_relative_path(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user_id = "01HZX3Y9M0E9W7Z6M5QK9S8P7U"
    node = seed_node(
        db_session, user_id, node_id="01HZX3Y9M0E9W7Z6M5QK9S8P7N", workspace_id=DEFAULT_WORKSPACE_ID
    )
    run = seed_run(
        db_session,
        user_id=user_id,
        run_id="01HZX3Y9M0E9W7Z6M5QK9S8P7A",
        node=node,
        workspace_id=DEFAULT_WORKSPACE_ID,
        run_type="debug",
        state="running",
        validity="invalid",
    )
    db_session.commit()
    storage = MemoryStorage()
    monkeypatch.setattr("app.services.runs.get_storage_client", lambda: storage)
    payload = jsonl(trace_row())
    digest = hashlib.sha256(payload).hexdigest()

    with pytest.raises(Exception) as exc_info:
        ingest_run_artifact(
            db_session,
            event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7C",
            run_id=run.id,
            node_id=node.id,
            authenticated_node_id=node.id,
            artifact_type="debug_http_trace",
            relative_path="artifacts/alternate-debug-http-trace.jsonl",
            declared_sha256=digest,
            declared_size_bytes=len(payload),
            file=BytesIO(payload),
            content_type="application/jsonl",
        )

    assert getattr(exc_info.value, "code", None) == "INVALID_ARTIFACT_PATH"
    assert storage.objects == {}


def test_debug_http_trace_rejects_terminal_race_after_upload(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    class TerminalAfterPutStorage(MemoryStorage):
        def put_stream(self, *, bucket, object_key, stream, size_limit, content_type=None):  # noqa: ANN001
            result = super().put_stream(
                bucket=bucket,
                object_key=object_key,
                stream=stream,
                size_limit=size_limit,
                content_type=content_type,
            )
            run.state = "finished"
            run.ended_at = datetime.now(UTC)
            db_session.commit()
            return result

    user_id = "01HZX3Y9M0E9W7Z6M5QK9S8P7U"
    node = seed_node(
        db_session, user_id, node_id="01HZX3Y9M0E9W7Z6M5QK9S8P7N", workspace_id=DEFAULT_WORKSPACE_ID
    )
    run = seed_run(
        db_session,
        user_id=user_id,
        run_id="01HZX3Y9M0E9W7Z6M5QK9S8P7A",
        node=node,
        workspace_id=DEFAULT_WORKSPACE_ID,
        run_type="debug",
        state="running",
        validity="invalid",
    )
    db_session.commit()
    storage = TerminalAfterPutStorage()
    monkeypatch.setattr("app.services.runs.get_storage_client", lambda: storage)
    payload = jsonl(trace_row())
    digest = hashlib.sha256(payload).hexdigest()

    with pytest.raises(Exception) as exc_info:
        ingest_run_artifact(
            db_session,
            event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7C",
            run_id=run.id,
            node_id=node.id,
            authenticated_node_id=node.id,
            artifact_type="debug_http_trace",
            relative_path="artifacts/debug-http-trace.jsonl",
            declared_sha256=digest,
            declared_size_bytes=len(payload),
            file=BytesIO(payload),
            content_type="application/jsonl",
        )

    assert getattr(exc_info.value, "code", None) == "RUN_TERMINAL_STATE"
    assert storage.objects == {}


def seed_debug_scenario_run(db_session: Session, *, run_type: str = "debug") -> str:
    run_id = "01HZX3Y9M0E9W7Z6M5QK9S8P7D"
    now = datetime.now(UTC)
    db_session.add(
        Run(
            id=run_id,
            workspace_id=DEFAULT_WORKSPACE_ID,
            run_type=run_type,
            state="initializing",
            source_type="debug_scenario",
            source_id="01HZX3Y9M0E9W7Z6M5QK9S8P7S",
            selected_node_id="01HZX3Y9M0E9W7Z6M5QK9S8P7N",
            triggered_by_user_id="01HZX3Y9M0E9W7Z6M5QK9S8P7U",
            forced_convergence=False,
            validity="invalid" if run_type == "debug" else "valid",
            created_at=now,
            updated_at=now,
        )
    )
    db_session.add(
        RunSnapshot(
            id="01HZX3Y9M0E9W7Z6M5QK9S8P7E",
            workspace_id=DEFAULT_WORKSPACE_ID,
            run_id=run_id,
            snapshot_version=1,
            snapshot_hash="b" * 64,
            snapshot_json={
                "schemaVersion": 1,
                "runType": run_type,
                "sourceType": "debug_scenario",
                "sourceId": "01HZX3Y9M0E9W7Z6M5QK9S8P7S",
                "sourceRevision": 1,
                "scenario": {
                    "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7S",
                    "name": "Trace scenario",
                    "scenarioType": "visual",
                    "baseUrlExpression": "https://api.example.test",
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
                    "steps": [
                        {
                            "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7G",
                            "enabled": True,
                            "name": "Login",
                            "method": "POST",
                            "path": "/login",
                            "queryParams": [],
                            "headers": [],
                            "body": {
                                "type": "raw",
                                "contentType": "application/json",
                                "rawText": "{}",
                                "formFields": [],
                            },
                            "uploadFiles": [],
                            "extractors": [],
                            "assertions": [],
                            "scripts": [],
                            "settings": {},
                        }
                    ],
                },
                "envGroup": None,
                "dependencyFiles": [],
            },
            created_at=now,
        )
    )
    db_session.commit()
    return run_id


def test_debug_scenario_bundle_injects_inline_jsr223(db_session: Session) -> None:
    run_id = seed_debug_scenario_run(db_session)

    files = build_debug_scenario_execution_bundle(
        db_session,
        run_id=run_id,
        runner_home="/runner",
        settings=replace(
            get_settings(),
            debug_trace_max_requests=17,
            debug_trace_body_max_bytes=1234,
            debug_trace_artifact_max_bytes=5678,
            debug_trace_record_max_bytes=2468,
            debug_trace_body_blob_max_bytes=1357,
            debug_trace_body_blob_total_max_bytes=9753,
        ),
    )

    yaml_text = next(
        file.content for file in files if file.relative_path == "surgepilot.yml"
    ).decode()
    document = yaml.safe_load(yaml_text)
    scenario = next(iter(document["scenarios"].values()))
    request = scenario["requests"][0]
    script_text = request["jsr223"]["script-text"]
    assert request["jsr223"]["language"] == "groovy"
    assert request["jsr223"]["execute"] == "after"
    assert "script-text" in request["jsr223"]
    assert "jsr223:" in yaml_text
    assert "script-text:" in yaml_text
    assert "language: groovy" in yaml_text
    assert "artifacts/debug-http-trace.jsonl" in yaml_text
    assert "int maxRequests = 17" in yaml_text
    assert "int bodyMaxBytes = 1234" in yaml_text
    assert "long artifactMaxBytes = 5678L" in script_text
    assert "int recordMaxBytes = 2468" in script_text
    assert "int bodyBlobMaxBytes = 1357" in script_text
    assert "long bodyBlobTotalMaxBytes = 9753L" in script_text
    assert "JsonSlurper" in yaml_text
    assert "redactJson" in yaml_text
    assert "markTraceTruncated" in yaml_text
    assert "sanitizeFreeText" in yaml_text
    assert "bearer|basic|digest" in yaml_text
    assert "authorization|x-api-key" in yaml_text
    assert "cookie|set-cookie" in yaml_text
    assert "getRawFragment" in yaml_text
    assert "sanitizeUrlComponentValue" in yaml_text
    assert "sanitizeFreeText(header.getValue())" in yaml_text
    assert "sanitizeStringValue" in yaml_text
    assert "return sanitizeStringValue(raw)" in yaml_text
    assert "raw.replaceAll(/https?:\\/\\/" in script_text
    assert "decodeDepth < 3" in yaml_text
    assert "prev.getResponseData()" in yaml_text
    assert "prev.getResponseDataAsString()" not in yaml_text
    assert "bodyTruncated: requestBody.bodyTruncated || responseBody.bodyTruncated" in yaml_text
    assert "looksPreviewableBytes" in yaml_text
    assert "CodingErrorAction.REPORT" in yaml_text
    assert "ByteBuffer.wrap(bytes)" in yaml_text
    assert "value == 127" in yaml_text
    assert "value >= 128 && value <= 159" in yaml_text
    assert "shouldPreviewBody" in yaml_text
    assert "def responsePayload = prev.getResponseData()" in yaml_text
    assert "catch (Throwable traceError)" in script_text
    assert "Debug HTTP trace capture failed" in script_text
    assert "raw.contains('=')" in yaml_text
    assert "!raw.contains" in yaml_text
    assert "reservedArtifactMaxBytes" in yaml_text
    assert " > reservedArtifactMaxBytes" in yaml_text
    assert "artifacts/debug-http-body-blobs" in yaml_text
    assert "bodyStorage: 'sidecar'" in script_text
    assert "bodyStorage: 'dropped'" in script_text
    assert "downloadRelativePath" in script_text
    assert "record_too_large" in script_text
    assert "body_too_large" in script_text
    assert "sidecar_budget_exceeded" in script_text
    assert "blobFile.bytes = safeBytes" in script_text
    assert "sizeBytes: safeBytes.length" in script_text
    assert "sha256Prefix: sha256Prefix(safeBytes)" in script_text
    assert "sha256Prefix: sha256Prefix(bytes)" in script_text
    assert "encodedRow.getBytes('UTF-8').length > recordMaxBytes" in script_text
    assert "script-file" not in yaml_text


def test_standard_test_plan_bundle_excludes_debug_trace(db_session: Session) -> None:
    user_id = "01HZX3Y9M0E9W7Z6M5QK9S8P7U"
    node = seed_node(
        db_session,
        user_id,
        node_id="01HZX3Y9M0E9W7Z6M5QK9S8P7N",
        workspace_id=DEFAULT_WORKSPACE_ID,
    )
    run_id = "01HZX3Y9M0E9W7Z6M5QK9S8P7S"
    now = datetime.now(UTC)
    db_session.add(
        Run(
            id=run_id,
            workspace_id=DEFAULT_WORKSPACE_ID,
            run_type="standard",
            state="initializing",
            source_type="test_plan",
            source_id="01HZX3Y9M0E9W7Z6M5QK9S8P7P",
            selected_node_id=node.id,
            triggered_by_user_id=user_id,
            forced_convergence=False,
            validity="valid",
            created_at=now,
            updated_at=now,
        )
    )
    db_session.add(
        RunSnapshot(
            id="01HZX3Y9M0E9W7Z6M5QK9S8P7Q",
            workspace_id=DEFAULT_WORKSPACE_ID,
            run_id=run_id,
            snapshot_version=1,
            snapshot_hash="d" * 64,
            snapshot_json={
                "schemaVersion": 1,
                "runType": "standard",
                "sourceType": "test_plan",
                "sourceId": "01HZX3Y9M0E9W7Z6M5QK9S8P7P",
                "sourceRevision": 1,
                "testPlan": {
                    "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7P",
                    "name": "Plan",
                    "revision": 1,
                    "runMode": "sequential",
                },
                "envGroup": None,
                "scenarioItems": [
                    {
                        "itemId": "01HZX3Y9M0E9W7Z6M5QK9S8P7I",
                        "order": 0,
                        "scenarioId": "01HZX3Y9M0E9W7Z6M5QK9S8P7V",
                        "scenarioRevision": 1,
                        "scenarioName": "Scenario",
                        "loadSettings": {
                            "concurrencyPerNode": 1,
                            "rampUpSeconds": 0,
                            "holdForSeconds": None,
                            "iterations": 1,
                            "targetRps": None,
                            "steps": None,
                            "delaySeconds": 0,
                        },
                        "visualScenario": {
                            "requests": [
                                {
                                    "label": "GET /health",
                                    "method": "GET",
                                    "url": "https://api.example.test/health",
                                }
                            ]
                        },
                    }
                ],
                "dependencyFiles": [],
                "slaRules": [],
            },
            created_at=now,
        )
    )
    db_session.commit()

    files = build_test_plan_execution_bundle(
        db_session,
        run_id=run_id,
        runner_home="/runner",
        settings=get_settings(),
    )

    yaml_text = next(
        file.content for file in files if file.relative_path == "surgepilot.yml"
    ).decode()
    assert "debug-http-trace" not in yaml_text
    assert "jsr223" not in yaml_text


def test_debug_test_plan_bundle_injects_inline_jsr223(db_session: Session) -> None:
    user_id = "01HZX3Y9M0E9W7Z6M5QK9S8P7U"
    node = seed_node(
        db_session,
        user_id,
        node_id="01HZX3Y9M0E9W7Z6M5QK9S8P7N",
        workspace_id=DEFAULT_WORKSPACE_ID,
    )
    run_id = "01HZX3Y9M0E9W7Z6M5QK9S8P7T"
    now = datetime.now(UTC)
    db_session.add(
        Run(
            id=run_id,
            workspace_id=DEFAULT_WORKSPACE_ID,
            run_type="debug",
            state="initializing",
            source_type="test_plan",
            source_id="01HZX3Y9M0E9W7Z6M5QK9S8P7P",
            selected_node_id=node.id,
            triggered_by_user_id=user_id,
            forced_convergence=False,
            validity="invalid",
            created_at=now,
            updated_at=now,
        )
    )
    db_session.add(
        RunSnapshot(
            id="01HZX3Y9M0E9W7Z6M5QK9S8P7U",
            workspace_id=DEFAULT_WORKSPACE_ID,
            run_id=run_id,
            snapshot_version=1,
            snapshot_hash="e" * 64,
            snapshot_json={
                "schemaVersion": 1,
                "runType": "debug",
                "sourceType": "test_plan",
                "sourceId": "01HZX3Y9M0E9W7Z6M5QK9S8P7P",
                "sourceRevision": 1,
                "testPlan": {
                    "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7P",
                    "name": "Debug Plan",
                    "revision": 1,
                    "runMode": "sequential",
                },
                "envGroup": None,
                "scenarioItems": [
                    {
                        "itemId": "01HZX3Y9M0E9W7Z6M5QK9S8P7I",
                        "order": 0,
                        "scenarioId": "01HZX3Y9M0E9W7Z6M5QK9S8P7V",
                        "scenarioRevision": 1,
                        "scenarioName": "Scenario",
                        "loadSettings": {
                            "concurrencyPerNode": 1,
                            "rampUpSeconds": 0,
                            "holdForSeconds": None,
                            "iterations": 1,
                            "targetRps": None,
                            "steps": None,
                            "delaySeconds": 0,
                        },
                        "visualScenario": {
                            "requests": [
                                {
                                    "label": "POST /login",
                                    "method": "POST",
                                    "url": "https://api.example.test/login",
                                    "headers": {"Authorization": "Bearer token"},
                                    "body": "{}",
                                }
                            ]
                        },
                    }
                ],
                "dependencyFiles": [],
                "slaRules": [],
            },
            created_at=now,
        )
    )
    db_session.commit()

    files = build_test_plan_execution_bundle(
        db_session,
        run_id=run_id,
        runner_home="/runner",
        settings=get_settings(),
    )

    yaml_text = next(
        file.content for file in files if file.relative_path == "surgepilot.yml"
    ).decode()
    assert "jsr223:" in yaml_text
    assert "script-text:" in yaml_text
    assert "language: groovy" in yaml_text
    assert "artifacts/debug-http-trace.jsonl" in yaml_text
    assert "script-file" not in yaml_text
