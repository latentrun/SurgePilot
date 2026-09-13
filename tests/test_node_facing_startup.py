from __future__ import annotations

import json
from pathlib import Path
import socket
import subprocess
import sys

import pytest

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import node_facing_startup  # noqa: E402

from node_facing_startup import (  # noqa: E402
    NodeFacingStartupError,
    _effective_publish_port_environment,
    _published_families_from_compose_ps,
    _unavailable_port_families,
    discover_publish_addresses,
    resolve_node_facing_environment,
    validate_publish_ports,
)


def test_resolver_preserves_explicit_final_urls_without_host_discovery() -> None:
    discovered = False

    def discover() -> list[str]:
        nonlocal discovered
        discovered = True
        return ["192.168.1.20"]

    resolved = resolve_node_facing_environment(
        {
            "SURGEPILOT_NODE_API_BASE_URL": "https://surgepilot.example.com",
            "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL": "https://influxdb.example.com:8443",
        },
        discover=discover,
    )

    assert resolved == {
        "SURGEPILOT_NODE_API_BASE_URL": "https://surgepilot.example.com",
        "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL": "https://influxdb.example.com:8443",
    }
    assert discovered is False


def test_resolver_derives_final_urls_from_one_publish_address_and_existing_ports() -> None:
    resolved = resolve_node_facing_environment(
        {
            "SURGEPILOT_API_HOST_PORT": "18000",
            "SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT": "18086",
        },
        discover=lambda: ["192.168.1.20"],
    )

    assert resolved == {
        "SURGEPILOT_NODE_API_BASE_URL": "http://192.168.1.20:18000",
        "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL": "http://192.168.1.20:18086",
    }


def test_effective_publish_ports_apply_compose_defaults_for_empty_values() -> None:
    assert _effective_publish_port_environment(
        {
            "SURGEPILOT_API_HOST_PORT": "",
            "SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT": "",
        }
    ) == {
        "SURGEPILOT_API_HOST_PORT": "8000",
        "SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT": "8086",
    }


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("SURGEPILOT_API_HOST_PORT", " 18000 "),
        ("SURGEPILOT_API_HOST_PORT", "+18000"),
        ("SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT", "18_086"),
    ],
)
def test_effective_publish_ports_reject_non_compose_host_port_syntax(name: str, value: str) -> None:
    with pytest.raises(NodeFacingStartupError, match=name):
        _effective_publish_port_environment({name: value})


def test_main_passes_compose_default_ports_to_startup_child(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, str] = {}

    def execvpe(_file: str, _args: list[str], environ: dict[str, str]) -> None:
        captured.update(environ)
        raise RuntimeError("child captured")

    monkeypatch.setenv("SURGEPILOT_NODE_API_BASE_URL", "http://192.0.2.10:8000")
    monkeypatch.setenv("SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL", "http://192.0.2.10:8086")
    monkeypatch.setenv(
        "SSH_CREDENTIAL_ENCRYPTION_KEY",
        "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=",
    )
    monkeypatch.setenv("SURGEPILOT_API_HOST_PORT", "")
    monkeypatch.setenv("SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT", "")
    monkeypatch.setattr(node_facing_startup, "validate_publish_ports", lambda _environ: None)
    monkeypatch.setattr(node_facing_startup.os, "execvpe", execvpe)

    with pytest.raises(RuntimeError, match="child captured"):
        node_facing_startup.main(["--", "true"])

    assert captured["SURGEPILOT_API_HOST_PORT"] == "8000"
    assert captured["SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT"] == "8086"


def test_main_rejects_missing_credential_key_before_port_ownership_probe(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("SSH_CREDENTIAL_ENCRYPTION_KEY", raising=False)
    monkeypatch.setenv("SURGEPILOT_NODE_API_BASE_URL", "http://192.0.2.10:8000")
    monkeypatch.setenv("SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL", "http://192.0.2.10:8086")
    monkeypatch.setattr(
        node_facing_startup,
        "validate_publish_ports",
        lambda _environ: pytest.fail("port ownership probe must not run"),
    )

    assert node_facing_startup.main(["--", "true"]) == 2
    assert "SSH_CREDENTIAL_ENCRYPTION_KEY is required" in capsys.readouterr().err


@pytest.mark.parametrize("value", ["not-base64", "c2hvcnQ="])
def test_main_rejects_malformed_credential_key_before_port_ownership_probe(
    value: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("SSH_CREDENTIAL_ENCRYPTION_KEY", value)
    monkeypatch.setenv("SURGEPILOT_NODE_API_BASE_URL", "http://192.0.2.10:8000")
    monkeypatch.setenv("SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL", "http://192.0.2.10:8086")
    monkeypatch.setattr(
        node_facing_startup,
        "validate_publish_ports",
        lambda _environ: pytest.fail("port ownership probe must not run"),
    )

    assert node_facing_startup.main(["--", "true"]) == 2
    assert "SSH_CREDENTIAL_ENCRYPTION_KEY" in capsys.readouterr().err


@pytest.mark.parametrize("candidates", [[], ["10.0.0.5", "192.168.1.20"]])
def test_resolver_fails_closed_when_publish_address_is_missing_or_ambiguous(
    candidates: list[str],
) -> None:
    with pytest.raises(NodeFacingStartupError) as exc_info:
        resolve_node_facing_environment({}, discover=lambda: candidates)

    message = str(exc_info.value)
    assert "SURGEPILOT_NODE_API_BASE_URL" in message
    assert "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL" in message
    assert "final URL" in message


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("SURGEPILOT_API_HOST_PORT", "0"),
        ("SURGEPILOT_API_HOST_PORT", "65536"),
        ("SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT", "not-a-port"),
    ],
)
def test_resolver_rejects_invalid_publish_ports(name: str, value: str) -> None:
    with pytest.raises(NodeFacingStartupError, match=name):
        resolve_node_facing_environment({name: value}, discover=lambda: ["192.168.1.20"])


