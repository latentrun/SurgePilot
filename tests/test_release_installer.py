from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import functools
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tarfile
import threading

import pytest


ROOT = Path(__file__).resolve().parents[1]
INSTALLER_TEMPLATE = ROOT / "infra/release/install.sh"
VERSION = "v0.3.0"


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        del format, args


@contextmanager
def serve(directory: Path) -> Iterator[str]:
    handler = functools.partial(QuietHandler, directory=str(directory))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def render_installer(directory: Path, version: str = VERSION) -> Path:
    if not INSTALLER_TEMPLATE.is_file():
        pytest.fail("release installer template is missing")
    text = INSTALLER_TEMPLATE.read_text(encoding="utf-8")
    assert text.count("@@RELEASE_VERSION@@") == 1
    target = directory / "install.sh"
    target.write_text(text.replace("@@RELEASE_VERSION@@", version), encoding="utf-8")
    target.chmod(0o755)
    return target


def write_release_assets(
    directory: Path,
    *,
    version: str = VERSION,
    manifest_version: str | None = None,
    nested_manifest_version: str | None = None,
    manifest_text: str | None = None,
    marker_version: str | None = None,
    omit: str | None = None,
    extra_file: str | None = None,
    symlink_readme: bool = False,
    legacy: bool = False,
) -> tuple[Path, Path]:
    payload = directory / "payload" / "surgepilot"
    (payload / "compose").mkdir(parents=True)
    manifest: dict[str, object] = {
        "schemaVersion": 1,
        "version": manifest_version or version,
    }
    if not legacy:
        manifest["minimumUpgradeVersion"] = "v1.0.0" if version.startswith("v1.") else version
    if nested_manifest_version is not None:
        manifest["nested"] = {"version": nested_manifest_version}
    files = {
        "surgepilot": "#!/bin/sh\nprintf 'wrapper:%s\\n' \"$*\"\n",
        "compose/docker-compose.yml": "services: {}\n",
        ".env.example": "COMPOSE_PROJECT_NAME=surgepilot\n",
        "VERSION": f"{marker_version or version}\n",
        "README.md": "# SurgePilot\n",
        "release-manifest.json": manifest_text
        or json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        "scripts/__init__.py": "",
        "scripts/bootstrap_deployment_env.py": "",
        "scripts/release_preflight.py": "",
        "scripts/fetch_runtime_release.py": "",
        "compose/nginx/default.conf": "",
        "compose/minio/init-bucket.sh": "",
        "compose/grafana/entrypoint.sh": "",
        "compose/grafana/dashboards/surgepilot-jmeter-13644.json": "{}\n",
        "compose/grafana/provisioning/dashboards/surgepilot.yml": "",
        "compose/grafana/provisioning/datasources/influxdb.yml": "",
    }
    if not legacy:
        files["surgepilot-dispatcher"] = (ROOT / "infra/release/dispatcher").read_text(
            encoding="utf-8"
        )
        files["scripts/release_transition_probe.py"] = ""
    if extra_file is not None:
        files[extra_file] = "unexpected\n"
    for relative, content in files.items():
        if relative == omit:
            continue
        path = payload / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    if symlink_readme:
        (payload / "README.md").unlink()
        (payload / "README.md").symlink_to(".env.example")
    if (payload / "surgepilot").exists():
        (payload / "surgepilot").chmod(0o755)
    if (payload / "surgepilot-dispatcher").exists():
        (payload / "surgepilot-dispatcher").chmod(0o755)

    archive = directory / f"surgepilot-{version}.tar.gz"
    with tarfile.open(archive, "w:gz") as output:
        output.add(payload, arcname="surgepilot")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    sidecar = directory / f"{archive.name}.sha256"
    sidecar.write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
    return archive, sidecar


