from __future__ import annotations

from pathlib import Path
import shlex
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import run_runtime_builder  # noqa: E402


@pytest.mark.parametrize(
    ("daemon_arch", "expected"),
    [("x86_64", "amd64"), ("amd64", "amd64"), ("aarch64", "arm64"), ("arm64", "arm64")],
)
def test_normalize_daemon_arch(daemon_arch: str, expected: str) -> None:
    assert run_runtime_builder.normalize_daemon_arch(daemon_arch) == expected


def test_normalize_daemon_arch_rejects_unknown_value() -> None:
    with pytest.raises(run_runtime_builder.RuntimeBuilderError, match="unsupported"):
        run_runtime_builder.normalize_daemon_arch("riscv64")


def test_builder_command_uses_linux_container_and_host_owned_mounts(tmp_path: Path) -> None:
    command = run_runtime_builder.build_container_command(
        root=Path("/repo"),
        output_dir=tmp_path / "output",
        build_dir=tmp_path / "build",
        cache_dir=tmp_path / "cache",
        image="surgepilot-runtime-builder:test",
        fixed_version="v0.3.0",
        release_prefix="",
        user_id=1000,
        group_id=1000,
    )

    assert command[:4] == ["docker", "run", "--rm", "--user"]
    assert "1000:1000" in command
    assert "--fixed-version" in command
    assert "v0.3.0" in command
    assert "/workspace/scripts/release_runtime_artifact.py" in command
    assert any(value.endswith(":/output") for value in command)
    assert any(value.endswith(":/build") for value in command)
    assert any(value.endswith(":/cache") for value in command)


def test_builder_command_forwards_all_optional_plugin_checksum_pins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    checksum_names = (
        "RUNTIME_CASUTG_SHA256",
        "RUNTIME_JSON_SHA256",
        "RUNTIME_TST_SHA256",
        "RUNTIME_RANDOM_CSV_SHA256",
        "RUNTIME_INFLUXDB2_LISTENER_SHA256",
    )
    for name in checksum_names:
        monkeypatch.setenv(name, "a" * 64)

    command = run_runtime_builder.build_container_command(
        root=Path("/repo"),
        output_dir=tmp_path / "output",
        build_dir=tmp_path / "build",
        cache_dir=tmp_path / "cache",
        image="surgepilot-runtime-builder:test",
        fixed_version="v0.3.0",
        release_prefix="",
        user_id=1000,
        group_id=1000,
    )

    forwarded = {
        command[index + 1]
        for index, value in enumerate(command[:-1])
        if value == "--env" and command[index + 1].startswith("RUNTIME_")
    }
    assert set(checksum_names).issubset(forwarded)


def test_forced_platform_must_match_daemon_architecture() -> None:
    with pytest.raises(run_runtime_builder.RuntimeBuilderError, match="DOCKER_DEFAULT_PLATFORM"):
        run_runtime_builder.validate_forced_platform("linux/amd64", daemon_arch="arm64")
    with pytest.raises(run_runtime_builder.RuntimeBuilderError, match="DOCKER_DEFAULT_PLATFORM"):
        run_runtime_builder.validate_forced_platform("windows/amd64", daemon_arch="amd64")


def test_write_host_env_rewrites_container_path(tmp_path: Path) -> None:
    container_env = tmp_path / "runtime.container.env"
    container_env.write_text(
        "LOAD_NODE_RUNTIME_VERSION='v0.3.0'\nLOAD_NODE_RUNTIME_ARTIFACT_HOST_DIR=/output\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "output with spaces"
    env_file = tmp_path / "runtime.env"

    version = run_runtime_builder._write_host_env(
        container_env=container_env,
        env_file=env_file,
        output_dir=output_dir,
    )

    assert version == "v0.3.0"
    values = {}
    for line in env_file.read_text(encoding="utf-8").splitlines():
        key, value = line.split("=", 1)
        values[key] = shlex.split(value)[0]
    assert values == {
        "LOAD_NODE_RUNTIME_VERSION": "v0.3.0",
        "LOAD_NODE_RUNTIME_ARTIFACT_HOST_DIR": str(output_dir.resolve()),
    }


def test_run_builder_builds_native_image_runs_container_and_writes_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    output_dir = tmp_path / "output"
    env_file = output_dir / "runtime.env"
    calls: list[list[str]] = []
    monkeypatch.setattr(run_runtime_builder, "_daemon_arch", lambda _root: "arm64")
    monkeypatch.setattr(run_runtime_builder.os, "getuid", lambda: 1000)
    monkeypatch.setattr(run_runtime_builder.os, "getgid", lambda: 1000)

    def fake_stream(command: list[str], *, cwd: Path) -> None:
        assert cwd == tmp_path.resolve()
        calls.append(command)
        if command[:2] == ["docker", "build"] and "--iidfile" in command:
            iid_file = Path(command[command.index("--iidfile") + 1])
            iid_file.write_text(f"sha256:{'1' * 64}\n", encoding="utf-8")
        elif command[:2] == ["docker", "run"]:
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "runtime.container.env").write_text(
                "LOAD_NODE_RUNTIME_VERSION=v0.3.0\nLOAD_NODE_RUNTIME_ARTIFACT_HOST_DIR=/output\n",
                encoding="utf-8",
            )

    monkeypatch.setattr(run_runtime_builder, "_run_stream", fake_stream)

    version = run_runtime_builder.run_builder(
        root=tmp_path,
        output_dir=output_dir,
        build_dir=tmp_path / "build",
        cache_dir=tmp_path / "cache",
        env_file=env_file,
        fixed_version="v0.3.0",
        release_prefix="",
    )

    assert version == "v0.3.0"
    assert calls[0][:4] == ["docker", "build", "--platform", "linux/arm64"]
    assert "--progress=plain" in calls[0]
    assert "--iidfile" in calls[0]
    assert calls[1][:2] == ["docker", "run"]
    assert f"sha256:{'1' * 64}" in calls[1]
    assert "LOAD_NODE_RUNTIME_VERSION=v0.3.0" in env_file.read_text(encoding="utf-8")
    assert not (output_dir / "runtime.container.env").exists()
    output = capsys.readouterr().out
    assert "Building Runtime builder image for linux/arm64" in output
    assert "Running Runtime artifact builder" in output