def test_resolver_brackets_ipv6_publish_address() -> None:
    resolved = resolve_node_facing_environment({}, discover=lambda: ["2001:db8::20"])

    assert resolved["SURGEPILOT_NODE_API_BASE_URL"] == "http://[2001:db8::20]:8000"
    assert resolved["SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL"] == "http://[2001:db8::20]:8086"


def test_discovery_uses_distinct_safe_default_route_source_addresses() -> None:
    routes = [
        {"dst": "default", "dev": "eth0", "prefsrc": "192.168.1.20"},
        {"dst": "default", "dev": "tun0", "prefsrc": "10.8.0.2"},
        {"dst": "default", "dev": "lo", "prefsrc": "127.0.0.1"},
    ]

    def run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        del args, kwargs
        return subprocess.CompletedProcess([], 0, stdout=json.dumps(routes), stderr="")

    assert discover_publish_addresses(run=run) == ["10.8.0.2", "192.168.1.20"]


def test_discovery_reads_default_routes_from_all_policy_tables() -> None:
    calls: list[list[str]] = []

    def run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        del kwargs
        calls.append(args)
        if "-6" in args:
            payload: list[dict[str, str]] = []
        else:
            payload = [
                {"dst": "default", "table": "main", "dev": "eth0", "prefsrc": "192.168.1.20"},
                {"dst": "default", "table": "100", "dev": "tun0", "prefsrc": "10.8.0.2"},
            ]
        return subprocess.CompletedProcess(args, 0, stdout=json.dumps(payload), stderr="")

    assert discover_publish_addresses(run=run) == ["10.8.0.2", "192.168.1.20"]
    assert ["ip", "-json", "route", "show", "table", "all"] in calls
    assert ["ip", "-6", "-json", "route", "show", "table", "all"] in calls


def test_discovery_ignores_non_default_routes_from_all_tables() -> None:
    def run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        del kwargs
        payload = (
            []
            if "-6" in args
            else [
                {"dst": "default", "dev": "eth0", "prefsrc": "192.168.1.20"},
                {"dst": "10.255.255.254", "table": "128", "dev": "lo", "prefsrc": "10.255.255.254"},
            ]
        )
        return subprocess.CompletedProcess(args, 0, stdout=json.dumps(payload), stderr="")

    assert discover_publish_addresses(run=run) == ["192.168.1.20"]


def test_discovery_returns_no_candidate_when_route_command_is_unavailable() -> None:
    def run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        del args, kwargs
        raise FileNotFoundError

    assert discover_publish_addresses(run=run) == []


def test_discovery_resolves_source_address_for_default_route_without_prefsrc() -> None:
    calls: list[list[str]] = []

    def run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        del kwargs
        calls.append(args)
        payload = (
            [{"dst": "default", "gateway": "192.168.1.1", "dev": "eth0"}]
            if "show" in args
            else [{"dst": "192.168.1.1", "dev": "eth0", "prefsrc": "192.168.1.20"}]
        )
        return subprocess.CompletedProcess([], 0, stdout=json.dumps(payload), stderr="")

    assert discover_publish_addresses(run=run) == ["192.168.1.20"]
    assert calls[1] == [
        "ip",
        "-json",
        "route",
        "get",
        "192.0.2.1",
        "oif",
        "eth0",
    ]


def test_discovery_fails_closed_for_multiple_policy_defaults_without_sources() -> None:
    calls: list[list[str]] = []

    def run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        del kwargs
        calls.append(args)
        if "-6" in args:
            payload: list[dict[str, str]] = []
        elif "show" in args:
            payload = [
                {"dst": "default", "table": "100", "dev": "eth0"},
                {"dst": "default", "table": "200", "dev": "eth0"},
            ]
        else:
            payload = [{"dst": "192.0.2.1", "dev": "eth0", "prefsrc": "198.51.100.10"}]
        return subprocess.CompletedProcess(args, 0, stdout=json.dumps(payload), stderr="")

    assert discover_publish_addresses(run=run) == []
    assert not any("get" in call for call in calls)


