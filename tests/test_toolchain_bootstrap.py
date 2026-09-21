from __future__ import annotations

import hashlib
import io
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tarfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOLCHAIN = ROOT / "scripts/toolchain"


def toolchain_environment(tmp_path: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "HOME": str(tmp_path / "home"),
            "SURGEPILOT_TOOLCHAIN_DATA_ROOT": str(tmp_path / "data"),
            "SURGEPILOT_TOOLCHAIN_CACHE_ROOT": str(tmp_path / "cache"),
            "SURGEPILOT_TOOLCHAIN_STATE_ROOT": str(tmp_path / "state"),
            "SURGEPILOT_TOOLCHAIN_CONFIG_ROOT": str(tmp_path / "config"),
        }
    )
    return environment


def run_toolchain(
    tmp_path: Path, *arguments: str, environment: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["sh", str(TOOLCHAIN), *arguments],
        cwd=ROOT,
        env=environment or toolchain_environment(tmp_path),
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )


def write_executable(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)


def copied_toolchain(tmp_path: Path) -> tuple[Path, Path]:
    repository = tmp_path / "repository"
    scripts = repository / "scripts"
    scripts.mkdir(parents=True)
    script = scripts / "toolchain"
    shutil.copy2(TOOLCHAIN, script)
    shutil.copy2(ROOT / "scripts/toolchain-mise.sha256", scripts / "toolchain-mise.sha256")
    (repository / "mise.toml").write_text(
        '[tools]\npython = "3.12"\nnode = "22"\npnpm = "11.3.0"\nuv = "0.12.17"\n',
        encoding="utf-8",
    )
    return repository, script


def fake_host_commands(
    tmp_path: Path,
    *,
    operating_system: str,
    architecture: str,
    glibc: bool = True,
) -> Path:
    commands = tmp_path / "commands"
    commands.mkdir()
    write_executable(
        commands / "uname",
        "#!/bin/sh\n"
        'case "$1" in\n'
        f"  -s) printf '%s\\n' '{operating_system}' ;;\n"
        f"  -m) printf '%s\\n' '{architecture}' ;;\n"
        "  *) exit 2 ;;\n"
        "esac\n",
    )
    write_executable(
        commands / "getconf",
        "#!/bin/sh\n" + ("printf 'glibc 2.39\\n'\n" if glibc else "exit 1\n"),
    )
    write_executable(
        commands / "curl",
        "#!/bin/sh\n"
        "set -eu\n"
        "output=\n"
        "url=\n"
        'while [ "$#" -gt 0 ]; do\n'
        '  case "$1" in\n'
        "    -o|--output) output=$2; shift 2 ;;\n"
        "    http://*|https://*) url=$1; shift ;;\n"
        "    *) shift ;;\n"
        "  esac\n"
        "done\n"
        'printf \'%s\\n\' "$url" >> "$TOOLCHAIN_TEST_URL_LOG"\n'
        'cp "$TOOLCHAIN_TEST_DOWNLOAD" "$output"\n',
    )
    if shutil.which("sha256sum") is None:
        write_executable(
            commands / "sha256sum",
            '#!/bin/sh\nshasum -a 256 "$1"\n',
        )
    if shutil.which("shasum") is None:
        write_executable(
            commands / "shasum",
            '#!/bin/sh\n[ "$1" = "-a" ] && [ "$2" = "256" ] || exit 2\nshift 2\nsha256sum "$1"\n',
        )
    return commands


