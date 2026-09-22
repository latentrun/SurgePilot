from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import release_preflight  # noqa: E402


def test_prepare_preview_runtime_directory_creates_private_empty_directory(
    tmp_path: Path,
) -> None:
    target = tmp_path / "nested" / "preview-empty"

    release_preflight.prepare_preview_runtime_directory(target)

    assert target.is_dir()
    assert target.stat().st_uid == os.geteuid()
    assert target.stat().st_mode & 0o777 == 0o700
    assert list(target.iterdir()) == []


def test_prepare_preview_runtime_directory_rejects_relative_path() -> None:
    with pytest.raises(release_preflight.ReleasePreflightError, match="absolute"):
        release_preflight.prepare_preview_runtime_directory(Path("relative-preview"))


@pytest.mark.parametrize("invalid_kind", ["symlink", "file", "nonempty", "permissions"])
def test_prepare_preview_runtime_directory_rejects_unsafe_existing_path(
    tmp_path: Path, invalid_kind: str
) -> None:
    target = tmp_path / "preview-empty"
    if invalid_kind == "symlink":
        real_target = tmp_path / "real"
        real_target.mkdir(mode=0o700)
        target.symlink_to(real_target, target_is_directory=True)
    elif invalid_kind == "file":
        target.write_text("not a directory", encoding="utf-8")
    else:
        target.mkdir(mode=0o700)
        if invalid_kind == "nonempty":
            (target / "unexpected").write_text("runtime", encoding="utf-8")
        else:
            target.chmod(0o755)

    with pytest.raises(release_preflight.ReleasePreflightError, match="Preview Runtime"):
        release_preflight.prepare_preview_runtime_directory(target)


def test_prepare_preview_runtime_directory_rejects_foreign_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "preview-empty"
    target.mkdir(mode=0o700)
    current_uid = os.geteuid()
    monkeypatch.setattr(release_preflight.os, "geteuid", lambda: current_uid + 1)

    with pytest.raises(release_preflight.ReleasePreflightError, match="host user"):
        release_preflight.prepare_preview_runtime_directory(target)


def write_manifest(root: Path, *, version: str = "v0.3.0") -> None:
    (root / "release-manifest.json").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "version": version,
                "minimumUpgradeVersion": "v0.1.0",
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
                "runtimes": {
                    "amd64": {
                        "archive": f"surgepilot-runtime-linux-amd64-{version}.tar.gz",
                        "sha256": "4" * 64,
                        "sha256Sidecar": (
                            f"surgepilot-runtime-linux-amd64-{version}.tar.gz.sha256"
                        ),
                        "manifest": (f"surgepilot-runtime-linux-amd64-{version}.manifest.json"),
                    },
                    "arm64": {
                        "archive": f"surgepilot-runtime-linux-arm64-{version}.tar.gz",
                        "sha256": "5" * 64,
                        "sha256Sidecar": (
                            f"surgepilot-runtime-linux-arm64-{version}.tar.gz.sha256"
                        ),
                        "manifest": (f"surgepilot-runtime-linux-arm64-{version}.manifest.json"),
                    },
                },
            }
        ),
        encoding="utf-8",
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [("x86_64", "amd64"), ("amd64", "amd64"), ("aarch64", "arm64"), ("arm64", "arm64")],
)
def test_normalize_daemon_arch_uses_docker_daemon_values(value: str, expected: str) -> None:
    assert release_preflight.normalize_daemon_arch(value) == expected


def test_normalize_daemon_arch_rejects_unknown_architecture() -> None:
    with pytest.raises(release_preflight.ReleasePreflightError, match="unsupported Docker daemon"):
        release_preflight.normalize_daemon_arch("riscv64")


@pytest.mark.parametrize(
    ("configured", "demo_enabled", "daemon_arch", "expected"),
    [
        ("auto", True, "amd64", ("amd64",)),
        ("auto", True, "arm64", ("arm64",)),
        ("auto", False, "amd64", ("amd64",)),
        ("auto", False, "arm64", ("arm64",)),
        ("amd64", False, "arm64", ("amd64",)),
        ("arm64", True, "arm64", ("arm64",)),
        ("amd64,arm64", False, "amd64", ("amd64", "arm64")),
    ],
)
def test_resolve_runtime_architectures(
    configured: str,
    demo_enabled: bool,
    daemon_arch: str,
    expected: tuple[str, ...],
) -> None:
    assert (
        release_preflight.resolve_runtime_architectures(
            configured=configured,
            demo_enabled=demo_enabled,
            daemon_arch=daemon_arch,
            forced_platform="",
        )
        == expected
    )


def test_auto_demo_rejects_forced_platform_mismatch() -> None:
    with pytest.raises(release_preflight.ReleasePreflightError, match="forced Docker platform"):
        release_preflight.resolve_runtime_architectures(
            configured="auto",
            demo_enabled=True,
            daemon_arch="arm64",
            forced_platform="linux/amd64",
        )


