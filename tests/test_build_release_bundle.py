from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import build_release_bundle, fetch_runtime_release  # noqa: E402


VERSION = "v0.3.0"


def write_runtime_set(directory: Path, arch: str) -> None:
    prefix = f"surgepilot-runtime-linux-{arch}-{VERSION}"
    archive = directory / f"{prefix}.tar.gz"
    runtime_manifest: dict[str, object] = {
        "schemaVersion": 1,
        "version": VERSION,
        "target": {
            "platform": "linux",
            "artifactArch": f"linux-{arch}",
            "metadataArch": arch,
        },
        "components": {
            "taurus": {"version": "1.16.50"},
            "jmeter": {"version": "5.6.3"},
            "plugins": [
                {"name": plugin_name} for plugin_name in fetch_runtime_release.REQUIRED_PLUGINS
            ],
        },
    }
    manifest_hash = fetch_runtime_release._manifest_input_hash(runtime_manifest)
    runtime_manifest["manifestHash"] = manifest_hash
    metadata = {
        "name": "surgepilot-runtime",
        "version": VERSION,
        "platform": "linux",
        "arch": arch,
        "taurus": "1.16.50",
        "jmeter": "5.6.3",
        "plugins": list(fetch_runtime_release.REQUIRED_PLUGINS),
        "builder": {"manifestHash": manifest_hash},
    }
    with tarfile.open(archive, "w:gz") as tar:
        payload = json.dumps(metadata).encode()
        info = tarfile.TarInfo("metadata.json")
        info.size = len(payload)
        tar.addfile(info, io.BytesIO(payload))
        for _, jar_prefix, required_classes in fetch_runtime_release.REQUIRED_PLUGIN_CLASSES:
            jar_payload = io.BytesIO()
            with zipfile.ZipFile(jar_payload, "w") as jar:
                for class_name in required_classes:
                    jar.writestr(class_name, b"test-class")
            jar_bytes = jar_payload.getvalue()
            jar_info = tarfile.TarInfo(f"apache-jmeter-5.6.3/lib/ext/{jar_prefix}-test.jar")
            jar_info.size = len(jar_bytes)
            tar.addfile(jar_info, io.BytesIO(jar_bytes))
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (directory / f"{prefix}.tar.gz.sha256").write_text(
        f"{digest}  {archive.name}\n", encoding="utf-8"
    )
    (directory / f"{prefix}.manifest.json").write_text(
        json.dumps(runtime_manifest), encoding="utf-8"
    )


def image_digests() -> dict[str, dict[str, str]]:
    return {
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
    }


def test_bundle_module_import_does_not_load_runtime_preflight_dependencies() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import builtins
real_import = builtins.__import__
def guarded_import(name, *args, **kwargs):
    if name == 'dotenv':
        raise AssertionError('bundle import must not load release preflight dependencies')
    return real_import(name, *args, **kwargs)
