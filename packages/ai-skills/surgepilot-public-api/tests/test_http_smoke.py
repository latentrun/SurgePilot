from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import io
import json
from pathlib import Path
import sys
from threading import Thread
from urllib.error import HTTPError, URLError

import pytest


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
CALLER_PATH = PACKAGE_ROOT / "scripts/surgepilot_call.py"


def load_caller():
    assert CALLER_PATH.exists(), "Public API skill caller must exist."
    spec = importlib.util.spec_from_file_location("surgepilot_public_api_caller", CALLER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def caller():
    return load_caller()


def build_read(caller, base_url: str):
    return caller.build_request(
        "publicListScenarios",
        base_url=base_url,
        token="surgepilot_pat_smoke_secret",
        workspace_id="01JWORKSPACE00000000000000",
        path_params={},
        query_params={"page": 2, "tag": ["smoke", "api"]},
        body=None,
    )


def test_execute_request_calls_public_api_once_with_expected_headers(caller) -> None:
    captured: dict[str, str] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            captured["path"] = self.path
            captured["authorization"] = self.headers["Authorization"]
            captured["workspace"] = self.headers["x-workspace-id"]
            payload = json.dumps({"items": [], "page": 2, "pageSize": 20, "total": 0}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, _format: str, *_args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = build_read(caller, f"http://127.0.0.1:{server.server_port}")
        result = caller.execute_request(request)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert result["status"] == 200
    assert result["data"]["items"] == []
    assert captured == {
        "path": "/api/public/v1/scenarios?page=2&tag=smoke&tag=api",
        "authorization": "Bearer surgepilot_pat_smoke_secret",
        "workspace": "01JWORKSPACE00000000000000",
    }


def test_execute_request_refuses_redirect_without_forwarding_credentials(caller) -> None:
    forwarded: list[dict[str, str | None]] = []

    class SinkHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            forwarded.append(
                {
                    "authorization": self.headers.get("Authorization"),
                    "workspace": self.headers.get("x-workspace-id"),
                }
            )
            payload = json.dumps({"items": [], "page": 2, "pageSize": 20, "total": 0}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, _format: str, *_args: object) -> None:
            return

    sink = ThreadingHTTPServer(("127.0.0.1", 0), SinkHandler)

    class RedirectHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            self.send_response(302)
            self.send_header("Location", f"http://127.0.0.1:{sink.server_port}/steal")
            self.end_headers()

        def log_message(self, _format: str, *_args: object) -> None:
            return

    redirect = ThreadingHTTPServer(("127.0.0.1", 0), RedirectHandler)
    threads = [
        Thread(target=sink.serve_forever, daemon=True),
        Thread(target=redirect.serve_forever, daemon=True),
    ]
    for thread in threads:
        thread.start()
    try:
        request = build_read(caller, f"http://127.0.0.1:{redirect.server_port}")
        with pytest.raises(caller.ContractSafetyError, match="status 302"):
            caller.execute_request(request)
    finally:
        redirect.shutdown()
        sink.shutdown()
        redirect.server_close()
        sink.server_close()
        for thread in threads:
            thread.join(timeout=5)

    assert forwarded == []


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (400, "WORKSPACE_REQUIRED"),
        (401, "UNAUTHENTICATED"),
        (403, "PUBLIC_TOKEN_SCOPE_DENIED"),
        (409, "RUN_TERMINAL_STATE"),
        (422, "VALIDATION_ERROR"),
    ],
)
def test_execute_request_fails_closed_without_retry_or_fallback(
    caller, status: int, code: str
) -> None:
    calls = 0
    body = json.dumps(
        {
            "code": code,
            "message": "Public API request failed.",
            "requestId": "req_public_error",
            "details": None,
        }
    ).encode()

    def opener(request, timeout):
        nonlocal calls
        calls += 1
        raise HTTPError(request.full_url, status, "failed", {}, io.BytesIO(body))

    if status == 409:
        request = caller.build_request(
            "publicStopRun",
            base_url="https://surgepilot.example.com",
            token="surgepilot_pat_smoke_secret",
            workspace_id="01JWORKSPACE00000000000000",
            path_params={"runId": "01JRUN0000000000000000000"},
            query_params={},
            body=None,
        )
    else:
        request = build_read(caller, "https://surgepilot.example.com")

    with pytest.raises(caller.PublicApiError) as error:
        caller.execute_request(request, opener=opener)

    assert calls == 1
    assert error.value.status == status
    assert error.value.code == code


def test_execute_request_rejects_forbidden_response_fields(caller) -> None:
    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self) -> bytes:
            return b'{"runnerToken":"must-not-leak"}'

    request = build_read(caller, "https://surgepilot.example.com")

    with pytest.raises(caller.ContractSafetyError, match="runnerToken"):
        caller.execute_request(request, opener=lambda *_args, **_kwargs: Response())