@pytest.mark.parametrize("configured", ["amd64", "amd64,arm64"])
def test_demo_explicit_architectures_require_native_runtime_and_platform(
    configured: str,
) -> None:
    with pytest.raises(release_preflight.ReleasePreflightError, match="daemon architecture"):
        release_preflight.resolve_runtime_architectures(
            configured="amd64",
            demo_enabled=True,
            daemon_arch="arm64",
            forced_platform="",
        )
    with pytest.raises(release_preflight.ReleasePreflightError, match="forced Docker platform"):
        release_preflight.resolve_runtime_architectures(
            configured=configured,
            demo_enabled=True,
            daemon_arch="arm64",
            forced_platform="linux/amd64",
        )
    with pytest.raises(release_preflight.ReleasePreflightError, match="DOCKER_DEFAULT_PLATFORM"):
        release_preflight.resolve_runtime_architectures(
            configured="auto",
            demo_enabled=True,
            daemon_arch="amd64",
            forced_platform="windows/amd64",
        )


@pytest.mark.parametrize("configured", ["", "auto,amd64", "amd64,amd64", "riscv64"])
def test_runtime_architecture_set_rejects_invalid_values(configured: str) -> None:
    with pytest.raises(release_preflight.ReleasePreflightError):
        release_preflight.resolve_runtime_architectures(
            configured=configured,
            demo_enabled=False,
            daemon_arch="amd64",
            forced_platform="",
        )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("192.168.1.20", "192.168.1.20"),
        ("SurgePilot.LAN", "surgepilot.lan"),
        ("münich.example", "xn--mnich-kva.example"),
        ("2001:db8::20", "[2001:db8::20]"),
        ("[2001:db8::20]", "[2001:db8::20]"),
    ],
)
def test_normalize_lan_host_accepts_reachable_host_forms(raw: str, expected: str) -> None:
    assert release_preflight.normalize_lan_host(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("localhost", "localhost"),
        ("127.0.0.1", "127.0.0.1"),
        ("::1", "[::1]"),
        ("[::1]", "[::1]"),
    ],
)
def test_normalize_lan_host_accepts_explicit_canonical_local_only_forms(
    raw: str, expected: str
) -> None:
    assert release_preflight.normalize_lan_host(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "127.0.0.2",
        "[::ffff:127.0.0.1]",
        "[[2001:db8::20]]",
        "[2001:db8::20",
        "2001:db8::20]",
        "load[pilot.lan",
        "[surgepilot.lan]",
        "[192.168.1.20]",
        "bad_host",
        "fe80::1%eth0",
        "host.docker.internal",
        "api.surgepilot.test",
        "nginx",
        "web",
        "postgres",
        "minio",
        "grafana",
        "demo-load-node",
        "224.0.0.1",
        "ff02::1",
    ],
)
def test_normalize_lan_host_rejects_unsafe_or_ambiguous_values(raw: str) -> None:
    with pytest.raises(release_preflight.ReleasePreflightError):
        release_preflight.normalize_lan_host(raw)


@pytest.mark.parametrize(
    "raw",
    ["127.1", "127.0.0.01", "2130706433", "0177.0.0.1", "0x7f000001"],
)
def test_normalize_lan_host_rejects_legacy_ipv4_notation(raw: str) -> None:
    with pytest.raises(
        release_preflight.ReleasePreflightError,
        match="canonical IPv4 address notation",
    ):
        release_preflight.normalize_lan_host(raw)


@pytest.mark.parametrize(
    "raw",
    ["ｌｏｃａｌｈｏｓｔ", "0x７f000001", "２１３０７０６４３３", "１２７.０.０.１", "ｍｉｎｉｏ"],
)
def test_normalize_lan_host_revalidates_idna_normalized_values(raw: str) -> None:
    with pytest.raises(release_preflight.ReleasePreflightError):
        release_preflight.normalize_lan_host(raw)


def test_normalize_release_bootstrap_builds_consistent_direct_lan_environment() -> None:
    values = release_preflight.normalize_release_bootstrap(
        host="[2001:db8::20]",
        http_port="18080",
        influx_port="18086",
        runtime_architectures="auto",
        daemon_arch="arm64",
        forced_platform="",
    )

    assert values == {
        "SURGEPILOT_HTTP_PORT": "18080",
        "SURGEPILOT_NODE_API_BASE_URL": "http://[2001:db8::20]:18080",
        "SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT": "18086",
        "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL": "http://[2001:db8::20]:18086",
        "SURGEPILOT_DEMO_LOAD_NODE_ENABLED": "false",
        "SURGEPILOT_RUNTIME_ARCHITECTURES": "auto",
        "SESSION_COOKIE_SECURE": "false",
    }


@pytest.mark.parametrize(
    ("http_port", "influx_port"),
    [("", "8086"), ("0", "8086"), ("65536", "8086"), ("8080", "8080")],
)
def test_normalize_release_bootstrap_rejects_invalid_or_duplicate_ports(
    http_port: str, influx_port: str
) -> None:
    with pytest.raises(release_preflight.ReleasePreflightError, match="port"):
        release_preflight.normalize_release_bootstrap(
            host="192.168.1.20",
            http_port=http_port,
            influx_port=influx_port,
            runtime_architectures="auto",
            daemon_arch="amd64",
            forced_platform="",
        )


