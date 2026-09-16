from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
SCRIPT_PATH = SCRIPT_DIR / "verify_p2_02_public_api_lifecycle.py"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
spec = importlib.util.spec_from_file_location("verify_p2_02_public_api_lifecycle", SCRIPT_PATH)
assert spec is not None and spec.loader is not None
lifecycle = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = lifecycle
spec.loader.exec_module(lifecycle)


def test_parse_args_defaults_to_cleanup_data() -> None:
    args = lifecycle.parse_args([])

    assert args.data_mode == "cleanup"
    assert args.keep_stack is False


def test_parse_args_supports_retain_data() -> None:
    args = lifecycle.parse_args(["--retain-data"])

    assert args.data_mode == "retain"
    assert args.keep_stack is True


def test_archive_path_uses_tmp_e2e_results_and_sanitized_run_id(tmp_path: Path) -> None:
    archive = lifecycle.archive_path(root=tmp_path, run_id="01ABC/unsafe")

    assert archive.parent == tmp_path
    assert "public-api-lifecycle-01ABC-unsafe" in archive.name


def test_write_archive_records_retain_metadata(tmp_path: Path) -> None:
    summary = lifecycle.LifecycleSummary(
        email="public@example.com",
        workspace_id="01JWORKSPACE00000000000000",
        token_public_ids=["pat_public_1"],
        run_id="01JRUN0000000000000000000",
        mode="retain",
    )

    archive = lifecycle.write_archive(summary, root=tmp_path)

    summary_file = archive / "summary.json"
    assert summary_file.exists()
    text = summary_file.read_text()
    assert "public@example.com" in text
    assert "pat_public_1" in text
    assert "plaintext" not in text.lower()


def test_cleanup_mode_revokes_created_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    revoked: list[str] = []
    session = object()
    summary = lifecycle.LifecycleSummary(
        email="public@example.com",
        workspace_id="01JWORKSPACE00000000000000",
        token_public_ids=["public-read"],
        run_id="01JRUN0000000000000000000",
        mode="cleanup",
        token_ids=["token-1", "token-2"],
    )

    monkeypatch.setattr(
        lifecycle, "delete_session_resource", lambda _session, path: revoked.append(path)
    )

    lifecycle.cleanup_created_data(session, summary)

    assert revoked == ["/api/v1/account/api-tokens/token-1", "/api/v1/account/api-tokens/token-2"]


def test_create_setup_load_node_scans_and_confirms_ssh_host_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = object()
    scanned = {
        "algorithm": "ssh-ed25519",
        "publicKey": "AAAAC3NzaC1lZDI1NTE5AAAAITest",
        "fingerprintSha256": "SHA256:test",
    }
    payloads: list[dict] = []
    initialized: list[str] = []

    monkeypatch.setattr(
        lifecycle.base,
        "scan_load_node_ssh_host_key",
        lambda actual_session, *, host, ssh_port: (
            scanned
            if actual_session is session
            and host == lifecycle.base.NODE_SSH_HOST
            and ssh_port == lifecycle.base.NODE_SSH_PORT
            else pytest.fail("unexpected SSH host key scan inputs")
        ),
    )
    monkeypatch.setattr(
        lifecycle.base,
        "load_node_payload",
        lambda ssh_host_key=None: {"sshHostKey": ssh_host_key},
    )
    monkeypatch.setattr(
        lifecycle.base,
        "create_json",
        lambda actual_session, path, payload: (
            payloads.append(payload) or {"id": "01JNODE0000000000000000000"}
            if actual_session is session and path == "/api/v1/load-nodes"
            else pytest.fail("unexpected Load Node create inputs")
        ),
    )
    monkeypatch.setattr(
        lifecycle.base,
        "initialize_node",
        lambda actual_session, node_id: (
            initialized.append(node_id)
            if actual_session is session
            else pytest.fail("unexpected initialize inputs")
        ),
    )

    node = lifecycle.create_setup_load_node(session)

    assert node["id"] == "01JNODE0000000000000000000"
    assert payloads == [{"sshHostKey": scanned}]
    assert initialized == ["01JNODE0000000000000000000"]
