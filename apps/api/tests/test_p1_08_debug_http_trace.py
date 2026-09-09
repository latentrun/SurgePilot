import json
from io import BytesIO

from app.services.debug_http_trace import parse_debug_http_trace_jsonl


def trace_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "schemaVersion": 1,
        "sequence": 1,
        "label": "Login",
        "url": "https://user:pass@example.test/login?api_key=query-secret&safe=ok",
        "method": "post",
        "requestHeaders": {"Authorization": "Bearer secret-token", "X-Trace": "safe"},
        "requestBody": {
            "contentType": "application/json",
            "text": '{"username":"alice","password":"open-sesame"}',
        },
        "responseStatus": 401,
        "responseHeaders": {"Set-Cookie": "session=secret"},
        "responseBody": {"contentType": "application/json", "text": '{"token":"abc"}'},
        "durationMs": 123,
        "error": "password=open-sesame",
    }
    row.update(overrides)
    return row


def jsonl(*rows: dict[str, object]) -> BytesIO:
    payload = "\n".join(json.dumps(row) for row in rows) + "\n"
    return BytesIO(payload.encode())


def test_debug_trace_parser_redacts_urls_headers_bodies_and_errors() -> None:
    result = parse_debug_http_trace_jsonl(
        jsonl(trace_row()),
        source_artifact_id="01HZX3Y9M0E9W7Z6M5QK9S8P7A",
        max_requests=100,
        body_max_bytes=64 * 1024,
        artifact_max_bytes=10 * 1024 * 1024,
    )

    assert result.status == "available"
    entry = result.entries[0]
    assert entry.method == "POST"
    assert entry.request_headers["Authorization"] == "[REDACTED]"
    assert "query-secret" not in entry.url
    assert "open-sesame" not in (entry.request_body.text or "")
    assert "abc" not in (entry.response_body.text or "")
    assert "open-sesame" not in (entry.error or "")


def test_debug_trace_parser_handles_malformed_lines_and_request_limit() -> None:
    payload = b"not-json\n" + b"\n".join(
        json.dumps(trace_row(sequence=index)).encode() for index in range(1, 4)
    ) + b"\n"
    result = parse_debug_http_trace_jsonl(
        BytesIO(payload),
        source_artifact_id="01HZX3Y9M0E9W7Z6M5QK9S8P7A",
        max_requests=2,
        body_max_bytes=64 * 1024,
        artifact_max_bytes=10 * 1024 * 1024,
    )

    assert result.status == "available"
    assert result.entry_count == 2
    assert result.trace_truncated is True
    assert "debug_http_trace_line_parse_failed" in result.warnings


def test_debug_trace_parser_returns_safe_unavailable_result_when_artifact_is_too_large() -> None:
    result = parse_debug_http_trace_jsonl(
        jsonl(trace_row()),
        source_artifact_id="01HZX3Y9M0E9W7Z6M5QK9S8P7A",
        max_requests=100,
        body_max_bytes=64 * 1024,
        artifact_max_bytes=8,
    )

    assert result.status == "unavailable"
    assert result.entries == []
    assert result.warnings == ["debug_http_trace_too_large"]


def test_debug_trace_parser_keeps_binary_body_as_metadata_only() -> None:
    result = parse_debug_http_trace_jsonl(
        jsonl(
            trace_row(
                requestBody={
                    "contentType": "application/octet-stream",
                    "sizeBytes": 1024,
                    "sha256Prefix": "abcdef1234567890",
                }
            )
        ),
        source_artifact_id="01HZX3Y9M0E9W7Z6M5QK9S8P7A",
        max_requests=100,
        body_max_bytes=64 * 1024,
        artifact_max_bytes=10 * 1024 * 1024,
    )

    body = result.entries[0].request_body
    assert body.text is None
    assert body.body_storage == "dropped"
    assert body.size_bytes == 1024
    assert body.sha256_prefix == "abcdef1234567890"