def run_installer(
    installer: Path,
    *,
    home: Path,
    xdg_data_home: Path,
    base_url: str,
    path: str | None = None,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.update(
        {
            "HOME": str(home),
            "XDG_DATA_HOME": str(xdg_data_home),
            "SURGEPILOT_INSTALLER_RELEASE_BASE_URL": base_url,
        }
    )
    if path is not None:
        environment["PATH"] = path
    return subprocess.run(
        ["sh"],
        input=installer.read_text(encoding="utf-8"),
        env=environment,
        text=True,
        capture_output=True,
        timeout=30,
    )


def write_installed_launcher(home: Path, install_root: Path) -> Path:
    launcher = home / ".local/bin/surgepilot"
    launcher.parent.mkdir(parents=True, exist_ok=True)
    launcher.write_text(
        "#!/bin/sh\n"
        "set -eu\n"
        "SURGEPILOT_COMMAND_NAME=surgepilot\n"
        "export SURGEPILOT_COMMAND_NAME\n"
        f"INSTALL_ROOT='{install_root}'\n"
        'exec "$INSTALL_ROOT/surgepilot" "$@"\n',
        encoding="utf-8",
    )
    launcher.chmod(0o700)
    return launcher


def isolated_tool_path(
    directory: Path,
    *,
    uname_output: str,
    include_checksum_tool: bool,
) -> str:
    directory.mkdir()
    for name in (
        "sh",
        "cat",
        "curl",
        "gzip",
        "tar",
        "mktemp",
        "mkdir",
        "rm",
        "rmdir",
        "chmod",
        "mv",
        "grep",
        "sed",
        "sort",
        "cmp",
        "sync",
        "readlink",
        "ps",
        "ls",
        "cp",
        "ln",
        "wc",
        "tr",
        "stat",
        "id",
        "find",
    ):
        source = shutil.which(name)
        assert source is not None
        (directory / name).symlink_to(source)
    if include_checksum_tool:
        checksum_name = "shasum" if uname_output == "Darwin" else "sha256sum"
        checksum = shutil.which(checksum_name)
        assert checksum is not None
        (directory / checksum_name).symlink_to(checksum)
    uname = directory / "uname"
    uname.write_text(f"#!/bin/sh\nprintf '%s\\n' '{uname_output}'\n", encoding="utf-8")
    uname.chmod(0o755)
    return str(directory)


def test_installer_publishes_user_owned_release_and_location_independent_launcher(
    tmp_path: Path,
) -> None:
    assets = tmp_path / "assets"
    assets.mkdir()
    installer = render_installer(assets)
    write_release_assets(assets)
    home = tmp_path / "home"
    home.mkdir()
    xdg_data_home = tmp_path / "data"
    shell_rc = home / ".zshrc"
    shell_rc.write_text("preserve-me\n", encoding="utf-8")

    with serve(assets) as base_url:
        result = run_installer(
            installer,
            home=home,
            xdg_data_home=xdg_data_home,
            base_url=base_url,
        )

    assert result.returncode == 0, result.stderr
    install_root = xdg_data_home / "surgepilot"
    launcher = home / ".local/bin/surgepilot"
    assert install_root.is_dir()
    assert (install_root / "surgepilot").read_bytes() == (
        install_root / ".releases" / VERSION / "surgepilot-dispatcher"
    ).read_bytes()
    assert (install_root / ".release-state").read_text(encoding="utf-8") == (
        f"schema=1\nphase=installed\ntarget={VERSION}\nbase=none\n"
    )
    release_root = install_root / ".releases" / VERSION
    assert (release_root / "surgepilot").is_file()
    assert (release_root / ".surgepilot").is_symlink()
    assert os.readlink(release_root / ".surgepilot") == "../../.surgepilot"
    assert launcher.stat().st_mode & 0o111
    launched = subprocess.run(
        [launcher, "--help"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )
    assert launched.returncode == 0, launched.stderr
    assert launched.stdout == "wrapper:--help\n"
    assert "Run surgepilot up" in result.stdout
    assert str(launcher) in result.stdout
    assert shell_rc.read_text(encoding="utf-8") == "preserve-me\n"


def test_installer_prepares_newer_same_major_release_from_stable_installation(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    xdg_data_home = tmp_path / "data"

    source_assets = tmp_path / "source-assets"
    source_assets.mkdir()
    source_installer = render_installer(source_assets, "v1.2.3")
    write_release_assets(source_assets, version="v1.2.3")
    with serve(source_assets) as base_url:
        first = run_installer(
            source_installer,
            home=home,
            xdg_data_home=xdg_data_home,
            base_url=base_url,
        )
    assert first.returncode == 0, first.stderr

    install_root = xdg_data_home / "surgepilot"
    (install_root / ".release-state").write_text(
        "schema=1\nphase=stable\ntarget=v1.2.3\nbase=v1.2.3\n",
        encoding="utf-8",
    )
    (install_root / ".release-state").chmod(0o600)
    (install_root / ".env").write_text("PRESERVE=yes\n", encoding="utf-8")

    target_assets = tmp_path / "target-assets"
    target_assets.mkdir()
    target_installer = render_installer(target_assets, "v1.2.4")
    write_release_assets(target_assets, version="v1.2.4")
    with serve(target_assets) as base_url:
        result = run_installer(
            target_installer,
            home=home,
            xdg_data_home=xdg_data_home,
            base_url=base_url,
        )

    assert result.returncode == 0, result.stderr
    assert (install_root / ".release-state").read_text(encoding="utf-8") == (
        "schema=1\nphase=prepared\ntarget=v1.2.4\nbase=v1.2.3\n"
    )
    assert (install_root / ".releases/v1.2.3").is_dir()
    assert (install_root / ".releases/v1.2.4").is_dir()
    assert (install_root / ".env").read_text(encoding="utf-8") == "PRESERVE=yes\n"
    assert not Path(f"{install_root}.lock").exists()


def test_same_target_installer_verifies_and_leaves_state_unchanged(tmp_path: Path) -> None:
    assets = tmp_path / "assets"
    assets.mkdir()
    installer = render_installer(assets, "v1.2.3")
    write_release_assets(assets, version="v1.2.3")
    home = tmp_path / "home"
    home.mkdir()
    xdg_data_home = tmp_path / "data"

    with serve(assets) as base_url:
        first = run_installer(installer, home=home, xdg_data_home=xdg_data_home, base_url=base_url)
        second = run_installer(installer, home=home, xdg_data_home=xdg_data_home, base_url=base_url)

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    install_root = xdg_data_home / "surgepilot"
    assert (install_root / ".release-state").read_text(encoding="utf-8") == (
        "schema=1\nphase=installed\ntarget=v1.2.3\nbase=none\n"
    )
    assert not Path(f"{install_root}.lock").exists()


@pytest.mark.parametrize("source_version", ["v1.0.0", "v1.1.0"])
@pytest.mark.parametrize("target_version", ["v1.2.3", "v1.2.4"])
def test_installer_bootstraps_supported_legacy_installation(
    tmp_path: Path, source_version: str, target_version: str
) -> None:
    assets = tmp_path / "assets"
    assets.mkdir()
    installer = render_installer(assets, target_version)
    write_release_assets(assets, version=target_version)
    source_build = tmp_path / "source-build"
    source_build.mkdir()
    source_archive, source_sidecar = write_release_assets(
        source_build, version=source_version, legacy=True
    )
    shutil.copy2(source_archive, assets / source_archive.name)
    shutil.copy2(source_sidecar, assets / source_sidecar.name)

    home = tmp_path / "home"
    home.mkdir()
    xdg_data_home = tmp_path / "data"
    install_root = xdg_data_home / "surgepilot"
    shutil.copytree(source_build / "payload/surgepilot", install_root)
    (install_root / ".env").write_text(
        "COMPOSE_PROJECT_NAME=surgepilot\nPRESERVE=yes\n", encoding="utf-8"
    )
    (install_root / ".env").chmod(0o600)
    (install_root / ".surgepilot").mkdir()
    write_installed_launcher(home, install_root)

    with serve(assets) as base_url:
        result = run_installer(installer, home=home, xdg_data_home=xdg_data_home, base_url=base_url)

    assert result.returncode == 0, result.stderr
    assert (install_root / ".release-state").read_text(encoding="utf-8") == (
        f"schema=1\nphase=unclassified\ntarget={target_version}\nbase={source_version}\n"
    )
    assert (install_root / "surgepilot").read_bytes() == (
        install_root / ".releases" / target_version / "surgepilot-dispatcher"
    ).read_bytes()
    assert (install_root / ".releases" / source_version).is_dir()
    assert (install_root / ".releases" / target_version).is_dir()
    assert (install_root / ".env").is_file()
    assert (install_root / ".surgepilot").is_dir()


def test_legacy_upgrade_rejects_symlinked_private_state_before_publication(
    tmp_path: Path,
) -> None:
    assets = tmp_path / "assets"
    assets.mkdir()
    installer = render_installer(assets, "v1.2.3")
    write_release_assets(assets, version="v1.2.3")
    source_build = tmp_path / "source-build"
    source_build.mkdir()
    source_archive, source_sidecar = write_release_assets(
        source_build, version="v1.1.0", legacy=True
    )
    shutil.copy2(source_archive, assets / source_archive.name)
    shutil.copy2(source_sidecar, assets / source_sidecar.name)
    home = tmp_path / "home"
    home.mkdir()
    xdg_data_home = tmp_path / "data"
    install_root = xdg_data_home / "surgepilot"
    shutil.copytree(source_build / "payload/surgepilot", install_root)
    (install_root / ".env").write_text("COMPOSE_PROJECT_NAME=surgepilot\n", encoding="utf-8")
    unsafe_target = tmp_path / "unsafe-private-state"
    unsafe_target.mkdir()
    (install_root / ".surgepilot").symlink_to(unsafe_target)
    write_installed_launcher(home, install_root)

    with serve(assets) as base_url:
        result = run_installer(
            installer,
            home=home,
            xdg_data_home=xdg_data_home,
            base_url=base_url,
        )

    assert result.returncode != 0
    assert "private state is unsafe" in result.stderr.lower()
    assert not (install_root / ".release-state").exists()
    assert not (install_root / ".releases").exists()


def test_legacy_recovery_rejects_tampered_launcher(tmp_path: Path) -> None:
    assets = tmp_path / "assets"
    assets.mkdir()
    installer = render_installer(assets, "v1.2.3")
    write_release_assets(assets, version="v1.2.3")
    source_build = tmp_path / "source-build"
    source_build.mkdir()
    source_archive, source_sidecar = write_release_assets(
        source_build, version="v1.1.0", legacy=True
    )
    shutil.copy2(source_archive, assets / source_archive.name)
    shutil.copy2(source_sidecar, assets / source_sidecar.name)

    home = tmp_path / "home"
    home.mkdir()
    xdg_data_home = tmp_path / "data"
    install_root = xdg_data_home / "surgepilot"
    source_payload = source_build / "payload/surgepilot"
    target_payload = assets / "payload/surgepilot"
    shutil.copytree(source_payload, install_root)
    (install_root / ".surgepilot").mkdir()
    releases = install_root / ".releases"
    releases.mkdir()
    source_release = releases / "v1.1.0"
    target_release = releases / "v1.2.3"
    shutil.copytree(source_payload, source_release)
    shutil.copytree(target_payload, target_release)
    (source_release / ".surgepilot").symlink_to("../../.surgepilot")
    (target_release / ".surgepilot").symlink_to("../../.surgepilot")
    shutil.copy2(target_payload / "surgepilot-dispatcher", install_root / "surgepilot")
    (install_root / "surgepilot").chmod(0o700)
    launcher = write_installed_launcher(home, install_root)
    launcher.write_text(
        launcher.read_text(encoding="utf-8") + "# tampered\n",
        encoding="utf-8",
    )

    with serve(assets) as base_url:
        result = run_installer(
            installer,
            home=home,
            xdg_data_home=xdg_data_home,
            base_url=base_url,
        )

    assert result.returncode != 0
    assert "launcher differs" in result.stderr.lower()
    assert not (install_root / ".release-state").exists()
    assert source_release.is_dir()
    assert target_release.is_dir()
    assert (install_root / "surgepilot").read_bytes() == (
        target_payload / "surgepilot-dispatcher"
    ).read_bytes()


def test_schema1_upgrade_rejects_symlinked_private_state_before_publication(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    xdg_data_home = tmp_path / "data"
    source_assets = tmp_path / "source-assets"
    source_assets.mkdir()
    source_installer = render_installer(source_assets, "v1.1.0")
    write_release_assets(source_assets, version="v1.1.0")
    with serve(source_assets) as base_url:
        first = run_installer(
            source_installer,
            home=home,
            xdg_data_home=xdg_data_home,
            base_url=base_url,
        )
    assert first.returncode == 0, first.stderr
    install_root = xdg_data_home / "surgepilot"
    state = install_root / ".release-state"
    state.write_text("schema=1\nphase=stable\ntarget=v1.1.0\nbase=v1.1.0\n", encoding="utf-8")
    state.chmod(0o600)
    unsafe_target = tmp_path / "unsafe-private-state"
    unsafe_target.mkdir()
    (install_root / ".surgepilot").symlink_to(unsafe_target)
    target_assets = tmp_path / "target-assets"
    target_assets.mkdir()
    target_installer = render_installer(target_assets, "v1.2.0")
    write_release_assets(target_assets, version="v1.2.0")

    with serve(target_assets) as base_url:
        result = run_installer(
            target_installer,
            home=home,
            xdg_data_home=xdg_data_home,
            base_url=base_url,
        )

    assert result.returncode != 0
    assert "private state is unsafe" in result.stderr.lower()
    assert "target=v1.1.0" in state.read_text(encoding="utf-8")
    assert not (install_root / ".releases/v1.2.0").exists()


@pytest.mark.parametrize("owner_pid", [os.getpid(), 999999])
def test_upgrade_installer_never_reclaims_existing_deployment_lock(
    tmp_path: Path, owner_pid: int
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    xdg_data_home = tmp_path / "data"
    source_assets = tmp_path / "source-assets"
    source_assets.mkdir()
    source_installer = render_installer(source_assets, "v1.1.0")
    write_release_assets(source_assets, version="v1.1.0")
    with serve(source_assets) as base_url:
        first = run_installer(
            source_installer,
            home=home,
            xdg_data_home=xdg_data_home,
            base_url=base_url,
        )
    assert first.returncode == 0, first.stderr
    install_root = xdg_data_home / "surgepilot"
    state = install_root / ".release-state"
    state.write_text("schema=1\nphase=stable\ntarget=v1.1.0\nbase=v1.1.0\n", encoding="utf-8")
    state.chmod(0o600)
    lock = Path(f"{install_root}.lock")
    lock.mkdir(mode=0o700)
    owner = lock / "owner"
    owner.write_text(f"schema=1\npid={owner_pid}\nnonce=test-lock\n", encoding="utf-8")
    owner.chmod(0o600)

    target_assets = tmp_path / "target-assets"
    target_assets.mkdir()
    target_installer = render_installer(target_assets, "v1.2.0")
    write_release_assets(target_assets, version="v1.2.0")
    with serve(target_assets) as base_url:
        result = run_installer(
            target_installer,
            home=home,
            xdg_data_home=xdg_data_home,
            base_url=base_url,
        )

    assert result.returncode != 0
    assert ("running" if owner_pid == os.getpid() else "stale") in result.stderr.lower()
    assert lock.is_dir()
    assert owner.is_file()
    assert "target=v1.1.0" in state.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("case", "expected_error"),
    [
        ("checksum", "checksum"),
        ("payload", "member"),
        ("version", "version"),
    ],
)
def test_installer_rejects_invalid_release_before_publication(
    tmp_path: Path,
    case: str,
    expected_error: str,
) -> None:
    assets = tmp_path / "assets"
    assets.mkdir()
    installer = render_installer(assets)
    _, sidecar = write_release_assets(
        assets,
        manifest_version="v9.9.9" if case == "version" else None,
        omit="compose/docker-compose.yml" if case == "payload" else None,
    )
    if case == "checksum":
        sidecar.write_text(f"{'0' * 64}  surgepilot-{VERSION}.tar.gz\n", encoding="utf-8")
    home = tmp_path / "home"
    home.mkdir()
    xdg_data_home = tmp_path / "data"

    with serve(assets) as base_url:
        result = run_installer(
            installer,
            home=home,
            xdg_data_home=xdg_data_home,
            base_url=base_url,
        )

    assert result.returncode != 0
    assert expected_error in result.stderr.lower()
    assert not (xdg_data_home / "surgepilot").exists()
    assert not (home / ".local/bin/surgepilot").exists()


def test_installer_rejects_nested_matching_version_when_top_level_manifest_mismatches(
    tmp_path: Path,
) -> None:
    assets = tmp_path / "assets"
    assets.mkdir()
    installer = render_installer(assets)
    write_release_assets(
        assets,
        manifest_text=(
            f'{{\n  "version": "v9.9.9",\n  "nested": {{\n  "version": "{VERSION}"\n  }}\n}}\n'
        ),
    )
    home = tmp_path / "home"
    home.mkdir()
    xdg_data_home = tmp_path / "data"

    with serve(assets) as base_url:
        result = run_installer(
            installer,
            home=home,
            xdg_data_home=xdg_data_home,
            base_url=base_url,
        )

    assert result.returncode != 0
    assert "version" in result.stderr.lower()
    assert not (xdg_data_home / "surgepilot").exists()
    assert not (home / ".local/bin/surgepilot").exists()


@pytest.mark.parametrize(
    ("asset_kwargs", "expected_error"),
    [
        ({"extra_file": "unexpected.txt"}, "unexpected"),
        ({"symlink_readme": True}, "type"),
        ({"omit": "scripts/release_preflight.py"}, "member"),
    ],
)
def test_installer_rejects_unbounded_or_non_regular_archive_members(
    tmp_path: Path,
    asset_kwargs: dict[str, object],
    expected_error: str,
) -> None:
    assets = tmp_path / "assets"
    assets.mkdir()
    installer = render_installer(assets)
    write_release_assets(assets, **asset_kwargs)
    home = tmp_path / "home"
    home.mkdir()
    xdg_data_home = tmp_path / "data"

    with serve(assets) as base_url:
        result = run_installer(
            installer,
            home=home,
            xdg_data_home=xdg_data_home,
            base_url=base_url,
        )

    assert result.returncode != 0
    assert expected_error in result.stderr.lower()
    assert not (xdg_data_home / "surgepilot").exists()
    assert not (home / ".local/bin/surgepilot").exists()


@pytest.mark.parametrize("signal_name", ["HUP", "INT", "TERM"])
@pytest.mark.parametrize("move_number", [1, 2])
def test_installer_signal_during_publication_never_leaves_partial_state(
    tmp_path: Path,
    signal_name: str,
    move_number: int,
) -> None:
    assets = tmp_path / "assets"
    assets.mkdir()
    installer = render_installer(assets)
    write_release_assets(assets)
    home = tmp_path / "home"
    home.mkdir()
    xdg_data_home = tmp_path / "data"
    tools = Path(
        isolated_tool_path(
            tmp_path / "tools",
            uname_output=platform.system(),
            include_checksum_tool=True,
        )
    )
    real_mv = shutil.which("mv")
    assert real_mv is not None
    (tools / "mv").unlink()
    (tools / "mv").write_text(
        "#!/bin/sh\n"
        f'{real_mv} "$@"\n'
        "count=0\n"
        'if [ -e "$SURGEPILOT_TEST_MV_COUNT" ]; then\n'
        '  count=$(cat "$SURGEPILOT_TEST_MV_COUNT")\n'
        "fi\n"
        "count=$((count + 1))\n"
        'printf \'%s\\n\' "$count" > "$SURGEPILOT_TEST_MV_COUNT"\n'
        'if [ "$count" -eq "$SURGEPILOT_TEST_SIGNAL_MOVE" ]; then\n'
        '  : > "$SURGEPILOT_TEST_MV_SIGNAL_SENT"\n'
        '  kill -"$SURGEPILOT_TEST_SIGNAL_NAME" "$PPID"\n'
        "fi\n",
        encoding="utf-8",
    )
    (tools / "mv").chmod(0o755)
    move_count = tmp_path / "mv-count"
    signal_marker = tmp_path / "mv-signal-sent"

    environment = os.environ.copy()
    environment.update(
        {
            "HOME": str(home),
            "XDG_DATA_HOME": str(xdg_data_home),
            "PATH": str(tools),
            "SURGEPILOT_INSTALLER_RELEASE_BASE_URL": "unused",
            "SURGEPILOT_TEST_MV_COUNT": str(move_count),
            "SURGEPILOT_TEST_MV_SIGNAL_SENT": str(signal_marker),
            "SURGEPILOT_TEST_SIGNAL_MOVE": str(move_number),
            "SURGEPILOT_TEST_SIGNAL_NAME": signal_name,
        }
    )
    with serve(assets) as base_url:
        environment["SURGEPILOT_INSTALLER_RELEASE_BASE_URL"] = base_url
        result = subprocess.run(
            ["sh"],
            input=installer.read_text(encoding="utf-8"),
            env=environment,
            text=True,
            capture_output=True,
            timeout=30,
        )

    install_root = xdg_data_home / "surgepilot"
    launcher = home / ".local/bin/surgepilot"
    assert signal_marker.is_file()
    assert move_count.read_text(encoding="utf-8") == "2\n"
    assert result.returncode == 0, result.stderr
    assert install_root.is_dir()
    assert launcher.is_file()


@pytest.mark.parametrize("occupied", ["install", "launcher"])
def test_installer_never_overwrites_existing_destination(tmp_path: Path, occupied: str) -> None:
    assets = tmp_path / "assets"
    assets.mkdir()
    installer = render_installer(assets)
    write_release_assets(assets)
    home = tmp_path / "home"
    home.mkdir()
    xdg_data_home = tmp_path / "data"
    install_root = xdg_data_home / "surgepilot"
    launcher = home / ".local/bin/surgepilot"
    target = install_root if occupied == "install" else launcher
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("keep-me\n", encoding="utf-8")

    with serve(assets) as base_url:
        result = run_installer(
            installer,
            home=home,
            xdg_data_home=xdg_data_home,
            base_url=base_url,
        )

    assert result.returncode != 0
    assert "already exists" in result.stderr.lower()
    assert target.read_text(encoding="utf-8") == "keep-me\n"
    other = launcher if occupied == "install" else install_root
    assert not other.exists()


def test_installer_rejects_unsupported_operating_system_before_download(tmp_path: Path) -> None:
    assets = tmp_path / "assets"
    assets.mkdir()
    installer = render_installer(assets)
    home = tmp_path / "home"
    home.mkdir()
    xdg_data_home = tmp_path / "data"
    tools = isolated_tool_path(
        tmp_path / "tools",
        uname_output="FreeBSD",
        include_checksum_tool=False,
    )

    result = run_installer(
        installer,
        home=home,
        xdg_data_home=xdg_data_home,
        base_url="http://127.0.0.1:1",
        path=tools,
    )

    assert result.returncode != 0
    assert "unsupported operating system" in result.stderr.lower()
    assert not (xdg_data_home / "surgepilot").exists()
    assert not (home / ".local/bin/surgepilot").exists()


def test_installer_requires_platform_checksum_tool_before_download(tmp_path: Path) -> None:
    assets = tmp_path / "assets"
    assets.mkdir()
    installer = render_installer(assets)
    home = tmp_path / "home"
    home.mkdir()
    xdg_data_home = tmp_path / "data"
    tools = isolated_tool_path(
        tmp_path / "tools",
        uname_output="Linux",
        include_checksum_tool=False,
    )

    result = run_installer(
        installer,
        home=home,
        xdg_data_home=xdg_data_home,
        base_url="http://127.0.0.1:1",
        path=tools,
    )

    assert result.returncode != 0
    assert "sha256sum" in result.stderr
    assert not (xdg_data_home / "surgepilot").exists()
    assert not (home / ".local/bin/surgepilot").exists()


def test_installer_reports_failed_download_without_publication(tmp_path: Path) -> None:
    assets = tmp_path / "assets"
    assets.mkdir()
    installer = render_installer(assets)
    home = tmp_path / "home"
    home.mkdir()
    xdg_data_home = tmp_path / "data"

    with serve(assets) as base_url:
        result = run_installer(
            installer,
            home=home,
            xdg_data_home=xdg_data_home,
            base_url=base_url,
        )

    assert result.returncode != 0
    assert "download" in result.stderr.lower()
    assert not (xdg_data_home / "surgepilot").exists()
    assert not (home / ".local/bin/surgepilot").exists()


def test_installer_is_posix_bounded_and_does_not_start_or_escalate() -> None:
    if not INSTALLER_TEMPLATE.is_file():
        pytest.fail("release installer template is missing")
    installer = INSTALLER_TEMPLATE.read_text(encoding="utf-8")

    assert installer.startswith("#!/bin/sh\n")
    assert "@@RELEASE_VERSION@@" in installer
    assert "sudo" not in installer
    assert re.search(r"(^|\s)docker(\s|$)", installer) is None
    assert ".zshrc" not in installer
    assert ".bashrc" not in installer
    assert "python" not in installer.lower()
    assert "node" not in installer.lower()
    assert "jq" not in installer
    assert "gh " not in installer