def direct_release_environment() -> dict[str, str]:
    return {
        "SURGEPILOT_HTTP_PORT": "8080",
        "SURGEPILOT_NODE_API_BASE_URL": "http://192.168.1.20:8080",
        "SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT": "8086",
        "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL": "http://192.168.1.20:8086",
        "SURGEPILOT_DEMO_LOAD_NODE_ENABLED": "false",
        "SURGEPILOT_RUNTIME_ARCHITECTURES": "auto",
        "SESSION_COOKIE_SECURE": "false",
    }


def write_release_environment(root: Path, values: dict[str, str] | None = None) -> None:
    effective = direct_release_environment() if values is None else values
    (root / ".env").write_text(
        "".join(f"{key}={value}\n" for key, value in effective.items()),
        encoding="utf-8",
    )


def write_release_environment_with_quoted_value(root: Path, *, key: str, value: str) -> None:
    effective = direct_release_environment()
    effective[key] = f'"{value}"'
    write_release_environment(root, effective)


def test_describe_release_environment_returns_fixed_non_secret_direct_lan_fields(
    tmp_path: Path,
) -> None:
    values = direct_release_environment()
    values["SURGEPILOT_RUNTIME_ARCHITECTURES"] = "amd64,arm64"
    values["POSTGRES_PASSWORD"] = "database-secret-value"
    values["SURGEPILOT_RUNNER_TOKEN"] = "runner-secret-value"
    env_bytes = "".join(f"{key}={value}\n" for key, value in values.items()).encode()
    (tmp_path / ".env").write_bytes(env_bytes)

    description = release_preflight.describe_release_environment(
        tmp_path,
        daemon_arch="x86_64",
        forced_platform="",
    )

    assert description == {
        "SURGEPILOT_CONFIG_MODE": "direct_lan_http",
        "SURGEPILOT_CONFIG_HOST": "192.168.1.20",
        "SURGEPILOT_HTTP_PORT": "8080",
        "SURGEPILOT_NODE_API_BASE_URL": "http://192.168.1.20:8080",
        "SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT": "8086",
        "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL": "http://192.168.1.20:8086",
        "SURGEPILOT_RUNTIME_ARCHITECTURES": "amd64,arm64",
        "SURGEPILOT_SELECTED_RUNTIME_ARCHITECTURES": "amd64,arm64",
        "SURGEPILOT_DEMO_LOAD_NODE_ENABLED": "false",
        "SURGEPILOT_ENV_SHA256": hashlib.sha256(env_bytes).hexdigest(),
    }
    assert not any("PASSWORD" in key or "TOKEN" in key or "SECRET" in key for key in description)


def test_describe_release_environment_restores_brackets_around_ipv6_host(
    tmp_path: Path,
) -> None:
    values = direct_release_environment()
    values.update(
        {
            "SURGEPILOT_NODE_API_BASE_URL": "http://[2001:db8::20]:8080",
            "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL": ("http://[2001:db8::20]:8086"),
        }
    )
    write_release_environment(tmp_path, values)

    description = release_preflight.describe_release_environment(
        tmp_path,
        daemon_arch="amd64",
        forced_platform="",
    )

    assert description["SURGEPILOT_CONFIG_MODE"] == "direct_lan_http"
    assert description["SURGEPILOT_CONFIG_HOST"] == "[2001:db8::20]"


def test_describe_release_environment_classifies_advanced_https_without_quick_path_host(
    tmp_path: Path,
) -> None:
    values = direct_release_environment()
    values.update(
        {
            "SURGEPILOT_NODE_API_BASE_URL": "https://surgepilot.example.com",
            "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL": ("https://metrics.example.com"),
            "SESSION_COOKIE_SECURE": "true",
        }
    )
    write_release_environment(tmp_path, values)

    description = release_preflight.describe_release_environment(
        tmp_path,
        daemon_arch="arm64",
        forced_platform="",
    )

    assert description["SURGEPILOT_CONFIG_MODE"] == "advanced_https"
    assert description["SURGEPILOT_CONFIG_HOST"] == ""
    assert description["SURGEPILOT_SELECTED_RUNTIME_ARCHITECTURES"] == "arm64"


@pytest.mark.parametrize(
    ("url_key", "port"),
    [
        ("SURGEPILOT_NODE_API_BASE_URL", "8080"),
        ("SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL", "8086"),
    ],
)
@pytest.mark.parametrize("escaped_control", [r"\r", r"\n", r"\t"])
def test_describe_release_environment_rejects_dotenv_escaped_url_controls(
    tmp_path: Path,
    url_key: str,
    port: str,
    escaped_control: str,
) -> None:
    injected_url = f"http://192.168.1.20:{port[:2]}{escaped_control}{port[2:]}"
    write_release_environment_with_quoted_value(
        tmp_path,
        key=url_key,
        value=injected_url,
    )

    with pytest.raises(release_preflight.ReleasePreflightError, match=url_key):
        release_preflight.describe_release_environment(
            tmp_path,
            daemon_arch="amd64",
            forced_platform="",
        )


