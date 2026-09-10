from __future__ import annotations

from pathlib import Path
import os
import subprocess
import sys
import xml.etree.ElementTree as ET

BACKEND_LISTENER_CLASSNAME = (
    "io.github.mderevyankoaqa.influxdb2.visualizer.InfluxDatabaseBackendListenerClient"
)
INFLUXDB2_LOG_LEVEL_ARGUMENT = "-Lio.github.mderevyankoaqa.influxdb2=ERROR"
BACKEND_LISTENER_TESTNAME = "SurgePilot Monitoring Backend Listener"

ARGUMENTS = {
    "testName": "${__P(SURGEPILOT_RUN_ID)}",
    "nodeName": "${__P(SURGEPILOT_NODE_ID)}",
    "runId": "${__P(SURGEPILOT_RUN_ID)}",
    "influxDBURL": "${__P(SURGEPILOT_INFLUXDB_URL)}",
    "influxDBToken": "${__P(SURGEPILOT_INFLUXDB_TOKEN)}",
    "influxDBOrganization": "${__P(SURGEPILOT_INFLUXDB_ORG)}",
    "influxDBBucket": "${__P(SURGEPILOT_INFLUXDB_BUCKET)}",
    "samplersList": "${__P(SURGEPILOT_MONITORING_SAMPLERS_LIST)}",
    "useRegexForSamplerList": "${__P(SURGEPILOT_MONITORING_USE_REGEX)}",
    "summaryOnly": "${__P(SURGEPILOT_MONITORING_SUMMARY_ONLY)}",
    "saveResponseBodyOfFailures": "${__P(SURGEPILOT_MONITORING_SAVE_RESPONSE_BODY_OF_FAILURES)}",
    "responseBodyLength": "${__P(SURGEPILOT_MONITORING_RESPONSE_BODY_LENGTH)}",
    "influxDBFlushInterval": "${__P(SURGEPILOT_MONITORING_FLUSH_INTERVAL_MS)}",
    "influxDBMaxBatchSize": "${__P(SURGEPILOT_MONITORING_MAX_BATCH_SIZE)}",
    "influxDBThresholdError": "${__P(SURGEPILOT_MONITORING_THRESHOLD_ERROR_COUNT)}",
}


def _argument_element(name: str, value: str) -> ET.Element:
    element = ET.Element("elementProp", {"name": name, "elementType": "Argument"})
    ET.SubElement(element, "stringProp", {"name": "Argument.name"}).text = name
    ET.SubElement(element, "stringProp", {"name": "Argument.value"}).text = value
    ET.SubElement(element, "stringProp", {"name": "Argument.metadata"}).text = "="
    return element


def _backend_listener() -> ET.Element:
    listener = ET.Element(
        "BackendListener",
        {
            "guiclass": "BackendListenerGui",
            "testclass": "BackendListener",
            "testname": BACKEND_LISTENER_TESTNAME,
            "enabled": "true",
        },
    )
    ET.SubElement(listener, "stringProp", {"name": "classname"}).text = BACKEND_LISTENER_CLASSNAME
    arguments = ET.SubElement(
        listener,
        "elementProp",
        {
            "name": "arguments",
            "elementType": "Arguments",
            "guiclass": "ArgumentsPanel",
            "testclass": "Arguments",
            "enabled": "true",
        },
    )
    collection = ET.SubElement(arguments, "collectionProp", {"name": "Arguments.arguments"})
    for name, value in ARGUMENTS.items():
        collection.append(_argument_element(name, value))
    return listener


def _remove_existing_surgepilot_listener(parent_hash_tree: ET.Element) -> None:
    index = 0
    while index < len(parent_hash_tree):
        child = parent_hash_tree[index]
        if (
            child.tag == "BackendListener"
            and child.attrib.get("testname") == BACKEND_LISTENER_TESTNAME
        ):
            del parent_hash_tree[index]
            if index < len(parent_hash_tree) and parent_hash_tree[index].tag == "hashTree":
                del parent_hash_tree[index]
            continue
        if child.tag == "hashTree":
            _remove_existing_surgepilot_listener(child)
        index += 1


def _test_plan_hash_tree(root_hash_tree: ET.Element) -> ET.Element:
    children = list(root_hash_tree)
    for index, child in enumerate(children[:-1]):
        if child.tag == "TestPlan" and children[index + 1].tag == "hashTree":
            return children[index + 1]
    raise RuntimeError("JMX TestPlan hashTree not found.")


def inject_monitoring_backend_listener(source: Path, target: Path) -> None:
    tree = ET.parse(source)
    root = tree.getroot()
    root_hash_tree = root.find("hashTree")
    if root_hash_tree is None:
        raise RuntimeError("JMX hashTree root not found.")
    _remove_existing_surgepilot_listener(root_hash_tree)
    parent_hash_tree = _test_plan_hash_tree(root_hash_tree)
    parent_hash_tree.append(_backend_listener())
    parent_hash_tree.append(ET.Element("hashTree"))
    target.parent.mkdir(parents=True, exist_ok=True)
    tree.write(target, encoding="utf-8", xml_declaration=True)


def _properties_path(cwd: Path) -> Path:
    candidates = [
        cwd / "secrets" / "monitoring.properties",
        cwd.parent / "secrets" / "monitoring.properties",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[-1]


def _jmx_copy_path(cwd: Path, original: Path) -> Path:
    work_dir = cwd.parent / "work"
    return work_dir / f"{original.stem}.monitoring.jmx"


def _argument_value(argv: list[str], flag: str) -> str | None:
    try:
        index = argv.index(flag)
    except ValueError:
        return None
    next_index = index + 1
    if next_index >= len(argv):
        return None
    return argv[next_index]


def build_jmeter_wrapper_command(*, real_jmeter: str, argv: list[str], cwd: Path) -> list[str]:
    properties = _properties_path(cwd)
    if not properties.is_file():
        return [real_jmeter, INFLUXDB2_LOG_LEVEL_ARGUMENT, *argv]
    jmx_arg = _argument_value(argv, "-t")
    if jmx_arg is None:
        return [real_jmeter, INFLUXDB2_LOG_LEVEL_ARGUMENT, *argv]
    source_jmx = Path(jmx_arg)
    if not source_jmx.is_absolute():
        source_jmx = cwd / source_jmx
    target_jmx = _jmx_copy_path(cwd, source_jmx)
    inject_monitoring_backend_listener(source_jmx, target_jmx)
    updated = list(argv)
    updated[updated.index("-t") + 1] = str(target_jmx)
    updated.extend(["-q", str(properties)])
    return [real_jmeter, INFLUXDB2_LOG_LEVEL_ARGUMENT, *updated]


def main() -> int:
    script = Path(sys.argv[0]).resolve()
    configured_runtime = os.environ.get("SURGEPILOT_RUNTIME_HOME")
    if configured_runtime:
        runtime = Path(configured_runtime).resolve()
    elif script.parent.name == "bin" and script.parent.parent.name.startswith("apache-jmeter-"):
        runtime = script.parents[2]
    else:
        runtime = script.parents[1]
    real_jmeter = runtime / "apache-jmeter-5.6.3" / "bin" / "jmeter"
    cwd = Path.cwd()
    command = build_jmeter_wrapper_command(real_jmeter=str(real_jmeter), argv=sys.argv[1:], cwd=cwd)
    return subprocess.call(command)


if __name__ == "__main__":
    raise SystemExit(main())
