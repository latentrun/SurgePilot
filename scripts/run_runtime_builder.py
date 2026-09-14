"""Run the production Runtime builder inside a native Linux Docker container."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile


DEFAULT_IMAGE = "surgepilot-runtime-builder:local"
CHECKSUM_ENV_NAMES = (
    "RUNTIME_JMETER_SHA256",
    "RUNTIME_CASUTG_SHA256",
    "RUNTIME_JSON_SHA256",
    "RUNTIME_TST_SHA256",
    "RUNTIME_RANDOM_CSV_SHA256",
    "RUNTIME_INFLUXDB2_LISTENER_SHA256",
    "SURGEPILOT_PIP_INDEX_URL",
    "PIP_INDEX_URL",
    "UV_INDEX_URL",
)


class RuntimeBuilderError(RuntimeError):
    """Raised when the containerized Runtime builder cannot run safely."""


def normalize_daemon_arch(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"x86_64", "amd64"}:
        return "amd64"
    if normalized in {"aarch64", "arm64"}:
        return "arm64"
    raise RuntimeBuilderError(f"unsupported Docker daemon architecture: {value or '<empty>'}")


def validate_forced_platform(value: str, *, daemon_arch: str) -> None:
    normalized = value.strip().lower()
    if not normalized:
        return
    expected = {
        "linux/amd64": "amd64",
        "amd64": "amd64",
        "linux/arm64": "arm64",
        "linux/arm64/v8": "arm64",
        "arm64": "arm64",
    }.get(normalized)
    if expected is None or expected != normalize_daemon_arch(daemon_arch):
        raise RuntimeBuilderError(
            "DOCKER_DEFAULT_PLATFORM must match the actual Docker daemon architecture; "
            "Runtime release builds do not use silent emulation"
        )


def build_container_command(
    *,
    root: Path,
    output_dir: Path,
    build_dir: Path,
    cache_dir: Path,
    image: str,
    fixed_version: str | None,
    release_prefix: str,
    user_id: int,
    group_id: int,
) -> list[str]:
    del root  # The builder image contains the exact checked-out recipe sources.
    command = [
        "docker",
        "run",
        "--rm",
        "--user",
        f"{user_id}:{group_id}",
        "--env",
        "HOME=/tmp",
    ]
    for name in CHECKSUM_ENV_NAMES:
        if os.environ.get(name):
            command.extend(["--env", name])
    command.extend(
        [
            "--volume",
            f"{output_dir.resolve()}:/output",
            "--volume",
            f"{build_dir.resolve()}:/build",
            "--volume",
            f"{cache_dir.resolve()}:/cache",
            image,
            "python",
            "/workspace/scripts/release_runtime_artifact.py",
            "--output-dir",
            "/output",
            "--build-dir",
            "/build",
            "--cache-dir",
            "/cache",
            "--env-file",
            "/output/runtime.container.env",
        ]
    )
    if fixed_version:
        command.extend(["--fixed-version", fixed_version])
    elif release_prefix:
        command.extend(["--release-prefix", release_prefix])
    return command


def _run(command: list[str], *, cwd: Path) -> str:
    result = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if result.returncode != 0:
        raise RuntimeBuilderError(
            f"command failed ({shlex.join(command)}):\n{result.stdout.rstrip()}"
        )
    return result.stdout


def _run_stream(command: list[str], *, cwd: Path) -> None:
    result = subprocess.run(command, cwd=cwd, text=True)
    if result.returncode != 0:
        raise RuntimeBuilderError(f"command failed ({shlex.join(command)})")


def _daemon_arch(root: Path) -> str:
    output = _run(["docker", "info", "--format", "{{.Architecture}}"], cwd=root)
    return normalize_daemon_arch(output)


def _write_host_env(*, container_env: Path, env_file: Path, output_dir: Path) -> str:
    try:
        text = container_env.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeBuilderError(f"Runtime builder did not write its result environment: {exc}")
    match = re.search(r"^LOAD_NODE_RUNTIME_VERSION=(.+)$", text, flags=re.MULTILINE)
    if match is None:
        raise RuntimeBuilderError(
            "Runtime builder result did not include LOAD_NODE_RUNTIME_VERSION"
        )
    version = shlex.split(match.group(1))[0]
    env_file.parent.mkdir(parents=True, exist_ok=True)
    env_file.write_text(
        f"LOAD_NODE_RUNTIME_VERSION={shlex.quote(version)}\n"
        f"LOAD_NODE_RUNTIME_ARTIFACT_HOST_DIR={shlex.quote(str(output_dir.resolve()))}\n",
        encoding="utf-8",
    )
    return version


def run_builder(
    *,
    root: Path,
    output_dir: Path,
    build_dir: Path,
    cache_dir: Path,
    env_file: Path,
    fixed_version: str | None,
    release_prefix: str,
    image: str = DEFAULT_IMAGE,
) -> str:
    root = root.resolve()
    arch = _daemon_arch(root)
    validate_forced_platform(os.environ.get("DOCKER_DEFAULT_PLATFORM", ""), daemon_arch=arch)
    for directory in (output_dir, build_dir, cache_dir):
        directory.mkdir(parents=True, exist_ok=True)
    descriptor, iid_name = tempfile.mkstemp(prefix=".runtime-builder-iid-", dir=output_dir)
    os.close(descriptor)
    iid_file = Path(iid_name)
    iid_file.unlink()
    try:
        build_command = [
            "docker",
            "build",
            "--platform",
            f"linux/{arch}",
            "--progress=plain",
            "--file",
            "infra/docker/runtime-builder/Dockerfile",
            "--iidfile",
            str(iid_file),
            "--tag",
            image,
            ".",
        ]
        print(f"Building Runtime builder image for linux/{arch}...", flush=True)
        _run_stream(build_command, cwd=root)
        try:
            built_image = iid_file.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise RuntimeBuilderError(f"Runtime builder image ID was not recorded: {exc}") from exc
        if re.fullmatch(r"sha256:[a-f0-9]{64}", built_image) is None:
            raise RuntimeBuilderError("Runtime builder image ID is invalid")
    finally:
        iid_file.unlink(missing_ok=True)
    command = build_container_command(
        root=root,
        output_dir=output_dir,
        build_dir=build_dir,
        cache_dir=cache_dir,
        image=built_image,
        fixed_version=fixed_version,
        release_prefix=release_prefix,
        user_id=os.getuid(),
        group_id=os.getgid(),
    )
    print("Running Runtime artifact builder...", flush=True)
    _run_stream(command, cwd=root)
    version = _write_host_env(
        container_env=output_dir / "runtime.container.env",
        env_file=env_file,
        output_dir=output_dir,
    )
    (output_dir / "runtime.container.env").unlink(missing_ok=True)
    print(f"Containerized Runtime ready: version={version} architecture=linux-{arch}")
    return version


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--build-dir", required=True, type=Path)
    parser.add_argument("--cache-dir", required=True, type=Path)
    parser.add_argument("--env-file", required=True, type=Path)
    parser.add_argument("--fixed-version")
    parser.add_argument("--release-prefix", default=os.environ.get("RUNTIME_RELEASE_PREFIX", ""))
    parser.add_argument("--image", default=DEFAULT_IMAGE)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        run_builder(
            root=args.root,
            output_dir=args.output_dir,
            build_dir=args.build_dir,
            cache_dir=args.cache_dir,
            env_file=args.env_file,
            fixed_version=args.fixed_version,
            release_prefix=args.release_prefix,
            image=args.image,
        )
    except RuntimeBuilderError as exc:
        print(f"Runtime builder failed: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