def test_validate_release_environment_requires_complete_consistent_direct_lan_values() -> None:
    values = direct_release_environment()

    assert release_preflight.validate_release_environment(
        values, daemon_arch="amd64", forced_platform=""
    ) == ("amd64",)

    for missing in values:
        incomplete = values.copy()
        incomplete.pop(missing)
        with pytest.raises(release_preflight.ReleasePreflightError, match=missing):
            release_preflight.validate_release_environment(
                incomplete, daemon_arch="amd64", forced_platform=""
            )


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "[::1]"])
def test_validate_release_environment_allows_local_only_when_demo_is_disabled(
    host: str,
) -> None:
    values = direct_release_environment()
    values["SURGEPILOT_NODE_API_BASE_URL"] = f"http://{host}:8080"
    values["SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL"] = f"http://{host}:8086"

    assert release_preflight.validate_release_environment(
        values, daemon_arch="amd64", forced_platform=""
    ) == ("amd64",)


def test_validate_release_environment_rejects_local_only_when_demo_is_enabled() -> None:
    values = direct_release_environment()
    values.update(
        {
            "SURGEPILOT_NODE_API_BASE_URL": "http://127.0.0.1:8080",
            "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL": "http://127.0.0.1:8086",
            "SURGEPILOT_DEMO_LOAD_NODE_ENABLED": "true",
        }
    )

    with pytest.raises(release_preflight.ReleasePreflightError, match="Demo Load Node"):
        release_preflight.validate_release_environment(
            values, daemon_arch="amd64", forced_platform=""
        )


@pytest.mark.parametrize("demo_enabled", ["false", "true"])
@pytest.mark.parametrize(
    "host",
    ["127.1", "127.0.0.01", "2130706433", "0177.0.0.1", "0x7f000001"],
)
def test_validate_release_environment_rejects_legacy_ipv4_notation(
    host: str, demo_enabled: str
) -> None:
    values = direct_release_environment()
    values.update(
        {
            "SURGEPILOT_NODE_API_BASE_URL": f"http://{host}:8080",
            "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL": f"http://{host}:8086",
            "SURGEPILOT_DEMO_LOAD_NODE_ENABLED": demo_enabled,
        }
    )

    with pytest.raises(
        release_preflight.ReleasePreflightError,
        match="canonical IPv4 address notation",
    ):
        release_preflight.validate_release_environment(
            values, daemon_arch="amd64", forced_platform=""
        )


@pytest.mark.parametrize("demo_enabled", ["false", "true"])
@pytest.mark.parametrize(
    "host",
    ["ｌｏｃａｌｈｏｓｔ", "0x７f000001", "２１３０７０６４３３", "１２７.０.０.１", "ｍｉｎｉｏ"],
)
def test_validate_release_environment_revalidates_idna_normalized_hosts(
    host: str, demo_enabled: str
) -> None:
    values = direct_release_environment()
    values.update(
        {
            "SURGEPILOT_NODE_API_BASE_URL": f"http://{host}:8080",
            "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL": f"http://{host}:8086",
            "SURGEPILOT_DEMO_LOAD_NODE_ENABLED": demo_enabled,
        }
    )

    with pytest.raises(release_preflight.ReleasePreflightError):
        release_preflight.validate_release_environment(
            values, daemon_arch="amd64", forced_platform=""
        )


def test_validate_release_environment_normalizes_malformed_origin_error() -> None:
    values = direct_release_environment()
    values["SURGEPILOT_NODE_API_BASE_URL"] = "http://[::1:8080"
    values["SURGEPILOT_DEMO_LOAD_NODE_ENABLED"] = "true"

    with pytest.raises(release_preflight.ReleasePreflightError, match="absolute"):
        release_preflight.validate_release_environment(
            values, daemon_arch="amd64", forced_platform=""
        )


def test_source_external_url_validation_remains_strict_for_loopback() -> None:
    with pytest.raises(release_preflight.ReleasePreflightError, match="external Load Nodes"):
        release_preflight.validate_external_node_urls(
            {
                "SURGEPILOT_NODE_API_BASE_URL": "http://127.0.0.1:8080",
                "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL": "http://127.0.0.1:8086",
            }
        )


@pytest.mark.parametrize(
    "host",
    ["127.1", "127.0.0.01", "2130706433", "0177.0.0.1", "0x7f000001"],
)
def test_source_external_url_validation_rejects_legacy_ipv4_notation(host: str) -> None:
    with pytest.raises(
        release_preflight.ReleasePreflightError,
        match="canonical IPv4 address notation",
    ):
        release_preflight.validate_external_node_urls(
            {
                "SURGEPILOT_NODE_API_BASE_URL": f"http://{host}:8080",
                "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL": f"http://{host}:8086",
            }
        )


@pytest.mark.parametrize(
    "host",
    ["ｌｏｃａｌｈｏｓｔ", "0x７f000001", "２１３０７０６４３３", "１２７.０.０.１", "ｍｉｎｉｏ"],
)
def test_source_external_url_validation_revalidates_idna_normalized_hosts(host: str) -> None:
    with pytest.raises(release_preflight.ReleasePreflightError):
        release_preflight.validate_external_node_urls(
            {
                "SURGEPILOT_NODE_API_BASE_URL": f"http://{host}:8080",
                "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL": f"http://{host}:8086",
            }
        )


