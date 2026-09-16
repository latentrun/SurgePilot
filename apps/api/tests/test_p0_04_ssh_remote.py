from __future__ import annotations

from dataclasses import replace

import pytest

from app.services.load_nodes import CredentialPlaintext
from app.services.ssh_remote import (
    ParamikoSshSftpAdapter,
    scan_ssh_host_key,
    SshHostKeyChangedError,
    SshHostKeyUntrustedError,
    SshTarget,
    trusted_known_hosts_line,
)

TRUSTED_HOST_KEY_PUBLIC_KEY = "AAAAC3NzaC1lZDI1NTE5AAAAIF6W/+2uAKbK71edPOwIYEGmhaggGtRy5wu0lXPVysEC"
TRUSTED_HOST_KEY_FINGERPRINT = "SHA256:O2aKxyafGFKzfLtx65+fWrT6LeEGX77is7PwJuuzXdc"


class FakeChannel:
    def __init__(
        self,
        *,
        stdout_chunks: list[bytes] | None = None,
        stderr_chunks: list[bytes] | None = None,
        exit_status: int = 0,
        ready_after_drains: int = 1,
    ) -> None:
        self.stdout_chunks = stdout_chunks or []
        self.stderr_chunks = stderr_chunks or []
        self.exit_status = exit_status
        self.ready_after_drains = ready_after_drains
        self.drain_count = 0
        self.closed = False

    def exit_status_ready(self) -> bool:
        return self.drain_count >= self.ready_after_drains

    def recv_ready(self) -> bool:
        return bool(self.stdout_chunks)

    def recv(self, _size: int) -> bytes:
        self.drain_count += 1
        return self.stdout_chunks.pop(0)

    def recv_stderr_ready(self) -> bool:
        return bool(self.stderr_chunks)

    def recv_stderr(self, _size: int) -> bytes:
        self.drain_count += 1
        return self.stderr_chunks.pop(0)

    def recv_exit_status(self) -> int:
        return self.exit_status

    def close(self) -> None:
        self.closed = True


class FakeStdout:
    def __init__(self, channel: FakeChannel) -> None:
        self.channel = channel


class FakeClient:
    def __init__(self, channel: FakeChannel) -> None:
        self.channel = channel
        self.commands: list[str] = []

    def __enter__(self) -> FakeClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def exec_command(self, command: str, *, get_pty: bool) -> tuple[None, FakeStdout, None]:
        self.commands.append(command)
        return None, FakeStdout(self.channel), None


class FakeParamikoAdapter(ParamikoSshSftpAdapter):
    def __init__(self, client: FakeClient) -> None:
        self.client = client

    def _client(self, target: SshTarget) -> FakeClient:
        return self.client


class FakeHostKey:
    def get_name(self) -> str:
        return "ssh-ed25519"

    def asbytes(self) -> bytes:
        return b"fake-host-key"


def target() -> SshTarget:
    return SshTarget(
        host="node.example.test",
        port=22,
        username="surgepilot",
        credential=CredentialPlaintext(auth_type="password", password="ssh-password"),
        connect_timeout_seconds=3,
        trusted_host_key_algorithm="ssh-ed25519",
        trusted_host_key_public_key=TRUSTED_HOST_KEY_PUBLIC_KEY,
        trusted_host_key_fingerprint_sha256=TRUSTED_HOST_KEY_FINGERPRINT,
    )


def test_paramiko_run_command_drains_channel_previews_without_stream_read() -> None:
    channel = FakeChannel(
        stdout_chunks=[b"hello ", b"world"],
        stderr_chunks=[b"token=secret-value"],
        exit_status=2,
        ready_after_drains=3,
    )
    client = FakeClient(channel)
    adapter = FakeParamikoAdapter(client)

    result = adapter.run_command(
        target(), command="printf hello", timeout_seconds=5, output_limit_bytes=4096
    )

    assert result.ok is False
    assert result.exit_status == 2
    assert result.stdout_preview == "hello world"
    assert result.stderr_preview == "token[REDACTED]"
    assert client.commands == ["printf hello"]


def test_paramiko_run_command_closes_channel_on_timeout() -> None:
    channel = FakeChannel(stdout_chunks=[b"partial"], ready_after_drains=999)
    client = FakeClient(channel)
    adapter = FakeParamikoAdapter(client)

    result = adapter.run_command(target(), command="sleep 60", timeout_seconds=0)

    assert result.ok is False
    assert result.timed_out is True
    assert result.exit_status is None
    assert result.stdout_preview == "partial"
    assert result.stderr_preview == "Remote command timed out."
    assert channel.closed is True


def test_paramiko_run_command_bounds_preview_bytes() -> None:
    channel = FakeChannel(stdout_chunks=[b"0123456789abcdef"], ready_after_drains=1)
    adapter = FakeParamikoAdapter(FakeClient(channel))

    result = adapter.run_command(
        target(), command="large-output", timeout_seconds=5, output_limit_bytes=8
    )

    assert result.ok is True
    assert result.stdout_preview == "01234567"


