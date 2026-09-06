from __future__ import annotations

from dataclasses import dataclass
import json
import hashlib
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from uuid import uuid4
import zipfile

import click

SAFE_PATH_SEGMENT = re.compile(r"^[A-Za-z0-9._-]+$")
MAX_RUN_ID_LENGTH = 64
MAX_ARTIFACT_UPLOAD_BYTES = 200 * 1024 * 1024
DEFAULT_ARCHIVE_UPLOAD_MAX_BYTES = 50 * 1024 * 1024
SUPERVISOR_PIDFILE = "supervisor.pid"
WORKLOAD_PIDFILE = "workload.pid"
TERMINATE_GROUP_SIGNAL_GRACE_SECONDS = 10.0
DEFAULT_STOP_SUPERVISOR_TIMEOUT_SECONDS = 120.0
RUNNER_VERSION = "0.1.0"


@dataclass(frozen=True)
class ManagedPid:
    pid: int
    starttime: str | None


@dataclass(frozen=True)
class ProcEntry:
    pid: int
    pgid: int
    state: str
    starttime: str


class DiagnosticArchiveOversize(Exception):
    pass


@dataclass(frozen=True)
class ArtifactUploadResult:
    artifact_type: str
    relative_path: str
    status: str
    path: Path | None = None


@dataclass(frozen=True)
class ArtifactUploadSummary:
    next_seq: int
    results: list[ArtifactUploadResult]

    @property
    def has_failed_upload(self) -> bool:
        return any(result.status == "failed" for result in self.results)

    @property
    def artifacts_zip_status(self) -> str | None:
        for result in self.results:
            if result.artifact_type == "artifacts_zip":
                return result.status
        return None


