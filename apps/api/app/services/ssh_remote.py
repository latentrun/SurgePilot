from __future__ import annotations

from dataclasses import dataclass
from io import StringIO
import base64
import hashlib
import posixpath
import socket
import time
from typing import BinaryIO, Protocol

import paramiko

from app.services.load_nodes import CredentialPlaintext, sanitize_log


@dataclass(frozen=True)
class SshTarget:
    host: str
    port: int
    username: str
    credential: CredentialPlaintext
    connect_timeout_seconds: int
    trusted_host_key_algorithm: str
    trusted_host_key_public_key: str
    trusted_host_key_fingerprint_sha256: str


@dataclass(frozen=True)
class ScannedSshHostKey:
    host: str
    port: int
    algorithm: str
    public_key: str
    fingerprint_sha256: str


@dataclass(frozen=True)
class RemoteCommandResult:
    exit_status: int | None
    stdout_preview: str
    stderr_preview: str
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.exit_status == 0 and not self.timed_out


class SshSftpAdapter(Protocol):
    def upload_text(
        self, target: SshTarget, *, remote_path: str, content: str, mode: int
    ) -> None: ...

    def upload_bytes(
        self, target: SshTarget, *, remote_path: str, content: bytes, mode: int
    ) -> None: ...

    def upload_stream(
        self, target: SshTarget, *, remote_path: str, source: BinaryIO, mode: int
    ) -> None: ...

    def run_command(
        self,
        target: SshTarget,
        *,
        command: str,
        timeout_seconds: int,
        output_limit_bytes: int = 4096,
    ) -> RemoteCommandResult: ...


class SshHostKeyUntrustedError(Exception):
    """Raised when the remote SSH host key is not in node-level trust data."""


class SshHostKeyChangedError(Exception):
    """Raised when the remote SSH host key differs from node-level trust data."""


def _normalize_host_for_known_hosts(host: str) -> str:
    return host.strip().lower()


def _known_hosts_host_label(host: str, port: int) -> str:
    normalized_host = _normalize_host_for_known_hosts(host)
    return normalized_host if port == 22 else f"[{normalized_host}]:{port}"


def trusted_known_hosts_line(*, host: str, algorithm: str, public_key: str, port: int = 22) -> str:
    return f"{_known_hosts_host_label(host, port)} {algorithm.strip()} {public_key.strip()}"


def _host_key_fingerprint_sha256(key: paramiko.PKey) -> str:
    digest = hashlib.sha256(key.asbytes()).digest()
    return "SHA256:" + base64.b64encode(digest).decode().rstrip("=")


def scan_ssh_host_key(*, host: str, port: int, timeout_seconds: int) -> ScannedSshHostKey:
    normalized_host = _normalize_host_for_known_hosts(host)
    sock = socket.create_connection((normalized_host, port), timeout=timeout_seconds)
    transport: paramiko.Transport | None = None
    try:
        transport = paramiko.Transport(sock)
        transport.start_client(timeout=timeout_seconds)
        key = transport.get_remote_server_key()
        algorithm = key.get_name()
        public_key = base64.b64encode(key.asbytes()).decode()
        return ScannedSshHostKey(
            host=normalized_host,
            port=port,
            algorithm=algorithm,
            public_key=public_key,
            fingerprint_sha256=_host_key_fingerprint_sha256(key),
        )
    finally:
        if transport is not None:
            transport.close()
        else:
            sock.close()


