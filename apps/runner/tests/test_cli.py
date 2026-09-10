from pathlib import Path
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
import urllib.error

from click.testing import CliRunner
from jsonschema import Draft202012Validator
import pytest

import surgepilot_runner.cli as runner_cli
import surgepilot_runner.jmeter_wrapper as jmeter_wrapper
from surgepilot_runner.cli import (
    cli,
    ManagedPid,
    ProcessGroupProbe,
    monitoring_properties_path,
    process_group_alive,
    read_workload_pidfile,
    supervisor_pidfile_path,
    validate_artifact_relative_path,
    workload_pidfile_path,
    write_pidfile,
    write_supervisor_pidfile,
    write_workload_pidfile,
)
from surgepilot_runner.jmeter_wrapper import (
    BACKEND_LISTENER_CLASSNAME,
    build_jmeter_wrapper_command,
    inject_monitoring_backend_listener,
)

ROOT = Path(__file__).resolve().parents[3]
CALLBACK_SCHEMA = json.loads(
    (ROOT / "packages" / "contracts" / "runner" / "runner-callback.schema.json").read_text()
)
CALLBACK_VALIDATOR = Draft202012Validator(CALLBACK_SCHEMA)
RUN_ID = "01HZX3Y9M0E9W7Z6M5QK9S8P7A"
NODE_ID = "01HZX3Y9M0E9W7Z6M5QK9S8P7B"
REQUIRES_LINUX_PROC = pytest.mark.skipif(
    not Path("/proc").exists(), reason="requires Linux /proc and real POSIX process groups"
)
RUNTIME_VERSION = "0.1.0"


def test_callback_schema_requires_runtime_version() -> None:
    callback = {
        "schemaVersion": "1",
        "eventId": "01HZX3Y9M0E9W7Z6M5QK9S8P7C",
        "runId": RUN_ID,
        "nodeId": NODE_ID,
        "eventType": "heartbeat",
        "seq": 1,
        "eventTime": "2030-06-01T10:00:00Z",
    }

    assert any(error.validator == "required" for error in CALLBACK_VALIDATOR.iter_errors(callback))


def test_sla_result_maps_only_pinned_taurus_passfail_exit_codes() -> None:
    assert runner_cli.sla_result_for_exit("passfail", 0) == "passed"
    assert runner_cli.sla_result_for_exit("passfail", 3) == "failed"
    assert runner_cli.sla_result_for_exit("passfail", 1) is None
    assert runner_cli.sla_result_for_exit("not_evaluated", 0) is None


def write_fake_bzt(tmp_path: Path, *, exit_code: int = 0, sleep_seconds: float = 0) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True)
    script = bin_dir / "bzt"
    script.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "from pathlib import Path",
                "import sys",
                "import time",
                f"time.sleep({sleep_seconds!r})",
                "Path('bzt.args').write_text(' '.join(sys.argv[1:]))",
                "artifacts = Path('artifacts')",
                "artifacts.mkdir(exist_ok=True)",
                "artifacts.joinpath('bzt.log').write_text('taurus log\\n')",
                "artifacts.joinpath('jmeter.log').write_text('jmeter log\\n')",
                "artifacts.joinpath('final_stats.csv').write_text('label,throughput,succ,fail,avg_rt\\n,1,1,0,0.1\\n')",
                "artifacts.joinpath('error.jtl').write_text('timeStamp,elapsed,label,responseCode\\n')",
                f"raise SystemExit({exit_code})",
            ]
        )
        + "\n"
    )
    script.chmod(0o755)
    return bin_dir


def write_run_bundle(
    tmp_path: Path, run_id: str = RUN_ID, *, sla_evaluation_mode: str = "not_evaluated"
) -> Path:
    bundle = tmp_path / "runs" / run_id / "bundle"
    bundle.mkdir(parents=True)
    (bundle / "surgepilot.yml").write_text("execution: []\n")
    (bundle / "manifest.json").write_text(
        json.dumps({"slaEvaluationMode": sla_evaluation_mode}), encoding="utf-8"
    )
    return bundle


def write_fake_proc_stat(
    proc_root: Path,
    pid: int,
    *,
    state: str,
    pgid: int,
    starttime: int,
    name: str = "cmd",
) -> None:
    proc_dir = proc_root / str(pid)
    proc_dir.mkdir(parents=True)
    fields = [
        state,
        "1",  # ppid
        str(pgid),
        str(pgid),  # session
        "0",
        "0",
        "0",
        "0",
        "0",
        "0",
        "0",
        "0",
        "0",
        "0",
        "0",
        "20",
        "0",
        "1",
        "0",
        str(starttime),
    ]
    (proc_dir / "stat").write_text(f"{pid} ({name}) {' '.join(fields)}\n")


def test_process_group_probe_treats_zombie_leader_with_live_member_as_alive(tmp_path: Path) -> None:
    proc_root = tmp_path / "proc"
    write_fake_proc_stat(proc_root, 100, state="Z", pgid=100, starttime=1000, name="bzt")
    write_fake_proc_stat(proc_root, 101, state="S", pgid=100, starttime=1001, name="java")

    probe = ProcessGroupProbe(proc_root=proc_root)

    assert probe.process_group_alive(100) is True


def test_process_group_probe_ignores_zombie_only_group(tmp_path: Path) -> None:
    proc_root = tmp_path / "proc"
    write_fake_proc_stat(proc_root, 100, state="Z", pgid=100, starttime=1000, name="bzt")

    probe = ProcessGroupProbe(proc_root=proc_root)

    assert probe.process_group_alive(100) is False


def test_process_group_probe_falls_back_to_killpg_when_proc_is_unavailable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[tuple[int, int]] = []

    def fake_killpg(pgid: int, sig: int) -> None:
        calls.append((pgid, sig))

    monkeypatch.setattr(runner_cli.os, "killpg", fake_killpg)
    probe = ProcessGroupProbe(proc_root=tmp_path / "missing-proc", use_killpg_fallback=True)

    assert probe.process_group_alive(12345) is True
    assert calls == [(12345, 0)]


def test_workload_pidfile_requires_matching_starttime(tmp_path: Path) -> None:
    proc_root = tmp_path / "proc"
    write_fake_proc_stat(proc_root, 123, state="S", pgid=123, starttime=4567, name="bzt")
    probe = ProcessGroupProbe(proc_root=proc_root)
    write_workload_pidfile("run_01", ManagedPid(pid=123, starttime="4567"), runner_home=tmp_path)

    workload = read_workload_pidfile("run_01", runner_home=tmp_path, probe=probe)

    assert workload == ManagedPid(pid=123, starttime="4567")
    write_workload_pidfile("run_01", ManagedPid(pid=123, starttime="9999"), runner_home=tmp_path)
    assert read_workload_pidfile("run_01", runner_home=tmp_path, probe=probe) is None