class ProcessGroupProbe:
    def __init__(
        self, *, proc_root: Path = Path("/proc"), use_killpg_fallback: bool | None = None
    ) -> None:
        self.proc_root = proc_root
        self.use_killpg_fallback = (
            proc_root == Path("/proc") if use_killpg_fallback is None else use_killpg_fallback
        )

    def process_group_alive(self, pgid: int) -> bool:
        if pgid <= 1:
            return False
        if self.proc_root.exists():
            return any(entry.pgid == pgid and entry.state != "Z" for entry in self.iter_entries())
        if self.use_killpg_fallback:
            return self._killpg_group_alive(pgid)
        return False

    def process_alive(self, pid: int, starttime: str | None = None) -> bool:
        entry = self.read_entry(pid)
        if entry is None or entry.state == "Z":
            if starttime is None and self.use_killpg_fallback and not self.proc_root.exists():
                return self._kill_pid_alive(pid)
            return False
        return starttime is None or entry.starttime == starttime

    def read_starttime(self, pid: int) -> str | None:
        entry = self.read_entry(pid)
        return entry.starttime if entry is not None else None

    def read_entry(self, pid: int) -> ProcEntry | None:
        try:
            return self._parse_stat(pid, (self.proc_root / str(pid) / "stat").read_text())
        except OSError:
            return None

    def iter_entries(self) -> list[ProcEntry]:
        try:
            children = list(self.proc_root.iterdir())
        except OSError:
            return []
        entries: list[ProcEntry] = []
        for child in children:
            if not child.name.isdigit():
                continue
            entry = self.read_entry(int(child.name))
            if entry is not None:
                entries.append(entry)
        return entries

    @staticmethod
    def _killpg_group_alive(pgid: int) -> bool:
        try:
            os.killpg(pgid, 0)
            return True
        except PermissionError:
            return True
        except ProcessLookupError:
            return False
        except OSError:
            return False

    @staticmethod
    def _kill_pid_alive(pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except PermissionError:
            return True
        except ProcessLookupError:
            return False
        except OSError:
            return False

    @staticmethod
    def _parse_stat(pid: int, stat: str) -> ProcEntry | None:
        _, _sep, suffix = stat.strip().rpartition(") ")
        if not suffix:
            return None
        fields = suffix.split()
        if len(fields) < 20:
            return None
        try:
            return ProcEntry(
                pid=pid,
                state=fields[0],
                pgid=int(fields[2]),
                starttime=fields[19],
            )
        except ValueError:
            return None


def runner_home() -> Path:
    return Path(os.environ.get("RUNNER_HOME", "/opt/surgepilot/runner")).expanduser()


def validate_run_id_segment(run_id: str) -> str:
    if (
        not run_id
        or len(run_id) > MAX_RUN_ID_LENGTH
        or run_id in {".", ".."}
        or "/" in run_id
        or "\\" in run_id
        or ":" in run_id
        or not SAFE_PATH_SEGMENT.fullmatch(run_id)
    ):
        raise ValueError("unsafe run id")
    return run_id


def require_safe_run_id(run_id: str) -> str:
    try:
        return validate_run_id_segment(run_id)
    except ValueError as exc:
        raise click.ClickException("unsafe run id") from exc


def run_dir(run_id: str, *, base: Path | None = None) -> Path:
    return (base or runner_home()) / "runs" / validate_run_id_segment(run_id)


def bundle_dir(run_id: str, *, base: Path | None = None) -> Path:
    return run_dir(run_id, base=base) / "bundle"


def surgepilot_yaml_path(run_id: str, *, base: Path | None = None) -> Path:
    return bundle_dir(run_id, base=base) / "surgepilot.yml"


def supervisor_pidfile_path(run_id: str, *, base: Path | None = None) -> Path:
    return run_dir(run_id, base=base) / SUPERVISOR_PIDFILE


def workload_pidfile_path(run_id: str, *, base: Path | None = None) -> Path:
    return run_dir(run_id, base=base) / WORKLOAD_PIDFILE


def pidfile_path(run_id: str, *, base: Path | None = None) -> Path:
    return supervisor_pidfile_path(run_id, base=base)


def runner_entrypoint() -> Path:
    return Path(__file__).resolve().parents[1] / "runner.py"


def _write_managed_pidfile(
    run_id: str,
    filename: str,
    managed: ManagedPid,
    *,
    runner_home: Path | None = None,
) -> Path:
    path = run_dir(run_id, base=runner_home) / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.parent / f".{filename}.{os.getpid()}.{uuid4().hex}.tmp"
    try:
        with tmp_path.open("w") as tmp_file:
            tmp_file.write(json.dumps({"pid": managed.pid, "starttime": managed.starttime}) + "\n")
            tmp_file.flush()
            os.fsync(tmp_file.fileno())
        os.replace(tmp_path, path)
        _fsync_directory(path.parent)
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
    return path


def _fsync_directory(path: Path) -> None:
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def write_supervisor_pidfile(
    run_id: str, managed: ManagedPid, *, runner_home: Path | None = None
) -> Path:
    return _write_managed_pidfile(run_id, SUPERVISOR_PIDFILE, managed, runner_home=runner_home)


def write_workload_pidfile(
    run_id: str, managed: ManagedPid, *, runner_home: Path | None = None
) -> Path:
    return _write_managed_pidfile(run_id, WORKLOAD_PIDFILE, managed, runner_home=runner_home)


def write_pidfile(run_id: str, pgid: int, *, runner_home: Path | None = None) -> Path:
    return write_supervisor_pidfile(
        run_id, ManagedPid(pid=pgid, starttime=None), runner_home=runner_home
    )


def _read_managed_pidfile(
    path: Path,
    *,
    probe: ProcessGroupProbe | None = None,
    validate_starttime: bool = True,
) -> ManagedPid | None:
    managed = read_managed_pidfile_raw(path)
    if managed is None:
        return None
    if validate_starttime and managed.starttime is not None:
        active_probe = probe or ProcessGroupProbe()
        if active_probe.read_starttime(managed.pid) != managed.starttime:
            return None
    return managed


def read_managed_pidfile_raw(path: Path) -> ManagedPid | None:
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    pid = data.get("pid")
    starttime = data.get("starttime")
    if not isinstance(pid, int) or pid <= 1:
        return None
    if starttime is not None and not isinstance(starttime, str):
        return None
    return ManagedPid(pid=pid, starttime=starttime)


def read_supervisor_pidfile(
    run_id: str,
    *,
    runner_home: Path | None = None,
    probe: ProcessGroupProbe | None = None,
    validate_starttime: bool = True,
) -> ManagedPid | None:
    return _read_managed_pidfile(
        supervisor_pidfile_path(run_id, base=runner_home),
        probe=probe,
        validate_starttime=validate_starttime,
    )


def read_workload_pidfile(
    run_id: str,
    *,
    runner_home: Path | None = None,
    probe: ProcessGroupProbe | None = None,
    validate_starttime: bool = True,
) -> ManagedPid | None:
    return _read_managed_pidfile(
        workload_pidfile_path(run_id, base=runner_home),
        probe=probe,
        validate_starttime=validate_starttime,
    )


def read_workload_pidfile_for_kill(
    run_id: str,
    *,
    runner_home: Path | None = None,
    probe: ProcessGroupProbe | None = None,
) -> ManagedPid | None:
    managed = _read_managed_pidfile(
        workload_pidfile_path(run_id, base=runner_home), validate_starttime=False
    )
    if managed is None:
        return None
    if managed.starttime is None:
        return managed
    active_probe = probe or ProcessGroupProbe()
    entry = active_probe.read_entry(managed.pid)
    if entry is not None and entry.starttime != managed.starttime:
        return None
    return managed


def cleanup_supervisor_pidfile(run_id: str, *, runner_home: Path | None = None) -> None:
    try:
        supervisor_pidfile_path(run_id, base=runner_home).unlink(missing_ok=True)
    except OSError:
        pass


def cleanup_workload_pidfile(run_id: str, *, runner_home: Path | None = None) -> None:
    try:
        workload_pidfile_path(run_id, base=runner_home).unlink(missing_ok=True)
    except OSError:
        pass


def cleanup_pidfile(run_id: str, *, runner_home: Path | None = None) -> None:
    cleanup_supervisor_pidfile(run_id, runner_home=runner_home)


def validate_artifact_relative_path(path: str) -> str:
    if not path or path.startswith("/") or "\\" in path or "//" in path or ":" in path:
        raise ValueError("unsafe artifact path")
    parts = path.split("/")
    if any(part in {"", ".", ".."} or not SAFE_PATH_SEGMENT.fullmatch(part) for part in parts):
        raise ValueError("unsafe artifact path")
    return path


def event_id() -> str:
    return uuid4().hex[:26].upper().ljust(26, "0")


def api_base() -> str | None:
    return os.environ.get("SURGEPILOT_API_BASE_URL")


def runner_token() -> str | None:
    return os.environ.get("RUNNER_INTERNAL_TOKEN")


def runner_archive_upload_max_bytes() -> int:
    raw = os.environ.get("SURGEPILOT_RUNNER_ARCHIVE_MAX_BYTES")
    if raw is None:
        return DEFAULT_ARCHIVE_UPLOAD_MAX_BYTES
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_ARCHIVE_UPLOAD_MAX_BYTES
    return min(max(value, 0), MAX_ARTIFACT_UPLOAD_BYTES)


def _callback_response_is_acked(response_bytes: bytes) -> bool:
    try:
        data = json.loads(response_bytes.decode() or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False
    if not isinstance(data, dict):
        return False
    ignored_reason = data.get("ignoredReason", data.get("ignored_reason"))
    return data.get("accepted") is True and ignored_reason is None


def post_callback(payload: dict) -> bool:
    base = api_base()
    token = runner_token()
    if not base or not token:
        click.echo(f"callback {payload['eventType']} skipped; API is not configured")
        return False
    body = json.dumps(payload).encode()
    request = urllib.request.Request(
        f"{base.rstrip('/')}/api/internal/v1/runner/callbacks",
        data=body,
        method="POST",
        headers={"content-type": "application/json", "x-runner-token": token},
    )
    for delay in [1, 2, 4, 8, 16]:
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                status = getattr(response, "status", 200)
                if not 200 <= status < 300:
                    return False
                return _callback_response_is_acked(response.read())
        except urllib.error.HTTPError as exc:
            if delay == 16:
                click.echo(f"callback delivery failed with status {exc.code}", err=True)
                return False
            time.sleep(delay)
        except (urllib.error.URLError, TimeoutError):
            if delay == 16:
                click.echo("callback delivery failed after bounded retries", err=True)
                return False
            time.sleep(delay)
    return False


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class _MultipartFileBody:
    fields: dict[str, str]
    file_field: str
    filename: str
    path: Path
    boundary: str

    def __len__(self) -> int:
        total = 0
        for name, value in self.fields.items():
            total += len(f"--{self.boundary}\r\n".encode())
            total += len(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
            total += len(value.encode())
            total += len(b"\r\n")
        total += len(f"--{self.boundary}\r\n".encode())
        total += len(
            (
                f'Content-Disposition: form-data; name="{self.file_field}"; '
                f'filename="{self.filename}"\r\n'
            ).encode()
        )
        total += len(b"Content-Type: application/octet-stream\r\n\r\n")
        total += self.path.stat().st_size
        total += len(b"\r\n")
        total += len(f"--{self.boundary}--\r\n".encode())
        return total

    def __iter__(self):
        for name, value in self.fields.items():
            yield f"--{self.boundary}\r\n".encode()
            yield f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode()
            yield value.encode()
            yield b"\r\n"
        yield f"--{self.boundary}\r\n".encode()
        yield (
            f'Content-Disposition: form-data; name="{self.file_field}"; '
            f'filename="{self.filename}"\r\n'
        ).encode()
        yield b"Content-Type: application/octet-stream\r\n\r\n"
        with self.path.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                yield chunk
        yield b"\r\n"
        yield f"--{self.boundary}--\r\n".encode()


def _multipart_body(
    fields: dict[str, str], *, file_field: str, filename: str, path: Path
) -> tuple[_MultipartFileBody, str]:
    boundary = f"surgepilot-{uuid4().hex}"
    body = _MultipartFileBody(
        fields=fields,
        file_field=file_field,
        filename=filename,
        path=path,
        boundary=boundary,
    )
    return body, f"multipart/form-data; boundary={boundary}"


def upload_artifact(
    *,
    run_id: str,
    node_id: str,
    artifact_type: str,
    relative_path: str,
    path: Path,
) -> dict | None:
    safe_relative_path = validate_artifact_relative_path(relative_path)
    base = api_base()
    token = runner_token()
    if not base or not token:
        click.echo("artifact upload skipped; API is not configured")
        return None
    artifact_size = path.stat().st_size
    if artifact_size > MAX_ARTIFACT_UPLOAD_BYTES:
        click.echo(
            (
                "artifact upload skipped; "
                f"size {artifact_size} exceeds runner hard limit {MAX_ARTIFACT_UPLOAD_BYTES}"
            ),
            err=True,
        )
        return None
    digest = _sha256_file(path)
    body, content_type = _multipart_body(
        {
            "schemaVersion": "1",
            "eventId": event_id(),
            "runId": run_id,
            "nodeId": node_id,
            "artifactType": artifact_type,
            "relativePath": safe_relative_path,
            "sha256": digest,
            "sizeBytes": str(artifact_size),
        },
        file_field="file",
        filename=safe_relative_path.rsplit("/", 1)[-1],
        path=path,
    )
    request = urllib.request.Request(
        f"{base.rstrip('/')}/api/internal/v1/runner/artifacts",
        data=body,
        method="POST",
        headers={
            "content-type": content_type,
            "content-length": str(len(body)),
            "x-runner-token": token,
        },
    )
    for delay in [1, 2, 4, 8, 16]:
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                upload_response = json.loads(response.read().decode())
                return {
                    "artifactId": upload_response["artifactId"],
                    "sizeBytes": artifact_size,
                    "sha256": digest,
                }
        except urllib.error.HTTPError as exc:
            click.echo(f"artifact upload failed with status {exc.code}", err=True)
            return None
        except (urllib.error.URLError, TimeoutError):
            if delay == 16:
                click.echo("artifact upload failed after bounded retries", err=True)
                return None
            time.sleep(delay)
    return None


def sla_result_for_exit(mode: str, exit_code: int) -> str | None:
    if mode != "passfail":
        return None
    if exit_code == 0:
        return "passed"
    if exit_code == 3:
        return "failed"
    return None


def bundle_sla_evaluation_mode(run_id: str) -> str:
    manifest_path = bundle_dir(run_id) / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError("Execution bundle manifest is unavailable.") from exc
    mode = manifest.get("slaEvaluationMode")
    if mode not in {"passfail", "not_evaluated", "not_configured"}:
        raise RuntimeError("Execution bundle SLA evaluation mode is invalid.")
    return mode


def payload(
    run_id: str,
    node_id: str,
    event_type: str,
    seq: int,
    *,
    runtime_version: str,
    **extra,
) -> dict:
    data = {
        "schemaVersion": "1",
        "eventId": event_id(),
        "runId": run_id,
        "nodeId": node_id,
        "runtimeVersion": runtime_version,
        "eventType": event_type,
        "seq": seq,
        "eventTime": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "message": f"Runner {event_type} callback.",
        "details": {},
    }
    data.update(extra)
    return data


def pidfile_pgid(path: Path) -> int | None:
    managed = _read_managed_pidfile(path, validate_starttime=False)
    return managed.pid if managed is not None else None


def process_group_alive(pgid: int) -> bool:
    return ProcessGroupProbe().process_group_alive(pgid)


def _process_is_zombie(pid: int) -> bool:
    entry = ProcessGroupProbe().read_entry(pid)
    return entry is not None and entry.state == "Z"


def managed_pid_alive(managed: ManagedPid, probe: ProcessGroupProbe | None = None) -> bool:
    active_probe = probe or ProcessGroupProbe()
    return active_probe.process_alive(managed.pid, managed.starttime)


def managed_process_group_alive(
    managed: ManagedPid, probe: ProcessGroupProbe | None = None
) -> bool:
    active_probe = probe or ProcessGroupProbe()
    return active_probe.process_group_alive(managed.pid)


def _managed_pidfile_entries(
    *, base: Path | None = None
) -> list[tuple[str, Path, ManagedPid | None]]:
    runs_root = (base or runner_home()) / "runs"
    if not runs_root.exists():
        return []
    entries: list[tuple[str, Path, ManagedPid | None]] = []
    for path in sorted(runs_root.glob("*/*.pid")):
        run_id = path.parent.name
        try:
            validate_run_id_segment(run_id)
        except ValueError:
            continue
        managed = _read_managed_pidfile(path)
        entries.append((run_id, path, managed))
    return entries


def live_managed_pidfiles(*, base: Path | None = None) -> list[tuple[str, Path, int]]:
    live: list[tuple[str, Path, int]] = []
    for run_id, path, managed in _managed_pidfile_entries(base=base):
        if managed is not None and managed_process_group_alive(managed):
            live.append((run_id, path, managed.pid))
    return live


def suspicious_managed_pidfiles(*, base: Path | None = None) -> list[tuple[str, Path]]:
    suspicious: list[tuple[str, Path]] = []
    for run_id, path, managed in _managed_pidfile_entries(base=base):
        if managed is None:
            suspicious.append((run_id, path))
    return suspicious


def _classify_pidfile_for_start(path: Path, probe: ProcessGroupProbe) -> str:
    managed = read_managed_pidfile_raw(path)
    if managed is None:
        return "corrupt_workload" if path.name == WORKLOAD_PIDFILE else "corrupt_supervisor"
    if path.name == WORKLOAD_PIDFILE:
        if managed.starttime is not None:
            entry = probe.read_entry(managed.pid)
            if entry is not None and entry.starttime != managed.starttime:
                return "stale"
        return "live" if probe.process_group_alive(managed.pid) else "stale"
    if managed.starttime is not None:
        entry = probe.read_entry(managed.pid)
        if entry is None or entry.state == "Z" or entry.starttime != managed.starttime:
            return "stale"
    return "live" if probe.process_group_alive(managed.pid) else "stale"


def _archive_corrupt_workload_pidfile(path: Path) -> bool:
    archive = path.with_name(f"{path.name}.corrupt.{time.time_ns()}")
    try:
        os.replace(path, archive)
        _fsync_directory(path.parent)
        return True
    except OSError:
        return False


def _delete_pidfile(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
        _fsync_directory(path.parent)
    except OSError:
        pass


def reconcile_managed_pidfiles_before_start(
    *, base: Path | None = None
) -> list[tuple[str, Path, int]]:
    runs_root = (base or runner_home()) / "runs"
    if not runs_root.exists():
        return []
    probe = ProcessGroupProbe()
    live: list[tuple[str, Path, int]] = []
    for path in sorted(runs_root.glob("*/*.pid")):
        run_id = path.parent.name
        try:
            validate_run_id_segment(run_id)
        except ValueError:
            continue
        classification = _classify_pidfile_for_start(path, probe)
        if classification == "live":
            managed = read_managed_pidfile_raw(path)
            if managed is not None:
                live.append((run_id, path, managed.pid))
        elif classification == "corrupt_workload":
            if not _archive_corrupt_workload_pidfile(path):
                live.append((run_id, path, -1))
        else:
            _delete_pidfile(path)
    return live


def terminate_group(pgid: int) -> bool:
    if pgid <= 1 or pgid == os.getpgrp():
        return False
    for sig in [signal.SIGTERM, signal.SIGKILL]:
        try:
            os.killpg(pgid, sig)
        except ProcessLookupError:
            return True
        deadline = time.monotonic() + TERMINATE_GROUP_SIGNAL_GRACE_SECONDS
        while time.monotonic() < deadline:
            if not process_group_alive(pgid):
                return True
            time.sleep(0.1)
    return not process_group_alive(pgid)


def _signal_and_wait_supervisor(supervisor: ManagedPid) -> bool:
    if supervisor.pid <= 1 or supervisor.pid == os.getpgrp():
        return False
    try:
        os.killpg(supervisor.pid, signal.SIGTERM)
    except ProcessLookupError:
        return True
    deadline = time.monotonic() + stop_supervisor_timeout_seconds()
    while time.monotonic() < deadline:
        if not managed_pid_alive(supervisor):
            return True
        time.sleep(0.1)
    return not managed_pid_alive(supervisor)


def fail_if_other_managed_process_exists(run_id: str) -> None:
    live = [entry for entry in live_managed_pidfiles() if entry[0] != run_id]
    suspicious = [entry for entry in suspicious_managed_pidfiles() if entry[0] != run_id]
    if live or suspicious:
        click.echo("suspicious managed process detected", err=True)
        raise click.ClickException("suspicious managed process detected")


def heartbeat_interval_seconds() -> float:
    try:
        return max(float(os.environ.get("SURGEPILOT_RUNNER_HEARTBEAT_INTERVAL_SECONDS", "15")), 0.1)
    except ValueError:
        return 15.0


def managed_duration_seconds() -> float | None:
    value = os.environ.get("SURGEPILOT_RUNNER_MANAGED_DURATION_SECONDS")
    if value is None or value == "":
        return None
    try:
        return max(float(value), 0.0)
    except ValueError:
        return None


def group_exit_timeout_seconds() -> float:
    try:
        return max(float(os.environ.get("SURGEPILOT_RUNNER_GROUP_EXIT_TIMEOUT_SECONDS", "10")), 0.0)
    except ValueError:
        return 10.0


def start_workload_wait_seconds() -> float:
    try:
        return max(float(os.environ.get("SURGEPILOT_RUNNER_START_WORKLOAD_WAIT_SECONDS", "5")), 0.0)
    except ValueError:
        return 5.0


def stop_supervisor_timeout_seconds() -> float:
    try:
        return max(
            float(
                os.environ.get(
                    "SURGEPILOT_RUNNER_STOP_SUPERVISOR_TIMEOUT_SECONDS",
                    str(DEFAULT_STOP_SUPERVISOR_TIMEOUT_SECONDS),
                )
            ),
            0.0,
        )
    except ValueError:
        return DEFAULT_STOP_SUPERVISOR_TIMEOUT_SECONDS


def _wait_for_process_group_exit(managed: ManagedPid, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while True:
        if not managed_process_group_alive(managed):
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.1)


def _is_safe_archive_relative_path(relative_path: str) -> bool:
    try:
        validate_artifact_relative_path(relative_path)
    except ValueError:
        return False
    parts = relative_path.split("/")
    if any(part.startswith(".") for part in parts):
        return False
    filename = parts[-1]
    if filename == "artifacts.zip" or filename.startswith(".tmp-"):
        return False
    return True


def _is_regular_file_inside_run(path: Path, root: Path) -> bool:
    try:
        if path.is_symlink() or not path.is_file():
            return False
        resolved_path = path.resolve(strict=True)
        resolved_root = root.resolve(strict=True)
        return os.path.commonpath([str(resolved_root), str(resolved_path)]) == str(resolved_root)
    except (OSError, ValueError):
        return False


def iter_diagnostic_archive_members(run_id: str) -> list[tuple[str, Path]]:
    root = run_dir(run_id)
    artifacts = bundle_dir(run_id) / "artifacts"
    candidates: list[tuple[str, Path]] = [
        ("logs/runner.log", root / "logs" / "runner.log"),
        ("artifacts/bzt.log", artifacts / "bzt.log"),
        ("artifacts/jmeter.log", artifacts / "jmeter.log"),
        ("artifacts/final_stats.csv", artifacts / "final_stats.csv"),
        ("artifacts/finalstats.csv", artifacts / "finalstats.csv"),
    ]
    candidates.extend((f"artifacts/{path.name}", path) for path in sorted(artifacts.glob("*.jtl")))

    members: list[tuple[str, Path]] = []
    seen: set[str] = set()
    for relative_path, path in candidates:
        if relative_path in seen:
            continue
        if not _is_safe_archive_relative_path(relative_path):
            continue
        if not _is_regular_file_inside_run(path, root):
            continue
        members.append((relative_path, path))
        seen.add(relative_path)
    return members


def _diagnostic_archive_source_bytes(members: list[tuple[str, Path]]) -> int | None:
    total = 0
    try:
        for _relative_path, source_path in members:
            total += source_path.stat().st_size
    except OSError:
        return None
    return total


def build_diagnostic_archive(run_id: str, *, max_bytes: int | None = None) -> ArtifactUploadResult:
    relative_path = "artifacts/artifacts.zip"
    archive_path = bundle_dir(run_id) / "artifacts" / "artifacts.zip"
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    archive_path.unlink(missing_ok=True)
    members = iter_diagnostic_archive_members(run_id)
    if not members:
        return ArtifactUploadResult("artifacts_zip", relative_path, "missing", archive_path)

    byte_limit = runner_archive_upload_max_bytes() if max_bytes is None else max(max_bytes, 0)
    source_bytes = _diagnostic_archive_source_bytes(members)
    if source_bytes is None:
        return ArtifactUploadResult("artifacts_zip", relative_path, "failed", archive_path)
    if source_bytes > byte_limit:
        click.echo(
            f"artifact archive upload skipped; source bytes exceed runner threshold {byte_limit}",
            err=True,
        )
        return ArtifactUploadResult(
            "artifacts_zip", relative_path, "skipped_oversize", archive_path
        )

    tmp_path = archive_path.parent / f".artifacts.zip.tmp.{os.getpid()}.{uuid4().hex}"
    try:
        with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_STORED) as archive:
            for member_path, source_path in members:
                archive.write(source_path, arcname=member_path)
                if tmp_path.stat().st_size > byte_limit:
                    raise DiagnosticArchiveOversize
        if tmp_path.stat().st_size > byte_limit:
            raise DiagnosticArchiveOversize
        os.replace(tmp_path, archive_path)
        _fsync_directory(archive_path.parent)
        return ArtifactUploadResult("artifacts_zip", relative_path, "uploaded", archive_path)
    except DiagnosticArchiveOversize:
        tmp_path.unlink(missing_ok=True)
        archive_path.unlink(missing_ok=True)
        click.echo(
            f"artifact archive upload skipped; archive exceeds runner threshold {byte_limit}",
            err=True,
        )
        return ArtifactUploadResult(
            "artifacts_zip", relative_path, "skipped_oversize", archive_path
        )
    except OSError:
        tmp_path.unlink(missing_ok=True)
        archive_path.unlink(missing_ok=True)
        return ArtifactUploadResult("artifacts_zip", relative_path, "failed", archive_path)


def _artifact_candidates(run_id: str) -> list[tuple[str, str, Path]]:
    root = run_dir(run_id)
    bundle = bundle_dir(run_id)
    artifacts = bundle / "artifacts"
    return [
        ("artifacts_zip", "artifacts/artifacts.zip", artifacts / "artifacts.zip"),
        ("final_stats_csv", "artifacts/final_stats.csv", artifacts / "final_stats.csv"),
        ("final_stats_csv", "artifacts/finalstats.csv", artifacts / "finalstats.csv"),
        ("run_log", "logs/runner.log", root / "logs" / "runner.log"),
        ("taurus_log", "artifacts/bzt.log", artifacts / "bzt.log"),
        ("jmeter_log", "artifacts/jmeter.log", artifacts / "jmeter.log"),
    ]


def upload_run_artifacts(
    run_id: str, node_id: str, seq: int, *, runtime_version: str
) -> ArtifactUploadSummary:
    results: list[ArtifactUploadResult] = []
    archive_result = build_diagnostic_archive(run_id)
    if archive_result.status != "uploaded":
        results.append(archive_result)

    seen: set[str] = set()
    for artifact_type, relative_path, path in _artifact_candidates(run_id):
        if relative_path in seen or not path.is_file():
            continue
        seen.add(relative_path)
        upload = upload_artifact(
            run_id=run_id,
            node_id=node_id,
            artifact_type=artifact_type,
            relative_path=relative_path,
            path=path,
        )
        if upload is None:
            results.append(ArtifactUploadResult(artifact_type, relative_path, "failed", path))
            continue
        results.append(ArtifactUploadResult(artifact_type, relative_path, "uploaded", path))
        post_callback(
            payload(
                run_id,
                node_id,
                "artifact",
                seq,
                runtime_version=runtime_version,
                details={
                    "artifactId": upload["artifactId"],
                    "artifactType": artifact_type,
                    "relativePath": relative_path,
                    "sizeBytes": upload["sizeBytes"],
                    "sha256": upload["sha256"],
                },
            )
        )
        seq += 1
    return ArtifactUploadSummary(next_seq=seq, results=results)


def _managed_pid_live_for_cleanup(
    managed: ManagedPid | None,
    *,
    probe: ProcessGroupProbe,
    allow_current_process: bool = False,
) -> bool:
    if managed is None:
        return False
    if allow_current_process and managed.pid == os.getpid():
        if managed.starttime is None:
            return False
        current_starttime = probe.read_starttime(managed.pid)
        return current_starttime is not None and current_starttime != managed.starttime
    if managed.starttime is not None:
        entry = probe.read_entry(managed.pid)
        if entry is not None and entry.starttime != managed.starttime:
            return True
    return managed_process_group_alive(managed, probe)


def _pidfiles_uncertain_for_cleanup(
    run_id: str, *, supervisor: ManagedPid | None, workload: ManagedPid | None
) -> bool:
    for path, expected in [
        (supervisor_pidfile_path(run_id), supervisor),
        (workload_pidfile_path(run_id), workload),
    ]:
        if not path.exists():
            continue
        managed = read_managed_pidfile_raw(path)
        if managed is None or expected is None:
            return True
        if managed.pid != expected.pid or managed.starttime != expected.starttime:
            return True
    return False


def cleanup_run_directory_if_safe(
    run_id: str,
    *,
    terminal_callback_ack: bool,
    artifact_results: list[ArtifactUploadResult],
    supervisor: ManagedPid | None,
    workload: ManagedPid | None,
    probe: ProcessGroupProbe | None = None,
) -> bool:
    if not terminal_callback_ack:
        return False
    if any(result.status == "failed" for result in artifact_results):
        return False
    archive_status = next(
        (result.status for result in artifact_results if result.artifact_type == "artifacts_zip"),
        None,
    )
    if archive_status not in {"uploaded", "skipped_oversize"}:
        return False

    if _pidfiles_uncertain_for_cleanup(run_id, supervisor=supervisor, workload=workload):
        return False

    active_probe = probe or ProcessGroupProbe()
    if _managed_pid_live_for_cleanup(supervisor, probe=active_probe, allow_current_process=True):
        return False
    if _managed_pid_live_for_cleanup(workload, probe=active_probe):
        return False

    root = run_dir(run_id)
    try:
        shutil.rmtree(root)
        return True
    except FileNotFoundError:
        return True
    except OSError:
        return False


def managed_run(run_id: str) -> None:
    require_safe_run_id(run_id)
    node_id = os.environ.get("SURGEPILOT_NODE_ID", "01HZX3Y9M0E9W7Z6M5QK9S8P7C")
    stop_requested = False
    process: subprocess.Popen | None = None
    workload: ManagedPid | None = None
    artifact_summary = ArtifactUploadSummary(next_seq=1, results=[])
    terminal_callback_ack = False

    def request_stop(_signum, _frame) -> None:
        nonlocal stop_requested
        stop_requested = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    supervisor = ManagedPid(
        pid=os.getpid(), starttime=ProcessGroupProbe().read_starttime(os.getpid())
    )
    try:
        write_supervisor_pidfile(run_id, supervisor)
        log_path = run_dir(run_id) / "logs" / "runner.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        terminal = "failed"
        details: dict = {"processGroupExited": True, "reason": "bundle_invalid"}
        runtime_version = RUNNER_VERSION
        seq = 1
        post_callback(
            payload(
                run_id,
                node_id,
                "accepted",
                seq,
                runtime_version=runtime_version,
                runnerPid=os.getpid(),
            )
        )
        seq += 1
        config_path = surgepilot_yaml_path(run_id)
        if not config_path.is_file():
            log_path.write_text("Execution bundle is missing surgepilot.yml.\n")
        else:
            sla_evaluation_mode = bundle_sla_evaluation_mode(run_id)
            with log_path.open("ab") as log_file:
                log_file.write(b"Starting Taurus execution.\n")
                log_file.flush()
                try:
                    process = subprocess.Popen(
                        ["bzt", "-n", "surgepilot.yml"],
                        cwd=bundle_dir(run_id),
                        stdout=log_file,
                        stderr=subprocess.STDOUT,
                        start_new_session=True,
                    )
                except OSError:
                    log_file.write(b"Taurus start failed.\n")
                    details = {"processGroupExited": True, "reason": "runner_start_failed"}
                else:
                    workload = ManagedPid(
                        pid=process.pid,
                        starttime=ProcessGroupProbe().read_starttime(process.pid),
                    )
                    write_workload_pidfile(run_id, workload)
                    post_callback(
                        payload(run_id, node_id, "running", seq, runtime_version=runtime_version)
                    )
                    seq += 1
                    post_callback(
                        payload(run_id, node_id, "heartbeat", seq, runtime_version=runtime_version)
                    )
                    seq += 1
                    interval = heartbeat_interval_seconds()
                    last_heartbeat = time.monotonic()
                    while process.poll() is None:
                        if stop_requested:
                            terminate_group(workload.pid)
                            break
                        time.sleep(min(interval, 0.5))
                        now = time.monotonic()
                        if process.poll() is None and now - last_heartbeat >= interval:
                            post_callback(
                                payload(
                                    run_id,
                                    node_id,
                                    "heartbeat",
                                    seq,
                                    runtime_version=runtime_version,
                                )
                            )
                            seq += 1
                            last_heartbeat = now
                    if stop_requested:
                        try:
                            process.wait(timeout=1)
                        except subprocess.TimeoutExpired:
                            pass
                        terminal = "aborted"
                        details = {"processGroupExited": False, "reason": "runner_stopped"}
                    else:
                        exit_code = process.wait()
                        sla_result = sla_result_for_exit(sla_evaluation_mode, exit_code)
                        if exit_code == 0 or sla_result == "failed":
                            terminal = "finished"
                            details = {"processGroupExited": False, "exitCode": exit_code}
                            if sla_result is not None:
                                details["slaResult"] = sla_result
                        else:
                            terminal = "failed"
                            details = {
                                "processGroupExited": False,
                                "reason": "runner_exit_nonzero",
                                "exitCode": exit_code,
                            }
                    process_group_exited = _wait_for_process_group_exit(
                        workload, group_exit_timeout_seconds()
                    )
                    details["processGroupExited"] = process_group_exited
        artifact_summary = upload_run_artifacts(
            run_id, node_id, seq, runtime_version=runtime_version
        )
        seq = artifact_summary.next_seq
        terminal_callback_ack = post_callback(
            payload(
                run_id,
                node_id,
                terminal,
                seq,
                runtime_version=runtime_version,
                details=details,
            )
        )
    finally:
        if workload is not None and not managed_process_group_alive(workload):
            cleanup_workload_pidfile(run_id)
        deleted = cleanup_run_directory_if_safe(
            run_id,
            terminal_callback_ack=terminal_callback_ack,
            artifact_results=artifact_summary.results,
            supervisor=supervisor,
            workload=workload,
        )
        if not deleted:
            cleanup_supervisor_pidfile(run_id)


def fake_scenario(run_id: str) -> None:
    require_safe_run_id(run_id)
    node_id = os.environ.get("SURGEPILOT_NODE_ID", "01HZX3Y9M0E9W7Z6M5QK9S8P7C")
    scenario = os.environ.get("RUNNER_FAKE_SCENARIO", "success")
    runtime_version = RUNNER_VERSION
    accepted = payload(
        run_id,
        node_id,
        "accepted",
        1,
        runtime_version=runtime_version,
        runnerPid=os.getpid(),
    )
    click.echo("accepted")
    post_callback(accepted)
    if scenario == "heartbeat_timeout":
        return
    click.echo("running")
    post_callback(payload(run_id, node_id, "running", 2, runtime_version=runtime_version))
    if scenario == "failed":
        click.echo("failed")
        post_callback(
            payload(
                run_id,
                node_id,
                "failed",
                3,
                runtime_version=runtime_version,
                details={"processGroupExited": True, "reason": "unknown_runner_error"},
            )
        )
        return
    if scenario == "aborted":
        click.echo("aborted")
        post_callback(
            payload(
                run_id,
                node_id,
                "aborted",
                3,
                runtime_version=runtime_version,
                details={"processGroupExited": True, "reason": "stop_grace_timeout"},
            )
        )
        return
    click.echo("heartbeat")
    post_callback(payload(run_id, node_id, "heartbeat", 3, runtime_version=runtime_version))
    artifact_path = run_dir(run_id) / "logs" / "runner.log"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text("fake runner completed successfully\n")
    upload = upload_artifact(
        run_id=run_id,
        node_id=node_id,
        artifact_type="run_log",
        relative_path="logs/runner.log",
        path=artifact_path,
    )
    if upload is not None:
        click.echo("artifact")
        post_callback(
            payload(
                run_id,
                node_id,
                "artifact",
                4,
                runtime_version=runtime_version,
                details={
                    "artifactId": upload["artifactId"],
                    "artifactType": "run_log",
                    "relativePath": "logs/runner.log",
                    "sizeBytes": upload["sizeBytes"],
                    "sha256": upload["sha256"],
                },
            )
        )
    click.echo("finished")
    post_callback(
        payload(
            run_id,
            node_id,
            "finished",
            5,
            runtime_version=runtime_version,
            details={"processGroupExited": True},
        )
    )


@click.group()
def cli() -> None:
    """SurgePilot runner CLI."""


@cli.command()
def version() -> None:
    click.echo("SurgePilot Runner 0.1.0")


@cli.command()
@click.option("--run-id", required=True, help="External run identifier.")
@click.option("--fake", is_flag=True, help="Use the local fake runner mode.")
def start(run_id: str, fake: bool) -> None:
    require_safe_run_id(run_id)
    if fake:
        fake_scenario(run_id)
        return
    if reconcile_managed_pidfiles_before_start():
        post_callback(
            payload(
                run_id,
                os.environ.get("SURGEPILOT_NODE_ID", "01HZX3Y9M0E9W7Z6M5QK9S8P7C"),
                "failed",
                1,
                runtime_version=RUNNER_VERSION,
                details={
                    "processGroupExited": False,
                    "reason": "stale_process_detected",
                },
            )
        )
        click.echo("stale managed process detected", err=True)
        raise click.ClickException("stale managed process detected")
    process = subprocess.Popen(
        [sys.executable, str(runner_entrypoint()), "managed", "--run-id", run_id],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    child_ready = False
    deadline = time.monotonic() + start_workload_wait_seconds()
    while time.monotonic() < deadline:
        if (
            read_supervisor_pidfile(run_id) is not None
            or read_workload_pidfile(run_id) is not None
        ):
            child_ready = True
            break
        if process.poll() is not None:
            break
        time.sleep(0.05)
    if not child_ready:
        if process.poll() is None:
            terminate_group(process.pid)
        raise click.ClickException("managed runner failed to start")
    click.echo(f"runner accepted run {run_id}")


@cli.command()
@click.option("--run-id", required=True, help="External run identifier.")
def stop(run_id: str) -> None:
    require_safe_run_id(run_id)
    supervisor_path = supervisor_pidfile_path(run_id)
    supervisor = read_supervisor_pidfile(run_id)
    if supervisor is None:
        if supervisor_path.exists():
            raw_supervisor = _read_managed_pidfile(supervisor_path, validate_starttime=False)
            if raw_supervisor is None:
                raise click.ClickException("suspicious managed process detected")
            workload = read_workload_pidfile_for_kill(run_id)
            if workload is not None and managed_process_group_alive(workload):
                raise click.ClickException("managed workload is still running without supervisor")
            click.echo(f"no managed process for run {run_id}")
            return
        fail_if_other_managed_process_exists(run_id)
        click.echo(f"no managed process for run {run_id}")
        return
    if _signal_and_wait_supervisor(supervisor):
        click.echo(f"stopped run {run_id}")
        return
    raise click.ClickException("managed supervisor did not stop")


@cli.command()
@click.option("--run-id", required=True, help="External run identifier.")
def kill(run_id: str) -> None:
    require_safe_run_id(run_id)
    killed = False
    supervisor_path = supervisor_pidfile_path(run_id)
    workload_path = workload_pidfile_path(run_id)
    if not supervisor_path.exists() and not workload_path.exists():
        deadline = time.monotonic() + start_workload_wait_seconds()
        while (
            time.monotonic() < deadline
            and not supervisor_path.exists()
            and not workload_path.exists()
        ):
            time.sleep(0.05)
    if supervisor_path.exists():
        supervisor = read_managed_pidfile_raw(supervisor_path)
        if supervisor is None:
            raise click.ClickException("suspicious managed process detected")
        if managed_pid_alive(supervisor):
            if not terminate_group(supervisor.pid):
                raise click.ClickException("managed supervisor did not exit")
            killed = True
        cleanup_supervisor_pidfile(run_id)
        if supervisor_path.exists():
            raise click.ClickException("managed supervisor cleanup is uncertain")

    # The supervisor can publish workload.pid while force-kill is arriving.
    # Read it only after the supervisor group has been confirmed terminated.
    workload = read_workload_pidfile_for_kill(run_id)
    if workload is None:
        if workload_path.exists():
            raise click.ClickException("suspicious managed process detected")
    else:
        if not terminate_group(workload.pid):
            raise click.ClickException("managed process did not exit")
        killed = True
        cleanup_workload_pidfile(run_id)
        if workload_path.exists():
            raise click.ClickException("managed workload cleanup is uncertain")

    if supervisor_path.exists() or workload_path.exists():
        raise click.ClickException("managed process cleanup is uncertain")
    fail_if_other_managed_process_exists(run_id)
    click.echo(f"{'killed' if killed else 'no managed process for'} run {run_id}")


@cli.command(hidden=True)
@click.option("--run-id", required=True, help="External run identifier.")
def managed(run_id: str) -> None:
    managed_run(run_id)