builtins.__import__ = guarded_import
import scripts.build_release_bundle
""",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr


def test_assemble_bundle_pins_images_and_excludes_source_and_private_state(tmp_path: Path) -> None:
    runtimes = tmp_path / "runtimes"
    runtimes.mkdir()
    write_runtime_set(runtimes, "amd64")
    write_runtime_set(runtimes, "arm64")
    output = tmp_path / "dist"

    result = build_release_bundle.assemble_bundle(
        root=ROOT,
        version=VERSION,
        revision="a" * 40,
        images=image_digests(),
        runtime_directory=runtimes,
        output_directory=output,
    )

    assert result.archive.name == "surgepilot-v0.3.0.tar.gz"
    assert result.archive.is_file()
    assert result.checksum.name == "surgepilot-v0.3.0.tar.gz.sha256"
    assert result.checksum.read_text(encoding="utf-8") == (
        f"{hashlib.sha256(result.archive.read_bytes()).hexdigest()}  {result.archive.name}\n"
    )
    assert result.installer.name == "install.sh"
    installer = result.installer.read_text(encoding="utf-8")
    assert 'RELEASE_VERSION="v0.3.0"' in installer
    assert "@@RELEASE_VERSION@@" not in installer
    assert result.installer.stat().st_mode & 0o111
    manifest = json.loads((result.bundle_root / "release-manifest.json").read_text())
    assert manifest["images"]["api"]["digest"] == f"sha256:{'1' * 64}"
    assert manifest["runtimes"]["amd64"]["sha256"]
    assert (result.bundle_root / "VERSION").read_text(encoding="utf-8") == f"{VERSION}\n"
    compose = (result.bundle_root / "compose/docker-compose.yml").read_text()
    assert f"ghcr.io/latentrun/surgepilot-api@sha256:{'1' * 64}" in compose
    assert "@@API_IMAGE@@" not in compose
    wrapper = (result.bundle_root / "surgepilot").read_text()
    assert f"ghcr.io/latentrun/surgepilot-api@sha256:{'1' * 64}" in wrapper
    assert "@@RELEASE_VERSION@@" not in wrapper
    bundled_fetch = subprocess.run(
        [sys.executable, str(result.bundle_root / "scripts/fetch_runtime_release.py"), "--help"],
        cwd=result.bundle_root,
        text=True,
        capture_output=True,
    )
    assert bundled_fetch.returncode == 0, bundled_fetch.stderr

    with tarfile.open(result.archive, "r:gz") as archive:
        names = set(archive.getnames())
    assert "surgepilot/.env" not in names
    assert not any(name.startswith("surgepilot/.surgepilot/") for name in names)
    assert not any(name.startswith("surgepilot/apps/") for name in names)
    assert not any("ai-skills" in name for name in names)
    assert not any(name.endswith(".tar.gz") and "runtime" in name for name in names)


def test_assemble_bundle_rejects_non_semantic_version_or_wrong_image_repository(
    tmp_path: Path,
) -> None:
    runtimes = tmp_path / "runtimes"
    runtimes.mkdir()
    write_runtime_set(runtimes, "amd64")
    write_runtime_set(runtimes, "arm64")

    with pytest.raises(build_release_bundle.ReleaseBundleError, match="vX.Y.Z"):
        build_release_bundle.assemble_bundle(
            root=ROOT,
            version="latest",
            revision="a" * 40,
            images=image_digests(),
            runtime_directory=runtimes,
            output_directory=tmp_path / "dist",
        )

    images = image_digests()
    images["api"]["repository"] = "docker.io/example/api"
    with pytest.raises(build_release_bundle.ReleaseBundleError, match="repository"):
        build_release_bundle.assemble_bundle(
            root=ROOT,
            version=VERSION,
            revision="a" * 40,
            images=images,
            runtime_directory=runtimes,
            output_directory=tmp_path / "dist-2",
        )


def test_bundle_rejects_invalid_revision_digest_shape_and_missing_runtime(tmp_path: Path) -> None:
    runtimes = tmp_path / "runtimes"
    runtimes.mkdir()
    write_runtime_set(runtimes, "amd64")
    write_runtime_set(runtimes, "arm64")

    with pytest.raises(build_release_bundle.ReleaseBundleError, match="revision"):
        build_release_bundle.assemble_bundle(
            root=ROOT,
            version=VERSION,
            revision="short",
            images=image_digests(),
            runtime_directory=runtimes,
            output_directory=tmp_path / "revision",
        )

    images = image_digests()
    images["web"]["digest"] = "latest"
    with pytest.raises(build_release_bundle.ReleaseBundleError, match="digest"):
        build_release_bundle.assemble_bundle(
            root=ROOT,
            version=VERSION,
            revision="a" * 40,
            images=images,
            runtime_directory=runtimes,
            output_directory=tmp_path / "digest",
        )

    (runtimes / f"surgepilot-runtime-linux-arm64-{VERSION}.tar.gz").unlink()
    with pytest.raises(build_release_bundle.ReleaseBundleError, match="missing for arm64"):
        build_release_bundle.assemble_bundle(
            root=ROOT,
            version=VERSION,
            revision="a" * 40,
            images=image_digests(),
            runtime_directory=runtimes,
            output_directory=tmp_path / "runtime",
        )


def test_bundle_cli_writes_archive_and_reports_invalid_json(tmp_path: Path, capsys) -> None:
    runtimes = tmp_path / "runtimes"
    runtimes.mkdir()
    write_runtime_set(runtimes, "amd64")
    write_runtime_set(runtimes, "arm64")
    images_path = tmp_path / "images.json"
    images_path.write_text(json.dumps(image_digests()), encoding="utf-8")
    output = tmp_path / "output"

    result = build_release_bundle.main(
        [
            "--root",
            str(ROOT),
            "--version",
            VERSION,
            "--revision",
            "a" * 40,
            "--images-json",
            str(images_path),
            "--runtime-directory",
            str(runtimes),
            "--output-directory",
            str(output),
        ]
    )

    assert result == 0
    assert "Release bundle ready" in capsys.readouterr().out
    images_path.write_text("not-json", encoding="utf-8")
    assert (
        build_release_bundle.main(
            [
                "--version",
                VERSION,
                "--revision",
                "a" * 40,
                "--images-json",
                str(images_path),
                "--runtime-directory",
                str(runtimes),
                "--output-directory",
                str(output),
            ]
        )
        == 1
    )
    assert "Release bundle failed" in capsys.readouterr().out
