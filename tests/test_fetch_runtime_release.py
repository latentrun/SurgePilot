from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import fetch_runtime_release, release_runtime_artifact  # noqa: E402


VERSION = "v0.3.0"
PLUGIN_FIXTURES = (
    (
        "jpgc-casutg",
        "jmeter-plugins-casutg-2.10.jar",
        ("com/blazemeter/jmeter/threads/concurrency/ConcurrencyThreadGroup.class",),
    ),
    (
        "jpgc-json",
        "jmeter-plugins-json-2.7.jar",
        (
            "com/atlantbh/jmeter/plugins/jsonutils/jsonpathextractor/JSONPathExtractor.class",
            "com/atlantbh/jmeter/plugins/jsonutils/jsonpathassertion/JSONPathAssertion.class",
        ),
    ),
    (
        "jpgc-tst",
        "jmeter-plugins-tst-2.6.jar",
        ("kg/apc/jmeter/timers/VariableThroughputTimer.class",),
    ),
    (
        "bzm-random-csv",
        "jmeter-plugins-random-csv-data-set-0.8.jar",
        ("com/blazemeter/jmeter/RandomCSVDataSetConfig.class",),
    ),
    (
        "jmeter-plugin-influxdb2-listener",
        "jmeter-plugins-influxdb2-listener-2.8.jar",
        (
            "io/github/mderevyankoaqa/influxdb2/visualizer/"
            "InfluxDatabaseBackendListenerClient.class",
        ),
    ),
)
EXPECTED_PLUGINS = [plugin[0] for plugin in PLUGIN_FIXTURES]


def runtime_manifest_input_hash(manifest: dict[str, object]) -> str:
    inputs = {
        key: value for key, value in manifest.items() if key not in {"manifestHash", "version"}
    }
    payload = json.dumps(inputs, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )
    return hashlib.sha256(payload).hexdigest()[:12]


def test_runtime_manifest_hash_matches_builder_contract() -> None:
    manifest = {
        "schemaVersion": 1,
        "version": VERSION,
        "manifestHash": "0" * 12,
        "target": {"platform": "linux", "artifactArch": "linux-amd64"},
        "components": {"taurus": {"version": "1.16.50"}},
    }

    assert fetch_runtime_release._manifest_input_hash(
        manifest
    ) == release_runtime_artifact.manifest_input_hash(manifest)


def write_runtime_assets(
    directory: Path,
    *,
    arch: str = "amd64",
    version: str = VERSION,
    omitted_plugin_jar: str | None = None,
    invalid_plugin_jar: str | None = None,
    omitted_plugin_class: str | None = None,
) -> dict[str, object]:
    artifact_arch = f"linux-{arch}"
    archive_name = f"surgepilot-runtime-{artifact_arch}-{version}.tar.gz"
    archive = directory / archive_name
    runtime_manifest_data: dict[str, object] = {
        "schemaVersion": 1,
        "version": version,
        "target": {
            "platform": "linux",
            "artifactArch": artifact_arch,
            "metadataArch": arch,
        },
        "components": {
            "taurus": {"version": "1.16.50"},
            "jmeter": {"version": "5.6.3"},
            "plugins": [{"name": name} for name in EXPECTED_PLUGINS],
        },
        "recipeFiles": [{"path": "scripts/release_runtime_artifact.py", "sha256": "1" * 64}],
    }
    manifest_hash = runtime_manifest_input_hash(runtime_manifest_data)
    runtime_manifest_data["manifestHash"] = manifest_hash
    metadata = {
        "name": "surgepilot-runtime",
        "version": version,
        "platform": "linux",
        "arch": arch,
        "python": "3.12.11",
        "taurus": "1.16.50",
        "jmeter": "5.6.3",
        "plugins": EXPECTED_PLUGINS,
        "builder": {"arch": arch, "manifestHash": manifest_hash},
    }
    with tarfile.open(archive, "w:gz") as tar:
        payload = json.dumps(metadata).encode("utf-8")
        info = tarfile.TarInfo("metadata.json")
        info.size = len(payload)
        tar.addfile(info, io.BytesIO(payload))
        for plugin_name, filename, classes in PLUGIN_FIXTURES:
            if plugin_name == omitted_plugin_jar:
                continue
            if plugin_name == invalid_plugin_jar:
                jar_payload = b"not-a-zip"
            else:
                jar_bytes = io.BytesIO()
                with zipfile.ZipFile(jar_bytes, "w") as jar:
                    if plugin_name != omitted_plugin_class:
                        for class_name in classes:
                            jar.writestr(class_name, b"class")
                jar_payload = jar_bytes.getvalue()
            jar_info = tarfile.TarInfo(f"apache-jmeter-5.6.3/lib/ext/{filename}")
            jar_info.size = len(jar_payload)
            tar.addfile(jar_info, io.BytesIO(jar_payload))
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    sidecar = directory / f"{archive_name}.sha256"
    sidecar.write_text(f"{digest}  {archive_name}\n", encoding="utf-8")
    runtime_manifest = directory / f"surgepilot-runtime-{artifact_arch}-{version}.manifest.json"
    runtime_manifest.write_text(json.dumps(runtime_manifest_data), encoding="utf-8")
    return {
        "archive": archive_name,
        "sha256Sidecar": sidecar.name,
        "manifest": runtime_manifest.name,
        "sha256": digest,
    }


