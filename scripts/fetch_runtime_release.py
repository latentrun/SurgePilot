"""Fetch and validate P2-05 Runtime assets from the official GitHub Release."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import tarfile
import tempfile
import urllib.error
import urllib.request
from urllib.parse import urlsplit
import zipfile


REPOSITORY_RELEASE_BASE = "https://github.com/latentrun/SurgePilot/releases/download"
LOCAL_ONLY_VALIDATION_VERSION = "v0.0.0"
REQUIRED_PLUGIN_CLASSES = (
    (
        "jpgc-casutg",
        "jmeter-plugins-casutg",
        ("com/blazemeter/jmeter/threads/concurrency/ConcurrencyThreadGroup.class",),
    ),
    (
        "jpgc-json",
        "jmeter-plugins-json",
        (
            "com/atlantbh/jmeter/plugins/jsonutils/jsonpathextractor/JSONPathExtractor.class",
            "com/atlantbh/jmeter/plugins/jsonutils/jsonpathassertion/JSONPathAssertion.class",
        ),
    ),
    (
        "jpgc-tst",
        "jmeter-plugins-tst",
        ("kg/apc/jmeter/timers/VariableThroughputTimer.class",),
    ),
    (
        "bzm-random-csv",
        "jmeter-plugins-random-csv-data-set",
        ("com/blazemeter/jmeter/RandomCSVDataSetConfig.class",),
    ),
    (
        "jmeter-plugin-influxdb2-listener",
        "jmeter-plugins-influxdb2-listener",
        (
            "io/github/mderevyankoaqa/influxdb2/visualizer/"
            "InfluxDatabaseBackendListenerClient.class",
        ),
    ),
)
REQUIRED_PLUGINS = tuple(plugin[0] for plugin in REQUIRED_PLUGIN_CLASSES)


class RuntimeFetchError(RuntimeError):
    """Raised when a Runtime release asset cannot be trusted."""


def _load_release_manifest(root: Path, *, expected_version: str) -> dict[str, object]:
    try:
        from scripts.release_preflight import load_release_manifest
    except ModuleNotFoundError:  # pragma: no cover - exercised by bundled subprocess smoke.
        from release_preflight import load_release_manifest
    return load_release_manifest(root, expected_version=expected_version)


@dataclass(frozen=True)
class ValidatedRuntime:
    archive: Path
    sidecar: Path
    manifest: Path
    sha256: str


def runtime_asset_names(arch: str, version: str) -> tuple[str, str, str]:
    if arch not in {"amd64", "arm64"}:
        raise RuntimeFetchError(f"unsupported Runtime architecture: {arch}")
    prefix = f"surgepilot-runtime-linux-{arch}-{version}"
    return f"{prefix}.tar.gz", f"{prefix}.tar.gz.sha256", f"{prefix}.manifest.json"


def validate_download_url(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.username or parsed.password:
        raise RuntimeFetchError(f"Runtime download URL is not an allowed HTTPS origin: {url}")
    host = (parsed.hostname or "").lower()
    allowed = host == "github.com" or host in {
        "release-assets.githubusercontent.com",
        "objects.githubusercontent.com",
    }
    if not allowed:
        raise RuntimeFetchError(f"Runtime download redirected to an untrusted origin: {host}")


class AllowedRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001, ANN201
        validate_download_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sidecar_digest(path: Path, *, expected_filename: str) -> str:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise RuntimeFetchError(f"cannot read Runtime SHA256 sidecar: {exc}") from exc
    for line in lines:
        parts = line.strip().split()
        if len(parts) >= 2:
            digest = parts[0].lower()
            filename = parts[-1].lstrip("*")
            if re.fullmatch(r"[a-f0-9]{64}", digest) and filename == expected_filename:
                return digest
    raise RuntimeFetchError("Runtime SHA256 sidecar does not name the expected archive")


def _archive_metadata(path: Path) -> dict[str, object]:
    try:
        with tarfile.open(path, "r:gz") as archive:
            member = archive.extractfile("metadata.json")
            if member is None:
                raise RuntimeFetchError("Runtime archive metadata.json is missing")
            metadata = json.loads(member.read().decode("utf-8"))
    except RuntimeFetchError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError, tarfile.TarError, KeyError) as exc:
        raise RuntimeFetchError(f"cannot read Runtime archive metadata: {exc}") from exc
    if not isinstance(metadata, dict):
        raise RuntimeFetchError("Runtime archive metadata must be a JSON object")
    return metadata


def _runtime_manifest(path: Path) -> dict[str, object]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeFetchError(f"cannot read Runtime manifest: {exc}") from exc
    if not isinstance(manifest, dict):
        raise RuntimeFetchError("Runtime manifest must be a JSON object")
    return manifest


def _validate_archive_plugin_jars(path: Path) -> None:
    try:
        with tarfile.open(path, "r:gz") as archive:
            members = {
                Path(member.name).name: member
                for member in archive.getmembers()
                if member.isfile() and member.name.startswith("apache-jmeter-5.6.3/lib/ext/")
            }
            for plugin_name, jar_prefix, required_classes in REQUIRED_PLUGIN_CLASSES:
                matches = [
                    member
                    for name, member in members.items()
                    if name.startswith(f"{jar_prefix}-") and name.endswith(".jar")
                ]
                if len(matches) != 1:
                    raise RuntimeFetchError(
                        f"Runtime archive plugin jar is missing or ambiguous: {plugin_name}"
                    )
                extracted = archive.extractfile(matches[0])
                if extracted is None:
                    raise RuntimeFetchError(
                        f"Runtime archive plugin jar is unreadable: {plugin_name}"
                    )
                try:
                    with zipfile.ZipFile(io.BytesIO(extracted.read())) as jar:
                        names = set(jar.namelist())
                except zipfile.BadZipFile as exc:
                    raise RuntimeFetchError(
                        f"Runtime archive plugin jar is invalid: {plugin_name}"
                    ) from exc
                missing = [class_name for class_name in required_classes if class_name not in names]
                if missing:
                    raise RuntimeFetchError(
                        f"Runtime archive plugin class is missing: {plugin_name}: {missing[0]}"
                    )
    except RuntimeFetchError:
        raise
    except (OSError, tarfile.TarError) as exc:
        raise RuntimeFetchError(f"cannot inspect Runtime plugin jars: {exc}") from exc


def _manifest_input_hash(manifest: dict[str, object]) -> str:
    inputs = {
        key: value for key, value in manifest.items() if key not in {"manifestHash", "version"}
    }
    payload = json.dumps(inputs, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )
    return hashlib.sha256(payload).hexdigest()[:12]


def validate_runtime_files(
    *,
    directory: Path,
    version: str,
    arch: str,
    release_entry: dict[str, object],
) -> ValidatedRuntime:
    archive_name, sidecar_name, manifest_name = runtime_asset_names(arch, version)
    expected_names = {
        "archive": archive_name,
        "sha256Sidecar": sidecar_name,
        "manifest": manifest_name,
    }
    for field, expected in expected_names.items():
        if release_entry.get(field) != expected:
            raise RuntimeFetchError(f"release manifest Runtime {field} does not match {expected}")
    archive = directory / archive_name
    sidecar = directory / sidecar_name
    manifest_path = directory / manifest_name
    for path in (archive, sidecar, manifest_path):
        if not path.is_file() or path.is_symlink():
            raise RuntimeFetchError(f"Runtime asset is missing or unsafe: {path.name}")
    actual_digest = _sha256(archive)
    sidecar_digest = _sidecar_digest(sidecar, expected_filename=archive_name)
    release_digest = str(release_entry.get("sha256") or "").lower()
    if sidecar_digest != actual_digest:
        raise RuntimeFetchError("Runtime archive SHA256 does not match its sidecar")
    if release_digest != actual_digest:
        raise RuntimeFetchError("Runtime archive SHA256 does not match release manifest digest")

    runtime_manifest = _runtime_manifest(manifest_path)
    metadata = _archive_metadata(archive)
    expected_metadata = {
        "name": "surgepilot-runtime",
        "version": version,
        "platform": "linux",
        "arch": arch,
        "taurus": "1.16.50",
        "jmeter": "5.6.3",
    }
    for field, expected in expected_metadata.items():
        if metadata.get(field) != expected:
            raise RuntimeFetchError(
                f"Runtime metadata {field} mismatch: expected {expected}, found {metadata.get(field)}"
            )
    plugins = metadata.get("plugins")
    if plugins != list(REQUIRED_PLUGINS):
        raise RuntimeFetchError("Runtime metadata required plugins are incomplete")
    _validate_archive_plugin_jars(archive)
    target = runtime_manifest.get("target")
    if not isinstance(target, dict):
        raise RuntimeFetchError("Runtime manifest target is missing")
    if target.get("platform") != "linux" or target.get("metadataArch") != arch:
        raise RuntimeFetchError("Runtime manifest platform or architecture does not match")
    if target.get("artifactArch") != f"linux-{arch}":
        raise RuntimeFetchError("Runtime manifest artifact architecture does not match")
    if runtime_manifest.get("version") != version:
        raise RuntimeFetchError("Runtime manifest version does not match")
    manifest_hash = runtime_manifest.get("manifestHash")
    if (
        not isinstance(manifest_hash, str)
        or re.fullmatch(r"[a-f0-9]{12}", manifest_hash) is None
        or _manifest_input_hash(runtime_manifest) != manifest_hash
    ):
        raise RuntimeFetchError("Runtime manifest hash does not match its canonical inputs")
    components = runtime_manifest.get("components")
    if not isinstance(components, dict):
        raise RuntimeFetchError("Runtime manifest component contract is missing")
    taurus = components.get("taurus")
    jmeter = components.get("jmeter")
    manifest_plugins = components.get("plugins")
    plugin_names = (
        {
            str(plugin.get("name"))
            for plugin in manifest_plugins
            if isinstance(plugin, dict) and plugin.get("name")
        }
        if isinstance(manifest_plugins, list)
        else set()
    )
    if (
        not isinstance(taurus, dict)
        or taurus.get("version") != "1.16.50"
        or not isinstance(jmeter, dict)
        or jmeter.get("version") != "5.6.3"
        or plugin_names != set(REQUIRED_PLUGINS)
    ):
        raise RuntimeFetchError("Runtime manifest component contract does not match release")
    builder = metadata.get("builder")
    if not isinstance(builder, dict) or builder.get("manifestHash") != manifest_hash:
        raise RuntimeFetchError("Runtime metadata manifest hash does not match Runtime manifest")
    return ValidatedRuntime(archive, sidecar, manifest_path, actual_digest)


def _copy_private_atomic(source: Path, target: Path) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=".runtime-", dir=target.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with source.open("rb") as input_file, os.fdopen(descriptor, "wb") as output_file:
            descriptor = -1
            shutil.copyfileobj(input_file, output_file)
            output_file.flush()
            os.fsync(output_file.fileno())
        os.replace(temporary, target)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)


def _write_env_file(path: Path, *, version: str, host_directory: Path) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=".runtime-env-", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            descriptor = -1
            handle.write(
                f"LOAD_NODE_RUNTIME_VERSION={version}\n"
                f"LOAD_NODE_RUNTIME_ARTIFACT_HOST_DIR={host_directory}\n"
            )
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)


def publish_runtime_files(
    *,
    staging_directory: Path,
    target_directory: Path,
    version: str,
    architectures: tuple[str, ...],
    release_entries: dict[str, dict[str, object]],
    env_file: Path,
    env_host_directory: Path,
) -> None:
    validated = {
        arch: validate_runtime_files(
            directory=staging_directory,
            version=version,
            arch=arch,
            release_entry=release_entries[arch],
        )
        for arch in architectures
    }
    target_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(target_directory, 0o700)
    for runtime in validated.values():
        for source in (runtime.archive, runtime.sidecar, runtime.manifest):
            _copy_private_atomic(source, target_directory / source.name)
    env_file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    _write_env_file(env_file, version=version, host_directory=env_host_directory)


def download_file(url: str, target: Path) -> None:
    validate_download_url(url)
    opener = urllib.request.build_opener(AllowedRedirectHandler())
    descriptor, temporary_name = tempfile.mkstemp(prefix=".download-", dir=target.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as output:
            descriptor = -1
            try:
                with opener.open(url, timeout=60) as response:
                    validate_download_url(response.geturl())
                    shutil.copyfileobj(response, output)
            except (OSError, urllib.error.URLError) as exc:
                raise RuntimeFetchError(
                    f"Runtime download failed for {target.name}: {exc}"
                ) from exc
            output.flush()
            os.fsync(output.fileno())
        if temporary.stat().st_size == 0:
            raise RuntimeFetchError(f"Runtime download was empty for {target.name}")
        os.replace(temporary, target)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)


def fetch_release_runtimes(
    *,
    root: Path,
    version: str,
    architectures: tuple[str, ...],
    target_directory: Path,
    env_host_directory: Path,
) -> None:
    manifest = _load_release_manifest(root, expected_version=version)
    runtime_entries = manifest["runtimes"]
    assert isinstance(runtime_entries, dict)
    entries = {arch: runtime_entries[arch] for arch in architectures}
    if all(
        _is_reusable(
            target_directory=target_directory,
            version=version,
            arch=arch,
            release_entry=entries[arch],
        )
        for arch in architectures
    ):
        target_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        _write_env_file(
            target_directory / "runtime.env",
            version=version,
            host_directory=env_host_directory,
        )
        return

    if version == LOCAL_ONLY_VALIDATION_VERSION:
        raise RuntimeFetchError(
            "development validation Runtime v0.0.0 must be pre-positioned and valid; "
            "GitHub Release download is disabled"
        )

    target_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.TemporaryDirectory(prefix=".runtime-fetch-", dir=target_directory) as name:
        staging = Path(name)
        for arch in architectures:
            entry = entries[arch]
            assert isinstance(entry, dict)
            for field in ("archive", "sha256Sidecar", "manifest"):
                asset_name = str(entry[field])
                download_file(
                    f"{REPOSITORY_RELEASE_BASE}/{version}/{asset_name}", staging / asset_name
                )
        publish_runtime_files(
            staging_directory=staging,
            target_directory=target_directory,
            version=version,
            architectures=architectures,
            release_entries=entries,  # type: ignore[arg-type]
            env_file=target_directory / "runtime.env",
            env_host_directory=env_host_directory,
        )


def _is_reusable(
    *,
    target_directory: Path,
    version: str,
    arch: str,
    release_entry: object,
) -> bool:
    if not isinstance(release_entry, dict):
        return False
    try:
        validate_runtime_files(
            directory=target_directory,
            version=version,
            arch=arch,
            release_entry=release_entry,
        )
    except RuntimeFetchError:
        return False
    return True


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--architectures", default="")
    parser.add_argument("--target-directory", required=True, type=Path)
    parser.add_argument("--env-host-directory", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    architectures = tuple(value for value in args.architectures.split(",") if value)
    try:
        fetch_release_runtimes(
            root=args.root,
            version=args.version,
            architectures=architectures,
            target_directory=args.target_directory,
            env_host_directory=args.env_host_directory,
        )
    except (RuntimeFetchError, ValueError) as exc:
        print(f"Runtime fetch failed: {exc}")
        return 1
    print(
        "Runtime assets ready: "
        + (", ".join(f"linux-{arch}" for arch in architectures) or "none requested")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