@REQUIRES_LINUX_PROC
def test_managed_runner_reports_process_group_not_exited_when_workload_child_survives(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    events: list[dict] = []
    write_run_bundle(tmp_path, "run_01")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True)
    child_pid_file = tmp_path / "child.pid"
    script = bin_dir / "bzt"
    script.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import os, time",
                "from pathlib import Path",
                f"child_file = Path({str(child_pid_file)!r})",
                "pid = os.fork()",
                "if pid == 0:",
                "    time.sleep(60)",
                "    raise SystemExit(0)",
                "child_file.write_text(str(pid))",
                "raise SystemExit(0)",
            ]
        )
        + "\n"
    )
    script.chmod(0o755)
    monkeypatch.setattr(
        "surgepilot_runner.cli.post_callback", lambda payload: events.append(payload)
    )
    monkeypatch.setattr("surgepilot_runner.cli.upload_artifact", lambda **kwargs: None)
    monkeypatch.setenv("RUNNER_HOME", str(tmp_path))
    monkeypatch.setenv("SURGEPILOT_NODE_ID", NODE_ID)
    monkeypatch.setenv("SURGEPILOT_RUNNER_GROUP_EXIT_TIMEOUT_SECONDS", "0.1")
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    try:
        runner_cli.managed_run("run_01")

        assert [event["eventType"] for event in events][-1] == "finished"
        assert events[-1]["details"]["processGroupExited"] is False
        assert workload_pidfile_path("run_01", base=tmp_path).exists()
    finally:
        workload = read_workload_pidfile("run_01", runner_home=tmp_path, validate_starttime=False)
        if workload is not None:
            try:
                os.killpg(workload.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


def test_start_does_not_recreate_supervisor_pidfile_after_child_exits(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class ExitedProcess:
        pid = 999999

        def poll(self) -> int:
            return 1

    monkeypatch.setattr(runner_cli.subprocess, "Popen", lambda *args, **kwargs: ExitedProcess())
    monkeypatch.setattr(runner_cli, "live_managed_pidfiles", lambda: [])
    monkeypatch.setattr(runner_cli, "suspicious_managed_pidfiles", lambda: [])
    monkeypatch.setattr(runner_cli, "start_workload_wait_seconds", lambda: 0.01)

    result = CliRunner().invoke(
        cli, ["start", "--run-id", "run_01"], env={"RUNNER_HOME": str(tmp_path)}
    )

    assert result.exit_code != 0
    assert "managed runner failed to start" in result.output
    assert not supervisor_pidfile_path("run_01", base=tmp_path).exists()


def test_start_deletes_stale_workload_pidfile_when_group_is_empty(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class ExitedProcess:
        pid = 999999

        def poll(self) -> int:
            return 1

    write_workload_pidfile("run_01", ManagedPid(pid=777, starttime="1111"), runner_home=tmp_path)
    monkeypatch.setattr(runner_cli.subprocess, "Popen", lambda *args, **kwargs: ExitedProcess())
    monkeypatch.setattr(runner_cli, "start_workload_wait_seconds", lambda: 0.01)

    result = CliRunner().invoke(
        cli, ["start", "--run-id", "run_01"], env={"RUNNER_HOME": str(tmp_path)}
    )

    assert result.exit_code != 0
    assert not workload_pidfile_path("run_01", base=tmp_path).exists()


def test_start_blocks_when_workload_leader_is_reaped_but_group_member_lives(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    proc_root = tmp_path / "proc"
    write_fake_proc_stat(proc_root, 778, state="S", pgid=777, starttime=2222, name="java")
    probe = ProcessGroupProbe(proc_root=proc_root)
    write_workload_pidfile("run_01", ManagedPid(pid=777, starttime="1111"), runner_home=tmp_path)
    monkeypatch.setattr(runner_cli, "ProcessGroupProbe", lambda: probe)
    monkeypatch.setattr(
        runner_cli.subprocess,
        "Popen",
        lambda *args, **kwargs: pytest.fail("start must not spawn over a live workload"),
    )

    result = CliRunner().invoke(
        cli, ["start", "--run-id", "run_01"], env={"RUNNER_HOME": str(tmp_path)}
    )

    assert result.exit_code != 0
    assert workload_pidfile_path("run_01", base=tmp_path).exists()
    assert "stale managed process detected" in result.output


def test_start_deletes_reused_workload_pidfile_without_scanning_reused_group(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class ExitedProcess:
        pid = 999999

        def poll(self) -> int:
            return 1

    class Probe(ProcessGroupProbe):
        def __init__(self) -> None:
            super().__init__(proc_root=tmp_path / "proc")

        def read_entry(self, pid: int):
            if pid == 777:
                return runner_cli.ProcEntry(pid=777, pgid=777, state="S", starttime="2222")
            return None

        def process_group_alive(self, pgid: int) -> bool:
            if pgid == 777:
                raise AssertionError("reused workload PGID must not be scanned")
            return False

    write_workload_pidfile("run_01", ManagedPid(pid=777, starttime="1111"), runner_home=tmp_path)
    monkeypatch.setattr(runner_cli, "ProcessGroupProbe", Probe)
    monkeypatch.setattr(runner_cli.subprocess, "Popen", lambda *args, **kwargs: ExitedProcess())
    monkeypatch.setattr(runner_cli, "start_workload_wait_seconds", lambda: 0.01)

    result = CliRunner().invoke(
        cli, ["start", "--run-id", "run_01"], env={"RUNNER_HOME": str(tmp_path)}
    )

    assert result.exit_code != 0
    assert not workload_pidfile_path("run_01", base=tmp_path).exists()


def test_start_blocks_when_starttime_matched_workload_group_is_live(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    proc_root = tmp_path / "proc"
    write_fake_proc_stat(proc_root, 777, state="S", pgid=777, starttime=1111, name="bzt")
    probe = ProcessGroupProbe(proc_root=proc_root)
    write_workload_pidfile("run_01", ManagedPid(pid=777, starttime="1111"), runner_home=tmp_path)
    monkeypatch.setattr(runner_cli, "ProcessGroupProbe", lambda: probe)
    monkeypatch.setattr(
        runner_cli.subprocess,
        "Popen",
        lambda *args, **kwargs: pytest.fail("start must not spawn over a live workload"),
    )

    result = CliRunner().invoke(
        cli, ["start", "--run-id", "run_01"], env={"RUNNER_HOME": str(tmp_path)}
    )

    assert result.exit_code != 0
    assert workload_pidfile_path("run_01", base=tmp_path).exists()


def test_start_deletes_stale_supervisor_pidfile(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class ExitedProcess:
        pid = 999999

        def poll(self) -> int:
            return 1

    proc_root = tmp_path / "proc"
    write_fake_proc_stat(proc_root, 777, state="S", pgid=777, starttime=2222, name="reused")
    probe = ProcessGroupProbe(proc_root=proc_root)
    write_supervisor_pidfile("run_01", ManagedPid(pid=777, starttime="1111"), runner_home=tmp_path)
    monkeypatch.setattr(runner_cli, "ProcessGroupProbe", lambda: probe)
    monkeypatch.setattr(runner_cli.subprocess, "Popen", lambda *args, **kwargs: ExitedProcess())
    monkeypatch.setattr(runner_cli, "start_workload_wait_seconds", lambda: 0.01)

    result = CliRunner().invoke(
        cli, ["start", "--run-id", "run_01"], env={"RUNNER_HOME": str(tmp_path)}
    )

    assert result.exit_code != 0
    assert not supervisor_pidfile_path("run_01", base=tmp_path).exists()


def test_start_deletes_corrupt_supervisor_pidfile(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class ExitedProcess:
        pid = 999999

        def poll(self) -> int:
            return 1

    supervisor_pidfile_path("run_01", base=tmp_path).parent.mkdir(parents=True)
    supervisor_pidfile_path("run_01", base=tmp_path).write_text("not-json\n")
    monkeypatch.setattr(runner_cli.subprocess, "Popen", lambda *args, **kwargs: ExitedProcess())
    monkeypatch.setattr(runner_cli, "start_workload_wait_seconds", lambda: 0.01)

    result = CliRunner().invoke(
        cli, ["start", "--run-id", "run_01"], env={"RUNNER_HOME": str(tmp_path)}
    )

    assert result.exit_code != 0
    assert not supervisor_pidfile_path("run_01", base=tmp_path).exists()


def test_start_archives_corrupt_workload_pidfile(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class ExitedProcess:
        pid = 999999

        def poll(self) -> int:
            return 1

    workload_pidfile_path("run_01", base=tmp_path).parent.mkdir(parents=True)
    workload_pidfile_path("run_01", base=tmp_path).write_text("not-json\n")
    monkeypatch.setattr(runner_cli.subprocess, "Popen", lambda *args, **kwargs: ExitedProcess())
    monkeypatch.setattr(runner_cli, "start_workload_wait_seconds", lambda: 0.01)

    result = CliRunner().invoke(
        cli, ["start", "--run-id", "run_01"], env={"RUNNER_HOME": str(tmp_path)}
    )

    assert result.exit_code != 0
    assert not workload_pidfile_path("run_01", base=tmp_path).exists()
    assert list(
        workload_pidfile_path("run_01", base=tmp_path).parent.glob("workload.pid.corrupt.*")
    )


def test_start_blocks_when_corrupt_workload_pidfile_archive_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workload_pidfile_path("run_01", base=tmp_path).parent.mkdir(parents=True)
    workload_pidfile_path("run_01", base=tmp_path).write_text("not-json\n")

    def fail_replace(src, dst) -> None:
        raise OSError("archive failed")

    monkeypatch.setattr(runner_cli.os, "replace", fail_replace)
    monkeypatch.setattr(
        runner_cli.subprocess,
        "Popen",
        lambda *args, **kwargs: pytest.fail("start must not spawn when archive fails"),
    )

    result = CliRunner().invoke(
        cli, ["start", "--run-id", "run_01"], env={"RUNNER_HOME": str(tmp_path)}
    )

    assert result.exit_code != 0
    assert workload_pidfile_path("run_01", base=tmp_path).exists()
    assert "stale managed process detected" in result.output


def test_write_managed_pidfile_uses_atomic_replace(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    replaced: list[tuple[Path, Path]] = []
    real_replace = os.replace

    def spy_replace(src, dst) -> None:
        replaced.append((Path(src), Path(dst)))
        real_replace(src, dst)

    monkeypatch.setattr(runner_cli.os, "replace", spy_replace)

    path = write_workload_pidfile(
        "run_01", ManagedPid(pid=777, starttime="1111"), runner_home=tmp_path
    )

    assert json.loads(path.read_text()) == {"pid": 777, "starttime": "1111"}
    assert replaced
    assert replaced[-1][1] == path
    assert replaced[-1][0].parent == path.parent


def test_stop_is_idempotent_when_same_run_supervisor_pidfile_is_stale(
    tmp_path: Path,
) -> None:
    write_supervisor_pidfile(
        "run_01", ManagedPid(pid=999999, starttime="stale-starttime"), runner_home=tmp_path
    )

    result = CliRunner().invoke(
        cli, ["stop", "--run-id", "run_01"], env={"RUNNER_HOME": str(tmp_path)}
    )

    assert result.exit_code == 0
    assert "no managed process" in result.output
    assert supervisor_pidfile_path("run_01", base=tmp_path).exists()


def test_stop_is_idempotent_when_same_run_supervisor_pid_is_reused_without_workload(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    proc_root = tmp_path / "proc"
    write_fake_proc_stat(proc_root, 777, state="S", pgid=777, starttime=2222, name="reused")
    probe = ProcessGroupProbe(proc_root=proc_root)
    write_supervisor_pidfile("run_01", ManagedPid(pid=777, starttime="1111"), runner_home=tmp_path)
    monkeypatch.setattr(runner_cli, "ProcessGroupProbe", lambda: probe)

    result = CliRunner().invoke(
        cli, ["stop", "--run-id", "run_01"], env={"RUNNER_HOME": str(tmp_path)}
    )

    assert result.exit_code == 0
    assert "no managed process" in result.output
    assert supervisor_pidfile_path("run_01", base=tmp_path).exists()


def test_stop_signals_supervisor_without_deleting_pidfiles(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[tuple[int, int]] = []
    write_supervisor_pidfile("run_01", ManagedPid(pid=321, starttime=None), runner_home=tmp_path)
    write_workload_pidfile("run_01", ManagedPid(pid=654, starttime=None), runner_home=tmp_path)
    states = iter([True, False])
    monkeypatch.setattr(runner_cli, "managed_pid_alive", lambda managed, probe=None: next(states))
    monkeypatch.setattr(runner_cli.os, "killpg", lambda pgid, sig: calls.append((pgid, sig)))

    result = CliRunner().invoke(
        cli, ["stop", "--run-id", "run_01"], env={"RUNNER_HOME": str(tmp_path)}
    )

    assert result.exit_code == 0
    assert calls == [(321, signal.SIGTERM)]
    assert supervisor_pidfile_path("run_01", base=tmp_path).exists()
    assert workload_pidfile_path("run_01", base=tmp_path).exists()


def test_default_stop_supervisor_timeout_covers_supervisor_cleanup_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SURGEPILOT_RUNNER_STOP_SUPERVISOR_TIMEOUT_SECONDS", raising=False)

    assert runner_cli.stop_supervisor_timeout_seconds() >= 120


def test_kill_deletes_same_run_pidfiles_only_after_success(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    write_supervisor_pidfile("run_01", ManagedPid(pid=321, starttime=None), runner_home=tmp_path)
    write_workload_pidfile("run_01", ManagedPid(pid=654, starttime=None), runner_home=tmp_path)
    monkeypatch.setattr(runner_cli, "terminate_group", lambda pgid: True)

    result = CliRunner().invoke(
        cli, ["kill", "--run-id", "run_01"], env={"RUNNER_HOME": str(tmp_path)}
    )

    assert result.exit_code == 0
    assert not supervisor_pidfile_path("run_01", base=tmp_path).exists()
    assert not workload_pidfile_path("run_01", base=tmp_path).exists()


def test_kill_without_workload_terminates_live_same_run_supervisor(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    write_supervisor_pidfile("run_01", ManagedPid(pid=321, starttime=None), runner_home=tmp_path)
    terminated: set[int] = set()
    monkeypatch.setattr(
        runner_cli, "managed_pid_alive", lambda managed, probe=None: managed.pid not in terminated
    )
    monkeypatch.setattr(runner_cli, "terminate_group", lambda pgid: not terminated.add(pgid))

    result = CliRunner().invoke(
        cli, ["kill", "--run-id", "run_01"], env={"RUNNER_HOME": str(tmp_path)}
    )

    assert result.exit_code == 0
    assert terminated == {321}
    assert not supervisor_pidfile_path("run_01", base=tmp_path).exists()


def test_kill_waits_for_inflight_start_identity(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    terminated: set[int] = set()

    def publish_supervisor(_seconds: float) -> None:
        write_supervisor_pidfile(
            "run_01", ManagedPid(pid=321, starttime=None), runner_home=tmp_path
        )

    monkeypatch.setattr(runner_cli, "start_workload_wait_seconds", lambda: 1.0)
    monkeypatch.setattr(runner_cli.time, "sleep", publish_supervisor)
    monkeypatch.setattr(
        runner_cli, "managed_pid_alive", lambda managed, probe=None: managed.pid not in terminated
    )
    monkeypatch.setattr(runner_cli, "terminate_group", lambda pgid: not terminated.add(pgid))

    result = CliRunner().invoke(
        cli, ["kill", "--run-id", "run_01"], env={"RUNNER_HOME": str(tmp_path)}
    )

    assert result.exit_code == 0
    assert terminated == {321}


def test_kill_rereads_workload_after_terminating_supervisor(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    write_supervisor_pidfile("run_01", ManagedPid(pid=321, starttime=None), runner_home=tmp_path)
    terminated: set[int] = set()

    def terminate(pgid: int) -> bool:
        terminated.add(pgid)
        if pgid == 321:
            write_workload_pidfile(
                "run_01", ManagedPid(pid=654, starttime=None), runner_home=tmp_path
            )
        return True

    monkeypatch.setattr(
        runner_cli, "managed_pid_alive", lambda managed, probe=None: managed.pid not in terminated
    )
    monkeypatch.setattr(runner_cli, "terminate_group", terminate)

    result = CliRunner().invoke(
        cli, ["kill", "--run-id", "run_01"], env={"RUNNER_HOME": str(tmp_path)}
    )

    assert result.exit_code == 0
    assert terminated == {321, 654}
    assert not supervisor_pidfile_path("run_01", base=tmp_path).exists()
    assert not workload_pidfile_path("run_01", base=tmp_path).exists()


def test_kill_preserves_supervisor_pidfile_when_supervisor_exit_is_unconfirmed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    write_supervisor_pidfile("run_01", ManagedPid(pid=321, starttime=None), runner_home=tmp_path)
    monkeypatch.setattr(runner_cli, "managed_pid_alive", lambda managed, probe=None: True)
    monkeypatch.setattr(runner_cli, "terminate_group", lambda pgid: False)

    result = CliRunner().invoke(
        cli, ["kill", "--run-id", "run_01"], env={"RUNNER_HOME": str(tmp_path)}
    )

    assert result.exit_code != 0
    assert supervisor_pidfile_path("run_01", base=tmp_path).exists()


@REQUIRES_LINUX_PROC
def test_kill_rejects_workload_pidfile_when_starttime_mismatches(tmp_path: Path) -> None:
    write_workload_pidfile(
        "run_01", ManagedPid(pid=os.getpid(), starttime="wrong-starttime"), runner_home=tmp_path
    )

    result = CliRunner().invoke(
        cli, ["kill", "--run-id", "run_01"], env={"RUNNER_HOME": str(tmp_path)}
    )

    assert result.exit_code != 0
    assert workload_pidfile_path("run_01", base=tmp_path).exists()


def test_kill_allows_cleanup_when_workload_leader_is_gone_but_group_member_lives(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    proc_root = tmp_path / "proc"
    write_fake_proc_stat(proc_root, 778, state="S", pgid=777, starttime=2222, name="java")
    probe = ProcessGroupProbe(proc_root=proc_root)
    write_workload_pidfile("run_01", ManagedPid(pid=777, starttime="1111"), runner_home=tmp_path)
    terminated: list[int] = []
    monkeypatch.setattr(runner_cli, "ProcessGroupProbe", lambda: probe)
    monkeypatch.setattr(runner_cli, "terminate_group", lambda pgid: terminated.append(pgid) or True)

    result = CliRunner().invoke(
        cli, ["kill", "--run-id", "run_01"], env={"RUNNER_HOME": str(tmp_path)}
    )

    assert result.exit_code == 0
    assert terminated == [777]
    assert not workload_pidfile_path("run_01", base=tmp_path).exists()


def test_kill_preserves_workload_pidfile_after_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    write_workload_pidfile("run_01", ManagedPid(pid=654, starttime=None), runner_home=tmp_path)
    monkeypatch.setattr(runner_cli, "terminate_group", lambda pgid: False)

    result = CliRunner().invoke(
        cli, ["kill", "--run-id", "run_01"], env={"RUNNER_HOME": str(tmp_path)}
    )

    assert result.exit_code != 0
    assert workload_pidfile_path("run_01", base=tmp_path).exists()


def test_cli_help_lists_runner_commands() -> None:
    result = CliRunner().invoke(cli, ["--help"])

    assert result.exit_code == 0
    assert "version" in result.output
    assert "start" in result.output
    assert "stop" in result.output
    assert "kill" in result.output


def test_version_command_reports_runner_version() -> None:
    result = CliRunner().invoke(cli, ["version"])

    assert result.exit_code == 0
    assert result.output.strip() == "SurgePilot Runner 0.1.0"


def test_start_fake_accepts_run_id_and_uses_protocol_words(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        cli,
        ["start", "--run-id", "run_01", "--fake"],
        env={
            "RUNNER_HOME": str(tmp_path),
            "RUNNER_FAKE_SCENARIO": "success",
        },
    )

    assert result.exit_code == 0
    assert "accepted" in result.output
    assert "finished" in result.output


def test_artifact_relative_path_validator_rejects_unsafe_examples() -> None:
    assert validate_artifact_relative_path("logs/runner.log") == "logs/runner.log"
    for value in ["/abs.log", "../secret", "logs\\runner.log", "logs//runner.log", "C:/x"]:
        try:
            validate_artifact_relative_path(value)
        except ValueError:
            pass
        else:  # pragma: no cover - makes failure clearer
            raise AssertionError(f"accepted unsafe path {value}")


def test_stop_and_kill_are_idempotent_when_pidfile_missing(tmp_path: Path) -> None:
    env = {"RUNNER_HOME": str(tmp_path)}
    stop = CliRunner().invoke(cli, ["stop", "--run-id", "missing"], env=env)
    kill = CliRunner().invoke(cli, ["kill", "--run-id", "missing"], env=env)

    assert stop.exit_code == 0
    assert kill.exit_code == 0
    assert "no managed process" in stop.output
    assert "no managed process" in kill.output


@REQUIRES_LINUX_PROC
def test_stop_and_kill_fail_missing_target_pidfile_when_other_managed_process_is_live(
    tmp_path: Path,
) -> None:
    process = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        start_new_session=True,
    )
    try:
        write_pidfile("other_run", process.pid, runner_home=tmp_path)
        env = {"RUNNER_HOME": str(tmp_path)}

        stop = CliRunner().invoke(cli, ["stop", "--run-id", "missing"], env=env)
        kill = CliRunner().invoke(cli, ["kill", "--run-id", "missing"], env=env)

        assert stop.exit_code != 0
        assert kill.exit_code != 0
        assert "suspicious managed process detected" in stop.output
        assert "suspicious managed process detected" in kill.output
    finally:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=5)


def test_pidfile_is_scoped_to_run_directory(tmp_path: Path) -> None:
    pidfile = write_pidfile("run_01", 12345, runner_home=tmp_path)

    assert pidfile == tmp_path / "runs" / "run_01" / "supervisor.pid"
    assert json.loads(pidfile.read_text()) == {"pid": 12345, "starttime": None}
    assert str(tmp_path) in str(pidfile)


def test_runner_rejects_unsafe_run_id_for_pidfile(tmp_path: Path) -> None:
    for value in ["../escape", "nested/run", "run\\bad", "", ".", ".."]:
        result = CliRunner().invoke(
            cli, ["stop", "--run-id", value], env={"RUNNER_HOME": str(tmp_path)}
        )

        assert result.exit_code != 0


@REQUIRES_LINUX_PROC
def test_start_refuses_live_managed_pidfile_from_another_run(tmp_path: Path) -> None:
    process = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        start_new_session=True,
    )
    try:
        write_pidfile("run_a", process.pid, runner_home=tmp_path)

        result = CliRunner().invoke(
            cli, ["start", "--run-id", "run_b"], env={"RUNNER_HOME": str(tmp_path)}
        )

        assert result.exit_code != 0
        assert "stale managed process detected" in result.output
    finally:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=5)


def test_managed_runner_executes_bzt_bundle_and_uploads_artifacts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    events: list[dict] = []
    uploads: list[dict] = []
    bundle = write_run_bundle(tmp_path, "run_01")
    bin_dir = write_fake_bzt(tmp_path)
    monkeypatch.setattr(
        "surgepilot_runner.cli.post_callback", lambda payload: events.append(payload)
    )
    monkeypatch.setattr(
        "surgepilot_runner.cli.upload_artifact",
        lambda **kwargs: (
            uploads.append(kwargs)
            or {
                "artifactId": "01HZX3Y9M0E9W7Z6M5QK9S8P7C",
                "sizeBytes": kwargs["path"].stat().st_size,
                "sha256": "a" * 64,
            }
        ),
    )
    monkeypatch.setenv("RUNNER_HOME", str(tmp_path))
    monkeypatch.setenv("SURGEPILOT_NODE_ID", "node_01")
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    runner_cli.managed_run("run_01")

    assert (bundle / "bzt.args").read_text() == "-n surgepilot.yml"
    assert [event["eventType"] for event in events][:3] == ["accepted", "running", "heartbeat"]
    assert [event["eventType"] for event in events][-1] == "finished"
    assert events[0]["runnerPid"] > 0
    assert events[-1]["details"]["processGroupExited"] is True
    assert {upload["artifact_type"] for upload in uploads} >= {
        "final_stats_csv",
        "taurus_log",
        "jmeter_log",
        "run_log",
    }
    upload_types = [upload["artifact_type"] for upload in uploads]
    assert "artifacts_zip" not in set(upload_types)
    assert "failed_requests_csv" not in set(upload_types)


def test_managed_runner_deletes_run_directory_after_terminal_ack_and_safe_uploads(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    events: list[dict] = []
    write_run_bundle(tmp_path, "run_01")
    bin_dir = write_fake_bzt(tmp_path)
    monkeypatch.setattr(
        "surgepilot_runner.cli.post_callback",
        lambda payload: events.append(payload) or True,
    )
    monkeypatch.setattr(
        "surgepilot_runner.cli.upload_artifact",
        lambda **kwargs: {
            "artifactId": "01HZX3Y9M0E9W7Z6M5QK9S8P7C",
            "sizeBytes": kwargs["path"].stat().st_size,
            "sha256": "a" * 64,
        },
    )
    monkeypatch.setenv("RUNNER_HOME", str(tmp_path))
    monkeypatch.setenv("SURGEPILOT_NODE_ID", NODE_ID)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    runner_cli.managed_run("run_01")

    assert [event["eventType"] for event in events][-1] == "finished"
    assert not runner_cli.run_dir("run_01").exists()


def test_cleanup_gate_keeps_run_directory_when_terminal_callback_is_not_acked(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("RUNNER_HOME", str(tmp_path))
    root = runner_cli.run_dir("run_01")
    root.mkdir(parents=True)

    deleted = runner_cli.cleanup_run_directory_if_safe(
        "run_01",
        terminal_callback_ack=False,
        artifact_results=[
            runner_cli.ArtifactUploadResult(
                artifact_type="run_log",
                relative_path="logs/runner.log",
                status="uploaded",
                path=root / "logs" / "runner.log",
            )
        ],
        supervisor=runner_cli.ManagedPid(pid=os.getpid(), starttime=None),
        workload=None,
    )

    assert deleted is False
    assert root.exists()


def test_cleanup_gate_keeps_run_directory_when_artifact_upload_failed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("RUNNER_HOME", str(tmp_path))
    root = runner_cli.run_dir("run_01")
    root.mkdir(parents=True)

    deleted = runner_cli.cleanup_run_directory_if_safe(
        "run_01",
        terminal_callback_ack=True,
        artifact_results=[
            runner_cli.ArtifactUploadResult(
                artifact_type="final_stats_csv",
                relative_path="artifacts/final_stats.csv",
                status="uploaded",
                path=root / "bundle" / "artifacts" / "final_stats.csv",
            ),
            runner_cli.ArtifactUploadResult(
                artifact_type="run_log",
                relative_path="logs/runner.log",
                status="failed",
                path=root / "logs" / "runner.log",
            ),
        ],
        supervisor=runner_cli.ManagedPid(pid=os.getpid(), starttime=None),
        workload=None,
    )

    assert deleted is False
    assert root.exists()


def test_cleanup_gate_keeps_run_directory_when_workload_group_is_live(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("RUNNER_HOME", str(tmp_path))
    root = runner_cli.run_dir("run_01")
    root.mkdir(parents=True)
    proc_root = tmp_path / "proc"
    write_fake_proc_stat(proc_root, 100, state="S", pgid=100, starttime=1000)

    deleted = runner_cli.cleanup_run_directory_if_safe(
        "run_01",
        terminal_callback_ack=True,
        artifact_results=[
            runner_cli.ArtifactUploadResult(
                artifact_type="run_log",
                relative_path="logs/runner.log",
                status="uploaded",
                path=root / "logs" / "runner.log",
            )
        ],
        supervisor=runner_cli.ManagedPid(pid=os.getpid(), starttime=None),
        workload=runner_cli.ManagedPid(pid=100, starttime="1000"),
        probe=runner_cli.ProcessGroupProbe(proc_root=proc_root),
    )

    assert deleted is False
    assert root.exists()


def test_cleanup_gate_keeps_run_directory_when_pidfile_is_uncertain(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("RUNNER_HOME", str(tmp_path))
    root = runner_cli.run_dir("run_01")
    root.mkdir(parents=True)
    runner_cli.write_supervisor_pidfile(
        "run_01",
        runner_cli.ManagedPid(pid=os.getpid(), starttime="unexpected-starttime"),
        runner_home=tmp_path,
    )

    deleted = runner_cli.cleanup_run_directory_if_safe(
        "run_01",
        terminal_callback_ack=True,
        artifact_results=[
            runner_cli.ArtifactUploadResult(
                artifact_type="run_log",
                relative_path="logs/runner.log",
                status="uploaded",
                path=root / "logs" / "runner.log",
            )
        ],
        supervisor=runner_cli.ManagedPid(pid=os.getpid(), starttime=None),
        workload=None,
    )

    assert deleted is False
    assert root.exists()


def test_upload_artifact_skips_files_above_hard_limit_before_reading(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    artifact_path = tmp_path / "too-large.log"
    artifact_path.write_bytes(b"x")
    monkeypatch.setattr(
        "surgepilot_runner.cli.MAX_ARTIFACT_UPLOAD_BYTES",
        0,
    )
    monkeypatch.setenv("SURGEPILOT_API_BASE_URL", "http://api.internal")
    monkeypatch.setenv("RUNNER_INTERNAL_TOKEN", "runner-token")
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *args, **kwargs: pytest.fail("oversized artifact should not be uploaded"),
    )

    result = runner_cli.upload_artifact(
        run_id="run_01",
        node_id=NODE_ID,
        artifact_type="run_log",
        relative_path="logs/too-large.log",
        path=artifact_path,
    )

    assert result is None


def test_upload_artifact_streams_multipart_without_read_bytes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    content = b"runner artifact content\n"
    artifact_path = tmp_path / "runner.log"
    artifact_path.write_bytes(content)
    captured: dict[str, object] = {}

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self) -> bytes:
            return json.dumps({"artifactId": "01HZX3Y9M0E9W7Z6M5QK9S8P7C"}).encode()

    def fail_read_bytes(self: Path) -> bytes:
        pytest.fail("upload_artifact must not read the whole file with Path.read_bytes()")

    def fake_urlopen(request, timeout):
        assert timeout == 5
        captured["data_type"] = type(request.data)
        assert not isinstance(request.data, (bytes, bytearray))
        body = b"".join(request.data)
        captured["body"] = body
        captured["headers"] = dict(request.header_items())
        return Response()

    monkeypatch.setenv("SURGEPILOT_API_BASE_URL", "http://api.internal")
    monkeypatch.setenv("RUNNER_INTERNAL_TOKEN", "runner-token")
    monkeypatch.setattr(Path, "read_bytes", fail_read_bytes)
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    result = runner_cli.upload_artifact(
        run_id="run_01",
        node_id=NODE_ID,
        artifact_type="run_log",
        relative_path="logs/runner.log",
        path=artifact_path,
    )

    expected_sha = hashlib.sha256(content).hexdigest()
    assert result == {
        "artifactId": "01HZX3Y9M0E9W7Z6M5QK9S8P7C",
        "sizeBytes": len(content),
        "sha256": expected_sha,
    }
    body = captured["body"]
    assert isinstance(body, bytes)
    headers = {key.lower(): value for key, value in dict(captured["headers"]).items()}
    assert headers["content-length"] == str(len(body))
    assert b'name="artifactType"\r\n\r\nrun_log' in body
    assert b'name="relativePath"\r\n\r\nlogs/runner.log' in body
    assert f'name="sha256"\r\n\r\n{expected_sha}'.encode() in body
    assert b'Content-Disposition: form-data; name="file"; filename="runner.log"' in body
    assert content in body


def test_managed_runner_reports_failed_when_bzt_exits_nonzero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    events: list[dict] = []
    write_run_bundle(tmp_path, RUN_ID)
    bin_dir = write_fake_bzt(tmp_path, exit_code=7)
    monkeypatch.setattr(
        "surgepilot_runner.cli.post_callback", lambda payload: events.append(payload)
    )
    monkeypatch.setattr(
        "surgepilot_runner.cli.upload_artifact",
        lambda **kwargs: {
            "artifactId": "01HZX3Y9M0E9W7Z6M5QK9S8P7C",
            "sizeBytes": kwargs["path"].stat().st_size,
            "sha256": "a" * 64,
        },
    )
    monkeypatch.setenv("RUNNER_HOME", str(tmp_path))
    monkeypatch.setenv("SURGEPILOT_NODE_ID", NODE_ID)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    runner_cli.managed_run(RUN_ID)

    assert [event["eventType"] for event in events][-1] == "failed"
    assert events[-1]["details"]["reason"] == "runner_exit_nonzero"
    assert events[-1]["details"]["exitCode"] == 7


def test_managed_runner_maps_taurus_passfail_exit_to_finished_sla_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    events: list[dict] = []
    write_run_bundle(tmp_path, RUN_ID, sla_evaluation_mode="passfail")
    bin_dir = write_fake_bzt(tmp_path, exit_code=3)
    monkeypatch.setattr(
        "surgepilot_runner.cli.post_callback", lambda payload: events.append(payload) or True
    )
    monkeypatch.setattr("surgepilot_runner.cli.upload_artifact", lambda **_kwargs: None)
    monkeypatch.setenv("RUNNER_HOME", str(tmp_path))
    monkeypatch.setenv("SURGEPILOT_NODE_ID", NODE_ID)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    runner_cli.managed_run(RUN_ID)

    assert events[-1]["eventType"] == "finished"
    assert events[-1]["details"]["exitCode"] == 3
    assert events[-1]["details"]["slaResult"] == "failed"


@REQUIRES_LINUX_PROC
def test_managed_runner_reports_aborted_process_group_exit_from_probe(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    events: list[dict] = []
    liveness_checks: list[ManagedPid] = []
    write_run_bundle(tmp_path, "run_01")
    bin_dir = write_fake_bzt(tmp_path, sleep_seconds=60)

    def stop_after_running(event: dict) -> None:
        events.append(event)
        if event["eventType"] == "running":
            os.kill(os.getpid(), signal.SIGTERM)

    monkeypatch.setattr("surgepilot_runner.cli.post_callback", stop_after_running)
    monkeypatch.setattr("surgepilot_runner.cli.upload_artifact", lambda **kwargs: None)

    def fake_managed_process_group_alive(managed, probe=None):
        liveness_checks.append(managed)
        return False

    monkeypatch.setattr(
        "surgepilot_runner.cli.managed_process_group_alive", fake_managed_process_group_alive
    )
    monkeypatch.setenv("RUNNER_HOME", str(tmp_path))
    monkeypatch.setenv("SURGEPILOT_NODE_ID", NODE_ID)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    runner_cli.managed_run("run_01")

    assert [event["eventType"] for event in events][-1] == "aborted"
    assert events[-1]["details"]["processGroupExited"] is True
    assert liveness_checks


def test_managed_runner_fails_safely_when_bundle_is_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    events: list[dict] = []
    monkeypatch.setattr(
        "surgepilot_runner.cli.post_callback", lambda payload: events.append(payload)
    )
    monkeypatch.setenv("RUNNER_HOME", str(tmp_path))
    monkeypatch.setenv("SURGEPILOT_NODE_ID", NODE_ID)

    runner_cli.managed_run(RUN_ID)

    assert [event["eventType"] for event in events] == ["accepted", "failed"]
    assert events[-1]["details"]["reason"] == "bundle_invalid"


@REQUIRES_LINUX_PROC
def test_start_real_spawns_managed_process_and_kill_cleans_up(tmp_path: Path) -> None:
    write_run_bundle(tmp_path, "run_01")
    bin_dir = write_fake_bzt(tmp_path, sleep_seconds=60)
    env = {
        "RUNNER_HOME": str(tmp_path),
        "SURGEPILOT_RUNNER_HEARTBEAT_INTERVAL_SECONDS": "1",
        "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
    }
    start = CliRunner().invoke(cli, ["start", "--run-id", "run_01"], env=env)

    assert start.exit_code == 0
    pidfile = workload_pidfile_path("run_01", base=tmp_path)
    workload = read_workload_pidfile("run_01", runner_home=tmp_path)
    deadline = time.monotonic() + 5
    while workload is None and time.monotonic() < deadline:
        time.sleep(0.05)
        workload = read_workload_pidfile("run_01", runner_home=tmp_path)
    assert workload is not None
    assert process_group_alive(workload.pid)

    kill = CliRunner().invoke(cli, ["kill", "--run-id", "run_01"], env=env)

    assert kill.exit_code == 0
    assert not process_group_alive(workload.pid)
    assert not pidfile.exists()


def test_terminate_group_rejects_self_process_group(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[int, int]] = []

    def fake_killpg(pgid: int, sig: int) -> None:
        calls.append((pgid, sig))
        raise AssertionError("self process group must not be signalled")

    monkeypatch.setattr(runner_cli.os, "killpg", fake_killpg)

    assert runner_cli.terminate_group(os.getpgrp()) is False
    assert calls == []


def test_post_callback_uses_bounded_backoff_without_logging_token(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    attempts = []
    sleeps: list[int] = []
    monkeypatch.setenv("SURGEPILOT_API_BASE_URL", "http://api.internal")
    monkeypatch.setenv("RUNNER_INTERNAL_TOKEN", "runner-secret-token")

    def fail_urlopen(request, timeout):
        attempts.append((request.full_url, timeout))
        raise urllib.error.URLError("network unavailable")

    monkeypatch.setattr(runner_cli.urllib.request, "urlopen", fail_urlopen)
    monkeypatch.setattr(runner_cli.time, "sleep", lambda delay: sleeps.append(delay))

    runner_cli.post_callback(
        runner_cli.payload(RUN_ID, NODE_ID, "heartbeat", 1, runtime_version=RUNTIME_VERSION)
    )

    captured = capsys.readouterr()
    assert len(attempts) == 5
    assert sleeps == [1, 2, 4, 8]
    assert "runner-secret-token" not in captured.out
    assert "runner-secret-token" not in captured.err


class UrlopenResponse:
    def __init__(self, body: dict, status: int = 200) -> None:
        self.status = status
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return json.dumps(self.body).encode()


def test_post_callback_requires_semantic_ack_without_ignored_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SURGEPILOT_API_BASE_URL", "http://api.internal")
    monkeypatch.setenv("RUNNER_INTERNAL_TOKEN", "runner-token")
    monkeypatch.setattr(
        runner_cli.urllib.request,
        "urlopen",
        lambda request, timeout: UrlopenResponse(
            {
                "accepted": True,
                "duplicate": False,
                "stateChanged": False,
                "currentState": "running",
                "ignoredReason": "illegal_transition",
            }
        ),
    )

    acked = runner_cli.post_callback(
        runner_cli.payload(RUN_ID, NODE_ID, "finished", 1, runtime_version=RUNTIME_VERSION)
    )

    assert acked is False


def test_post_callback_accepts_safe_duplicate_ack(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SURGEPILOT_API_BASE_URL", "http://api.internal")
    monkeypatch.setenv("RUNNER_INTERNAL_TOKEN", "runner-token")
    monkeypatch.setattr(
        runner_cli.urllib.request,
        "urlopen",
        lambda request, timeout: UrlopenResponse(
            {
                "accepted": True,
                "duplicate": True,
                "stateChanged": False,
                "currentState": "finished",
                "ignoredReason": None,
            }
        ),
    )

    acked = runner_cli.post_callback(
        runner_cli.payload(RUN_ID, NODE_ID, "finished", 1, runtime_version=RUNTIME_VERSION)
    )

    assert acked is True


def test_fake_runner_callbacks_validate_against_shared_schema(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    events: list[dict] = []
    monkeypatch.setattr(
        "surgepilot_runner.cli.post_callback", lambda payload: events.append(payload)
    )

    result = CliRunner().invoke(
        cli,
        ["start", "--run-id", RUN_ID, "--fake"],
        env={
            "RUNNER_HOME": str(tmp_path),
            "SURGEPILOT_NODE_ID": NODE_ID,
            "RUNNER_FAKE_SCENARIO": "failed",
        },
    )

    assert result.exit_code == 0
    assert [event["eventType"] for event in events] == ["accepted", "running", "failed"]
    for event in events:
        CALLBACK_VALIDATOR.validate(event)


def test_fake_success_uploads_artifact_and_emits_artifact_callback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    events: list[dict] = []
    uploads: list[dict] = []
    monkeypatch.setattr(
        "surgepilot_runner.cli.post_callback", lambda payload: events.append(payload)
    )

    def fake_upload_artifact(*, run_id, node_id, artifact_type, relative_path, path):
        uploads.append(
            {
                "runId": run_id,
                "nodeId": node_id,
                "artifactType": artifact_type,
                "relativePath": relative_path,
                "path": path,
            }
        )
        return {
            "artifactId": "01HZX3Y9M0E9W7Z6M5QK9S8P7C",
            "sizeBytes": path.stat().st_size,
            "sha256": __import__("hashlib").sha256(path.read_bytes()).hexdigest(),
        }

    monkeypatch.setattr("surgepilot_runner.cli.upload_artifact", fake_upload_artifact)

    result = CliRunner().invoke(
        cli,
        ["start", "--run-id", RUN_ID, "--fake"],
        env={
            "RUNNER_HOME": str(tmp_path),
            "SURGEPILOT_NODE_ID": NODE_ID,
            "RUNNER_FAKE_SCENARIO": "success",
        },
    )

    assert result.exit_code == 0
    assert [event["eventType"] for event in events] == [
        "accepted",
        "running",
        "heartbeat",
        "artifact",
        "finished",
    ]
    assert uploads[0]["artifactType"] == "run_log"
    assert uploads[0]["relativePath"] == "logs/runner.log"
    assert uploads[0]["path"].is_file()
    artifact_event = events[3]
    assert artifact_event["details"]["artifactId"] == "01HZX3Y9M0E9W7Z6M5QK9S8P7C"
    CALLBACK_VALIDATOR.validate(artifact_event)


def test_managed_runner_callbacks_validate_against_shared_schema(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    events: list[dict] = []
    write_run_bundle(tmp_path, RUN_ID)
    bin_dir = write_fake_bzt(tmp_path)
    monkeypatch.setattr(
        "surgepilot_runner.cli.post_callback", lambda payload: events.append(payload)
    )
    monkeypatch.setattr(
        "surgepilot_runner.cli.upload_artifact",
        lambda **kwargs: {
            "artifactId": "01HZX3Y9M0E9W7Z6M5QK9S8P7C",
            "sizeBytes": kwargs["path"].stat().st_size,
            "sha256": "a" * 64,
        },
    )
    monkeypatch.setenv("RUNNER_HOME", str(tmp_path))
    monkeypatch.setenv("SURGEPILOT_NODE_ID", NODE_ID)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    runner_cli.managed_run(RUN_ID)

    assert [event["eventType"] for event in events][:3] == ["accepted", "running", "heartbeat"]
    assert [event["eventType"] for event in events][-1] == "finished"
    for event in events:
        CALLBACK_VALIDATOR.validate(event)


@REQUIRES_LINUX_PROC
def test_stale_process_failure_callback_validates_against_shared_schema(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    events: list[dict] = []
    process = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        start_new_session=True,
    )
    try:
        write_pidfile("stale_run", process.pid, runner_home=tmp_path)
        monkeypatch.setattr(
            "surgepilot_runner.cli.post_callback", lambda payload: events.append(payload)
        )
        result = CliRunner().invoke(
            cli,
            ["start", "--run-id", RUN_ID],
            env={"RUNNER_HOME": str(tmp_path), "SURGEPILOT_NODE_ID": NODE_ID},
        )

        assert result.exit_code != 0
        assert events[0]["eventType"] == "failed"
        assert events[0]["details"]["reason"] == "stale_process_detected"
        CALLBACK_VALIDATOR.validate(events[0])
    finally:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=5)


def test_runner_callback_schema_accepts_runner_artifact_types_and_sla_result() -> None:
    artifact_payload = {
        "schemaVersion": "1",
        "eventType": "artifact",
        "eventId": "01HZX3Y9M0E9W7Z6M5QK9S8P7C",
        "runId": RUN_ID,
        "nodeId": NODE_ID,
        "runtimeVersion": RUNTIME_VERSION,
        "seq": 2,
        "eventTime": "2030-06-01T10:00:00.000Z",
        "details": {
            "artifactId": "01HZX3Y9M0E9W7Z6M5QK9S8P7D",
            "artifactType": "run_log",
            "relativePath": "logs/runner.log",
            "sizeBytes": 12,
            "sha256": "a" * 64,
        },
    }
    finished_payload = {
        "schemaVersion": "1",
        "eventType": "finished",
        "eventId": "01HZX3Y9M0E9W7Z6M5QK9S8P7E",
        "runId": RUN_ID,
        "nodeId": NODE_ID,
        "runtimeVersion": RUNTIME_VERSION,
        "seq": 3,
        "eventTime": "2030-06-01T10:00:01.000Z",
        "details": {"processGroupExited": True, "exitCode": 0, "slaResult": "passed"},
    }
    artifacts_zip_payload = {
        **artifact_payload,
        "eventId": "01HZX3Y9M0E9W7Z6M5QK9S8P7F",
        "details": {**artifact_payload["details"], "artifactType": "artifacts_zip"},
    }
    failed_requests_payload = {
        **artifact_payload,
        "eventId": "01HZX3Y9M0E9W7Z6M5QK9S8P7G",
        "details": {**artifact_payload["details"], "artifactType": "failed_requests_csv"},
    }

    for artifact_type in ["taurus_log", "jmeter_log", "final_stats_csv", "run_log"]:
        accepted_payload = {
            **artifact_payload,
            "details": {**artifact_payload["details"], "artifactType": artifact_type},
        }
        CALLBACK_VALIDATOR.validate(accepted_payload)
    CALLBACK_VALIDATOR.validate(finished_payload)
    with pytest.raises(Exception):
        CALLBACK_VALIDATOR.validate(artifacts_zip_payload)
    with pytest.raises(Exception):
        CALLBACK_VALIDATOR.validate(failed_requests_payload)


def test_monitoring_wrapper_injects_backend_listener_with_placeholders_only(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.jmx"
    target = tmp_path / "target.jmx"
    source.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<jmeterTestPlan>
  <hashTree>
    <TestPlan testname="SurgePilot"/>
    <hashTree/>
  </hashTree>
</jmeterTestPlan>
""",
        encoding="utf-8",
    )

    inject_monitoring_backend_listener(source, target)

    text = target.read_text(encoding="utf-8")
    assert BACKEND_LISTENER_CLASSNAME in text
    assert "${__P(SURGEPILOT_RUN_ID)}" in text
    assert "${__P(SURGEPILOT_NODE_ID)}" in text
    assert "${__P(SURGEPILOT_INFLUXDB_TOKEN)}" in text
    assert "secret-monitoring-token" not in text
    assert source.read_text(encoding="utf-8") != text
    inject_monitoring_backend_listener(target, target)
    assert target.read_text(encoding="utf-8").count(BACKEND_LISTENER_CLASSNAME) == 1

    root = __import__("xml.etree.ElementTree", fromlist=["parse"]).parse(target).getroot()
    top_hash_tree = root.find("hashTree")
    assert top_hash_tree is not None
    test_plan_hash_tree = list(top_hash_tree)[1]
    assert test_plan_hash_tree.tag == "hashTree"
    assert test_plan_hash_tree.find("BackendListener") is not None


def test_monitoring_wrapper_passes_through_without_properties(tmp_path: Path) -> None:
    bundle = tmp_path / "runs" / "01RUN" / "bundle"
    bundle.mkdir(parents=True)

    command = build_jmeter_wrapper_command(
        real_jmeter="/runtime/apache-jmeter-5.6.3/bin/jmeter",
        argv=["-n", "-t", "generated.jmx", "-l", "results.jtl"],
        cwd=bundle,
    )

    assert command == [
        "/runtime/apache-jmeter-5.6.3/bin/jmeter",
        "-Lio.github.mderevyankoaqa.influxdb2=ERROR",
        "-n",
        "-t",
        "generated.jmx",
        "-l",
        "results.jtl",
    ]


def test_monitoring_wrapper_finds_properties_from_taurus_artifacts_cwd(tmp_path: Path) -> None:
    run_root = tmp_path / "runs" / "01RUN"
    bundle = run_root / "bundle"
    artifacts = run_root / "artifacts"
    secrets = run_root / "secrets"
    bundle.mkdir(parents=True)
    artifacts.mkdir()
    secrets.mkdir()
    (bundle / "generated.jmx").write_text(
        "<jmeterTestPlan><hashTree><TestPlan/><hashTree/></hashTree></jmeterTestPlan>",
        encoding="utf-8",
    )
    (secrets / "monitoring.properties").write_text(
        "SURGEPILOT_INFLUXDB_TOKEN=secret\n", encoding="utf-8"
    )

    command = build_jmeter_wrapper_command(
        real_jmeter="/runtime/apache-jmeter-5.6.3/bin/jmeter",
        argv=["-n", "-t", "../bundle/generated.jmx", "-l", "results.jtl"],
        cwd=artifacts,
    )

    assert "-q" in command
    assert str(secrets / "monitoring.properties") in command
    assert "-Lio.github.mderevyankoaqa.influxdb2=ERROR" in command
    assert Path(command[command.index("-t") + 1]).is_file()


def test_monitoring_wrapper_version_probe_does_not_add_q_or_delete_secret(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run_root = tmp_path / "runs" / "01RUN"
    bundle = run_root / "bundle"
    secrets = run_root / "secrets"
    bundle.mkdir(parents=True)
    secrets.mkdir()
    secret = secrets / "monitoring.properties"
    secret.write_text("SURGEPILOT_INFLUXDB_TOKEN=secret\n", encoding="utf-8")
    captured: list[list[str]] = []

    def fake_call(command: list[str]) -> int:
        captured.append(command)
        return 0

    monkeypatch.chdir(bundle)
    monkeypatch.setattr(jmeter_wrapper.subprocess, "call", fake_call)
    monkeypatch.setattr(
        jmeter_wrapper.sys,
        "argv",
        [str(tmp_path / "runtime" / "bin" / "surgepilot-jmeter-wrapper"), "--version"],
    )

    assert jmeter_wrapper.main() == 0

    assert captured
    assert "-q" not in captured[0]
    assert secret.exists()


def test_monitoring_wrapper_keeps_shared_secret_when_existing_q_argument_is_present(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runtime = tmp_path / "runtime"
    run_root = tmp_path / "runs" / "01RUN"
    bundle = run_root / "bundle"
    secrets = run_root / "secrets"
    bundle.mkdir(parents=True)
    secrets.mkdir()
    (bundle / "generated.jmx").write_text(
        "<jmeterTestPlan><hashTree><TestPlan/><hashTree/></hashTree></jmeterTestPlan>",
        encoding="utf-8",
    )
    secret = secrets / "monitoring.properties"
    secret.write_text("SURGEPILOT_INFLUXDB_TOKEN=secret\n", encoding="utf-8")
    (bundle / "existing.properties").write_text("existing=true\n", encoding="utf-8")
    captured: list[list[str]] = []

    def fake_call(command: list[str]) -> int:
        captured.append(command)
        return 0

    monkeypatch.chdir(bundle)
    monkeypatch.setenv("SURGEPILOT_RUNTIME_HOME", str(runtime))
    monkeypatch.setattr(jmeter_wrapper.subprocess, "call", fake_call)
    monkeypatch.setattr(
        jmeter_wrapper.sys,
        "argv",
        [
            str(runtime / "apache-jmeter-5.6.3" / "bin" / "surgepilot-jmeter-wrapper"),
            "-n",
            "-q",
            "existing.properties",
            "-t",
            "generated.jmx",
        ],
    )

    assert jmeter_wrapper.main() == 0

    assert captured
    assert captured[0].count("-q") == 2
    assert captured[0][-2:] == ["-q", str(secret)]
    assert "-Lio.github.mderevyankoaqa.influxdb2=ERROR" in captured[0]
    assert secret.exists()


def test_monitoring_wrapper_uses_jmx_copy_and_properties_for_enabled_run(tmp_path: Path) -> None:
    bundle = tmp_path / "runs" / "01RUN" / "bundle"
    secrets = tmp_path / "runs" / "01RUN" / "secrets"
    bundle.mkdir(parents=True)
    secrets.mkdir()
    (bundle / "generated.jmx").write_text(
        "<jmeterTestPlan><hashTree><TestPlan/><hashTree/></hashTree></jmeterTestPlan>",
        encoding="utf-8",
    )
    (secrets / "monitoring.properties").write_text(
        "SURGEPILOT_INFLUXDB_TOKEN=secret\n", encoding="utf-8"
    )

    command = build_jmeter_wrapper_command(
        real_jmeter="/runtime/apache-jmeter-5.6.3/bin/jmeter",
        argv=["-n", "-t", "generated.jmx", "-l", "results.jtl"],
        cwd=bundle,
    )

    assert command[0] == "/runtime/apache-jmeter-5.6.3/bin/jmeter"
    assert "-q" in command
    assert "-Lio.github.mderevyankoaqa.influxdb2=ERROR" in command
    assert str(secrets / "monitoring.properties") in command
    injected_path = Path(command[command.index("-t") + 1])
    assert injected_path != bundle / "generated.jmx"
    assert injected_path.is_file()
    assert BACKEND_LISTENER_CLASSNAME in injected_path.read_text(encoding="utf-8")


def test_start_cleans_monitoring_secret_when_child_exits_before_ready(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class ExitedProcess:
        pid = 999999

        def poll(self) -> int:
            return 1

    monitoring_properties = monitoring_properties_path(RUN_ID, base=tmp_path)
    monitoring_properties.parent.mkdir(parents=True)
    monitoring_properties.write_text("SURGEPILOT_INFLUXDB_TOKEN=secret\n", encoding="utf-8")
    monkeypatch.setattr(runner_cli.subprocess, "Popen", lambda *args, **kwargs: ExitedProcess())
    monkeypatch.setattr(runner_cli, "start_workload_wait_seconds", lambda: 0.01)

    result = CliRunner().invoke(
        cli, ["start", "--run-id", RUN_ID], env={"RUNNER_HOME": str(tmp_path)}
    )

    assert result.exit_code != 0
    assert "managed runner failed to start" in result.output
    assert not monitoring_properties.exists()


def test_managed_runner_removes_monitoring_properties_when_bundle_is_invalid(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    events: list[dict] = []
    secrets = tmp_path / "runs" / RUN_ID / "secrets"
    secrets.mkdir(parents=True)
    monitoring_properties = secrets / "monitoring.properties"
    monitoring_properties.write_text("SURGEPILOT_INFLUXDB_TOKEN=secret\n", encoding="utf-8")
    monkeypatch.setattr(
        "surgepilot_runner.cli.post_callback", lambda payload: events.append(payload)
    )
    monkeypatch.setenv("RUNNER_HOME", str(tmp_path))
    monkeypatch.setenv("SURGEPILOT_NODE_ID", NODE_ID)

    runner_cli.managed_run(RUN_ID)

    assert [event["eventType"] for event in events] == ["accepted", "failed"]
    assert not monitoring_properties.exists()


def test_managed_runner_cleans_monitoring_secret_when_readiness_setup_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monitoring_properties = monitoring_properties_path(RUN_ID, base=tmp_path)
    monitoring_properties.parent.mkdir(parents=True)
    monitoring_properties.write_text("SURGEPILOT_INFLUXDB_TOKEN=secret\n", encoding="utf-8")
    monkeypatch.setenv("RUNNER_HOME", str(tmp_path))

    def fail_pidfile_write(*args, **kwargs) -> None:
        raise OSError("pidfile write failed")

    monkeypatch.setattr(runner_cli, "write_supervisor_pidfile", fail_pidfile_write)

    with pytest.raises(OSError, match="pidfile write failed"):
        runner_cli.managed_run(RUN_ID)

    assert not monitoring_properties.exists()


def test_kill_without_workload_removes_monitoring_properties(tmp_path: Path) -> None:
    monitoring_properties = monitoring_properties_path("run_01", base=tmp_path)
    monitoring_properties.parent.mkdir(parents=True)
    monitoring_properties.write_text("SURGEPILOT_INFLUXDB_TOKEN=secret\n", encoding="utf-8")

    result = CliRunner().invoke(
        cli, ["kill", "--run-id", "run_01"], env={"RUNNER_HOME": str(tmp_path)}
    )

    assert result.exit_code == 0
    assert "no managed process" in result.output
    assert not monitoring_properties.exists()


def test_kill_fails_when_monitoring_secret_cannot_be_deleted(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monitoring_properties = monitoring_properties_path("run_01", base=tmp_path)
    monitoring_properties.parent.mkdir(parents=True)
    monitoring_properties.write_text("SURGEPILOT_INFLUXDB_TOKEN=secret\n", encoding="utf-8")
    original_unlink = Path.unlink

    def fail_monitoring_unlink(path: Path, *args, **kwargs) -> None:
        if path == monitoring_properties:
            raise OSError("read-only filesystem")
        original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_monitoring_unlink)
    monkeypatch.setattr(runner_cli, "start_workload_wait_seconds", lambda: 0.0)

    result = CliRunner().invoke(
        cli, ["kill", "--run-id", "run_01"], env={"RUNNER_HOME": str(tmp_path)}
    )

    assert result.exit_code != 0
    assert "Monitoring secret cleanup failed" in result.output
    assert monitoring_properties.exists()


def test_kill_preserves_monitoring_secret_when_supervisor_exit_is_unconfirmed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monitoring_properties = monitoring_properties_path("run_01", base=tmp_path)
    monitoring_properties.parent.mkdir(parents=True)
    monitoring_properties.write_text("SURGEPILOT_INFLUXDB_TOKEN=secret\n", encoding="utf-8")
    write_supervisor_pidfile("run_01", ManagedPid(pid=321, starttime=None), runner_home=tmp_path)
    monkeypatch.setattr(runner_cli, "managed_pid_alive", lambda managed, probe=None: True)
    monkeypatch.setattr(runner_cli, "terminate_group", lambda pgid: False)

    result = CliRunner().invoke(
        cli, ["kill", "--run-id", "run_01"], env={"RUNNER_HOME": str(tmp_path)}
    )

    assert result.exit_code != 0
    assert monitoring_properties.exists()
    assert supervisor_pidfile_path("run_01", base=tmp_path).exists()