def write_release_manifest(
    root: Path, entries: dict[str, dict[str, object]], *, version: str = VERSION
) -> None:
    (root / "release-manifest.json").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "version": version,
                "minimumUpgradeVersion": version,
                "revision": "a" * 40,
                "images": {
                    "api": {
                        "repository": "ghcr.io/latentrun/surgepilot-api",
                        "digest": f"sha256:{'1' * 64}",
                    },
                    "web": {
                        "repository": "ghcr.io/latentrun/surgepilot-web",
                        "digest": f"sha256:{'2' * 64}",
                    },
                    "demoNode": {
                        "repository": "ghcr.io/latentrun/surgepilot-demo-node",
                        "digest": f"sha256:{'3' * 64}",
                    },
                },
                "runtimes": entries,
            }
        ),
        encoding="utf-8",
    )


def test_runtime_asset_names_are_exact() -> None:
    assert fetch_runtime_release.runtime_asset_names("amd64", VERSION) == (
        "surgepilot-runtime-linux-amd64-v0.3.0.tar.gz",
        "surgepilot-runtime-linux-amd64-v0.3.0.tar.gz.sha256",
        "surgepilot-runtime-linux-amd64-v0.3.0.manifest.json",
    )
    with pytest.raises(fetch_runtime_release.RuntimeFetchError, match="unsupported"):
        fetch_runtime_release.runtime_asset_names("riscv64", VERSION)


def test_runtime_validation_rejects_missing_required_plugin_jar(tmp_path: Path) -> None:
    entry = write_runtime_assets(tmp_path, omitted_plugin_jar="jpgc-tst")

    with pytest.raises(fetch_runtime_release.RuntimeFetchError, match="jpgc-tst"):
        fetch_runtime_release.validate_runtime_files(
            directory=tmp_path,
            version=VERSION,
            arch="amd64",
            release_entry=entry,
        )


def test_runtime_validation_rejects_invalid_plugin_jar(tmp_path: Path) -> None:
    entry = write_runtime_assets(tmp_path, invalid_plugin_jar="jpgc-json")

    with pytest.raises(fetch_runtime_release.RuntimeFetchError, match="jpgc-json"):
        fetch_runtime_release.validate_runtime_files(
            directory=tmp_path,
            version=VERSION,
            arch="amd64",
            release_entry=entry,
        )


def test_runtime_validation_rejects_missing_plugin_class(tmp_path: Path) -> None:
    entry = write_runtime_assets(tmp_path, omitted_plugin_class="bzm-random-csv")

    with pytest.raises(fetch_runtime_release.RuntimeFetchError, match="bzm-random-csv"):
        fetch_runtime_release.validate_runtime_files(
            directory=tmp_path,
            version=VERSION,
            arch="amd64",
            release_entry=entry,
        )


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/latentrun/SurgePilot/releases/download/v0.3.0/file",
        "https://release-assets.githubusercontent.com/github-production-release-asset/file",
        "https://objects.githubusercontent.com/github-production-release-asset/file",
    ],
)
def test_official_github_origins_are_allowed(url: str) -> None:
    fetch_runtime_release.validate_download_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/latentrun/SurgePilot/file",
        "https://github.example.com/file",
        "https://evil.example/file",
        "https://github.com.evil.example/file",
    ],
)
def test_non_official_redirect_origins_are_rejected(url: str) -> None:
    with pytest.raises(fetch_runtime_release.RuntimeFetchError):
        fetch_runtime_release.validate_download_url(url)


