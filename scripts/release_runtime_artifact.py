"""Build and validate SurgePilot Load Node runtime release artifacts.

The official local full-stack startup uses this helper as a release-job subset when
CI artifacts are unavailable. The produced artifact remains a deployment asset:
it is written to a local runtime artifact directory and is not uploaded to MinIO
or exposed as a product runtime-management capability.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import gzip
import hashlib
import http.client
import io
import json
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile


TAURUS_VERSION = "1.16.50"
JMETER_VERSION = "5.6.3"
DEFAULT_PYTHON_VERSION = "3.12.11"
MANIFEST_SCHEMA_VERSION = 1
ROOT = Path(__file__).resolve().parents[1]
RUNNER_WRAPPER = ROOT / "apps" / "runner" / "surgepilot_runner" / "jmeter_wrapper.py"
SAFE_RELEASE_PREFIX = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
DOWNLOAD_ATTEMPTS = 3
DOWNLOAD_RETRY_DELAY_SECONDS = 2


@dataclass(frozen=True)
class RuntimeArch:
    artifact_arch: str
    metadata_arch: str


@dataclass(frozen=True)
class ReleaseResult:
    version: str
    manifest_hash: str
    output_dir: Path
    archive_path: Path
    sha256_path: Path
    manifest_path: Path
    reused: bool


@dataclass(frozen=True)
class RuntimePlugin:
    name: str
    env_prefix: str
    default_version: str
    maven_group_path: str
    maven_artifact: str
    required_classes: tuple[str, ...]

    def artifact_filename(self, version: str) -> str:
        return f"{self.maven_artifact}-{version}.jar"

    def default_url(self, version: str) -> str:
        return (
            "https://repo1.maven.org/maven2/"
            f"{self.maven_group_path}/{self.maven_artifact}/{version}/"
            f"{self.artifact_filename(version)}"
        )

    @property
    def version_env(self) -> str:
        return f"RUNTIME_{self.env_prefix}_VERSION"

    @property
    def url_env(self) -> str:
        return f"RUNTIME_{self.env_prefix}_URL"

    @property
    def sha256_env(self) -> str:
        return f"RUNTIME_{self.env_prefix}_SHA256"


RUNTIME_PLUGINS = (
    RuntimePlugin(
        name="jpgc-casutg",
        env_prefix="CASUTG",
        default_version="2.10",
        maven_group_path="kg/apc",
        maven_artifact="jmeter-plugins-casutg",
        required_classes=(
            "com/blazemeter/jmeter/threads/concurrency/ConcurrencyThreadGroup.class",
        ),
    ),
    RuntimePlugin(
        name="jpgc-json",
        env_prefix="JSON",
        default_version="2.7",
        maven_group_path="kg/apc",
        maven_artifact="jmeter-plugins-json",
        required_classes=(
            "com/atlantbh/jmeter/plugins/jsonutils/jsonpathextractor/JSONPathExtractor.class",
            "com/atlantbh/jmeter/plugins/jsonutils/jsonpathassertion/JSONPathAssertion.class",
        ),
    ),
    RuntimePlugin(
        name="jpgc-tst",
        env_prefix="TST",
        default_version="2.6",
        maven_group_path="kg/apc",
        maven_artifact="jmeter-plugins-tst",
        required_classes=("kg/apc/jmeter/timers/VariableThroughputTimer.class",),
    ),
    RuntimePlugin(
        name="bzm-random-csv",
        env_prefix="RANDOM_CSV",
        default_version="0.8",
        maven_group_path="com/blazemeter",
        maven_artifact="jmeter-plugins-random-csv-data-set",
        required_classes=("com/blazemeter/jmeter/RandomCSVDataSetConfig.class",),
    ),
    RuntimePlugin(
        name="jmeter-plugin-influxdb2-listener",
        env_prefix="INFLUXDB2_LISTENER",
        default_version="2.8",
        maven_group_path="io/github/mderevyankoaqa",
        maven_artifact="jmeter-plugins-influxdb2-listener",
        required_classes=(
            "io/github/mderevyankoaqa/influxdb2/visualizer/"
            "InfluxDatabaseBackendListenerClient.class",
        ),
    ),
)
REQUIRED_PLUGINS = [plugin.name for plugin in RUNTIME_PLUGINS]


def normalize_arch(machine: str | None = None) -> RuntimeArch:
    normalized = (machine or platform.machine()).strip().lower()
    if normalized in {"x86_64", "amd64"}:
        return RuntimeArch(artifact_arch="linux-amd64", metadata_arch="amd64")
    if normalized in {"aarch64", "arm64"}:
        return RuntimeArch(artifact_arch="linux-arm64", metadata_arch="arm64")
    raise RuntimeError(f"unsupported runtime builder architecture: {machine or platform.machine()}")


def stable_json_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )


def stable_manifest_hash(manifest: dict[str, object]) -> str:
    return hashlib.sha256(stable_json_bytes(manifest)).hexdigest()[:12]


def manifest_input_hash(manifest: dict[str, object]) -> str:
    input_manifest = {
        key: value for key, value in manifest.items() if key not in {"manifestHash", "version"}
    }
    return stable_manifest_hash(input_manifest)


def runtime_version(*, release_prefix: str, manifest_hash: str) -> str:
    prefix = release_prefix.strip()
    return f"{prefix}-{manifest_hash}" if prefix else f"dev-{manifest_hash}"


def validate_release_prefix(release_prefix: str) -> str:
    prefix = release_prefix.strip()
    if not prefix:
        return ""
    if not SAFE_RELEASE_PREFIX.fullmatch(prefix):
        raise RuntimeError(
            "RUNTIME_RELEASE_PREFIX must use 1-64 characters from A-Z, a-z, 0-9, '.', '_', '-' "
            "and must start with an alphanumeric character"
        )
    return prefix


def validate_fixed_version(fixed_version: str | None) -> str | None:
    if fixed_version is None:
        return None
    version = validate_release_prefix(fixed_version)
    if not version:
        raise RuntimeError("--fixed-version must not be empty")
    return version


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_tree(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256_file(path).encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def parse_sha256_sidecar(path: Path, *, expected_filename: str) -> str | None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in lines:
        parts = line.strip().split()
        if not parts:
            continue
        digest = parts[0].lower()
        filename = parts[-1].lstrip("*")
        if re.fullmatch(r"[a-f0-9]{64}", digest) and filename == expected_filename:
            return digest
    return None


def _artifact_paths(
    *, output_dir: Path, artifact_arch: str, version: str
) -> tuple[Path, Path, Path]:
    archive = output_dir / f"surgepilot-runtime-{artifact_arch}-{version}.tar.gz"
    sha256_path = archive.with_name(f"{archive.name}.sha256")
    manifest_path = output_dir / f"surgepilot-runtime-{artifact_arch}-{version}.manifest.json"
    return archive, sha256_path, manifest_path


def _archive_metadata(archive: Path) -> dict[str, object] | None:
    try:
        with tarfile.open(archive, "r:gz") as tar:
            member = tar.getmember("metadata.json")
            extracted = tar.extractfile(member)
            if extracted is None:
                return None
            return json.loads(extracted.read().decode("utf-8"))
    except (OSError, KeyError, json.JSONDecodeError, tarfile.TarError):
        return None


def _archive_has_required_plugin_classes(archive: Path) -> bool:
    try:
        with tarfile.open(archive, "r:gz") as tar:
            members = {
                Path(member.name).name: member
                for member in tar.getmembers()
                if member.isfile()
                and member.name.startswith(f"apache-jmeter-{JMETER_VERSION}/lib/ext/")
            }
            for plugin in RUNTIME_PLUGINS:
                matches = [
                    member
                    for name, member in members.items()
                    if name.startswith(f"{plugin.maven_artifact}-") and name.endswith(".jar")
                ]
                if len(matches) != 1:
                    return False
                extracted = tar.extractfile(matches[0])
                if extracted is None:
                    return False
                with zipfile.ZipFile(io.BytesIO(extracted.read())) as jar:
                    names = set(jar.namelist())
                if not all(required_class in names for required_class in plugin.required_classes):
                    return False
    except (OSError, tarfile.TarError, zipfile.BadZipFile):
        return False
    return True


def artifact_is_reusable(
    *, output_dir: Path, artifact_arch: str, metadata_arch: str, version: str, manifest_hash: str
) -> bool:
    archive, sha256_path, manifest_path = _artifact_paths(
        output_dir=output_dir, artifact_arch=artifact_arch, version=version
    )
    if not archive.is_file() or not sha256_path.is_file() or not manifest_path.is_file():
        return False
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if manifest_input_hash(manifest) != manifest_hash:
        return False
    if manifest.get("manifestHash") != manifest_hash:
        return False
    if manifest.get("version") != version:
        return False
    expected_digest = parse_sha256_sidecar(sha256_path, expected_filename=archive.name)
    if expected_digest is None or expected_digest != sha256_file(archive):
        return False
    metadata = _archive_metadata(archive)
    if metadata is None:
        return False
    manifest_components = manifest.get("components")
    expected_plugin_artifacts = (
        manifest_components.get("plugins")
        if isinstance(manifest_components, dict)
        else None
    )
    if isinstance(expected_plugin_artifacts, list):
        if metadata.get("pluginArtifacts") != expected_plugin_artifacts:
            return False
    if isinstance(expected_plugin_artifacts, list):
        smoke = metadata.get("smoke")
        if not isinstance(smoke, dict) or any(
            smoke.get(name) != "passed" for name in ("taurus", "jmeter", "plugins")
        ):
            return False
    return (
        metadata.get("name") == "surgepilot-runtime"
        and metadata.get("version") == version
        and metadata.get("platform") == "linux"
        and metadata.get("arch") == metadata_arch
        and metadata.get("taurus") == TAURUS_VERSION
        and metadata.get("jmeter") == JMETER_VERSION
        and metadata.get("plugins") == REQUIRED_PLUGINS
        and _archive_has_required_plugin_classes(archive)
    )


def _run(
    command: list[str], *, cwd: Path | None = None, extra_env: dict[str, str] | None = None
) -> None:
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if result.returncode != 0:
        raise RuntimeError(f"command failed ({' '.join(command)}):\n{result.stdout}")


def _normalize_expected_sha256(value: str | None, *, name: str) -> str | None:
    expected = (value or "").strip().lower()
    if not expected:
        return None
    if not re.fullmatch(r"[a-f0-9]{64}", expected):
        raise RuntimeError(
            f"{name} must be a 64-character lowercase or uppercase SHA256 hex digest"
        )
    return expected


def _download_metadata_path(target: Path) -> Path:
    return target.with_name(f"{target.name}.metadata.json")


def _download_metadata_matches(
    metadata_path: Path, *, url: str, expected_sha256: str | None
) -> bool:
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return (
        metadata.get("schemaVersion") == 1
        and metadata.get("url") == url
        and metadata.get("expectedSha256") == expected_sha256
    )


def _write_download_metadata(
    metadata_path: Path, *, url: str, expected_sha256: str | None, sha256: str
) -> None:
    metadata_path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "url": url,
                "expectedSha256": expected_sha256,
                "sha256": sha256,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )


def _download(url: str, target: Path, *, expected_sha256: str | None = None) -> str:
    target.parent.mkdir(parents=True, exist_ok=True)
    expected = _normalize_expected_sha256(
        expected_sha256, name=f"expected checksum for {target.name}"
    )
    metadata_path = _download_metadata_path(target)
    if target.is_file() and _download_metadata_matches(
        metadata_path, url=url, expected_sha256=expected
    ):
        digest = sha256_file(target)
        if expected is None or digest == expected:
            return digest

    with tempfile.NamedTemporaryFile(
        dir=target.parent, prefix=f".{target.name}.", delete=False
    ) as tmp:
        tmp_path = Path(tmp.name)
    try:
        try:
            parsed_url = urllib.parse.urlsplit(url)
        except ValueError as exc:
            raise RuntimeError(f"failed to download {target.name}: invalid URL") from exc
        source = parsed_url.hostname or parsed_url.scheme or "unknown"
        for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
            print(
                f"Downloading {target.name} from {source} (attempt {attempt}/{DOWNLOAD_ATTEMPTS})",
                flush=True,
            )
            try:
                with urllib.request.urlopen(  # noqa: S310 - pinned HTTPS URLs.
                    url, timeout=120
                ) as response:
                    with tmp_path.open("wb") as handle:
                        shutil.copyfileobj(response, handle)
                break
            except urllib.error.HTTPError as exc:
                raise RuntimeError(
                    f"failed to download {target.name} from {source}: HTTP {exc.code}"
                ) from exc
            except http.client.InvalidURL as exc:
                raise RuntimeError(
                    f"failed to download {target.name} from {source}: invalid URL"
                ) from exc
            except (OSError, http.client.HTTPException) as exc:
                if attempt == DOWNLOAD_ATTEMPTS:
                    reason = getattr(exc, "reason", exc)
                    error_name = type(reason).__name__
                    raise RuntimeError(
                        f"failed to download {target.name} from {source} after "
                        f"{DOWNLOAD_ATTEMPTS} attempts: {error_name}"
                    ) from exc
                time.sleep(DOWNLOAD_RETRY_DELAY_SECONDS)
        digest = sha256_file(tmp_path)
        if expected is not None and digest != expected:
            raise RuntimeError(
                f"downloaded checksum mismatch for {target.name}: expected {expected}, got {digest}"
            )
        tmp_path.replace(target)
        _write_download_metadata(metadata_path, url=url, expected_sha256=expected, sha256=digest)
        return digest
    finally:
        tmp_path.unlink(missing_ok=True)


def _pip_index_env() -> dict[str, str]:
    return {
        "PIP_INDEX_URL": os.environ.get(
            "RUNTIME_PIP_INDEX_URL",
            os.environ.get("SURGEPILOT_PIP_INDEX_URL", "https://pypi.org/simple"),
        )
    }


def _resolver_cache_key(*, python_version: str) -> str:
    pip_index_url = _pip_index_env()["PIP_INDEX_URL"]
    payload = {
        "schemaVersion": 1,
        "taurusVersion": TAURUS_VERSION,
        "targetPythonVersion": python_version,
        "pipIndexUrl": pip_index_url,
        "resolverPython": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    }
    return hashlib.sha256(stable_json_bytes(payload)).hexdigest()[:12]


def _resolve_taurus_dependencies(cache_dir: Path, *, python_version: str) -> list[str]:
    cache_key = _resolver_cache_key(python_version=python_version)
    report_path = (
        cache_dir
        / "downloads"
        / f"taurus-{TAURUS_VERSION}-{python_version}-{cache_key}.pip-report.json"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    if not report_path.is_file():
        tmp_report = report_path.with_suffix(".tmp.json")
        _run(
            [
                "uv",
                "run",
                "--with",
                "pip",
                "python",
                "-m",
                "pip",
                "install",
                "--dry-run",
                "--ignore-installed",
                "--report",
                str(tmp_report),
                f"bzt=={TAURUS_VERSION}",
            ],
            extra_env=_pip_index_env(),
        )
        tmp_report.replace(report_path)
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"invalid Taurus dependency report: {report_path}") from exc
    dependencies: list[str] = []
    for item in report.get("install", []):
        metadata = item.get("metadata") or {}
        name = str(metadata.get("name") or "").strip()
        version = str(metadata.get("version") or "").strip()
        if name and version:
            dependencies.append(f"{name}=={version}")
    if f"bzt=={TAURUS_VERSION}" not in dependencies:
        dependencies.append(f"bzt=={TAURUS_VERSION}")
    return sorted(set(dependencies), key=str.lower)


def _safe_extract_tar(archive: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    target_root = target.resolve()
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar.getmembers():
            if member.issym() or member.islnk() or not (member.isdir() or member.isfile()):
                raise RuntimeError(f"unsafe tar member: {member.name}")
            member_target = (target / member.name).resolve()
            if member_target != target_root and not str(member_target).startswith(
                str(target_root) + os.sep
            ):
                raise RuntimeError(f"unsafe tar member: {member.name}")
        tar.extractall(target, filter="data")


def _validate_zip_contains(
    archive: Path, *, description: str, required_suffix: str | None = None
) -> None:
    try:
        with zipfile.ZipFile(archive) as jar:
            names = jar.namelist()
    except zipfile.BadZipFile as exc:
        raise RuntimeError(f"{description} jar is invalid: {archive}") from exc
    if required_suffix is not None:
        if not any(name.endswith(required_suffix) for name in names):
            raise RuntimeError(
                f"{description} jar does not contain required class: {required_suffix}"
            )
        return
    if not any(name.endswith(".class") for name in names):
        raise RuntimeError(f"{description} jar does not contain any class files")


def _current_component_selection() -> dict[str, object]:
    python_version = os.environ.get("RUNTIME_PYTHON_VERSION", DEFAULT_PYTHON_VERSION)
    jmeter_url = os.environ.get(
        "RUNTIME_JMETER_URL",
        f"https://archive.apache.org/dist/jmeter/binaries/apache-jmeter-{JMETER_VERSION}.tgz",
    )
    jmeter_expected_sha256 = _normalize_expected_sha256(
        os.environ.get("RUNTIME_JMETER_SHA256"), name="RUNTIME_JMETER_SHA256"
    )
    plugins: list[dict[str, object]] = []
    for plugin in RUNTIME_PLUGINS:
        version = os.environ.get(plugin.version_env, plugin.default_version)
        url = os.environ.get(plugin.url_env, plugin.default_url(version))
        expected_sha256 = _normalize_expected_sha256(
            os.environ.get(plugin.sha256_env), name=plugin.sha256_env
        )
        plugins.append(
            {
                "name": plugin.name,
                "version": version,
                "url": url,
                "expectedSha256": expected_sha256,
            }
        )
    return {
        "pythonVersion": python_version,
        "jmeter": {
            "version": JMETER_VERSION,
            "url": jmeter_url,
            "expectedSha256": jmeter_expected_sha256,
        },
        "plugins": plugins,
    }


def _find_uv_python_install(install_dir: Path, python_version: str) -> Path:
    candidates = sorted(
        (
            path
            for path in install_dir.iterdir()
            if path.is_dir()
            and (path / "bin" / "python3").is_file()
            and python_version in path.name
        ),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise RuntimeError(f"uv did not install Python {python_version} under {install_dir}")
    return candidates[0]


def _write_executable(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _runtime_component_inputs(*, cache_dir: Path) -> tuple[dict[str, object], dict[str, object]]:
    selection = _current_component_selection()
    python_version = str(selection["pythonVersion"])
    selected_jmeter = selection["jmeter"]
    selected_plugins = selection["plugins"]
    assert isinstance(selected_jmeter, dict)
    assert isinstance(selected_plugins, list)
    downloads_dir = cache_dir / "downloads"
    jmeter_url = str(selected_jmeter["url"])
    jmeter_expected_sha256 = selected_jmeter.get("expectedSha256")
    jmeter_archive = downloads_dir / f"apache-jmeter-{JMETER_VERSION}.tgz"
    jmeter_sha256 = _download(
        jmeter_url,
        jmeter_archive,
        expected_sha256=str(jmeter_expected_sha256) if jmeter_expected_sha256 is not None else None,
    )
    taurus_dependencies = _resolve_taurus_dependencies(cache_dir, python_version=python_version)
    selected_by_name = {
        str(plugin["name"]): plugin for plugin in selected_plugins if isinstance(plugin, dict)
    }
    plugin_components: list[dict[str, object]] = []
    plugin_downloads: dict[str, Path] = {}
    for plugin in RUNTIME_PLUGINS:
        selected = selected_by_name.get(plugin.name)
        if selected is None:
            raise RuntimeError(f"runtime component selection missing plugin: {plugin.name}")
        version = str(selected["version"])
        url = str(selected["url"])
        expected_sha256 = selected.get("expectedSha256")
        download = downloads_dir / plugin.artifact_filename(version)
        digest = _download(
            url,
            download,
            expected_sha256=str(expected_sha256) if expected_sha256 is not None else None,
        )
        for required_class in plugin.required_classes:
            _validate_zip_contains(
                download,
                description=f"{plugin.name} plugin",
                required_suffix=required_class,
            )
        plugin_downloads[plugin.name] = download
        plugin_components.append(
            {
                "name": plugin.name,
                "version": version,
                "url": url,
                "sha256": digest,
            }
        )
    components: dict[str, object] = {
        "pythonBuildStandalone": {"version": python_version, "provider": "uv-managed-python"},
        "taurus": {"version": TAURUS_VERSION, "pythonDependencies": taurus_dependencies},
        "jmeter": {"version": JMETER_VERSION, "url": jmeter_url, "sha256": jmeter_sha256},
        "plugins": plugin_components,
    }
    inputs: dict[str, object] = {
        "python_version": python_version,
        "jmeter_archive": jmeter_archive,
        "plugin_downloads": plugin_downloads,
        "plugin_components": plugin_components,
        "taurus_dependencies": taurus_dependencies,
    }
    return components, inputs


def _prepare_runtime_source(
    *, build_dir: Path, cache_dir: Path, arch: RuntimeArch, component_inputs: dict[str, object]
) -> Path:
    python_version = str(component_inputs["python_version"])
    python_install_dir = cache_dir / "python"
    source_dir = build_dir / "runtime-source"
    shutil.rmtree(source_dir, ignore_errors=True)
    source_dir.mkdir(parents=True, exist_ok=True)

    _run(
        [
            "uv",
            "python",
            "install",
            python_version,
            "--install-dir",
            str(python_install_dir),
            "--no-bin",
            "--no-progress",
        ]
    )
    python_install = _find_uv_python_install(python_install_dir, python_version)
    shutil.copytree(python_install, source_dir / "python")
    runtime_python = source_dir / "python" / "bin" / "python3"
    pip_env = {
        "PIP_BREAK_SYSTEM_PACKAGES": "1",
        "PIP_USER": "0",
        "PYTHONNOUSERSITE": "1",
        **_pip_index_env(),
    }
    pip_available = subprocess.run(
        [str(runtime_python), "-I", "-m", "pip", "--version"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env={**os.environ, **pip_env},
    )
    if pip_available.returncode != 0:
        _run([str(runtime_python), "-I", "-m", "ensurepip", "--upgrade"], extra_env=pip_env)
    taurus_dependencies = component_inputs.get("taurus_dependencies")
    if not isinstance(taurus_dependencies, list) or not taurus_dependencies:
        raise RuntimeError("runtime component inputs missing Taurus dependency closure")
    _run(
        [
            str(runtime_python),
            "-I",
            "-m",
            "pip",
            "install",
            "--prefix",
            str(source_dir / "python"),
            "--break-system-packages",
            "--no-cache-dir",
            *[str(dependency) for dependency in taurus_dependencies],
        ],
        extra_env=pip_env,
    )

    extracted = build_dir / "jmeter-extracted"
    shutil.rmtree(extracted, ignore_errors=True)
    _safe_extract_tar(Path(component_inputs["jmeter_archive"]), extracted)
    shutil.copytree(
        extracted / f"apache-jmeter-{JMETER_VERSION}",
        source_dir / f"apache-jmeter-{JMETER_VERSION}",
    )

    plugin_dir = source_dir / f"apache-jmeter-{JMETER_VERSION}" / "lib" / "ext"
    plugin_downloads = component_inputs.get("plugin_downloads")
    if not isinstance(plugin_downloads, dict):
        raise RuntimeError("runtime component inputs missing plugin downloads")
    for plugin in RUNTIME_PLUGINS:
        download = plugin_downloads.get(plugin.name)
        if not isinstance(download, Path):
            raise RuntimeError(f"runtime component inputs missing plugin: {plugin.name}")
        shutil.copy2(download, plugin_dir / download.name)

    wrapper_module = source_dir / "python" / "lib" / "surgepilot_runner" / "jmeter_wrapper.py"
    wrapper_module.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(RUNNER_WRAPPER, wrapper_module)
    (wrapper_module.parent / "__init__.py").write_text("", encoding="utf-8")

    _write_executable(
        source_dir / "bin" / "bzt",
        "#!/bin/sh\n"
        'script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"\n'
        'export PYTHONNOUSERSITE="1"\n'
        'exec "$script_dir/../python/bin/python3" -m bzt.cli "$@"\n',
    )
    _write_executable(
        source_dir / f"apache-jmeter-{JMETER_VERSION}" / "bin" / "surgepilot-jmeter-wrapper",
        "#!/bin/sh\n"
        'script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"\n'
        'runtime_root="$script_dir/../.."\n'
        'export PYTHONNOUSERSITE="1"\n'
        'export PYTHONPATH="$runtime_root/python/lib${PYTHONPATH:+:$PYTHONPATH}"\n'
        'export SURGEPILOT_RUNTIME_HOME="$runtime_root"\n'
        'exec "$runtime_root/python/bin/python3" -m surgepilot_runner.jmeter_wrapper "$@"\n',
    )

    plugin_metadata = component_inputs.get("plugin_components")
    if not isinstance(plugin_metadata, list):
        raise RuntimeError("runtime component inputs missing plugin metadata")
    metadata = {
        "name": "surgepilot-runtime",
        "version": "__VERSION__",
        "platform": "linux",
        "arch": arch.metadata_arch,
        "python": python_version,
        "taurus": TAURUS_VERSION,
        "jmeter": JMETER_VERSION,
        "plugins": REQUIRED_PLUGINS,
        "pluginArtifacts": plugin_metadata,
        "smoke": {"taurus": "passed", "jmeter": "passed", "plugins": "passed"},
        "builder": {"os": platform.platform(), "arch": arch.metadata_arch, "tool": "uv"},
    }
    (source_dir / "metadata.json").write_text(
        json.dumps(metadata, sort_keys=True, separators=(",", ":")), encoding="utf-8"
    )

    _run([str(source_dir / "bin" / "bzt"), "-h"])
    _run([str(source_dir / f"apache-jmeter-{JMETER_VERSION}" / "bin" / "jmeter"), "--version"])
    return source_dir


def _recipe_files() -> list[dict[str, str]]:
    paths = [
        Path(__file__).resolve(),
        RUNNER_WRAPPER,
        ROOT / "apps" / "runner" / "pyproject.toml",
        ROOT / "infra" / "docker" / "runtime-builder" / "Dockerfile",
    ]
    uv_lock = ROOT / "uv.lock"
    if uv_lock.is_file():
        paths.append(uv_lock)
    return [
        {"path": path.relative_to(ROOT).as_posix(), "sha256": sha256_file(path)}
        for path in paths
        if path.is_file()
    ]


def _build_manifest(
    *, release_prefix: str, arch: RuntimeArch, components: dict[str, object]
) -> dict[str, object]:
    return {
        "schemaVersion": MANIFEST_SCHEMA_VERSION,
        "releasePrefix": release_prefix.strip(),
        "target": {
            "platform": "linux",
            "artifactArch": arch.artifact_arch,
            "metadataArch": arch.metadata_arch,
        },
        "components": components,
        "recipeFiles": _recipe_files(),
    }


def _copy_source_with_metadata(
    *,
    source_dir: Path,
    staging_dir: Path,
    version: str,
    arch: RuntimeArch,
    manifest_hash: str,
    components: dict[str, object] | None = None,
) -> None:
    shutil.rmtree(staging_dir, ignore_errors=True)
    shutil.copytree(source_dir, staging_dir)
    metadata_path = staging_dir / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata.update(
        {
            "name": "surgepilot-runtime",
            "version": version,
            "platform": "linux",
            "arch": arch.metadata_arch,
            "taurus": TAURUS_VERSION,
            "jmeter": JMETER_VERSION,
            "plugins": REQUIRED_PLUGINS,
        }
    )
    if components is not None and isinstance(components.get("plugins"), list):
        metadata["pluginArtifacts"] = components["plugins"]
    else:
        metadata.setdefault("pluginArtifacts", [])
    metadata.setdefault(
        "smoke", {"taurus": "passed", "jmeter": "passed", "plugins": "passed"}
    )
    metadata.setdefault("builder", {})
    if isinstance(metadata["builder"], dict):
        metadata["builder"]["arch"] = arch.metadata_arch
        metadata["builder"]["manifestHash"] = manifest_hash
    metadata_path.write_text(
        json.dumps(metadata, sort_keys=True, separators=(",", ":")), encoding="utf-8"
    )


def _tar_add_directory(tar: tarfile.TarFile, root: Path, relative: Path) -> None:
    path = root / relative
    for item in sorted(path.rglob("*")):
        arcname = item.relative_to(root).as_posix()
        info = tar.gettarinfo(str(item), arcname=arcname)
        info.uid = info.gid = 0
        info.uname = info.gname = ""
        if item.is_file():
            with item.open("rb") as handle:
                tar.addfile(info, handle)
        else:
            tar.addfile(info)


def _write_archive(*, source_dir: Path, archive_path: Path) -> None:
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=archive_path.parent, suffix=".tar", delete=False
    ) as raw_file:
        raw_path = Path(raw_file.name)
    try:
        with tarfile.open(raw_path, "w") as tar:
            for name in ("metadata.json", "bin", "python", f"apache-jmeter-{JMETER_VERSION}"):
                path = source_dir / name
                if path.is_dir():
                    _tar_add_directory(tar, source_dir, Path(name))
                else:
                    info = tar.gettarinfo(str(path), arcname=name)
                    info.uid = info.gid = 0
                    info.uname = info.gname = ""
                    with path.open("rb") as handle:
                        tar.addfile(info, handle)
        with (
            raw_path.open("rb") as raw,
            gzip.GzipFile(filename="", mode="wb", fileobj=archive_path.open("wb"), mtime=0) as gz,
        ):
            shutil.copyfileobj(raw, gz)
    finally:
        raw_path.unlink(missing_ok=True)


def _write_env_file(*, env_file: Path, output_dir: Path, version: str) -> None:
    env_file.parent.mkdir(parents=True, exist_ok=True)
    env_file.write_text(
        "LOAD_NODE_RUNTIME_VERSION="
        f"{shlex.quote(version)}\n"
        "LOAD_NODE_RUNTIME_ARTIFACT_HOST_DIR="
        f"{shlex.quote(str(output_dir))}\n",
        encoding="utf-8",
    )


def release_runtime(
    *,
    output_dir: Path,
    build_dir: Path,
    cache_dir: Path,
    release_prefix: str = "",
    fixed_version: str | None = None,
    source_dir: Path | None = None,
    env_file: Path | None = None,
) -> ReleaseResult:
    fixed_version = validate_fixed_version(fixed_version)
    release_prefix = "" if fixed_version is not None else validate_release_prefix(release_prefix)
    output_dir = output_dir.resolve()
    build_dir = build_dir.resolve()
    cache_dir = cache_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    build_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    arch = normalize_arch()

    component_inputs: dict[str, object] | None = None
    if source_dir is None:
        components, component_inputs = _runtime_component_inputs(cache_dir=cache_dir)
    else:
        source_dir = source_dir.resolve()
        components = {"sourceRuntimeTreeSha256": sha256_tree(source_dir)}

    manifest = _build_manifest(release_prefix=release_prefix, arch=arch, components=components)
    manifest_hash = stable_manifest_hash(manifest)
    version = fixed_version or runtime_version(
        release_prefix=release_prefix, manifest_hash=manifest_hash
    )
    archive_path, sha256_path, manifest_path = _artifact_paths(
        output_dir=output_dir, artifact_arch=arch.artifact_arch, version=version
    )

    if artifact_is_reusable(
        output_dir=output_dir,
        artifact_arch=arch.artifact_arch,
        metadata_arch=arch.metadata_arch,
        version=version,
        manifest_hash=manifest_hash,
    ):
        if env_file is not None:
            _write_env_file(env_file=env_file, output_dir=output_dir, version=version)
        return ReleaseResult(
            version=version,
            manifest_hash=manifest_hash,
            output_dir=output_dir,
            archive_path=archive_path,
            sha256_path=sha256_path,
            manifest_path=manifest_path,
            reused=True,
        )

    if source_dir is None:
        assert component_inputs is not None
        source_dir = _prepare_runtime_source(
            build_dir=build_dir, cache_dir=cache_dir, arch=arch, component_inputs=component_inputs
        )

    staging_dir = build_dir / f"runtime-{version}"
    _copy_source_with_metadata(
        source_dir=source_dir,
        staging_dir=staging_dir,
        version=version,
        arch=arch,
        manifest_hash=manifest_hash,
        components=components,
    )
    _write_archive(source_dir=staging_dir, archive_path=archive_path)
    digest = sha256_file(archive_path)
    sha256_path.write_text(f"{digest}  {archive_path.name}\n", encoding="utf-8")
    manifest_with_hash = {**manifest, "manifestHash": manifest_hash, "version": version}
    manifest_path.write_text(
        json.dumps(manifest_with_hash, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if not artifact_is_reusable(
        output_dir=output_dir,
        artifact_arch=arch.artifact_arch,
        metadata_arch=arch.metadata_arch,
        version=version,
        manifest_hash=manifest_hash,
    ):
        raise RuntimeError("runtime artifact validation failed after packaging")
    if env_file is not None:
        _write_env_file(env_file=env_file, output_dir=output_dir, version=version)
    return ReleaseResult(
        version=version,
        manifest_hash=manifest_hash,
        output_dir=output_dir,
        archive_path=archive_path,
        sha256_path=sha256_path,
        manifest_path=manifest_path,
        reused=False,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a SurgePilot Load Node runtime artifact.")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--build-dir", required=True, type=Path)
    parser.add_argument("--cache-dir", required=True, type=Path)
    parser.add_argument("--release-prefix", default=os.environ.get("RUNTIME_RELEASE_PREFIX", ""))
    parser.add_argument("--fixed-version")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--source-dir", type=Path, help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = release_runtime(
            output_dir=args.output_dir,
            build_dir=args.build_dir,
            cache_dir=args.cache_dir,
            release_prefix=args.release_prefix,
            fixed_version=args.fixed_version,
            source_dir=args.source_dir,
            env_file=args.env_file,
        )
    except Exception as exc:  # noqa: BLE001 - CLI prints actionable failure and exits non-zero.
        print(f"Runtime release failed: {exc}")
        return 1
    action = "reused" if result.reused else "built"
    print(
        f"Runtime artifact {action}: version={result.version} "
        f"archive={result.archive_path} sha256={result.sha256_path} manifest={result.manifest_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
