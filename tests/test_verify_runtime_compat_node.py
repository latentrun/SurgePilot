from __future__ import annotations

import argparse
import importlib.util
import hashlib
import re
import sys
from pathlib import Path
from types import ModuleType


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "verify_runtime_compat_node.py"


def load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("verify_runtime_compat_node", MODULE_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_node_script_uses_safe_extract_filter_when_python_supports_it() -> None:
    module = load_module()

    script = module.node_script(
        archive_name="surgepilot-runtime-linux-amd64-p0-e2e.tar.gz",
        sidecar_name="surgepilot-runtime-linux-amd64-p0-e2e.tar.gz.sha256",
        version="p0-e2e",
        metadata_arch="amd64",
    )

    assert "unsafe tar member" in script
    assert "inspect.signature(tar.extractall).parameters" in script
    assert "extract_kwargs = {'filter': 'data'}" in script
    assert "tar.extractall(target, **extract_kwargs)" in script
    assert "sha256sum -c" in script
    assert "runtime-compat/runtimes/p0-e2e" in script
    assert 'ln -s "runtimes/p0-e2e" "$work/current"' in script
    assert "current/bin/bzt -h" in script
    assert "current/apache-jmeter-5.6.3/bin/jmeter --version" in script
    assert "runtime-compat/current/apache-jmeter-5.6.3/bin/surgepilot-jmeter-wrapper" in script
    assert "provisioning: local" in script
    assert "class: bzt.modules.provisioning.Local" in script
    assert "class: bzt.modules.aggregator.ConsolidatingAggregator" in script
    assert "class: bzt.modules.jmeter.JMeterExecutor" in script
    assert "aggregator: consolidator" in script
    assert "detect-plugins: false" in script
    assert "fix-log4j: false" in script
    assert "fix-jars: false" in script
    assert "http: bzt.jmx.http.HTTPProtocolHandler" in script
    assert "current/bin/bzt -n smoke.yml" in script
    assert "ConcurrencyThreadGroup.class" in script
    assert "JSONPathAssertion.class" in script
    assert "VariableThroughputTimer.class" in script
    assert "RandomCSVDataSetConfig.class" in script
    assert "InfluxDatabaseBackendListenerClient.class" in script
    assert "random-order: true" in script
    assert "assert-jsonpath" in script
    assert "ramp-up: 6s" in script
    assert "hold-for: 3s" in script
    assert "throughput: 2" in script
    assert "steps: 3" in script
    assert "force-ctg: true" in script
    assert "sequential: true" in script
    assert "monitoring.properties" in script
    assert "surgepilot-compat-token-do-not-log" in script
    assert "InfluxDB writes are missing" in script
    assert "Target RPS sample count is outside the expected bound" in script
    assert "Concurrency Thread Group did not execute samples" in script
    assert "Random CSV substitution was not observed" in script
    assert "JSONPath extraction was not observed" in script
    assert "Monitoring properties were removed before sequential execution completed" in script
    assert "monitoring token leaked into Runtime smoke output" in script
    assert "expected at least two Monitoring writes" in script
    assert "unresolved external JMX class" in script
    assert "com.blazemeter.jmeter.threads.concurrency.ConcurrencyThreadGroup" in script
    assert "kg.apc.jmeter.timers.VariableThroughputTimer" in script
    assert "InfluxDatabaseBackendListenerClient" in script


def test_node_script_embedded_python_probes_compile() -> None:
    module = load_module()
    script = module.node_script(
        archive_name="surgepilot-runtime-linux-amd64-p0-e2e.tar.gz",
        sidecar_name="surgepilot-runtime-linux-amd64-p0-e2e.tar.gz.sha256",
        version="p0-e2e",
        metadata_arch="amd64",
    )

    probes = re.findall(r"python3 - <<'([^']+)'\n(.*?)\n\1", script, re.DOTALL)
    assert probes
    for marker, source in probes:
        compile(source, marker, "exec")


def test_artifact_paths_follow_host_runtime_architecture(tmp_path: Path, monkeypatch) -> None:
    module = load_module()
    monkeypatch.setattr(module.platform, "machine", lambda: "aarch64")
    archive = tmp_path / "surgepilot-runtime-linux-arm64-p0-e2e.tar.gz"
    archive.write_bytes(b"runtime")
    archive.with_name(f"{archive.name}.sha256").write_text(
        f"{hashlib.sha256(archive.read_bytes()).hexdigest()}  {archive.name}\n",
        encoding="utf-8",
    )
    args = argparse.Namespace(artifact_dir=tmp_path, version="p0-e2e")

    selected_archive, selected_sidecar = module.artifact_paths(args)

    assert selected_archive == archive
    assert selected_sidecar.name == "surgepilot-runtime-linux-arm64-p0-e2e.tar.gz.sha256"


def test_verify_executes_compat_probe_as_surgepilot_user(tmp_path: Path, monkeypatch) -> None:
    module = load_module()
    artifact_arch, _metadata_arch = module.normalize_arch()
    archive = tmp_path / f"surgepilot-runtime-{artifact_arch}-p0-e2e.tar.gz"
    archive.write_bytes(b"runtime")
    archive.with_name(f"{archive.name}.sha256").write_text(
        f"{hashlib.sha256(archive.read_bytes()).hexdigest()}  {archive.name}\n",
        encoding="utf-8",
    )
    args = argparse.Namespace(
        artifact_dir=tmp_path,
        version="p0-e2e",
        service="ssh-load-node",
        compose_file=[],
        profile=[],
        compose_project="test",
    )
    calls: list[list[str]] = []

    def fake_run(command: list[str]):
        calls.append(command)
        return None

    monkeypatch.setattr(module, "run", fake_run)

    module.verify(args)

    chown_calls = [call for call in calls if "chown" in call]
    assert chown_calls
    assert "surgepilot:surgepilot" in chown_calls[0]
    exec_calls = [call for call in calls if "exec" in call]
    assert exec_calls
    user_exec_calls = [call for call in exec_calls if "--user" in call]
    assert user_exec_calls
    assert user_exec_calls[0][
        user_exec_calls[0].index("exec") + 1 : user_exec_calls[0].index("exec") + 4
    ] == [
        "-T",
        "--user",
        "surgepilot",
    ]