def test_validate_release_environment_rejects_direct_lan_host_or_port_drift() -> None:
    values = direct_release_environment()
    values["SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL"] = "http://192.168.1.21:8086"
    with pytest.raises(release_preflight.ReleasePreflightError, match="same host"):
        release_preflight.validate_release_environment(
            values, daemon_arch="amd64", forced_platform=""
        )

    values = direct_release_environment()
    values["SURGEPILOT_NODE_API_BASE_URL"] = "http://192.168.1.20:18080"
    with pytest.raises(release_preflight.ReleasePreflightError, match="SURGEPILOT_HTTP_PORT"):
        release_preflight.validate_release_environment(
            values, daemon_arch="amd64", forced_platform=""
        )

    values = direct_release_environment()
    values["SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL"] = "http://192.168.1.20:18086"
    with pytest.raises(
        release_preflight.ReleasePreflightError,
        match="SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT",
    ):
        release_preflight.validate_release_environment(
            values, daemon_arch="amd64", forced_platform=""
        )


def test_validate_release_environment_rejects_duplicate_ports_and_https_downgrade() -> None:
    values = direct_release_environment()
    values["SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT"] = "8080"
    with pytest.raises(release_preflight.ReleasePreflightError, match="must be distinct"):
        release_preflight.validate_release_environment(
            values, daemon_arch="amd64", forced_platform=""
        )

    values = direct_release_environment()
    values["SURGEPILOT_NODE_API_BASE_URL"] = "https://surgepilot.example.com"
    values["SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL"] = "https://metrics.example.com"
    with pytest.raises(release_preflight.ReleasePreflightError, match="must use http"):
        release_preflight.validate_release_environment(
            values, daemon_arch="amd64", forced_platform=""
        )


def test_validate_release_environment_allows_explicit_https_proxy_origins() -> None:
    values = direct_release_environment()
    values.update(
        {
            "SURGEPILOT_NODE_API_BASE_URL": "https://surgepilot.example.com",
            "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL": "https://metrics.example.com",
            "SESSION_COOKIE_SECURE": "true",
        }
    )

    assert release_preflight.validate_release_environment(
        values, daemon_arch="arm64", forced_platform=""
    ) == ("arm64",)


def test_validate_release_environment_requires_https_api_for_secure_cookie() -> None:
    values = direct_release_environment()
    values.update(
        {
            "SURGEPILOT_NODE_API_BASE_URL": "http://surgepilot.example.com:8080",
            "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL": "http://metrics.example.com:8086",
            "SESSION_COOKIE_SECURE": "true",
        }
    )

    with pytest.raises(release_preflight.ReleasePreflightError, match="must use https"):
        release_preflight.validate_release_environment(
            values, daemon_arch="amd64", forced_platform=""
        )


@pytest.mark.parametrize("value", ["", "ture", "1", "0", "yes", "no", "on", "off"])
def test_validate_release_environment_rejects_non_strict_cookie_boolean(value: str) -> None:
    values = direct_release_environment()
    values["SESSION_COOKIE_SECURE"] = value

    with pytest.raises(release_preflight.ReleasePreflightError, match="SESSION_COOKIE_SECURE"):
        release_preflight.validate_release_environment(
            values, daemon_arch="amd64", forced_platform=""
        )


@pytest.mark.parametrize(
    ("actual", "minimum"),
    [("26.0.0", "26.0.0"), ("27.2.1", "26.0.0"), ("v2.27.0", "2.27.0")],
)
def test_minimum_version_accepts_supported_versions(actual: str, minimum: str) -> None:
    release_preflight.require_minimum_version("tool", actual, minimum)


def test_minimum_version_rejects_old_or_malformed_versions() -> None:
    with pytest.raises(release_preflight.ReleasePreflightError, match="tool 26.0.0 or newer"):
        release_preflight.require_minimum_version("tool", "25.0.5", "26.0.0")
    with pytest.raises(release_preflight.ReleasePreflightError, match="could not parse"):
        release_preflight.require_minimum_version("tool", "desktop-edge", "26.0.0")


def test_release_manifest_requires_exact_version_and_digest_pins(tmp_path: Path) -> None:
    write_manifest(tmp_path)

    manifest = release_preflight.load_release_manifest(tmp_path, expected_version="v0.3.0")

    assert manifest["version"] == "v0.3.0"
    assert manifest["images"]["api"]["digest"] == f"sha256:{'1' * 64}"

    with pytest.raises(release_preflight.ReleasePreflightError, match="version mismatch"):
        release_preflight.load_release_manifest(tmp_path, expected_version="v0.3.1")