def fake_mise_archive(path: Path) -> str:
    mise = b"""#!/bin/sh
set -eu
printf '%s|%s|%s|%s|%s|%s|%s\\n' \
  "$MISE_DATA_DIR" "$MISE_SYSTEM_DATA_DIR" "$MISE_LOCKFILE" \
  "$MISE_CEILING_PATHS" "$MISE_OVERRIDE_CONFIG_FILENAMES" \
  "$MISE_OVERRIDE_TOOL_VERSIONS_FILENAMES" "$MISE_ENABLE_TOOLS" \
  >> "$TOOLCHAIN_TEST_MISE_LOG"
case "${1-}" in
  --version) printf '2026.9.11 linux-x64 (test)\\n' ;;
  install)
    for spec in python/3.12.11 node/22.18.0 pnpm/11.3.0 uv/0.12.17; do
      tool=${spec%%/*}
      version=${spec#*/}
      mkdir -p "$MISE_DATA_DIR/installs/$tool/$version/bin"
      : > "$MISE_DATA_DIR/installs/$tool/$version/bin/$tool"
    done
    ;;
  config)
    printf '[\\n  {\\n    "path": "%s/mise.toml"\\n  },\\n  {\\n    "path": "%s"\\n  },\\n  {\\n    "path": "%s"\\n  }\\n]\\n' \
      "$PWD" "$MISE_GLOBAL_CONFIG_FILE" "$MISE_SYSTEM_CONFIG_FILE"
    ;;
  settings)
    case "$3" in
      lockfile) printf 'false\\n' ;;
      enable_tools) printf '["node", "pnpm", "python", "uv"]\\n' ;;
      *) exit 2 ;;
    esac
    ;;
  exec)
    [ "$2" = -- ] || exit 2
    case "$3" in
      python) printf 'Python 3.12.11\\n' ;;
      node) printf 'v22.18.0\\n' ;;
      pnpm) printf '11.3.0\\n' ;;
      uv) printf 'uv 0.12.17 (test build metadata)\\n' ;;
      *) exit 2 ;;
    esac
    ;;
  which)
    case "$2" in
      python) version=3.12.11 ;;
      node) version=22.18.0 ;;
      pnpm) version=11.3.0 ;;
      uv) version=0.12.17 ;;
      *) exit 2 ;;
    esac
    printf '%s/installs/%s/%s/bin/%s\\n' "$MISE_DATA_DIR" "$2" "$version" "$2"
    ;;
  *) exit 2 ;;
esac
"""
    info = tarfile.TarInfo("mise/bin/mise")
    info.mode = 0o755
    info.size = len(mise)
    with tarfile.open(path, "w:gz") as archive:
        archive.addfile(info, io.BytesIO(mise))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_check_missing_toolchain_is_non_mutating_and_actionable(tmp_path: Path) -> None:
    environment = toolchain_environment(tmp_path)

    result = run_toolchain(tmp_path, "check", environment=environment)

    assert result.returncode != 0
    assert "make toolchain-install" in result.stderr
    for name in ("data", "cache", "state", "config"):
        assert not (tmp_path / name).exists()


@pytest.mark.parametrize(
    ("operating_system", "architecture", "artifact"),
    [
        ("Linux", "x86_64", "mise-v2026.9.11-linux-x64.tar.gz"),
        ("Linux", "aarch64", "mise-v2026.9.11-linux-arm64.tar.gz"),
        ("Darwin", "x86_64", "mise-v2026.9.11-macos-x64.tar.gz"),
        ("Darwin", "arm64", "mise-v2026.9.11-macos-arm64.tar.gz"),
    ],
)
def test_install_selects_pinned_artifact_and_rejects_corrupt_download(
    tmp_path: Path,
    operating_system: str,
    architecture: str,
    artifact: str,
) -> None:
    repository, script = copied_toolchain(tmp_path)
    corrupt = tmp_path / "corrupt.tar.gz"
    corrupt.write_bytes(b"not the pinned archive")
    url_log = tmp_path / "urls.log"
    commands = fake_host_commands(
        tmp_path,
        operating_system=operating_system,
        architecture=architecture,
    )
    environment = toolchain_environment(tmp_path)
    environment.update(
        {
            "PATH": f"{commands}{os.pathsep}{environment['PATH']}",
            "TOOLCHAIN_TEST_DOWNLOAD": str(corrupt),
            "TOOLCHAIN_TEST_URL_LOG": str(url_log),
        }
    )

    result = subprocess.run(
        ["sh", str(script), "install"],
        cwd=repository,
        env=environment,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )

    assert result.returncode != 0
    assert "checksum" in result.stderr.lower()
    assert url_log.read_text(encoding="utf-8").strip().endswith(f"/v2026.9.11/{artifact}")
    assert not list((tmp_path / "data").glob("bootstrap/mise/v2026.9.11/*/mise"))
    assert not list((tmp_path / "data/bootstrap").glob(".mise-stage.*"))
    assert not (tmp_path / "state/mutation.lock").exists()