@pytest.mark.parametrize(
    ("iid_contents", "message"),
    [
        (None, "image ID was not recorded"),
        ("not-an-image-id", "image ID is invalid"),
    ],
)
def test_run_builder_rejects_missing_or_invalid_immutable_image_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    iid_contents: str | None,
    message: str,
) -> None:
    monkeypatch.setattr(run_runtime_builder, "_daemon_arch", lambda _root: "amd64")

    def fake_stream(command: list[str], *, cwd: Path) -> None:
        assert cwd == tmp_path.resolve()
        if iid_contents is not None:
            iid_file = Path(command[command.index("--iidfile") + 1])
            iid_file.write_text(iid_contents, encoding="utf-8")

    monkeypatch.setattr(run_runtime_builder, "_run_stream", fake_stream)

    with pytest.raises(run_runtime_builder.RuntimeBuilderError, match=message):
        run_runtime_builder.run_builder(
            root=tmp_path,
            output_dir=tmp_path / "output",
            build_dir=tmp_path / "build",
            cache_dir=tmp_path / "cache",
            env_file=tmp_path / "runtime.env",
            fixed_version="v0.3.0",
            release_prefix="",
        )


def test_main_reports_builder_error(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setattr(
        run_runtime_builder,
        "run_builder",
        lambda **_kwargs: (_ for _ in ()).throw(run_runtime_builder.RuntimeBuilderError("boom")),
    )

    result = run_runtime_builder.main(
        [
            "--output-dir",
            "/tmp/output",
            "--build-dir",
            "/tmp/build",
            "--cache-dir",
            "/tmp/cache",
            "--env-file",
            "/tmp/runtime.env",
        ]
    )

    assert result == 1
    assert "Runtime builder failed: boom" in capsys.readouterr().out


def test_run_helper_and_daemon_arch_report_command_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        run_runtime_builder.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 1, stdout="bad output"),
    )
    with pytest.raises(run_runtime_builder.RuntimeBuilderError, match="bad output"):
        run_runtime_builder._run(["docker", "info"], cwd=tmp_path)

    monkeypatch.setattr(run_runtime_builder, "_run", lambda *_args, **_kwargs: "x86_64\n")
    assert run_runtime_builder._daemon_arch(tmp_path) == "amd64"


def test_stream_helper_inherits_output_and_reports_command_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def fake_subprocess_run(*args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess([], 1)

    monkeypatch.setattr(run_runtime_builder.subprocess, "run", fake_subprocess_run)

    with pytest.raises(run_runtime_builder.RuntimeBuilderError, match="docker build"):
        run_runtime_builder._run_stream(["docker", "build", "."], cwd=tmp_path)

    assert calls[0][1] == {"cwd": tmp_path, "text": True}


def test_write_host_env_rejects_missing_result(tmp_path: Path) -> None:
    missing = tmp_path / "missing.env"
    with pytest.raises(run_runtime_builder.RuntimeBuilderError, match="did not write"):
        run_runtime_builder._write_host_env(
            container_env=missing,
            env_file=tmp_path / "runtime.env",
            output_dir=tmp_path,
        )

    invalid = tmp_path / "invalid.env"
    invalid.write_text("OTHER=value\n", encoding="utf-8")
    with pytest.raises(run_runtime_builder.RuntimeBuilderError, match="did not include"):
        run_runtime_builder._write_host_env(
            container_env=invalid,
            env_file=tmp_path / "runtime.env",
            output_dir=tmp_path,
        )


def test_main_returns_zero_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run_runtime_builder, "run_builder", lambda **_kwargs: "v0.3.0")
    assert (
        run_runtime_builder.main(
            [
                "--output-dir",
                "/tmp/output",
                "--build-dir",
                "/tmp/build",
                "--cache-dir",
                "/tmp/cache",
                "--env-file",
                "/tmp/runtime.env",
            ]
        )
        == 0
    )