def test_legacy_identity_allows_only_the_missing_upgrade_minimum(tmp_path: Path) -> None:
    write_manifest(tmp_path, version="v1.1.0")
    path = tmp_path / "release-manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    del manifest["minimumUpgradeVersion"]
    path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(release_preflight.ReleasePreflightError, match="minimumUpgradeVersion"):
        release_preflight.release_identity(tmp_path, expected_version="v1.1.0")

    identity = release_preflight.release_identity(
        tmp_path,
        expected_version="v1.1.0",
        require_minimum_upgrade=False,
    )

    assert identity["SURGEPILOT_IDENTITY_VERSION"] == "v1.1.0"


def test_external_node_urls_must_be_supplied_as_a_pair() -> None:
    with pytest.raises(release_preflight.ReleasePreflightError, match="must be set together"):
        release_preflight.validate_external_node_urls(
            {
                "SURGEPILOT_NODE_API_BASE_URL": "https://surgepilot.example.com",
                "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL": "",
            }
        )

    release_preflight.validate_external_node_urls(
        {
            "SURGEPILOT_NODE_API_BASE_URL": "https://surgepilot.example.com",
            "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL": "https://influx.example.com",
        }
    )


@pytest.mark.parametrize(
    "api_url",
    [
        "https://surgepilot.example.com:bad",
        "https://surgepilot.example.com:0",
        "https://surgepilot.example.com:65536",
    ],
)
def test_external_node_urls_reject_invalid_ports(api_url: str) -> None:
    with pytest.raises(release_preflight.ReleasePreflightError, match="port"):
        release_preflight.validate_external_node_urls(
            {
                "SURGEPILOT_NODE_API_BASE_URL": api_url,
                "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL": "https://influx.example.com:8086",
            }
        )


def test_external_node_urls_reject_malformed_ipv6_origin() -> None:
    with pytest.raises(release_preflight.ReleasePreflightError, match="absolute"):
        release_preflight.validate_external_node_urls(
            {
                "SURGEPILOT_NODE_API_BASE_URL": "http://[2001:db8::20:8080",
                "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL": "http://metrics:8086",
            }
        )


@pytest.mark.parametrize(
    "host",
    ["bad host", "-bad", "bad-", "foo_bar", "bad..example", ".bad"],
)
def test_external_node_urls_reject_invalid_dns_hosts(host: str) -> None:
    with pytest.raises(release_preflight.ReleasePreflightError, match="valid DNS hostname"):
        release_preflight.validate_external_node_urls(
            {
                "SURGEPILOT_NODE_API_BASE_URL": f"http://{host}:8080",
                "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL": "http://metrics:8086",
            }
        )
    with pytest.raises(release_preflight.ReleasePreflightError, match="absolute"):
        release_preflight.validate_external_node_urls(
            {
                "SURGEPILOT_NODE_API_BASE_URL": "surgepilot.example.com",
                "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL": "https://influx.example.com",
            }
        )
    with pytest.raises(release_preflight.ReleasePreflightError, match="path"):
        release_preflight.validate_external_node_urls(
            {
                "SURGEPILOT_NODE_API_BASE_URL": "https://surgepilot.example.com/api",
                "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL": "https://influx.example.com",
            }
        )

    release_preflight.validate_external_node_urls(
        {
            "SURGEPILOT_NODE_API_BASE_URL": "http://surgepilot:8080",
            "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL": "http://metrics:8086",
        }
    )


@pytest.mark.parametrize(
    "api_url",
    [
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://host.docker.internal:8080",
        "http://api:8000",
        "http://api.surgepilot.test:8000",
        "http://nginx:8080",
        "http://224.0.0.1:8080",
    ],
)
def test_external_node_api_url_rejects_local_or_compose_only_hosts(api_url: str) -> None:
    with pytest.raises(release_preflight.ReleasePreflightError, match="external Load Nodes"):
        release_preflight.validate_external_node_urls(
            {
                "SURGEPILOT_NODE_API_BASE_URL": api_url,
                "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL": "https://influx.example.com",
            }
        )


@pytest.mark.parametrize(
    "influx_url",
    [
        "http://localhost:8086",
        "http://127.0.0.1:8086",
        "http://host.docker.internal:8086",
        "http://influxdb:8086",
        "http://grafana:8086",
        "http://[ff02::1]:8086",
    ],
)
def test_external_node_influx_url_rejects_local_or_compose_only_hosts(
    influx_url: str,
) -> None:
    with pytest.raises(release_preflight.ReleasePreflightError, match="external Load Nodes"):
        release_preflight.validate_external_node_urls(
            {
                "SURGEPILOT_NODE_API_BASE_URL": "https://surgepilot.example.com",
                "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL": influx_url,
            }
        )


def test_preflight_and_runtime_selection_cli(tmp_path: Path, capsys) -> None:
    write_manifest(tmp_path)
    values = direct_release_environment()
    values["SURGEPILOT_DEMO_LOAD_NODE_ENABLED"] = "true"
    write_release_environment(tmp_path, values)

    assert (
        release_preflight.main(
            [
                "preflight",
                "--root",
                str(tmp_path),
                "--expected-version",
                "v0.3.0",
                "--engine-version",
                "26.0.1",
                "--compose-version",
                "2.27.1",
                "--daemon-arch",
                "aarch64",
            ]
        )
        == 0
    )
    assert (
        release_preflight.main(
            [
                "select-runtime",
                "--root",
                str(tmp_path),
                "--expected-version",
                "v0.3.0",
                "--daemon-arch",
                "arm64",
            ]
        )
        == 0
    )
    assert capsys.readouterr().out.strip() == "arm64"