def test_discovery_ignores_non_forwarding_policy_default_routes() -> None:
    def run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        del kwargs
        payload = (
            []
            if "-6" in args
            else [
                {"dst": "default", "dev": "eth0", "prefsrc": "192.168.1.20"},
                {"type": "unreachable", "dst": "default", "table": "100"},
                {"type": "blackhole", "dst": "default", "table": "200"},
                {"type": "prohibit", "dst": "default", "table": "300"},
                {"type": "throw", "dst": "default", "table": "400"},
            ]
        )
        return subprocess.CompletedProcess(args, 0, stdout=json.dumps(payload), stderr="")

    assert discover_publish_addresses(run=run) == ["192.168.1.20"]


def test_discovery_includes_ipv6_default_route_candidates() -> None:
    def run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        del kwargs
        if "-6" in args:
            payload = [{"dst": "default", "dev": "eth0", "prefsrc": "2001:db8::20"}]
        else:
            payload = []
        return subprocess.CompletedProcess(args, 0, stdout=json.dumps(payload), stderr="")

    assert discover_publish_addresses(run=run) == ["2001:db8::20"]


def test_discovery_uses_global_probe_for_ipv6_link_local_default_gateway() -> None:
    calls: list[list[str]] = []

    def run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        del kwargs
        calls.append(args)
        if "-6" not in args:
            payload = []
        elif "show" in args:
            payload = [{"dst": "default", "gateway": "fe80::1", "dev": "eth0"}]
        else:
            payload = [{"dst": "2001:db8::1", "dev": "eth0", "prefsrc": "2001:db8::20"}]
        return subprocess.CompletedProcess(args, 0, stdout=json.dumps(payload), stderr="")

    assert discover_publish_addresses(run=run) == ["2001:db8::20"]
    assert [
        "ip",
        "-6",
        "-json",
        "route",
        "get",
        "2001:db8::1",
        "oif",
        "eth0",
    ] in calls


def test_publish_port_preflight_rejects_port_owned_by_another_process() -> None:
    with pytest.raises(NodeFacingStartupError, match="SURGEPILOT_API_HOST_PORT"):
        validate_publish_ports(
            {"SURGEPILOT_API_HOST_PORT": "18000"},
            unavailable_families=lambda port: {"ipv4"} if port == 18000 else set(),
            compose_owned_families=lambda _service, _container_port, _host_port: set(),
        )


def test_publish_port_preflight_allows_ports_owned_by_current_compose_stack() -> None:
    validate_publish_ports(
        {
            "SURGEPILOT_API_HOST_PORT": "18000",
            "SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT": "18086",
        },
        unavailable_families=lambda _port: {"ipv4", "ipv6"},
        compose_owned_families=lambda _service, _container_port, _host_port: {"ipv4", "ipv6"},
    )


def test_publish_port_preflight_rejects_api_influxdb_port_collision() -> None:
    with pytest.raises(NodeFacingStartupError, match="must use different host ports"):
        validate_publish_ports(
            {
                "SURGEPILOT_API_HOST_PORT": "18000",
                "SURGEPILOT_MONITORING_INFLUXDB_HOST_PORT": "18000",
            },
            unavailable_families=lambda _port: set(),
            compose_owned_families=lambda _service, _container_port, _host_port: set(),
        )


def test_publish_port_preflight_rejects_foreign_listener_in_other_address_family() -> None:
    with pytest.raises(NodeFacingStartupError, match="ipv6"):
        validate_publish_ports(
            {"SURGEPILOT_API_HOST_PORT": "18000"},
            unavailable_families=lambda port: {"ipv4", "ipv6"} if port == 18000 else set(),
            compose_owned_families=lambda service, _container_port, _host_port: (
                {"ipv4"} if service == "api" else set()
            ),
        )


def test_compose_port_ownership_preserves_ipv4_and_ipv6_publishers() -> None:
    output = json.dumps(
        {
            "Service": "api",
            "Publishers": [
                {"URL": "0.0.0.0", "TargetPort": 8000, "PublishedPort": 18000},
                {"URL": "::", "TargetPort": 8000, "PublishedPort": 18000},
            ],
        }
    )

    assert _published_families_from_compose_ps(output, 8000, 18000) == {"ipv4", "ipv6"}


@pytest.mark.skipif(not socket.has_ipv6, reason="IPv6 is unavailable on this host")
def test_publish_port_availability_detects_ipv6_only_listener() -> None:
    with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as listener:
        listener.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
        listener.bind(("::", 0))
        port = int(listener.getsockname()[1])

        assert _unavailable_port_families(port) == {"ipv6"}


@pytest.mark.parametrize(
    "invalid_url",
    [
        "http://localhost:8000",
        "http://host.docker.internal:8000",
        "http://api:8000",
        "http://0.0.0.0:8000",
        "http://169.254.10.20:8000",
    ],
)
def test_resolver_rejects_explicit_api_origins_the_backend_rejects(invalid_url: str) -> None:
    with pytest.raises(NodeFacingStartupError, match="SURGEPILOT_NODE_API_BASE_URL"):
        resolve_node_facing_environment(
            {
                "SURGEPILOT_NODE_API_BASE_URL": invalid_url,
                "SURGEPILOT_MONITORING_INFLUXDB_NODE_WRITE_URL": "http://host.docker.internal:8086",
            }
        )