class FakeRemoteFile:
    def __init__(self) -> None:
        self.content = b""

    def __enter__(self) -> FakeRemoteFile:
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def write(self, content: bytes) -> None:
        self.content += content


class FakeSftp:
    def __init__(self) -> None:
        self.created_dirs: list[str] = []
        self.files: dict[str, FakeRemoteFile] = {}
        self.modes: dict[str, int] = {}

    def __enter__(self) -> FakeSftp:
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def stat(self, path: str) -> None:
        if path not in self.created_dirs:
            raise OSError("missing")

    def mkdir(self, path: str) -> None:
        self.created_dirs.append(path)

    def file(self, path: str, _mode: str) -> FakeRemoteFile:
        remote_file = FakeRemoteFile()
        self.files[path] = remote_file
        return remote_file

    def chmod(self, path: str, mode: int) -> None:
        self.modes[path] = mode


class FakeSftpClient(FakeClient):
    def __init__(self, sftp: FakeSftp) -> None:
        super().__init__(FakeChannel())
        self.sftp = sftp

    def open_sftp(self) -> FakeSftp:
        return self.sftp


def test_paramiko_upload_text_creates_parent_directories_and_sets_mode() -> None:
    sftp = FakeSftp()
    adapter = FakeParamikoAdapter(FakeSftpClient(sftp))

    adapter.upload_text(
        target(), remote_path="/opt/surgepilot/runner/.env", content="KEY=value", mode=0o600
    )

    assert sftp.created_dirs == ["/opt", "/opt/surgepilot", "/opt/surgepilot/runner"]
    assert sftp.files["/opt/surgepilot/runner/.env"].content == b"KEY=value"
    assert sftp.modes["/opt/surgepilot/runner/.env"] == 0o600


def test_paramiko_client_configures_password_auth_with_memory_host_keys_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services import ssh_remote

    class RecordingSshClient:
        def __init__(self) -> None:
            self.policy = None
            self.connect_kwargs: dict[str, object] | None = None
            self.host_keys = ssh_remote.paramiko.HostKeys()
            self.system_host_keys_loaded = False
            self.host_key_paths: list[str] = []

        def load_system_host_keys(self) -> None:
            self.system_host_keys_loaded = True

        def load_host_keys(self, filename: str) -> None:
            self.host_key_paths.append(filename)

        def get_host_keys(self) -> object:
            return self.host_keys

        def set_missing_host_key_policy(self, policy: object) -> None:
            self.policy = policy

        def connect(self, **kwargs: object) -> None:
            self.connect_kwargs = kwargs

    client = RecordingSshClient()
    monkeypatch.setattr(ssh_remote.paramiko, "SSHClient", lambda: client)
    returned = ParamikoSshSftpAdapter()._client(target())

    assert returned is client
    assert client.system_host_keys_loaded is False
    assert client.host_key_paths == []
    assert client.host_keys.lookup("node.example.test") is not None
    assert isinstance(client.policy, ssh_remote.paramiko.RejectPolicy)
    assert client.connect_kwargs is not None
    assert client.connect_kwargs["hostname"] == "node.example.test"
    assert client.connect_kwargs["port"] == 22
    assert client.connect_kwargs["username"] == "surgepilot"
    assert client.connect_kwargs["password"] == "ssh-password"
    assert client.connect_kwargs["look_for_keys"] is False
    assert client.connect_kwargs["allow_agent"] is False


def test_trusted_known_hosts_line_uses_node_host_key_data() -> None:
    assert (
        trusted_known_hosts_line(
            host="Node.EXAMPLE.test",
            algorithm="ssh-ed25519",
            public_key="AAAAC3NzaC1lZDI1NTE5AAAAIF6W/+2uAKbK71edPOwIYEGmhaggGtRy5wu0lXPVysEC",
        )
        == "node.example.test ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIF6W/+2uAKbK71edPOwIYEGmhaggGtRy5wu0lXPVysEC"
    )


def test_trusted_known_hosts_line_uses_bracketed_host_for_non_default_port() -> None:
    assert (
        trusted_known_hosts_line(
            host="Node.EXAMPLE.test",
            port=2222,
            algorithm="ssh-ed25519",
            public_key="AAAAC3NzaC1lZDI1NTE5AAAAIF6W/+2uAKbK71edPOwIYEGmhaggGtRy5wu0lXPVysEC",
        )
        == "[node.example.test]:2222 ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIF6W/+2uAKbK71edPOwIYEGmhaggGtRy5wu0lXPVysEC"
    )


def test_paramiko_client_host_key_injection_uses_public_paramiko_api() -> None:
    from app.services import ssh_remote

    client = ssh_remote.paramiko.SSHClient()
    ParamikoSshSftpAdapter()._set_client_host_keys(
        client, ParamikoSshSftpAdapter()._host_keys(target())
    )

    assert client.get_host_keys().lookup("node.example.test") is not None