def test_describe_validated_release_cli_prints_fixed_order_without_secrets(
    tmp_path: Path, capsys
) -> None:
    write_manifest(tmp_path)
    values = direct_release_environment()
    values["SURGEPILOT_RUNTIME_ARCHITECTURES"] = "amd64,arm64"
    values["POSTGRES_PASSWORD"] = "must-not-be-printed"
    write_release_environment(tmp_path, values)
    env_sha256 = hashlib.sha256((tmp_path / ".env").read_bytes()).hexdigest()

    result = release_preflight.main(
        [
            "describe-release",
            "--root",
            str(tmp_path),
            "--expected-version",
            "v0.3.0",
            "--daemon-arch",
            "x86_64",
            "--forced-platform",
            "",
        ]
    )

    assert result == 0
    stdout = capsys.readouterr().out
    assert stdout.splitlines() == [
        "SURGEPILOT_CONFIG_MODE=direct_lan_http",
        "SURGEPILOT_CONFIG_HOST=192.168.1.20",
        "SURGEPILOT_HTTP_PORT=8080",
        "SURGEPILOT_NODE_API_BASE_URL=http://192.168.1.20:8080",
        "SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT=8086",
        "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL=http://192.168.1.20:8086",
        "SURGEPILOT_RUNTIME_ARCHITECTURES=amd64,arm64",
        "SURGEPILOT_SELECTED_RUNTIME_ARCHITECTURES=amd64,arm64",
        "SURGEPILOT_DEMO_LOAD_NODE_ENABLED=false",
        f"SURGEPILOT_ENV_SHA256={env_sha256}",
    ]
    assert "must-not-be-printed" not in stdout
    assert "PASSWORD" not in stdout


def test_describe_identity_prints_exact_manifest_identity(tmp_path: Path, capsys) -> None:
    write_manifest(tmp_path)

    result = release_preflight.main(
        [
            "describe-identity",
            "--root",
            str(tmp_path),
            "--expected-version",
            "v0.3.0",
        ]
    )

    assert result == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == "SURGEPILOT_IDENTITY_VERSION=v0.3.0"
    assert lines[1].startswith("SURGEPILOT_IDENTITY_REVISION=")
    assert lines[2].startswith("SURGEPILOT_IDENTITY_API_IMAGE=ghcr.io/latentrun/surgepilot-api@")
    assert lines[3].startswith("SURGEPILOT_IDENTITY_WEB_IMAGE=ghcr.io/latentrun/surgepilot-web@")
    assert lines[4].startswith(
        "SURGEPILOT_IDENTITY_DEMO_IMAGE=ghcr.io/latentrun/surgepilot-demo-node@"
    )


def test_describe_release_reads_manifest_and_environment_from_separate_roots(
    tmp_path: Path, capsys
) -> None:
    release_root = tmp_path / "release"
    deployment_root = tmp_path / "deployment"
    release_root.mkdir()
    deployment_root.mkdir()
    write_manifest(release_root)
    write_release_environment(deployment_root, direct_release_environment())

    result = release_preflight.main(
        [
            "describe-release",
            "--root",
            str(release_root),
            "--deployment-root",
            str(deployment_root),
            "--expected-version",
            "v0.3.0",
            "--daemon-arch",
            "amd64",
        ]
    )

    assert result == 0
    assert "SURGEPILOT_HTTP_PORT=8080" in capsys.readouterr().out


def test_select_runtime_reads_environment_from_deployment_root(tmp_path: Path, capsys) -> None:
    release_root = tmp_path / "release"
    deployment_root = tmp_path / "deployment"
    release_root.mkdir()
    deployment_root.mkdir()
    write_manifest(release_root)
    write_release_environment(deployment_root, direct_release_environment())

    result = release_preflight.main(
        [
            "select-runtime",
            "--root",
            str(release_root),
            "--deployment-root",
            str(deployment_root),
            "--expected-version",
            "v0.3.0",
            "--daemon-arch",
            "amd64",
        ]
    )

    assert result == 0
    assert capsys.readouterr().out.strip() == "amd64"


def test_describe_validated_release_cli_rejects_invalid_existing_environment(
    tmp_path: Path, capsys
) -> None:
    write_manifest(tmp_path)
    values = direct_release_environment()
    values.pop("SURGEPILOT_HTTP_PORT")
    values["POSTGRES_PASSWORD"] = "must-not-be-printed"
    write_release_environment(tmp_path, values)

    result = release_preflight.main(
        [
            "describe-release",
            "--root",
            str(tmp_path),
            "--expected-version",
            "v0.3.0",
            "--daemon-arch",
            "amd64",
        ]
    )

    assert result == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "existing .env is missing required SURGEPILOT_HTTP_PORT" in captured.err
    assert "must-not-be-printed" not in captured.err