def test_validate_runtime_files_accepts_matching_release_contract(tmp_path: Path) -> None:
    entry = write_runtime_assets(tmp_path)

    result = fetch_runtime_release.validate_runtime_files(
        directory=tmp_path,
        version=VERSION,
        arch="amd64",
        release_entry=entry,
    )

    assert result.archive.name == entry["archive"]
    assert result.sha256 == entry["sha256"]


def test_validate_runtime_files_rejects_manifest_inputs_changed_without_rehash(
    tmp_path: Path,
) -> None:
    entry = write_runtime_assets(tmp_path)
    manifest_path = tmp_path / str(entry["manifest"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["recipeFiles"][0]["sha256"] = "2" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(fetch_runtime_release.RuntimeFetchError, match="manifest hash"):
        fetch_runtime_release.validate_runtime_files(
            directory=tmp_path,
            version=VERSION,
            arch="amd64",
            release_entry=entry,
        )


def test_validate_runtime_files_rejects_release_digest_or_metadata_mismatch(tmp_path: Path) -> None:
    entry = write_runtime_assets(tmp_path)
    bad_entry = {**entry, "sha256": "0" * 64}
    with pytest.raises(fetch_runtime_release.RuntimeFetchError, match="release manifest digest"):
        fetch_runtime_release.validate_runtime_files(
            directory=tmp_path,
            version=VERSION,
            arch="amd64",
            release_entry=bad_entry,
        )

    entry = write_runtime_assets(tmp_path)
    archive = tmp_path / str(entry["archive"])
    with tarfile.open(archive, "w:gz") as tar:
        payload = json.dumps(
            {
                "name": "surgepilot-runtime",
                "version": VERSION,
                "platform": "darwin",
                "arch": "amd64",
                "taurus": "1.16.50",
                "jmeter": "5.6.3",
                "plugins": EXPECTED_PLUGINS,
                "builder": {"manifestHash": "a" * 12},
            }
        ).encode()
        info = tarfile.TarInfo("metadata.json")
        info.size = len(payload)
        tar.addfile(info, io.BytesIO(payload))
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (tmp_path / str(entry["sha256Sidecar"])).write_text(
        f"{digest}  {entry['archive']}\n", encoding="utf-8"
    )
    entry["sha256"] = digest

    with pytest.raises(fetch_runtime_release.RuntimeFetchError, match="platform"):
        fetch_runtime_release.validate_runtime_files(
            directory=tmp_path,
            version=VERSION,
            arch="amd64",
            release_entry=entry,
        )


def test_publish_runtime_files_is_atomic_and_writes_env_after_validation(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    staging.mkdir()
    entry = write_runtime_assets(staging)
    target = tmp_path / "target"
    env_file = target / "runtime.env"

    fetch_runtime_release.publish_runtime_files(
        staging_directory=staging,
        target_directory=target,
        version=VERSION,
        architectures=("amd64",),
        release_entries={"amd64": entry},
        env_file=env_file,
        env_host_directory=target,
    )

    assert (target / str(entry["archive"])).is_file()
    assert env_file.read_text(encoding="utf-8") == (
        f"LOAD_NODE_RUNTIME_VERSION={VERSION}\nLOAD_NODE_RUNTIME_ARTIFACT_HOST_DIR={target}\n"
    )


def test_fetch_release_runtimes_reuses_valid_files_without_downloading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "target"
    target.mkdir()
    amd64 = write_runtime_assets(target, arch="amd64")
    arm64 = write_runtime_assets(target, arch="arm64")
    write_release_manifest(tmp_path, {"amd64": amd64, "arm64": arm64})
    monkeypatch.setattr(
        fetch_runtime_release,
        "download_file",
        lambda *_args, **_kwargs: pytest.fail("valid dual Runtime should be reused"),
    )

    fetch_runtime_release.fetch_release_runtimes(
        root=tmp_path,
        version=VERSION,
        architectures=("amd64", "arm64"),
        target_directory=target,
        env_host_directory=target,
    )

    assert (target / str(amd64["archive"])).is_file()
    assert (target / str(arm64["archive"])).is_file()
    assert (target / "runtime.env").is_file()


def test_fetch_release_runtimes_downloads_validates_and_publishes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    amd64 = write_runtime_assets(source, arch="amd64")
    arm64 = write_runtime_assets(source, arch="arm64")
    write_release_manifest(tmp_path, {"amd64": amd64, "arm64": arm64})
    downloads: list[str] = []

    def copy_download(url: str, target: Path) -> None:
        downloads.append(url)
        target.write_bytes((source / target.name).read_bytes())

    monkeypatch.setattr(fetch_runtime_release, "download_file", copy_download)
    target = tmp_path / "target"

    fetch_runtime_release.fetch_release_runtimes(
        root=tmp_path,
        version=VERSION,
        architectures=("amd64", "arm64"),
        target_directory=target,
        env_host_directory=target,
    )

    assert len(downloads) == 6
    assert (target / str(amd64["archive"])).is_file()
    assert (target / str(arm64["archive"])).is_file()


@pytest.mark.parametrize("local_state", ["missing", "corrupt"])
def test_reserved_validation_runtime_requires_valid_local_assets_without_downloading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, local_state: str
) -> None:
    version = "v0.0.0"
    source = tmp_path / "source"
    source.mkdir()
    entry = write_runtime_assets(source, arch="amd64", version=version)
    arm64 = write_runtime_assets(source, arch="arm64", version=version)
    write_release_manifest(tmp_path, {"amd64": entry, "arm64": arm64}, version=version)
    target = tmp_path / "target"
    if local_state == "corrupt":
        target.mkdir()
        for name in (entry["archive"], entry["sha256Sidecar"], entry["manifest"]):
            source_path = source / str(name)
            (target / str(name)).write_bytes(source_path.read_bytes())
        (target / str(entry["sha256Sidecar"])).write_text(
            f"{'0' * 64}  {entry['archive']}\n", encoding="utf-8"
        )
    monkeypatch.setattr(
        fetch_runtime_release,
        "download_file",
        lambda *_args, **_kwargs: pytest.fail("reserved validation Runtime must not download"),
    )

    with pytest.raises(fetch_runtime_release.RuntimeFetchError, match="pre-positioned"):
        fetch_runtime_release.fetch_release_runtimes(
            root=tmp_path,
            version=version,
            architectures=("amd64",),
            target_directory=target,
            env_host_directory=target,
        )


def test_main_supports_no_runtime_assets_for_disabled_demo_auto(tmp_path: Path, capsys) -> None:
    source = tmp_path / "source"
    source.mkdir()
    amd64 = write_runtime_assets(source, arch="amd64")
    arm64 = write_runtime_assets(source, arch="arm64")
    write_release_manifest(tmp_path, {"amd64": amd64, "arm64": arm64})
    target = tmp_path / "target"

    result = fetch_runtime_release.main(
        [
            "--root",
            str(tmp_path),
            "--version",
            VERSION,
            "--architectures",
            "",
            "--target-directory",
            str(target),
            "--env-host-directory",
            str(target),
        ]
    )

    assert result == 0
    assert "none requested" in capsys.readouterr().out
    assert (target / "runtime.env").is_file()


def test_download_file_rejects_empty_response_and_removes_partial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def geturl(self) -> str:
            return "https://objects.githubusercontent.com/file"

        def read(self, _size: int = -1) -> bytes:
            return b""

    class Opener:
        def open(self, _url: str, timeout: int):
            assert timeout == 60
            return Response()

    monkeypatch.setattr(fetch_runtime_release.urllib.request, "build_opener", lambda *_: Opener())
    target = tmp_path / "asset"

    with pytest.raises(fetch_runtime_release.RuntimeFetchError, match="empty"):
        fetch_runtime_release.download_file(
            "https://github.com/latentrun/SurgePilot/releases/download/v0.3.0/asset",
            target,
        )

    assert not target.exists()
    assert not list(tmp_path.glob(".download-*"))


def test_download_file_writes_successful_response_and_reports_network_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Response:
        def __init__(self) -> None:
            self.remaining = b"runtime-bytes"

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def geturl(self) -> str:
            return "https://release-assets.githubusercontent.com/file"

        def read(self, _size: int = -1) -> bytes:
            data, self.remaining = self.remaining, b""
            return data

    class Opener:
        def open(self, _url: str, timeout: int):
            assert timeout == 60
            return Response()

    monkeypatch.setattr(fetch_runtime_release.urllib.request, "build_opener", lambda *_: Opener())
    target = tmp_path / "asset"
    fetch_runtime_release.download_file(
        "https://github.com/latentrun/SurgePilot/releases/download/v0.3.0/asset",
        target,
    )
    assert target.read_bytes() == b"runtime-bytes"

    class FailingOpener:
        def open(self, _url: str, timeout: int):
            raise OSError("network down")

    monkeypatch.setattr(
        fetch_runtime_release.urllib.request, "build_opener", lambda *_: FailingOpener()
    )
    with pytest.raises(fetch_runtime_release.RuntimeFetchError, match="network down"):
        fetch_runtime_release.download_file(
            "https://github.com/latentrun/SurgePilot/releases/download/v0.3.0/asset-2",
            tmp_path / "asset-2",
        )


def test_runtime_validation_rejects_missing_assets_and_bad_sidecar(tmp_path: Path) -> None:
    entry = write_runtime_assets(tmp_path)
    (tmp_path / str(entry["manifest"])).unlink()
    with pytest.raises(fetch_runtime_release.RuntimeFetchError, match="missing or unsafe"):
        fetch_runtime_release.validate_runtime_files(
            directory=tmp_path,
            version=VERSION,
            arch="amd64",
            release_entry=entry,
        )


def test_runtime_validation_rejects_plugin_manifest_and_version_mismatches(tmp_path: Path) -> None:
    entry = write_runtime_assets(tmp_path)
    archive = tmp_path / str(entry["archive"])
    with tarfile.open(archive, "w:gz") as tar:
        payload = json.dumps(
            {
                "name": "surgepilot-runtime",
                "version": VERSION,
                "platform": "linux",
                "arch": "amd64",
                "taurus": "1.16.50",
                "jmeter": "5.6.3",
                "plugins": ["jpgc-casutg"],
                "builder": {"manifestHash": "a" * 12},
            }
        ).encode()
        info = tarfile.TarInfo("metadata.json")
        info.size = len(payload)
        tar.addfile(info, io.BytesIO(payload))
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (tmp_path / str(entry["sha256Sidecar"])).write_text(
        f"{digest}  {entry['archive']}\n", encoding="utf-8"
    )
    entry["sha256"] = digest
    with pytest.raises(fetch_runtime_release.RuntimeFetchError, match="plugins"):
        fetch_runtime_release.validate_runtime_files(
            directory=tmp_path,
            version=VERSION,
            arch="amd64",
            release_entry=entry,
        )

    entry = write_runtime_assets(tmp_path)
    manifest_path = tmp_path / str(entry["manifest"])
    runtime_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    runtime_manifest["version"] = "v0.3.1"
    manifest_path.write_text(json.dumps(runtime_manifest), encoding="utf-8")
    with pytest.raises(fetch_runtime_release.RuntimeFetchError, match="manifest version"):
        fetch_runtime_release.validate_runtime_files(
            directory=tmp_path,
            version=VERSION,
            arch="amd64",
            release_entry=entry,
        )

    entry = write_runtime_assets(tmp_path)
    manifest_path = tmp_path / str(entry["manifest"])
    runtime_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    runtime_manifest["components"]["jmeter"]["version"] = "5.5"
    runtime_manifest["manifestHash"] = runtime_manifest_input_hash(runtime_manifest)
    manifest_path.write_text(json.dumps(runtime_manifest), encoding="utf-8")
    with pytest.raises(fetch_runtime_release.RuntimeFetchError, match="component contract"):
        fetch_runtime_release.validate_runtime_files(
            directory=tmp_path,
            version=VERSION,
            arch="amd64",
            release_entry=entry,
        )


def test_fetch_main_reports_manifest_error(tmp_path: Path, capsys) -> None:
    result = fetch_runtime_release.main(
        [
            "--root",
            str(tmp_path),
            "--version",
            VERSION,
            "--architectures",
            "amd64",
            "--target-directory",
            str(tmp_path / "target"),
            "--env-host-directory",
            str(tmp_path / "target"),
        ]
    )
    assert result == 1
    assert "Runtime fetch failed" in capsys.readouterr().out

    entry = write_runtime_assets(tmp_path)
    (tmp_path / str(entry["sha256Sidecar"])).write_text("invalid\n", encoding="utf-8")
    with pytest.raises(fetch_runtime_release.RuntimeFetchError, match="sidecar"):
        fetch_runtime_release.validate_runtime_files(
            directory=tmp_path,
            version=VERSION,
            arch="amd64",
            release_entry=entry,
        )