class ParamikoSshSftpAdapter:
    def upload_text(self, target: SshTarget, *, remote_path: str, content: str, mode: int) -> None:
        self.upload_bytes(target, remote_path=remote_path, content=content.encode(), mode=mode)

    def upload_bytes(
        self, target: SshTarget, *, remote_path: str, content: bytes, mode: int
    ) -> None:
        from io import BytesIO

        self.upload_stream(target, remote_path=remote_path, source=BytesIO(content), mode=mode)

    def upload_stream(
        self, target: SshTarget, *, remote_path: str, source: BinaryIO, mode: int
    ) -> None:
        with self._client(target) as client:
            with client.open_sftp() as sftp:
                self._mkdir_parent(sftp, remote_path)
                with sftp.file(remote_path, "wb") as remote_file:
                    while True:
                        chunk = source.read(1024 * 1024)
                        if not chunk:
                            break
                        remote_file.write(chunk)
                sftp.chmod(remote_path, mode)

    def run_command(
        self,
        target: SshTarget,
        *,
        command: str,
        timeout_seconds: int,
        output_limit_bytes: int = 4096,
    ) -> RemoteCommandResult:
        with self._client(target) as client:
            _stdin, stdout, _stderr = client.exec_command(command, get_pty=False)
            channel = stdout.channel
            deadline = time.monotonic() + timeout_seconds
            stdout_preview = bytearray()
            stderr_preview = bytearray()
            while not channel.exit_status_ready():
                self._drain_channel(
                    channel,
                    stdout_preview=stdout_preview,
                    stderr_preview=stderr_preview,
                    output_limit_bytes=output_limit_bytes,
                )
                if time.monotonic() > deadline:
                    channel.close()
                    return RemoteCommandResult(
                        exit_status=None,
                        stdout_preview=self._decode_preview(stdout_preview, output_limit_bytes),
                        stderr_preview="Remote command timed out.",
                        timed_out=True,
                    )
                time.sleep(0.05)
            self._drain_channel(
                channel,
                stdout_preview=stdout_preview,
                stderr_preview=stderr_preview,
                output_limit_bytes=output_limit_bytes,
            )
            exit_status = channel.recv_exit_status()
            self._drain_channel(
                channel,
                stdout_preview=stdout_preview,
                stderr_preview=stderr_preview,
                output_limit_bytes=output_limit_bytes,
            )
            return RemoteCommandResult(
                exit_status=exit_status,
                stdout_preview=self._decode_preview(stdout_preview, output_limit_bytes),
                stderr_preview=self._decode_preview(stderr_preview, output_limit_bytes),
            )

    def _client(self, target: SshTarget) -> paramiko.SSHClient:
        client = paramiko.SSHClient()
        self._set_client_host_keys(client, self._host_keys(target))
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
        kwargs = self._auth_kwargs(target.credential)
        try:
            client.connect(
                hostname=target.host,
                port=target.port,
                username=target.username,
                timeout=target.connect_timeout_seconds,
                banner_timeout=target.connect_timeout_seconds,
                auth_timeout=target.connect_timeout_seconds,
                look_for_keys=False,
                allow_agent=False,
                **kwargs,
            )
        except paramiko.BadHostKeyException as exc:
            raise SshHostKeyChangedError("SSH host key changed.") from exc
        except paramiko.SSHException as exc:
            if "not found in known_hosts" in str(exc):
                raise SshHostKeyUntrustedError("SSH host key is untrusted.") from exc
            raise
        return client

    def _set_client_host_keys(
        self, client: paramiko.SSHClient, host_keys: paramiko.HostKeys
    ) -> None:
        client_host_keys = client.get_host_keys()
        for hostname, keys in host_keys.items():
            for key_type, key in keys.items():
                client_host_keys.add(hostname, key_type, key)

    def _host_keys(self, target: SshTarget) -> paramiko.HostKeys:
        host = _normalize_host_for_known_hosts(target.host)
        line = trusted_known_hosts_line(
            host=host,
            algorithm=target.trusted_host_key_algorithm,
            public_key=target.trusted_host_key_public_key,
            port=target.port,
        )
        entry = paramiko.hostkeys.HostKeyEntry.from_line(line)
        if entry is None or entry.key is None:
            raise SshHostKeyUntrustedError("SSH host key trust data is invalid.")
        if (
            _host_key_fingerprint_sha256(entry.key)
            != target.trusted_host_key_fingerprint_sha256.strip()
        ):
            raise SshHostKeyUntrustedError("SSH host key trust data is invalid.")
        host_keys = paramiko.HostKeys()
        host_keys.add(_known_hosts_host_label(host, target.port), entry.key.get_name(), entry.key)
        return host_keys

    def _auth_kwargs(self, credential: CredentialPlaintext) -> dict[str, object]:
        if credential.auth_type == "password":
            return {"password": credential.password or ""}
        key = self._private_key(credential)
        return {"pkey": key}

    def _private_key(self, credential: CredentialPlaintext) -> paramiko.PKey:
        raw = credential.private_key or ""
        passphrase = credential.private_key_passphrase
        errors: list[Exception] = []
        for key_cls in (
            paramiko.Ed25519Key,
            paramiko.RSAKey,
            paramiko.ECDSAKey,
            paramiko.DSSKey,
        ):
            try:
                return key_cls.from_private_key(StringIO(raw), password=passphrase)
            except Exception as exc:  # noqa: BLE001 - paramiko key parsers raise several types.
                errors.append(exc)
        raise ValueError("Unsupported private key material.") from errors[-1] if errors else None

    def _mkdir_parent(self, sftp: paramiko.SFTPClient, remote_path: str) -> None:
        parent = posixpath.dirname(remote_path)
        parts = [part for part in parent.split("/") if part]
        current = "/"
        for part in parts:
            current = posixpath.join(current, part)
            try:
                sftp.stat(current)
            except OSError:
                sftp.mkdir(current)

    def _drain_channel(
        self,
        channel,
        *,
        stdout_preview: bytearray,
        stderr_preview: bytearray,
        output_limit_bytes: int,
    ) -> None:
        while channel.recv_ready():
            self._append_preview(
                stdout_preview, channel.recv(4096), output_limit_bytes=output_limit_bytes
            )
        while channel.recv_stderr_ready():
            self._append_preview(
                stderr_preview,
                channel.recv_stderr(4096),
                output_limit_bytes=output_limit_bytes,
            )

    def _append_preview(self, preview: bytearray, data: bytes, *, output_limit_bytes: int) -> None:
        remaining = max(output_limit_bytes - len(preview), 0)
        if remaining:
            preview.extend(data[:remaining])

    def _decode_preview(self, preview: bytearray, output_limit_bytes: int) -> str:
        return sanitize_log(
            bytes(preview[:output_limit_bytes]).decode("utf-8", errors="replace"),
            max_bytes=output_limit_bytes,
        )