def test_execute_request_validates_declared_json_response(caller) -> None:
    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self) -> bytes:
            return b'{"items":[],"page":2,"pageSize":20,"total":0}'

    request = build_read(caller, "https://surgepilot.example.com")
    result = caller.execute_request(request, opener=lambda *_args, **_kwargs: Response())

    assert result["data"]["items"] == []


def test_execute_request_rejects_undeclared_status_and_schema_mismatch(caller) -> None:
    class Response:
        def __init__(self, status: int, payload: bytes) -> None:
            self.status = status
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self) -> bytes:
            return self.payload

    request = build_read(caller, "https://surgepilot.example.com")

    with pytest.raises(caller.ContractSafetyError, match="status 204"):
        caller.execute_request(request, opener=lambda *_args, **_kwargs: Response(204, b""))
    with pytest.raises(caller.ContractSafetyError, match="does not match"):
        caller.execute_request(
            request, opener=lambda *_args, **_kwargs: Response(200, b'{"items":[]}')
        )


def test_execute_request_rejects_actual_pat_in_response_value(caller) -> None:
    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self) -> bytes:
            return (
                b'{"items":[],"page":2,"pageSize":20,"total":0,'
                b'"notice":"received Bearer surgepilot_pat_smoke_secret"}'
            )

    request = build_read(caller, "https://surgepilot.example.com")

    with pytest.raises(caller.ContractSafetyError, match="credential"):
        caller.execute_request(request, opener=lambda *_args, **_kwargs: Response())


def test_execute_request_rejects_actual_pat_in_response_keys_without_echo(caller) -> None:
    token = "surgepilot_pat_smoke_secret"
    success_payload = {
        "id": "01JENVGROUP000000000000000",
        "name": "Production",
        "variableCount": 1,
        "inUse": False,
        "createdBy": "01JUSER0000000000000000000",
        "updatedBy": "01JUSER0000000000000000000",
        "createdAt": "2030-07-13T00:00:00Z",
        "updatedAt": "2030-07-13T00:00:00Z",
        "variables": {token: {"type": "plain", "value": "hidden"}},
    }

    class Response:
        status = 201

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self) -> bytes:
            return json.dumps(success_payload).encode()

    request = caller.build_request(
        "publicCreateEnvGroup",
        base_url="https://surgepilot.example.com",
        token=token,
        workspace_id="01JWORKSPACE00000000000000",
        path_params={},
        query_params={},
        body={"name": "Production", "variables": {}},
    )

    with pytest.raises(caller.ContractSafetyError, match="credential") as success_error:
        caller.execute_request(request, opener=lambda *_args, **_kwargs: Response())
    assert token not in str(success_error.value)

    error_payload = json.dumps(
        {
            "code": "VALIDATION_ERROR",
            "message": "Validation failed.",
            "requestId": "req_public_error",
            token: "must-not-echo",
        }
    ).encode()

    def error_opener(http_request, timeout):
        raise HTTPError(http_request.full_url, 422, "failed", {}, io.BytesIO(error_payload))

    with pytest.raises(caller.ContractSafetyError, match="credential") as error:
        caller.execute_request(request, opener=error_opener)
    assert token not in str(error.value)


def test_execute_request_rejects_non_json_and_nested_forbidden_fields(caller) -> None:
    class Response:
        status = 200

        def __init__(self, payload: bytes) -> None:
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self) -> bytes:
            return self.payload

    request = build_read(caller, "https://surgepilot.example.com")

    with pytest.raises(caller.ContractSafetyError, match="non-JSON"):
        caller.execute_request(request, opener=lambda *_args, **_kwargs: Response(b"not-json"))
    with pytest.raises(caller.ContractSafetyError, match="objectKey"):
        caller.execute_request(
            request,
            opener=lambda *_args, **_kwargs: Response(b'[{"objectKey":"hidden"}]'),
        )


@pytest.mark.parametrize(
    "payload",
    [
        b"[]",
        b'{"message":123,"code":null}',
    ],
)
def test_execute_request_rejects_invalid_error_contract(caller, payload: bytes) -> None:
    def opener(request, timeout):
        raise HTTPError(request.full_url, 422, "failed", {}, io.BytesIO(payload))

    request = build_read(caller, "https://surgepilot.example.com")

    with pytest.raises(caller.ContractSafetyError, match="does not match"):
        caller.execute_request(request, opener=opener)


def test_execute_request_reports_network_error_without_retry(caller) -> None:
    calls = 0

    def opener(_request, timeout):
        nonlocal calls
        calls += 1
        raise URLError("offline")

    request = build_read(caller, "https://surgepilot.example.com")

    with pytest.raises(caller.NetworkRequestError, match="without retry"):
        caller.execute_request(request, opener=opener)

    assert calls == 1
