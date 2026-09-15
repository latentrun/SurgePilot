"""Assemble the bounded digest-pinned P2-05 GitHub Release bundle."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tarfile
import tempfile

from scripts.fetch_runtime_release import runtime_asset_names, validate_runtime_files


EXPECTED_IMAGES = {
    "api": "ghcr.io/latentrun/surgepilot-api",
    "web": "ghcr.io/latentrun/surgepilot-web",
    "demoNode": "ghcr.io/latentrun/surgepilot-demo-node",
}
SEMANTIC_VERSION_PATTERN = re.compile(r"v[0-9]+\.[0-9]+\.[0-9]+\Z")
DIGEST_PATTERN = re.compile(r"sha256:[a-f0-9]{64}\Z")


class ReleaseBundleError(RuntimeError):
    """Raised when release inputs cannot produce a trusted bounded bundle."""


@dataclass(frozen=True)
class BundleResult:
    bundle_root: Path
    archive: Path
    checksum: Path
    installer: Path
    manifest: Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_text_atomic(target: Path, content: str, *, mode: int) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(mode)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def _write_checksum(archive: Path) -> Path:
    checksum = archive.with_name(f"{archive.name}.sha256")
    _write_text_atomic(checksum, f"{_sha256(archive)}  {archive.name}\n", mode=0o644)
    return checksum


def _write_installer(*, root: Path, output_directory: Path, version: str) -> Path:
    template = (root / "infra/release/install.sh").read_text(encoding="utf-8")
    rendered = _replace_exact(template, "@@RELEASE_VERSION@@", version)
    target = output_directory / "install.sh"
    _write_text_atomic(target, rendered, mode=0o755)
    return target


def _validated_images(images: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    if set(images) != set(EXPECTED_IMAGES):
        raise ReleaseBundleError("image digest input must contain api, web, and demoNode")
    validated: dict[str, dict[str, str]] = {}
    for key, expected_repository in EXPECTED_IMAGES.items():
        entry = images[key]
        repository = entry.get("repository", "")
        digest = entry.get("digest", "").lower()
        if repository != expected_repository:
            raise ReleaseBundleError(f"image repository mismatch for {key}")
        if DIGEST_PATTERN.fullmatch(digest) is None:
            raise ReleaseBundleError(f"image digest is invalid for {key}")
        validated[key] = {"repository": repository, "digest": digest}
    return validated


def _runtime_entries(*, directory: Path, version: str) -> dict[str, dict[str, object]]:
    entries: dict[str, dict[str, object]] = {}
    for arch in ("amd64", "arm64"):
        archive_name, sidecar_name, manifest_name = runtime_asset_names(arch, version)
        archive = directory / archive_name
        if not archive.is_file():
            raise ReleaseBundleError(f"Runtime archive is missing for {arch}: {archive_name}")
        entry: dict[str, object] = {
            "archive": archive_name,
            "sha256Sidecar": sidecar_name,
            "manifest": manifest_name,
            "sha256": _sha256(archive),
        }
        try:
            validate_runtime_files(
                directory=directory,
                version=version,
                arch=arch,
                release_entry=entry,
            )
        except Exception as exc:  # noqa: BLE001 - normalize lower-level release validation.
            raise ReleaseBundleError(f"Runtime validation failed for {arch}: {exc}") from exc
        entries[arch] = entry
    return entries


def _replace_exact(text: str, placeholder: str, value: str, *, count: int = 1) -> str:
    if text.count(placeholder) != count:
        raise ReleaseBundleError(
            f"release template must contain {count} occurrence(s) of {placeholder}"
        )
    return text.replace(placeholder, value)


def _copy_release_files(*, root: Path, bundle_root: Path) -> None:
    compose_root = bundle_root / "compose"
    compose_root.mkdir(parents=True)
    shutil.copytree(root / "infra/docker/nginx", compose_root / "nginx")
    shutil.copytree(root / "infra/docker/minio", compose_root / "minio")
    shutil.copytree(root / "infra/docker/grafana", compose_root / "grafana")
    scripts_root = bundle_root / "scripts"
    scripts_root.mkdir()
    shutil.copy2(root / "scripts/__init__.py", scripts_root / "__init__.py")
    for name in (
        "bootstrap_deployment_env.py",
        "release_preflight.py",
        "fetch_runtime_release.py",
    ):
        shutil.copy2(root / "scripts" / name, scripts_root / name)
    shutil.copy2(root / "infra/release/.env.example", bundle_root / ".env.example")


def _write_archive(*, bundle_root: Path, archive: Path) -> None:
    archive.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".bundle-", dir=archive.parent)
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with tarfile.open(temporary, "w:gz", format=tarfile.PAX_FORMAT) as output:
            for path in sorted([bundle_root, *bundle_root.rglob("*")]):
                relative = Path("surgepilot") / path.relative_to(bundle_root)
                info = output.gettarinfo(str(path), arcname=relative.as_posix())
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                info.mtime = 0
                if path.is_file():
                    with path.open("rb") as handle:
                        output.addfile(info, handle)
                else:
                    output.addfile(info)
        os.replace(temporary, archive)
    finally:
        temporary.unlink(missing_ok=True)


def assemble_bundle(
    *,
    root: Path,
    version: str,
    revision: str,
    images: dict[str, dict[str, str]],
    runtime_directory: Path,
    output_directory: Path,
) -> BundleResult:
    if SEMANTIC_VERSION_PATTERN.fullmatch(version) is None:
        raise ReleaseBundleError("release version must use exact vX.Y.Z form")
    if re.fullmatch(r"[a-f0-9]{40}", revision) is None:
        raise ReleaseBundleError("release revision must be a full Git commit SHA")
    validated_images = _validated_images(images)
    runtimes = _runtime_entries(directory=runtime_directory, version=version)
    output_directory.mkdir(parents=True, exist_ok=True)
    bundle_root = output_directory / "surgepilot"
    if bundle_root.exists():
        shutil.rmtree(bundle_root)
    bundle_root.mkdir()
    _copy_release_files(root=root, bundle_root=bundle_root)

    manifest_data: dict[str, object] = {
        "schemaVersion": 1,
        "version": version,
        "revision": revision,
        "images": validated_images,
        "runtimes": runtimes,
    }
    manifest_path = bundle_root / "release-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest_data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (bundle_root / "VERSION").write_text(f"{version}\n", encoding="utf-8")

    image_refs = {
        key: f"{entry['repository']}@{entry['digest']}" for key, entry in validated_images.items()
    }
    compose = (root / "infra/release/docker-compose.release.yml").read_text(encoding="utf-8")
    compose = _replace_exact(compose, "@@API_IMAGE@@", image_refs["api"], count=3)
    compose = _replace_exact(compose, "@@WEB_IMAGE@@", image_refs["web"])
    compose = _replace_exact(compose, "@@DEMO_NODE_IMAGE@@", image_refs["demoNode"])
    (bundle_root / "compose/docker-compose.yml").write_text(compose, encoding="utf-8")

    wrapper = (root / "infra/release/surgepilot").read_text(encoding="utf-8")
    wrapper = _replace_exact(wrapper, "@@RELEASE_VERSION@@", version)
    wrapper = _replace_exact(wrapper, "@@API_IMAGE@@", image_refs["api"])
    wrapper_path = bundle_root / "surgepilot"
    wrapper_path.write_text(wrapper, encoding="utf-8")
    wrapper_path.chmod(0o755)

    readme = (root / "infra/release/README.md").read_text(encoding="utf-8")
    readme = _replace_exact(readme, "@@RELEASE_VERSION@@", version)
    (bundle_root / "README.md").write_text(readme, encoding="utf-8")

    archive = output_directory / f"surgepilot-{version}.tar.gz"
    _write_archive(bundle_root=bundle_root, archive=archive)
    checksum = _write_checksum(archive)
    installer = _write_installer(root=root, output_directory=output_directory, version=version)
    return BundleResult(
        bundle_root=bundle_root,
        archive=archive,
        checksum=checksum,
        installer=installer,
        manifest=manifest_path,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--version", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--images-json", required=True, type=Path)
    parser.add_argument("--runtime-directory", required=True, type=Path)
    parser.add_argument("--output-directory", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        images = json.loads(args.images_json.read_text(encoding="utf-8"))
        result = assemble_bundle(
            root=args.root,
            version=args.version,
            revision=args.revision,
            images=images,
            runtime_directory=args.runtime_directory,
            output_directory=args.output_directory,
        )
    except (OSError, json.JSONDecodeError, ReleaseBundleError) as exc:
        print(f"Release bundle failed: {exc}")
        return 1
    print(f"Release bundle ready: {result.archive}")
    print(f"Release checksum ready: {result.checksum}")
    print(f"Release installer ready: {result.installer}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
