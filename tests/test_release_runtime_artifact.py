from __future__ import annotations

import hashlib
import http.client
import importlib.util
import io
import json
import subprocess
import sys
import tarfile
import time
import urllib.error
import zipfile
from pathlib import Path
from types import ModuleType

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "release_runtime_artifact.py"


def load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("release_runtime_artifact", MODULE_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


EXPECTED_RUNTIME_PLUGINS = [
    "jpgc-casutg",
    "jpgc-json",
    "jpgc-tst",
    "bzm-random-csv",
    "jmeter-plugin-influxdb2-listener",
]
PLUGIN_ARCHIVE_FIXTURES = (
    (
        "jmeter-plugins-casutg-2.10.jar",
        ("com/blazemeter/jmeter/threads/concurrency/ConcurrencyThreadGroup.class",),
    ),
    (
        "jmeter-plugins-json-2.7.jar",
        (
            "com/atlantbh/jmeter/plugins/jsonutils/jsonpathextractor/JSONPathExtractor.class",
            "com/atlantbh/jmeter/plugins/jsonutils/jsonpathassertion/JSONPathAssertion.class",
        ),
    ),
    (
        "jmeter-plugins-tst-2.6.jar",
        ("kg/apc/jmeter/timers/VariableThroughputTimer.class",),
    ),
    (
        "jmeter-plugins-random-csv-data-set-0.8.jar",
        ("com/blazemeter/jmeter/RandomCSVDataSetConfig.class",),
    ),
    (
        "jmeter-plugins-influxdb2-listener-2.8.jar",
        (
            "io/github/mderevyankoaqa/influxdb2/visualizer/"
            "InfluxDatabaseBackendListenerClient.class",
        ),
    ),
)


def write_archive(
    output_dir: Path,
    *,
    version: str,
    metadata_arch: str = "amd64",
    artifact_arch: str | None = None,
) -> Path:
    resolved_artifact_arch = (
        artifact_arch
        or {
            "amd64": "linux-amd64",
            "arm64": "linux-arm64",
        }[metadata_arch]
    )
    runtime = output_dir / "runtime"
    (runtime / "bin").mkdir(parents=True)
    (runtime / "python" / "bin").mkdir(parents=True)
    (runtime / "python" / "lib" / "surgepilot_runner").mkdir(parents=True)
    (runtime / "apache-jmeter-5.6.3" / "bin").mkdir(parents=True)
    (runtime / "apache-jmeter-5.6.3" / "lib" / "ext").mkdir(parents=True)
    (runtime / "metadata.json").write_text(
        json.dumps(
            {
                "name": "surgepilot-runtime",
                "version": version,
                "platform": "linux",
                "arch": metadata_arch,
                "python": "3.12.11",
                "taurus": "1.16.50",
                "jmeter": "5.6.3",
                "plugins": EXPECTED_RUNTIME_PLUGINS,
                "builder": {"os": "test", "arch": metadata_arch},
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (runtime / "bin" / "bzt").write_text("#!/bin/sh\n", encoding="utf-8")
    (runtime / "apache-jmeter-5.6.3" / "bin" / "surgepilot-jmeter-wrapper").write_text(
        "#!/bin/sh\n", encoding="utf-8"
    )
    (runtime / "python" / "bin" / "python3").write_text("python", encoding="utf-8")
    (runtime / "python" / "lib" / "surgepilot_runner" / "jmeter_wrapper.py").write_text(
        "InfluxDatabaseBackendListenerClient = True\n",
        encoding="utf-8",
    )
    plugin_dir = runtime / "apache-jmeter-5.6.3" / "lib" / "ext"
    for filename, classes in PLUGIN_ARCHIVE_FIXTURES:
        with zipfile.ZipFile(plugin_dir / filename, "w") as jar:
            for class_name in classes:
                jar.writestr(class_name, b"class")
    archive = output_dir / f"surgepilot-runtime-{resolved_artifact_arch}-{version}.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for name in ("metadata.json", "bin", "python", "apache-jmeter-5.6.3"):
            tar.add(runtime / name, arcname=name)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_name(f"{archive.name}.sha256").write_text(
        f"{digest}  {archive.name}\n", encoding="utf-8"
    )
    return archive


def component_fixture(*, python_version: str = "3.12.11", jmeter_sha256: str = "a") -> dict:
    return {
        "pythonBuildStandalone": {"version": python_version, "provider": "uv-managed-python"},
        "taurus": {
            "version": "1.16.50",
            "pythonDependencies": ["bzt==1.16.50", "urllib3==2.7.0"],
        },
        "jmeter": {
            "version": "5.6.3",
            "url": "https://example.invalid/jmeter.tgz",
            "sha256": jmeter_sha256 * 64,
        },
        "plugins": [
            {
                "name": "jpgc-casutg",
                "version": "2.10",
                "url": "https://example.invalid/casutg.jar",
                "sha256": "b" * 64,
            },
            {
                "name": "jpgc-json",
                "version": "2.7",
                "url": "https://example.invalid/json.jar",
                "sha256": "c" * 64,
            },
            {
                "name": "jpgc-tst",
                "version": "2.6",
                "url": "https://example.invalid/tst.jar",
                "sha256": "d" * 64,
            },
            {
                "name": "bzm-random-csv",
                "version": "0.8",
                "url": "https://example.invalid/random-csv.jar",
                "sha256": "e" * 64,
            },
            {
                "name": "jmeter-plugin-influxdb2-listener",
                "version": "2.8",
                "url": "https://example.invalid/influx.jar",
                "sha256": "f" * 64,
            },
        ],
    }


def component_inputs(tmp_path: Path, *, python_version: str = "3.12.11") -> dict:
    return {
        "python_version": python_version,
        "jmeter_archive": tmp_path / "unused-jmeter.tgz",
        "plugin_downloads": {
            plugin_name: tmp_path / filename
            for plugin_name, (filename, _classes) in zip(
                EXPECTED_RUNTIME_PLUGINS, PLUGIN_ARCHIVE_FIXTURES, strict=True
            )
        },
        "taurus_dependencies": ["bzt==1.16.50", "urllib3==2.7.0"],
    }


def extract_metadata(archive: Path) -> dict:
    with tarfile.open(archive, "r:gz") as tar:
        member = tar.extractfile("metadata.json")
        assert member is not None
        return json.loads(member.read().decode("utf-8"))


def test_stable_manifest_hash_is_sorted_and_drives_version() -> None:
    module = load_module()

    left = {"b": 2, "a": {"d": 4, "c": 3}}
    right = {"a": {"c": 3, "d": 4}, "b": 2}

    digest = module.stable_manifest_hash(left)

    assert digest == module.stable_manifest_hash(right)
    assert len(digest) == 12
    assert module.runtime_version(release_prefix="", manifest_hash=digest) == f"dev-{digest}"
    assert (
        module.runtime_version(release_prefix="release-test", manifest_hash=digest)
        == f"release-test-{digest}"
    )


@pytest.mark.parametrize(
    ("machine", "artifact_arch", "metadata_arch"),
    [
        ("x86_64", "linux-amd64", "amd64"),
        ("amd64", "linux-amd64", "amd64"),
        ("aarch64", "linux-arm64", "arm64"),
        ("arm64", "linux-arm64", "arm64"),
    ],
)
def test_normalize_arch_supports_release_host_variants(
    machine: str, artifact_arch: str, metadata_arch: str
) -> None:
    module = load_module()

    arch = module.normalize_arch(machine)

    assert arch.artifact_arch == artifact_arch
    assert arch.metadata_arch == metadata_arch


def test_runtime_component_selection_is_exactly_the_generated_jmx_plugin_closure() -> None:
    module = load_module()

    selection = module._current_component_selection()

    assert module.REQUIRED_PLUGINS == EXPECTED_RUNTIME_PLUGINS
    assert [plugin["name"] for plugin in selection["plugins"]] == EXPECTED_RUNTIME_PLUGINS
    assert [plugin["version"] for plugin in selection["plugins"]] == [
        "2.10",
        "2.7",
        "2.6",
        "0.8",
        "2.8",
    ]


def test_runtime_plugin_contract_preserves_casutg_filename_and_key_classes() -> None:
    module = load_module()

    plugins = {plugin.name: plugin for plugin in module.RUNTIME_PLUGINS}

    assert plugins["jpgc-casutg"].artifact_filename("2.10") == ("jmeter-plugins-casutg-2.10.jar")
    assert plugins["jpgc-json"].required_classes == (
        "com/atlantbh/jmeter/plugins/jsonutils/jsonpathextractor/JSONPathExtractor.class",
        "com/atlantbh/jmeter/plugins/jsonutils/jsonpathassertion/JSONPathAssertion.class",
    )
    assert plugins["jpgc-tst"].required_classes == (
        "kg/apc/jmeter/timers/VariableThroughputTimer.class",
    )
    assert plugins["bzm-random-csv"].required_classes == (
        "com/blazemeter/jmeter/RandomCSVDataSetConfig.class",
    )


def test_runtime_builder_dockerfile_change_invalidates_recipe_hash(
    tmp_path: Path, monkeypatch
) -> None:
    module = load_module()
    runner_wrapper = tmp_path / "apps/runner/surgepilot_runner/jmeter_wrapper.py"
    runner_project = tmp_path / "apps/runner/pyproject.toml"
    builder_dockerfile = tmp_path / "infra/docker/runtime-builder/Dockerfile"
    recipe_script = tmp_path / "scripts/release_runtime_artifact.py"
    for path, text in (
        (recipe_script, "# recipe-v1\n"),
        (runner_wrapper, "wrapper-v1\n"),
        (runner_project, "[project]\nname = 'runner'\n"),
        (builder_dockerfile, "FROM python:3.12-slim-bookworm\n"),
        (tmp_path / "uv.lock", "version = 1\n"),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "RUNNER_WRAPPER", runner_wrapper)
    monkeypatch.setattr(module, "__file__", str(recipe_script))
    arch = module.normalize_arch()
    components = component_fixture()
    first = module.stable_manifest_hash(
        module._build_manifest(release_prefix="", arch=arch, components=components)
    )

    builder_dockerfile.write_text(
        "FROM python:3.12-slim-bookworm\nRUN echo changed\n", encoding="utf-8"
    )
    second = module.stable_manifest_hash(
        module._build_manifest(release_prefix="", arch=arch, components=components)
    )

    assert first != second
    recipe_paths = {
        item["path"]
        for item in module._build_manifest(release_prefix="", arch=arch, components=components)[
            "recipeFiles"
        ]
    }
    assert "infra/docker/runtime-builder/Dockerfile" in recipe_paths


def test_fixed_version_release_uses_explicit_version_without_changing_manifest_hash(
    tmp_path: Path,
) -> None:
    module = load_module()
    arch = module.normalize_arch()
    source = tmp_path / "source-runtime"
    write_archive(tmp_path, version="template", metadata_arch=arch.metadata_arch)
    with tarfile.open(
        tmp_path / f"surgepilot-runtime-{arch.artifact_arch}-template.tar.gz", "r:gz"
    ) as tar:
        tar.extractall(source, filter="data")

    env_file = tmp_path / "runtime.env"
    result = module.release_runtime(
        output_dir=tmp_path / "out",
        build_dir=tmp_path / "build",
        cache_dir=tmp_path / "cache",
        release_prefix="ignored-by-fixed-version",
        fixed_version="p0-e2e",
        source_dir=source,
        env_file=env_file,
    )

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    metadata = extract_metadata(result.archive_path)

    assert result.version == "p0-e2e"
    assert result.archive_path.name == f"surgepilot-runtime-{arch.artifact_arch}-p0-e2e.tar.gz"
    assert metadata["version"] == "p0-e2e"
    assert manifest["version"] == "p0-e2e"
    assert manifest["manifestHash"] == result.manifest_hash
    assert module.manifest_input_hash(manifest) == result.manifest_hash
    assert "LOAD_NODE_RUNTIME_VERSION=p0-e2e\n" in env_file.read_text(encoding="utf-8")


def test_fixed_version_reuse_still_requires_current_manifest_inputs(
    tmp_path: Path, monkeypatch
) -> None:
    module = load_module()
    arch = module.normalize_arch()
    old_components = component_fixture(python_version="3.12.11")
    old_manifest = module._build_manifest(release_prefix="", arch=arch, components=old_components)
    old_hash = module.stable_manifest_hash(old_manifest)
    fixed_version = "p0-e2e"
    write_archive(tmp_path, version=fixed_version, metadata_arch=arch.metadata_arch)
    (
        tmp_path / f"surgepilot-runtime-{arch.artifact_arch}-{fixed_version}.manifest.json"
    ).write_text(
        json.dumps(
            {**old_manifest, "manifestHash": old_hash, "version": fixed_version},
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    old_archive_digest = hashlib.sha256(
        (tmp_path / f"surgepilot-runtime-{arch.artifact_arch}-{fixed_version}.tar.gz").read_bytes()
    ).hexdigest()

    new_components = component_fixture(python_version="3.12.12")
    source = tmp_path / "source-runtime"
    template_dir = tmp_path / "template-fixed"
    template_dir.mkdir()
    write_archive(template_dir, version="template", metadata_arch=arch.metadata_arch)
    with tarfile.open(
        template_dir / f"surgepilot-runtime-{arch.artifact_arch}-template.tar.gz", "r:gz"
    ) as tar:
        tar.extractall(source, filter="data")
    (source / "python" / "bin" / "python3").write_text("new-python", encoding="utf-8")

    calls: list[str] = []

    def current_component_inputs(**_kwargs):
        calls.append("component-inputs")
        return new_components, component_inputs(tmp_path, python_version="3.12.12")

    monkeypatch.setattr(module, "_runtime_component_inputs", current_component_inputs)
    monkeypatch.setattr(module, "_prepare_runtime_source", lambda **_kwargs: source)

    result = module.release_runtime(
        output_dir=tmp_path,
        build_dir=tmp_path / "build",
        cache_dir=tmp_path / "cache",
        fixed_version=fixed_version,
    )

    new_manifest = module._build_manifest(release_prefix="", arch=arch, components=new_components)
    new_hash = module.stable_manifest_hash(new_manifest)
    new_archive_digest = hashlib.sha256(result.archive_path.read_bytes()).hexdigest()

    assert calls == ["component-inputs"]
    assert result.version == fixed_version
    assert result.manifest_hash == new_hash
    assert result.reused is False
    assert new_archive_digest != old_archive_digest


def test_reuse_requires_manifest_metadata_arch_and_whole_archive_checksum(tmp_path: Path) -> None:
    module = load_module()
    arch = module.normalize_arch()
    manifest = module._build_manifest(
        release_prefix="",
        arch=arch,
        components={"sourceRuntimeTreeSha256": "a" * 64},
    )
    manifest_hash = module.stable_manifest_hash(manifest)
    version = module.runtime_version(release_prefix="", manifest_hash=manifest_hash)
    archive = write_archive(tmp_path, version=version, metadata_arch=arch.metadata_arch)
    (tmp_path / f"surgepilot-runtime-{arch.artifact_arch}-{version}.manifest.json").write_text(
        json.dumps({**manifest, "manifestHash": manifest_hash, "version": version}, sort_keys=True),
        encoding="utf-8",
    )

    assert module.artifact_is_reusable(
        output_dir=tmp_path,
        artifact_arch=arch.artifact_arch,
        metadata_arch=arch.metadata_arch,
        version=version,
        manifest_hash=manifest_hash,
    )

    archive.with_name(f"{archive.name}.sha256").write_text(
        "0" * 64 + f"  {archive.name}\n", encoding="utf-8"
    )
    assert not module.artifact_is_reusable(
        output_dir=tmp_path,
        artifact_arch=arch.artifact_arch,
        metadata_arch=arch.metadata_arch,
        version=version,
        manifest_hash=manifest_hash,
    )


def test_reuse_requires_manifest_version_to_match_artifact_version(tmp_path: Path) -> None:
    module = load_module()
    arch = module.normalize_arch()
    manifest = module._build_manifest(
        release_prefix="",
        arch=arch,
        components={"sourceRuntimeTreeSha256": "a" * 64},
    )
    manifest_hash = module.stable_manifest_hash(manifest)
    version = "p0-e2e"
    write_archive(tmp_path, version=version, metadata_arch=arch.metadata_arch)
    (tmp_path / f"surgepilot-runtime-{arch.artifact_arch}-{version}.manifest.json").write_text(
        json.dumps(
            {**manifest, "manifestHash": manifest_hash, "version": "stale-version"},
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    assert not module.artifact_is_reusable(
        output_dir=tmp_path,
        artifact_arch=arch.artifact_arch,
        metadata_arch=arch.metadata_arch,
        version=version,
        manifest_hash=manifest_hash,
    )


def test_release_runtime_writes_env_file_and_reuses_matching_artifact(tmp_path: Path) -> None:
    module = load_module()
    arch = module.normalize_arch()
    source = tmp_path / "source-runtime"
    (source / "metadata.json").parent.mkdir(parents=True)
    write_archive(tmp_path, version="template", metadata_arch=arch.metadata_arch)
    with tarfile.open(
        tmp_path / f"surgepilot-runtime-{arch.artifact_arch}-template.tar.gz", "r:gz"
    ) as tar:
        tar.extractall(source, filter="data")

    env_file = tmp_path / "runtime.env"
    result = module.release_runtime(
        output_dir=tmp_path / "out",
        build_dir=tmp_path / "build",
        cache_dir=tmp_path / "cache",
        release_prefix="test",
        source_dir=source,
        env_file=env_file,
    )
    second = module.release_runtime(
        output_dir=tmp_path / "out",
        build_dir=tmp_path / "build",
        cache_dir=tmp_path / "cache",
        release_prefix="test",
        source_dir=source,
        env_file=env_file,
    )

    assert result.version == second.version
    assert second.reused is True
    assert result.archive_path.is_file()
    assert result.sha256_path.is_file()
    assert result.manifest_path.is_file()
    env_text = env_file.read_text(encoding="utf-8")
    assert f"LOAD_NODE_RUNTIME_VERSION={result.version}\n" in env_text
    assert f"LOAD_NODE_RUNTIME_ARTIFACT_HOST_DIR={result.output_dir}\n" in env_text


def test_write_env_file_shell_quotes_runtime_artifact_dir(tmp_path: Path) -> None:
    module = load_module()
    env_file = tmp_path / "runtime.env"
    output_dir = tmp_path / "path with spaces;and-symbols"

    module._write_env_file(env_file=env_file, output_dir=output_dir, version="dev-test")
    result = subprocess.run(
        [
            "sh",
            "-c",
            f'. "{env_file}"; printf "%s\\n%s\\n" "$LOAD_NODE_RUNTIME_VERSION" "$LOAD_NODE_RUNTIME_ARTIFACT_HOST_DIR"',
        ],
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0
    assert result.stdout.splitlines() == ["dev-test", str(output_dir)]


def test_release_runtime_reuses_existing_artifact_after_current_component_checksums_match(
    tmp_path: Path, monkeypatch
) -> None:
    module = load_module()
    arch = module.normalize_arch()
    components = {
        "pythonBuildStandalone": {"version": "3.12.11", "provider": "uv-managed-python"},
        "taurus": {
            "version": "1.16.50",
            "pythonDependencies": ["bzt==1.16.50", "urllib3==2.7.0"],
        },
        "jmeter": {
            "version": "5.6.3",
            "url": "https://example.invalid/jmeter.tgz",
            "sha256": "a" * 64,
        },
        "plugins": [
            {
                "name": "jpgc-casutg",
                "version": "2.10",
                "url": "https://example.invalid/casutg.jar",
                "sha256": "b" * 64,
            },
            {
                "name": "jmeter-plugin-influxdb2-listener",
                "version": "2.8",
                "url": "https://example.invalid/influx.jar",
                "sha256": "c" * 64,
            },
        ],
    }
    manifest = module._build_manifest(release_prefix="test", arch=arch, components=components)
    manifest_hash = module.stable_manifest_hash(manifest)
    version = module.runtime_version(release_prefix="test", manifest_hash=manifest_hash)
    write_archive(tmp_path, version=version, metadata_arch=arch.metadata_arch)
    (tmp_path / f"surgepilot-runtime-{arch.artifact_arch}-{version}.manifest.json").write_text(
        json.dumps({**manifest, "manifestHash": manifest_hash, "version": version}, sort_keys=True),
        encoding="utf-8",
    )

    calls: list[str] = []

    def current_component_inputs(**_kwargs):
        calls.append("component-inputs")
        return components, {
            "python_version": "3.12.11",
            "jmeter_archive": tmp_path / "unused-jmeter.tgz",
            "casutg_download": tmp_path / "unused-casutg.jar",
            "influx_download": tmp_path / "unused-influx.jar",
            "casutg_version": "2.10",
            "influx_version": "2.8",
            "taurus_dependencies": ["bzt==1.16.50", "urllib3==2.7.0"],
        }

    monkeypatch.setenv("RUNTIME_JMETER_URL", "https://example.invalid/jmeter.tgz")
    monkeypatch.setenv("RUNTIME_CASUTG_URL", "https://example.invalid/casutg.jar")
    monkeypatch.setenv("RUNTIME_INFLUXDB2_LISTENER_URL", "https://example.invalid/influx.jar")
    monkeypatch.setattr(module, "_runtime_component_inputs", current_component_inputs)

    result = module.release_runtime(
        output_dir=tmp_path,
        build_dir=tmp_path / "build",
        cache_dir=tmp_path / "cache",
        release_prefix="test",
    )

    assert calls == ["component-inputs"]
    assert result.version == version
    assert result.reused is True


def test_release_runtime_refuses_reuse_when_same_url_component_checksum_changes(
    tmp_path: Path, monkeypatch
) -> None:
    module = load_module()
    arch = module.normalize_arch()
    old_components = {
        "pythonBuildStandalone": {"version": "3.12.11", "provider": "uv-managed-python"},
        "taurus": {
            "version": "1.16.50",
            "pythonDependencies": ["bzt==1.16.50", "urllib3==2.7.0"],
        },
        "jmeter": {
            "version": "5.6.3",
            "url": "https://example.invalid/jmeter.tgz",
            "sha256": "a" * 64,
        },
        "plugins": [
            {
                "name": "jpgc-casutg",
                "version": "2.10",
                "url": "https://example.invalid/casutg.jar",
                "sha256": "b" * 64,
            },
            {
                "name": "jmeter-plugin-influxdb2-listener",
                "version": "2.8",
                "url": "https://example.invalid/influx.jar",
                "sha256": "c" * 64,
            },
        ],
    }
    old_manifest = module._build_manifest(
        release_prefix="test", arch=arch, components=old_components
    )
    old_hash = module.stable_manifest_hash(old_manifest)
    old_version = module.runtime_version(release_prefix="test", manifest_hash=old_hash)
    write_archive(tmp_path, version=old_version, metadata_arch=arch.metadata_arch)
    (tmp_path / f"surgepilot-runtime-{arch.artifact_arch}-{old_version}.manifest.json").write_text(
        json.dumps({**old_manifest, "manifestHash": old_hash, "version": old_version}),
        encoding="utf-8",
    )

    new_components = {
        **old_components,
        "jmeter": {
            "version": "5.6.3",
            "url": "https://example.invalid/jmeter.tgz",
            "sha256": "d" * 64,
        },
    }
    monkeypatch.setenv("RUNTIME_JMETER_URL", "https://example.invalid/jmeter.tgz")
    monkeypatch.setenv("RUNTIME_CASUTG_URL", "https://example.invalid/casutg.jar")
    monkeypatch.setenv("RUNTIME_INFLUXDB2_LISTENER_URL", "https://example.invalid/influx.jar")
    monkeypatch.setattr(
        module,
        "_runtime_component_inputs",
        lambda **_kwargs: (
            new_components,
            {
                "python_version": "3.12.11",
                "jmeter_archive": tmp_path / "unused-jmeter.tgz",
                "casutg_download": tmp_path / "unused-casutg.jar",
                "influx_download": tmp_path / "unused-influx.jar",
                "casutg_version": "2.10",
                "influx_version": "2.8",
                "taurus_dependencies": ["bzt==1.16.50", "urllib3==2.7.0"],
            },
        ),
    )
    source = tmp_path / "source-runtime"
    template_dir = tmp_path / "template-checksum"
    template_dir.mkdir()
    write_archive(template_dir, version="template", metadata_arch=arch.metadata_arch)
    with tarfile.open(
        template_dir / f"surgepilot-runtime-{arch.artifact_arch}-template.tar.gz", "r:gz"
    ) as tar:
        tar.extractall(source, filter="data")
    monkeypatch.setattr(module, "_prepare_runtime_source", lambda **_kwargs: source)

    result = module.release_runtime(
        output_dir=tmp_path,
        build_dir=tmp_path / "build",
        cache_dir=tmp_path / "cache",
        release_prefix="test",
    )

    assert result.version != old_version
    assert result.reused is False


def test_release_runtime_refuses_early_reuse_when_current_inputs_differ(
    tmp_path: Path, monkeypatch
) -> None:
    module = load_module()
    arch = module.normalize_arch()
    old_components = {
        "pythonBuildStandalone": {"version": "3.12.11", "provider": "uv-managed-python"},
        "taurus": {
            "version": "1.16.50",
            "pythonDependencies": ["bzt==1.16.50", "urllib3==2.7.0"],
        },
        "jmeter": {
            "version": "5.6.3",
            "url": "https://example.invalid/jmeter.tgz",
            "sha256": "a" * 64,
        },
        "plugins": [
            {
                "name": "jpgc-casutg",
                "version": "2.10",
                "url": "https://example.invalid/casutg.jar",
                "sha256": "b" * 64,
            },
            {
                "name": "jmeter-plugin-influxdb2-listener",
                "version": "2.8",
                "url": "https://example.invalid/influx.jar",
                "sha256": "c" * 64,
            },
        ],
    }
    old_manifest = module._build_manifest(
        release_prefix="test", arch=arch, components=old_components
    )
    old_hash = module.stable_manifest_hash(old_manifest)
    old_version = module.runtime_version(release_prefix="test", manifest_hash=old_hash)
    write_archive(tmp_path, version=old_version, metadata_arch=arch.metadata_arch)
    (tmp_path / f"surgepilot-runtime-{arch.artifact_arch}-{old_version}.manifest.json").write_text(
        json.dumps({**old_manifest, "manifestHash": old_hash, "version": old_version}),
        encoding="utf-8",
    )

    new_components = {
        **old_components,
        "pythonBuildStandalone": {"version": "3.12.12", "provider": "uv-managed-python"},
    }
    monkeypatch.setattr(
        module,
        "_runtime_component_inputs",
        lambda **_kwargs: (
            new_components,
            {
                "python_version": "3.12.12",
                "jmeter_archive": tmp_path / "unused-jmeter.tgz",
                "casutg_download": tmp_path / "unused-casutg.jar",
                "influx_download": tmp_path / "unused-influx.jar",
                "casutg_version": "2.10",
                "influx_version": "2.8",
                "taurus_dependencies": ["bzt==1.16.50", "urllib3==2.7.0"],
            },
        ),
    )
    source = tmp_path / "source-runtime"
    template_dir = tmp_path / "template"
    template_dir.mkdir()
    write_archive(template_dir, version="template", metadata_arch=arch.metadata_arch)
    with tarfile.open(
        template_dir / f"surgepilot-runtime-{arch.artifact_arch}-template.tar.gz", "r:gz"
    ) as tar:
        tar.extractall(source, filter="data")
    monkeypatch.setattr(module, "_prepare_runtime_source", lambda **_kwargs: source)

    result = module.release_runtime(
        output_dir=tmp_path,
        build_dir=tmp_path / "build",
        cache_dir=tmp_path / "cache",
        release_prefix="test",
    )

    assert result.version != old_version
    assert result.reused is False


def test_release_runtime_refuses_early_reuse_with_self_referential_manifest_hash(
    tmp_path: Path, monkeypatch
) -> None:
    module = load_module()
    arch = module.normalize_arch()
    components = {
        "pythonBuildStandalone": {"version": "3.12.11", "provider": "uv-managed-python"},
        "taurus": {
            "version": "1.16.50",
            "pythonDependencies": ["bzt==1.16.50", "urllib3==2.7.0"],
        },
        "jmeter": {
            "version": "5.6.3",
            "url": "https://example.invalid/jmeter.tgz",
            "sha256": "a" * 64,
        },
        "plugins": [
            {
                "name": "jpgc-casutg",
                "version": "2.10",
                "url": "https://example.invalid/casutg.jar",
                "sha256": "b" * 64,
            },
            {
                "name": "jmeter-plugin-influxdb2-listener",
                "version": "2.8",
                "url": "https://example.invalid/influx.jar",
                "sha256": "c" * 64,
            },
        ],
    }
    manifest = module._build_manifest(release_prefix="test", arch=arch, components=components)
    real_hash = module.stable_manifest_hash(manifest)
    real_version = module.runtime_version(release_prefix="test", manifest_hash=real_hash)
    fake_hash = "deadbeef0000"
    fake_version = module.runtime_version(release_prefix="test", manifest_hash=fake_hash)
    write_archive(tmp_path, version=fake_version, metadata_arch=arch.metadata_arch)
    (tmp_path / f"surgepilot-runtime-{arch.artifact_arch}-{fake_version}.manifest.json").write_text(
        json.dumps({**manifest, "manifestHash": fake_hash, "version": fake_version}),
        encoding="utf-8",
    )

    monkeypatch.setenv("RUNTIME_JMETER_URL", "https://example.invalid/jmeter.tgz")
    monkeypatch.setenv("RUNTIME_CASUTG_URL", "https://example.invalid/casutg.jar")
    monkeypatch.setenv("RUNTIME_INFLUXDB2_LISTENER_URL", "https://example.invalid/influx.jar")
    monkeypatch.setattr(module, "_runtime_component_inputs", lambda **_kwargs: (components, {}))
    source = tmp_path / "source-runtime"
    template_dir = tmp_path / "template-self-hash"
    template_dir.mkdir()
    write_archive(template_dir, version="template", metadata_arch=arch.metadata_arch)
    with tarfile.open(
        template_dir / f"surgepilot-runtime-{arch.artifact_arch}-template.tar.gz", "r:gz"
    ) as tar:
        tar.extractall(source, filter="data")
    monkeypatch.setattr(module, "_prepare_runtime_source", lambda **_kwargs: source)

    result = module.release_runtime(
        output_dir=tmp_path,
        build_dir=tmp_path / "build",
        cache_dir=tmp_path / "cache",
        release_prefix="test",
    )

    assert result.version == real_version
    assert result.version != fake_version
    assert result.reused is False


def test_download_retries_network_failures_and_reports_attempts(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    module = load_module()
    target = tmp_path / "download.bin"
    attempts = 0
    delays: list[float] = []

    def urlopen(*_args, **_kwargs):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise OSError("network interrupted")
        return io.BytesIO(b"downloaded")

    monkeypatch.setattr(module.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(time, "sleep", delays.append)

    digest = module._download(
        "https://user:secret@example.invalid/download.bin?token=secret",
        target,
    )

    assert digest == hashlib.sha256(b"downloaded").hexdigest()
    assert target.read_bytes() == b"downloaded"
    assert attempts == 3
    assert delays == [2, 2]
    output = capsys.readouterr().out
    assert "download.bin from example.invalid (attempt 1/3)" in output
    assert "download.bin from example.invalid (attempt 2/3)" in output
    assert "download.bin from example.invalid (attempt 3/3)" in output
    assert "secret" not in output


def test_download_does_not_retry_http_status_errors(tmp_path: Path, monkeypatch) -> None:
    module = load_module()
    target = tmp_path / "download.bin"
    attempts = 0
    delays: list[float] = []
    url = "https://user:secret@example.invalid/download.bin?token=secret"

    def urlopen(*_args, **_kwargs):
        nonlocal attempts
        attempts += 1
        raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)

    monkeypatch.setattr(module.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(time, "sleep", delays.append)

    try:
        module._download(url, target)
    except RuntimeError as exc:
        assert str(exc) == "failed to download download.bin from example.invalid: HTTP 404"
        assert "secret" not in str(exc)
    else:
        raise AssertionError("expected failed download")

    assert attempts == 1
    assert delays == []


def test_download_rejects_malformed_url_without_leaking_it(tmp_path: Path) -> None:
    module = load_module()
    target = tmp_path / "download.bin"

    try:
        module._download(
            "https://[example.invalid/download.bin?token=secret",
            target,
        )
    except RuntimeError as exc:
        assert str(exc) == "failed to download download.bin: invalid URL"
        assert "secret" not in str(exc)
    else:
        raise AssertionError("expected failed download")

    assert not target.exists()
    assert list(tmp_path.glob(".download.bin.*")) == []


def test_download_does_not_retry_invalid_url_errors(tmp_path: Path, monkeypatch) -> None:
    module = load_module()
    target = tmp_path / "download.bin"
    attempts = 0
    delays: list[float] = []

    def urlopen(*_args, **_kwargs):
        nonlocal attempts
        attempts += 1
        raise http.client.InvalidURL("invalid path?token=secret")

    monkeypatch.setattr(module.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(time, "sleep", delays.append)

    try:
        module._download("https://example.invalid/download.bin", target)
    except RuntimeError as exc:
        assert str(exc) == "failed to download download.bin from example.invalid: invalid URL"
        assert "secret" not in str(exc)
    else:
        raise AssertionError("expected failed download")

    assert attempts == 1
    assert delays == []
    assert not target.exists()
    assert list(tmp_path.glob(".download.bin.*")) == []


def test_download_retries_incomplete_reads_and_truncates_partial_data(
    tmp_path: Path, monkeypatch
) -> None:
    module = load_module()
    target = tmp_path / "download.bin"
    attempts = 0
    delays: list[float] = []

    class PartialResponse:
        def __init__(self) -> None:
            self._read = False

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, _size: int = -1) -> bytes:
            if not self._read:
                self._read = True
                return b"partial"
            raise http.client.IncompleteRead(b"", 10)

    def urlopen(*_args, **_kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return PartialResponse()
        return io.BytesIO(b"complete")

    monkeypatch.setattr(module.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(time, "sleep", delays.append)

    digest = module._download("https://example.invalid/download.bin", target)

    assert digest == hashlib.sha256(b"complete").hexdigest()
    assert target.read_bytes() == b"complete"
    assert attempts == 2
    assert delays == [2]
    assert list(tmp_path.glob(".download.bin.*")) == []


def test_download_checksum_mismatch_is_not_retried(tmp_path: Path, monkeypatch) -> None:
    module = load_module()
    target = tmp_path / "download.bin"
    attempts = 0
    delays: list[float] = []

    def urlopen(*_args, **_kwargs):
        nonlocal attempts
        attempts += 1
        return io.BytesIO(b"wrong-content")

    monkeypatch.setattr(module.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(time, "sleep", delays.append)

    try:
        module._download(
            "https://example.invalid/download.bin",
            target,
            expected_sha256=hashlib.sha256(b"expected-content").hexdigest(),
        )
    except RuntimeError as exc:
        assert "downloaded checksum mismatch" in str(exc)
    else:
        raise AssertionError("expected checksum mismatch")

    assert attempts == 1
    assert delays == []
    assert not target.exists()
    assert list(tmp_path.glob(".download.bin.*")) == []


def test_download_failure_does_not_leave_partial_target(tmp_path: Path, monkeypatch) -> None:
    module = load_module()
    target = tmp_path / "download.bin"
    attempts = 0
    delays: list[float] = []

    class BrokenResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, _size: int = -1) -> bytes:
            raise ConnectionRefusedError(
                111,
                "Connection refused",
                "/download.bin?token=secret",
            )

    def urlopen(*_args, **_kwargs):
        nonlocal attempts
        attempts += 1
        return BrokenResponse()

    monkeypatch.setattr(module.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(time, "sleep", delays.append)

    try:
        module._download(
            "https://user:secret@example.invalid/download.bin?token=secret",
            target,
        )
    except RuntimeError as exc:
        message = str(exc)
        assert message == (
            "failed to download download.bin from example.invalid after 3 attempts: "
            "ConnectionRefusedError"
        )
        assert "secret" not in message
    else:
        raise AssertionError("expected failed download")

    assert attempts == 3
    assert delays == [2, 2]
    assert not target.exists()
    assert list(tmp_path.glob(".download.bin.*")) == []


def test_download_redownloads_cached_file_when_expected_checksum_differs(tmp_path: Path) -> None:
    module = load_module()
    source = tmp_path / "source.bin"
    target = tmp_path / "cached.bin"
    source.write_bytes(b"new-content")
    target.write_bytes(b"old-content")
    expected = hashlib.sha256(b"new-content").hexdigest()

    digest = module._download(source.as_uri(), target, expected_sha256=expected)

    assert digest == expected
    assert target.read_bytes() == b"new-content"


def test_download_redownloads_cached_file_when_url_changes_without_expected_checksum(
    tmp_path: Path,
) -> None:
    module = load_module()
    first_source = tmp_path / "source-a.bin"
    second_source = tmp_path / "source-b.bin"
    target = tmp_path / "cached.bin"
    first_source.write_bytes(b"first")
    second_source.write_bytes(b"second")

    first_digest = module._download(first_source.as_uri(), target)
    second_digest = module._download(second_source.as_uri(), target)

    assert first_digest == hashlib.sha256(b"first").hexdigest()
    assert second_digest == hashlib.sha256(b"second").hexdigest()
    assert target.read_bytes() == b"second"


def test_runtime_manifest_records_resolved_taurus_dependency_closure(
    tmp_path: Path, monkeypatch
) -> None:
    module = load_module()
    arch = module.normalize_arch()

    def fake_download(_url: str, target: Path, **_kwargs) -> str:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.suffix == ".jar":
            matching = [fixture for fixture in PLUGIN_ARCHIVE_FIXTURES if fixture[0] == target.name]
            assert len(matching) == 1
            with zipfile.ZipFile(target, "w") as jar:
                for class_name in matching[0][1]:
                    jar.writestr(class_name, b"class")
        else:
            target.write_bytes(b"archive")
        return "a" * 64

    monkeypatch.setattr(module, "_download", fake_download)
    monkeypatch.setattr(
        module,
        "_resolve_taurus_dependencies",
        lambda _cache_dir, **_kwargs: ["bzt==1.16.50", "urllib3==2.7.0"],
    )

    components, _inputs = module._runtime_component_inputs(cache_dir=tmp_path / "cache")
    taurus = components["taurus"]

    assert taurus["version"] == "1.16.50"
    assert taurus["pythonDependencies"] == ["bzt==1.16.50", "urllib3==2.7.0"]
    manifest = module._build_manifest(release_prefix="test", arch=arch, components=components)
    assert manifest["components"]["taurus"]["pythonDependencies"] == [
        "bzt==1.16.50",
        "urllib3==2.7.0",
    ]


def test_runtime_component_inputs_rejects_invalid_casutg_jar(tmp_path: Path, monkeypatch) -> None:
    module = load_module()

    def fake_download(_url: str, target: Path, **_kwargs) -> str:
        target.parent.mkdir(parents=True, exist_ok=True)
        if "casutg" in target.name:
            target.write_bytes(b"not a jar")
        elif "influx" in target.name:
            with zipfile.ZipFile(target, "w") as jar:
                jar.writestr(
                    "io/github/mderevyankoaqa/influxdb2/visualizer/"
                    "InfluxDatabaseBackendListenerClient.class",
                    b"class",
                )
        else:
            target.write_bytes(b"archive")
        return "a" * 64

    monkeypatch.setattr(module, "_download", fake_download)
    monkeypatch.setattr(
        module,
        "_resolve_taurus_dependencies",
        lambda _cache_dir, **_kwargs: ["bzt==1.16.50", "urllib3==2.7.0"],
    )

    try:
        module._runtime_component_inputs(cache_dir=tmp_path / "cache")
    except RuntimeError as exc:
        assert "jpgc-casutg plugin jar is invalid" in str(exc)
    else:
        raise AssertionError("expected invalid CASUTG jar to be rejected")


def test_runtime_component_inputs_rejects_casutg_jar_without_required_thread_group(
    tmp_path: Path, monkeypatch
) -> None:
    module = load_module()

    def fake_download(_url: str, target: Path, **_kwargs) -> str:
        target.parent.mkdir(parents=True, exist_ok=True)
        if "casutg" in target.name:
            with zipfile.ZipFile(target, "w") as jar:
                jar.writestr("example/Other.class", b"class")
        elif "influx" in target.name:
            with zipfile.ZipFile(target, "w") as jar:
                jar.writestr(
                    "io/github/mderevyankoaqa/influxdb2/visualizer/"
                    "InfluxDatabaseBackendListenerClient.class",
                    b"class",
                )
        else:
            target.write_bytes(b"archive")
        return "a" * 64

    monkeypatch.setattr(module, "_download", fake_download)
    monkeypatch.setattr(
        module,
        "_resolve_taurus_dependencies",
        lambda _cache_dir, **_kwargs: ["bzt==1.16.50", "urllib3==2.7.0"],
    )

    try:
        module._runtime_component_inputs(cache_dir=tmp_path / "cache")
    except RuntimeError as exc:
        assert "jpgc-casutg plugin jar does not contain required class" in str(exc)
    else:
        raise AssertionError("expected CASUTG jar without required class to be rejected")


def test_prepare_runtime_source_installs_recorded_taurus_dependency_closure(
    tmp_path: Path, monkeypatch
) -> None:
    module = load_module()
    arch = module.normalize_arch()
    python_install = tmp_path / "python-install"
    (python_install / "bin").mkdir(parents=True)
    runtime_python = python_install / "bin" / "python3"
    runtime_python.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    runtime_python.chmod(0o755)
    runner_commands: list[list[str]] = []
    runner_envs: list[dict[str, str]] = []

    def fake_run(command, **kwargs):
        runner_commands.append([str(part) for part in command])
        runner_envs.append(dict(kwargs.get("extra_env") or {}))

    def fake_subprocess_run(*_args, **_kwargs):
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="")

    def fake_extract(_archive: Path, target: Path) -> None:
        jmeter = target / "apache-jmeter-5.6.3"
        (jmeter / "bin").mkdir(parents=True)
        (jmeter / "lib" / "ext").mkdir(parents=True)
        (jmeter / "bin" / "jmeter").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")

    plugin_downloads = {}
    for plugin_name, (filename, classes) in zip(
        EXPECTED_RUNTIME_PLUGINS, PLUGIN_ARCHIVE_FIXTURES, strict=True
    ):
        plugin_path = tmp_path / filename
        with zipfile.ZipFile(plugin_path, "w") as jar:
            for class_name in classes:
                jar.writestr(class_name, b"class")
        plugin_downloads[plugin_name] = plugin_path
    monkeypatch.setattr(module, "_run", fake_run)
    monkeypatch.setattr(module.subprocess, "run", fake_subprocess_run)
    monkeypatch.setattr(module, "_find_uv_python_install", lambda *_args: python_install)
    monkeypatch.setattr(module, "_safe_extract_tar", fake_extract)

    module._prepare_runtime_source(
        build_dir=tmp_path / "build",
        cache_dir=tmp_path / "cache",
        arch=arch,
        component_inputs={
            "python_version": "3.12.11",
            "jmeter_archive": tmp_path / "jmeter.tgz",
            "plugin_downloads": plugin_downloads,
            "taurus_dependencies": ["bzt==1.16.50", "urllib3==2.7.0"],
        },
    )

    source_dir = tmp_path / "build" / "runtime-source"
    runtime_python_path = source_dir / "python" / "bin" / "python3"
    pip_install_commands = [
        command
        for command in runner_commands
        if command[:5] == [str(runtime_python_path), "-I", "-m", "pip", "install"]
    ]
    assert pip_install_commands
    pip_install_command = pip_install_commands[0]
    assert "--prefix" in pip_install_command
    assert pip_install_command[pip_install_command.index("--prefix") + 1] == str(
        source_dir / "python"
    )
    assert "bzt==1.16.50" in pip_install_command
    assert "urllib3==2.7.0" in pip_install_command
    pip_install_env = runner_envs[runner_commands.index(pip_install_command)]
    assert pip_install_env["PYTHONNOUSERSITE"] == "1"
    assert pip_install_env["PIP_USER"] == "0"
    assert 'export PYTHONNOUSERSITE="1"' in (source_dir / "bin" / "bzt").read_text(encoding="utf-8")
    wrapper = source_dir / "apache-jmeter-5.6.3" / "bin" / "surgepilot-jmeter-wrapper"
    wrapper_text = wrapper.read_text(encoding="utf-8")
    assert 'export PYTHONNOUSERSITE="1"' in wrapper_text
    assert 'runtime_root="$script_dir/../.."' in wrapper_text
    assert not (source_dir / "bin" / "surgepilot-jmeter-wrapper").exists()


def test_resolve_taurus_dependencies_uses_uv_pip_when_current_python_has_no_pip(
    tmp_path: Path, monkeypatch
) -> None:
    module = load_module()
    commands: list[list[str]] = []

    def fake_run(command, **_kwargs):
        commands.append([str(part) for part in command])
        report_path = Path(command[command.index("--report") + 1])
        report_path.write_text(
            json.dumps(
                {
                    "install": [
                        {"metadata": {"name": "bzt", "version": "1.16.50"}},
                        {"metadata": {"name": "urllib3", "version": "2.7.0"}},
                    ]
                }
            ),
            encoding="utf-8",
        )

    monkeypatch.setattr(module, "_run", fake_run)

    dependencies = module._resolve_taurus_dependencies(tmp_path / "cache", python_version="3.12.11")

    assert dependencies == ["bzt==1.16.50", "urllib3==2.7.0"]
    assert commands
    assert commands[0][:4] == ["uv", "run", "--with", "pip"]
    assert commands[0][4:7] == ["python", "-m", "pip"]


def test_safe_extract_tar_rejects_link_members(tmp_path: Path) -> None:
    module = load_module()
    archive = tmp_path / "unsafe.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        info = tarfile.TarInfo("apache-jmeter-5.6.3/lib/ext/evil")
        info.type = tarfile.SYMTYPE
        info.linkname = "../../../../../outside"
        tar.addfile(info)

    try:
        module._safe_extract_tar(archive, tmp_path / "extract")
    except RuntimeError as exc:
        assert "unsafe tar member" in str(exc)
    else:
        raise AssertionError("expected unsafe symlink member to be rejected")