def test_describe_validated_release_cli_never_emits_control_injected_extra_lines(
    tmp_path: Path, capsys
) -> None:
    write_manifest(tmp_path)
    write_release_environment_with_quoted_value(
        tmp_path,
        key="SURGEPILOT_NODE_API_BASE_URL",
        value=r"http://192.168.1.20:80\n80",
    )

    result = release_preflight.main(
        [
            "describe-release",
            "--root",
            str(tmp_path),
            "--expected-version",
            "v0.3.0",
            "--daemon-arch",
            "amd64",
        ]
    )

    assert result == 2
    captured = capsys.readouterr()
    assert len(captured.out.splitlines()) <= len(
        release_preflight.RELEASE_ENVIRONMENT_DESCRIPTION_KEYS
    )
    assert all(
        line.partition("=")[0] in release_preflight.RELEASE_ENVIRONMENT_DESCRIPTION_KEYS
        for line in captured.out.splitlines()
    )
    assert captured.out == ""
    assert "SURGEPILOT_NODE_API_BASE_URL" in captured.err


def test_normalize_bootstrap_cli_prints_fixed_environment_contract(capsys) -> None:
    result = release_preflight.main(
        [
            "normalize-bootstrap",
            "--host",
            "192.168.1.20",
            "--http-port",
            "8080",
            "--influx-port",
            "8086",
            "--runtime-architectures",
            "auto",
            "--daemon-arch",
            "amd64",
        ]
    )

    assert result == 0
    assert capsys.readouterr().out.splitlines() == [
        "SURGEPILOT_HTTP_PORT=8080",
        "SURGEPILOT_NODE_API_BASE_URL=http://192.168.1.20:8080",
        "SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT=8086",
        "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL=http://192.168.1.20:8086",
        "SURGEPILOT_DEMO_LOAD_NODE_ENABLED=false",
        "SURGEPILOT_RUNTIME_ARCHITECTURES=auto",
        "SESSION_COOKIE_SECURE=false",
    ]


def test_preflight_cli_reports_safe_error(tmp_path: Path, capsys) -> None:
    write_manifest(tmp_path)

    result = release_preflight.main(
        [
            "preflight",
            "--root",
            str(tmp_path),
            "--expected-version",
            "v0.3.0",
            "--engine-version",
            "25.0.0",
            "--compose-version",
            "2.27.0",
            "--daemon-arch",
            "amd64",
        ]
    )

    assert result == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Release preflight failed" in captured.err


def test_runtime_selection_cli_rejects_invalid_boolean(tmp_path: Path, capsys) -> None:
    write_manifest(tmp_path)
    values = direct_release_environment()
    values["SURGEPILOT_DEMO_LOAD_NODE_ENABLED"] = "yes"
    write_release_environment(tmp_path, values)

    result = release_preflight.main(
        [
            "select-runtime",
            "--root",
            str(tmp_path),
            "--expected-version",
            "v0.3.0",
            "--daemon-arch",
            "amd64",
        ]
    )

    assert result == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "must be true or false" in captured.err


def test_external_url_cli_validates_effective_source_environment(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    monkeypatch.setenv("SURGEPILOT_NODE_API_BASE_URL", "https://surgepilot.example.com")
    monkeypatch.delenv("SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL", raising=False)

    assert release_preflight.main(["validate-external"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "must be set together" in captured.err

    monkeypatch.setenv(
        "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL", "https://influx.example.com"
    )
    assert release_preflight.main(["validate-external"]) == 0


def test_runtime_input_cli_rejects_non_native_demo_selection(capsys) -> None:
    result = release_preflight.main(
        [
            "validate-runtime",
            "--configured",
            "amd64",
            "--demo-enabled",
            "true",
            "--daemon-arch",
            "arm64",
        ]
    )

    assert result == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "daemon architecture" in captured.err


def test_release_manifest_reports_missing_or_malformed_file(tmp_path: Path) -> None:
    with pytest.raises(release_preflight.ReleasePreflightError, match="cannot read"):
        release_preflight.load_release_manifest(tmp_path, expected_version="v0.3.0")
    (tmp_path / "release-manifest.json").write_text("not-json", encoding="utf-8")
    with pytest.raises(release_preflight.ReleasePreflightError, match="cannot read"):
        release_preflight.load_release_manifest(tmp_path, expected_version="v0.3.0")


@pytest.mark.parametrize(
    "mutate",
    [
        lambda manifest: manifest.update(schemaVersion=2),
        lambda manifest: manifest.update(revision="short"),
        lambda manifest: manifest["images"]["api"].update(digest="latest"),
        lambda manifest: manifest["runtimes"]["arm64"].update(archive="wrong.tar.gz"),
    ],
)
def test_release_manifest_rejects_invalid_integrity_fields(tmp_path: Path, mutate) -> None:
    write_manifest(tmp_path)
    path = tmp_path / "release-manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    mutate(manifest)
    path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(release_preflight.ReleasePreflightError):
        release_preflight.load_release_manifest(tmp_path, expected_version="v0.3.0")