def test_install_rejects_musl_linux_before_download(tmp_path: Path) -> None:
    repository, script = copied_toolchain(tmp_path)
    commands = fake_host_commands(
        tmp_path,
        operating_system="Linux",
        architecture="x86_64",
        glibc=False,
    )
    environment = toolchain_environment(tmp_path)
    environment["PATH"] = f"{commands}{os.pathsep}{environment['PATH']}"

    result = subprocess.run(
        ["sh", str(script), "install"],
        cwd=repository,
        env=environment,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )

    assert result.returncode != 0
    assert "glibc" in result.stderr.lower()
    assert not (tmp_path / "urls.log").exists()


@pytest.mark.parametrize(
    ("operating_system", "architecture"),
    [("FreeBSD", "x86_64"), ("Linux", "riscv64")],
)
def test_install_rejects_unsupported_host_before_download(
    tmp_path: Path, operating_system: str, architecture: str
) -> None:
    repository, script = copied_toolchain(tmp_path)
    commands = fake_host_commands(
        tmp_path,
        operating_system=operating_system,
        architecture=architecture,
    )
    environment = toolchain_environment(tmp_path)
    environment["PATH"] = f"{commands}{os.pathsep}{environment['PATH']}"

    result = subprocess.run(
        ["sh", str(script), "install"],
        cwd=repository,
        env=environment,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )

    assert result.returncode != 0
    assert "unsupported" in result.stderr.lower()
    assert not (tmp_path / "urls.log").exists()