def test_scan_ssh_host_key_reads_remote_key_and_closes_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services import ssh_remote

    class FakeTransport:
        closed = False
        started_timeout: int | None = None

        def __init__(self, sock: object) -> None:
            self.sock = sock

        def start_client(self, *, timeout: int) -> None:
            self.started_timeout = timeout

        def get_remote_server_key(self) -> FakeHostKey:
            return FakeHostKey()

        def close(self) -> None:
            type(self).closed = True

    created: dict[str, object] = {}

    def fake_create_connection(address: tuple[str, int], *, timeout: int) -> object:
        created["address"] = address
        created["timeout"] = timeout
        return object()

    monkeypatch.setattr(ssh_remote.socket, "create_connection", fake_create_connection)
    monkeypatch.setattr(ssh_remote.paramiko, "Transport", FakeTransport)

    scanned = scan_ssh_host_key(host=" Node.EXAMPLE.test ", port=2222, timeout_seconds=7)

    assert created == {"address": ("node.example.test", 2222), "timeout": 7}
    assert scanned.host == "node.example.test"
    assert scanned.port == 2222
    assert scanned.algorithm == "ssh-ed25519"
    assert scanned.public_key == "ZmFrZS1ob3N0LWtleQ=="
    assert scanned.fingerprint_sha256.startswith("SHA256:")
    assert FakeTransport.closed is True


def test_host_key_builder_rejects_inconsistent_trusted_fingerprint() -> None:
    bad_target = replace(
        target(), trusted_host_key_fingerprint_sha256="SHA256:inconsistentFingerprint"
    )

    with pytest.raises(SshHostKeyUntrustedError, match="invalid"):
        ParamikoSshSftpAdapter()._host_keys(bad_target)


def test_host_key_builder_rejects_unparseable_trust_line(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services import ssh_remote

    monkeypatch.setattr(ssh_remote.paramiko.hostkeys.HostKeyEntry, "from_line", lambda _line: None)

    with pytest.raises(SshHostKeyUntrustedError, match="invalid"):
        ParamikoSshSftpAdapter()._host_keys(target())


def test_host_key_builder_adds_bracketed_non_default_port_entry() -> None:
    host_keys = ParamikoSshSftpAdapter()._host_keys(replace(target(), port=2222))

    assert host_keys.lookup("[node.example.test]:2222") is not None


def test_paramiko_client_maps_known_hosts_reject_policy_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services import ssh_remote

    class MissingHostKeyClient:
        def __init__(self) -> None:
            self.host_keys = ssh_remote.paramiko.HostKeys()

        def get_host_keys(self) -> object:
            return self.host_keys

        def set_missing_host_key_policy(self, _policy: object) -> None:
            return None

        def connect(self, **_kwargs: object) -> None:
            raise ssh_remote.paramiko.SSHException("Server 'node' not found in known_hosts")

    monkeypatch.setattr(ssh_remote.paramiko, "SSHClient", MissingHostKeyClient)
    with pytest.raises(SshHostKeyUntrustedError, match="untrusted"):
        ParamikoSshSftpAdapter()._client(target())


def test_paramiko_client_maps_bad_host_key_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services import ssh_remote

    class BadHostKeyClient:
        def __init__(self) -> None:
            self.host_keys = ssh_remote.paramiko.HostKeys()

        def get_host_keys(self) -> object:
            return self.host_keys

        def set_missing_host_key_policy(self, _policy: object) -> None:
            return None

        def connect(self, **_kwargs: object) -> None:
            raise ssh_remote.paramiko.BadHostKeyException("node", object(), object())

    monkeypatch.setattr(ssh_remote.paramiko, "SSHClient", BadHostKeyClient)
    with pytest.raises(SshHostKeyChangedError, match="changed"):
        ParamikoSshSftpAdapter()._client(target())


def test_paramiko_client_preserves_non_host_key_ssh_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services import ssh_remote

    class GenericSshFailClient:
        def __init__(self) -> None:
            self.host_keys = ssh_remote.paramiko.HostKeys()

        def get_host_keys(self) -> object:
            return self.host_keys

        def set_missing_host_key_policy(self, _policy: object) -> None:
            return None

        def connect(self, **_kwargs: object) -> None:
            raise ssh_remote.paramiko.SSHException("banner exchange failed")

    monkeypatch.setattr(ssh_remote.paramiko, "SSHClient", GenericSshFailClient)
    with pytest.raises(ssh_remote.paramiko.SSHException, match="banner exchange failed"):
        ParamikoSshSftpAdapter()._client(target())


def test_paramiko_private_key_auth_rejects_unsupported_material() -> None:
    credential = CredentialPlaintext(auth_type="private_key", private_key="not-a-key")

    with pytest.raises(ValueError, match="Unsupported private key material"):
        ParamikoSshSftpAdapter()._auth_kwargs(credential)