def test_install_publishes_pinned_mise_and_installs_in_isolated_state(tmp_path: Path) -> None:
    repository, script = copied_toolchain(tmp_path)
    archive = tmp_path / "mise.tar.gz"
    checksum = fake_mise_archive(archive)
    artifact = "mise-v2026.9.11-macos-arm64.tar.gz"
    (repository / "scripts/toolchain-mise.sha256").write_text(
        f"{checksum}  {artifact}\n", encoding="utf-8"
    )
    commands = fake_host_commands(
        tmp_path,
        operating_system="Darwin",
        architecture="arm64",
    )
    mise_log = tmp_path / "mise.log"
    environment = toolchain_environment(tmp_path)
    environment.update(
        {
            "PATH": f"{commands}{os.pathsep}{environment['PATH']}",
            "MISE_DATA_DIR": str(tmp_path / "host-mise-data"),
            "MISE_SYSTEM_DATA_DIR": str(tmp_path / "host-system-mise-data"),
            "MISE_LOCKFILE": "true",
            "TOOLCHAIN_TEST_DOWNLOAD": str(archive),
            "TOOLCHAIN_TEST_URL_LOG": str(tmp_path / "urls.log"),
            "TOOLCHAIN_TEST_MISE_LOG": str(mise_log),
        }
    )

    result = subprocess.run(
        ["sh", str(script), "install"],
        cwd=repository,
        env=environment,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    final_mise = tmp_path / "data/bootstrap/mise/v2026.9.11/macos-arm64/mise"
    assert final_mise.is_file()
    assert os.access(final_mise, os.X_OK)
    lines = mise_log.read_text(encoding="utf-8").splitlines()
    assert lines
    expected_prefix = (
        f"{tmp_path / 'data/mise'}|{tmp_path / 'data/mise-system'}|false|"
        f"{repository.parent}|mise.toml|none|python,node,pnpm,uv"
    )
    assert all(line == expected_prefix for line in lines)
    for tool in ("python", "node", "pnpm", "uv"):
        assert list((tmp_path / f"data/mise/installs/{tool}").glob("*/bin/*"))

    def snapshot() -> dict[str, tuple[int, int, bytes]]:
        result: dict[str, tuple[int, int, bytes]] = {}
        for root_name in ("data", "cache", "state", "config"):
            root = tmp_path / root_name
            for path in [root, *sorted(root.rglob("*"))]:
                relative = str(path.relative_to(tmp_path))
                stat = path.stat()
                contents = path.read_bytes() if path.is_file() else b""
                result[relative] = (stat.st_mode, stat.st_mtime_ns, contents)
        return result

    before = snapshot()
    check_result = subprocess.run(
        ["sh", str(script), "check"],
        cwd=repository,
        env=environment,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )

    assert check_result.returncode == 0, check_result.stderr
    assert snapshot() == before


@pytest.mark.parametrize("unsafe_kind", ["relative", "symlink", "writable", "managed_symlink"])
def test_install_rejects_unsafe_toolchain_roots_without_repair(
    tmp_path: Path, unsafe_kind: str
) -> None:
    environment = toolchain_environment(tmp_path)
    data_root = tmp_path / "data"
    if unsafe_kind == "relative":
        environment["SURGEPILOT_TOOLCHAIN_DATA_ROOT"] = "relative/data"
    elif unsafe_kind == "symlink":
        target = tmp_path / "target"
        target.mkdir()
        data_root.symlink_to(target, target_is_directory=True)
    elif unsafe_kind == "writable":
        data_root.mkdir()
        data_root.chmod(0o777)
    else:
        data_root.mkdir(mode=0o700)
        target = tmp_path / "target"
        target.mkdir()
        (data_root / "mise").symlink_to(target, target_is_directory=True)

    result = run_toolchain(tmp_path, "install", environment=environment)

    assert result.returncode != 0
    if unsafe_kind == "relative":
        assert "absolute" in result.stderr
    elif unsafe_kind == "symlink":
        assert "symlink" in result.stderr
    elif unsafe_kind == "writable":
        assert "writable" in result.stderr
        assert data_root.stat().st_mode & 0o022
    else:
        assert "symlink" in result.stderr


def configured_fake_install(tmp_path: Path) -> tuple[Path, Path, dict[str, str]]:
    repository, script = copied_toolchain(tmp_path)
    archive = tmp_path / "mise.tar.gz"
    checksum = fake_mise_archive(archive)
    artifact = "mise-v2026.9.11-macos-arm64.tar.gz"
    (repository / "scripts/toolchain-mise.sha256").write_text(
        f"{checksum}  {artifact}\n", encoding="utf-8"
    )
    commands = fake_host_commands(
        tmp_path,
        operating_system="Darwin",
        architecture="arm64",
    )
    environment = toolchain_environment(tmp_path)
    environment.update(
        {
            "PATH": f"{commands}{os.pathsep}{environment['PATH']}",
            "TOOLCHAIN_TEST_DOWNLOAD": str(archive),
            "TOOLCHAIN_TEST_URL_LOG": str(tmp_path / "urls.log"),
            "TOOLCHAIN_TEST_MISE_LOG": str(tmp_path / "mise.log"),
        }
    )
    return repository, script, environment


def test_concurrent_installs_publish_one_verified_bootstrap(tmp_path: Path) -> None:
    repository, script, environment = configured_fake_install(tmp_path)

    processes = [
        subprocess.Popen(
            ["sh", str(script), "install"],
            cwd=repository,
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for _ in range(2)
    ]
    results = [process.communicate(timeout=30) + (process.returncode,) for process in processes]

    assert all(returncode == 0 for _, _, returncode in results), results
    assert (tmp_path / "urls.log").read_text(encoding="utf-8").count("\n") == 1
    final_mise = tmp_path / "data/bootstrap/mise/v2026.9.11/macos-arm64/mise"
    assert final_mise.is_file()
    assert not list((tmp_path / "data/bootstrap").glob(".mise-stage.*"))


def test_install_recovers_lock_from_dead_local_owner(tmp_path: Path) -> None:
    repository, script, environment = configured_fake_install(tmp_path)
    for name in ("data", "cache", "state", "config"):
        (tmp_path / name).mkdir(mode=0o700)
    lock = tmp_path / "state/mutation.lock"
    lock.write_text(f"999999@{socket.gethostname()}\n", encoding="utf-8")

    result = subprocess.run(
        ["sh", str(script), "install"],
        cwd=repository,
        env=environment,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert not lock.exists()
    assert not list((tmp_path / "state").glob(".mutation-lock.*"))


def fake_external_tools(tmp_path: Path) -> Path:
    commands = tmp_path / "external-commands"
    commands.mkdir()
    versions = {
        "python": "Python 3.12.11",
        "uv": "uv 0.12.17 (test build metadata)",
        "node": "v22.18.0",
        "pnpm": "11.3.0",
    }
    for name, version in versions.items():
        write_executable(
            commands / name,
            f"#!/bin/sh\nprintf '%s\\n' '{version}'\n",
        )
    return commands


def test_external_exec_validates_declared_tools_without_managed_state(tmp_path: Path) -> None:
    commands = fake_external_tools(tmp_path)
    environment = toolchain_environment(tmp_path)
    original_path = f"{commands}{os.pathsep}{environment['PATH']}"
    environment.update(
        {
            "PATH": original_path,
            "SURGEPILOT_TOOLCHAIN_MODE": "external",
            "SURGEPILOT_TOOLCHAIN_EXTERNAL_TOOLS": "python,uv,node,pnpm",
        }
    )

    result = run_toolchain(
        tmp_path,
        "exec",
        "--",
        "sh",
        "-c",
        'printf "%s|%s|%s|%s\\n" "$SURGEPILOT_TOOLCHAIN_ACTIVE" '
        '"$UV_PYTHON_DOWNLOADS" "$UV_NO_MANAGED_PYTHON" "$PATH"',
        environment=environment,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == f"1|never|1|{original_path}"
    for name in ("data", "cache", "state", "config"):
        assert not (tmp_path / name).exists()


@pytest.mark.parametrize(
    ("declaration", "expected"),
    [
        ("", "non-empty"),
        ("python,python", "duplicate"),
        ("python,ruby", "unknown"),
        ("python,", "malformed"),
    ],
)
def test_external_exec_rejects_invalid_tool_declarations(
    tmp_path: Path, declaration: str, expected: str
) -> None:
    commands = fake_external_tools(tmp_path)
    environment = toolchain_environment(tmp_path)
    environment.update(
        {
            "PATH": f"{commands}{os.pathsep}{environment['PATH']}",
            "SURGEPILOT_TOOLCHAIN_MODE": "external",
            "SURGEPILOT_TOOLCHAIN_EXTERNAL_TOOLS": declaration,
        }
    )

    result = run_toolchain(
        tmp_path,
        "exec",
        "--",
        "sh",
        "-c",
        "exit 99",
        environment=environment,
    )

    assert result.returncode != 0
    assert expected in result.stderr.lower()


def test_external_exec_rejects_declaration_insufficient_for_make_goal(tmp_path: Path) -> None:
    commands = fake_external_tools(tmp_path)
    environment = toolchain_environment(tmp_path)
    environment.update(
        {
            "PATH": f"{commands}{os.pathsep}{environment['PATH']}",
            "SURGEPILOT_TOOLCHAIN_MODE": "external",
            "SURGEPILOT_TOOLCHAIN_EXTERNAL_TOOLS": "python,uv",
        }
    )

    result = run_toolchain(
        tmp_path,
        "exec",
        "--",
        "make",
        "verify",
        environment=environment,
    )

    assert result.returncode != 0
    assert "insufficient" in result.stderr.lower()
    assert "node" in result.stderr.lower()
