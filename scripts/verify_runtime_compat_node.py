"""Verify a production Load Node runtime artifact on one SSH load-node container."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import platform
import re
import shlex
import subprocess
import sys


JMETER_VERSION = "5.6.3"
TAURUS_VERSION = "1.16.50"
REQUIRED_PLUGIN_CLASSES = {
    "jpgc-casutg": {
        "jarPrefix": "jmeter-plugins-casutg",
        "classes": ["com/blazemeter/jmeter/threads/concurrency/ConcurrencyThreadGroup.class"],
    },
    "jpgc-json": {
        "jarPrefix": "jmeter-plugins-json",
        "classes": [
            "com/atlantbh/jmeter/plugins/jsonutils/jsonpathextractor/JSONPathExtractor.class",
            "com/atlantbh/jmeter/plugins/jsonutils/jsonpathassertion/JSONPathAssertion.class",
        ],
    },
    "jpgc-tst": {
        "jarPrefix": "jmeter-plugins-tst",
        "classes": ["kg/apc/jmeter/timers/VariableThroughputTimer.class"],
    },
    "bzm-random-csv": {
        "jarPrefix": "jmeter-plugins-random-csv-data-set",
        "classes": ["com/blazemeter/jmeter/RandomCSVDataSetConfig.class"],
    },
    "jmeter-plugin-influxdb2-listener": {
        "jarPrefix": "jmeter-plugins-influxdb2-listener",
        "classes": [
            "io/github/mderevyankoaqa/influxdb2/visualizer/"
            "InfluxDatabaseBackendListenerClient.class"
        ],
    },
}
EXPECTED_EXTERNAL_JMX_CLASSES = (
    "com.blazemeter.jmeter.threads.concurrency.ConcurrencyThreadGroup",
    "com.atlantbh.jmeter.plugins.jsonutils.jsonpathassertion.JSONPathAssertion",
    "kg.apc.jmeter.timers.VariableThroughputTimer",
    "com.blazemeter.jmeter.RandomCSVDataSetConfig",
    "io.github.mderevyankoaqa.influxdb2.visualizer.InfluxDatabaseBackendListenerClient",
)
SAFE_VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def normalize_arch(machine: str | None = None) -> tuple[str, str]:
    normalized = (machine or platform.machine()).strip().lower()
    if normalized in {"x86_64", "amd64"}:
        return "linux-amd64", "amd64"
    if normalized in {"aarch64", "arm64"}:
        return "linux-arm64", "arm64"
    raise RuntimeError(f"unsupported runtime builder architecture: {machine or platform.machine()}")


def validate_version(version: str) -> str:
    if not SAFE_VERSION.fullmatch(version):
        raise RuntimeError(
            "runtime version must use 1-64 characters from A-Z, a-z, 0-9, '.', '_', '-' "
            "and must start with an alphanumeric character"
        )
    return version


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if result.returncode != 0:
        raise RuntimeError(f"command failed ({' '.join(command)}):\n{result.stdout}")
    return result


def compose_command(args: argparse.Namespace, *extra: str) -> list[str]:
    command = ["docker", "compose"]
    for compose_file in args.compose_file:
        command.extend(["-f", str(compose_file)])
    for profile in args.profile:
        command.extend(["--profile", profile])
    if args.compose_project:
        command.extend(["--project-name", args.compose_project])
    command.extend(extra)
    return command


def artifact_paths(args: argparse.Namespace) -> tuple[Path, Path]:
    artifact_arch, _metadata_arch = normalize_arch()
    archive = args.artifact_dir / f"surgepilot-runtime-{artifact_arch}-{args.version}.tar.gz"
    sidecar = archive.with_name(f"{archive.name}.sha256")
    if not archive.is_file():
        raise RuntimeError(f"runtime archive is missing: {archive}")
    if not sidecar.is_file():
        raise RuntimeError(f"runtime sha256 sidecar is missing: {sidecar}")
    return archive, sidecar


def node_script(*, archive_name: str, sidecar_name: str, version: str, metadata_arch: str) -> str:
    version = validate_version(version)
    metadata_checks = {
        "name": "surgepilot-runtime",
        "version": version,
        "platform": "linux",
        "arch": metadata_arch,
        "taurus": TAURUS_VERSION,
        "jmeter": JMETER_VERSION,
    }
    plugin_classes = json.dumps(REQUIRED_PLUGIN_CLASSES, sort_keys=True)
    expected_plugins = json.dumps(list(REQUIRED_PLUGIN_CLASSES))
    expected_external_jmx_classes = json.dumps(EXPECTED_EXTERNAL_JMX_CLASSES)
    metadata_json = json.dumps(metadata_checks, sort_keys=True)
    return f"""
set -euo pipefail
work=/home/surgepilot/runtime-compat
archive=/tmp/{shlex.quote(archive_name)}
sidecar=/tmp/{shlex.quote(sidecar_name)}
rm -rf "$work" /home/surgepilot/work
mkdir -p "$work/runtimes/{shlex.quote(version)}"
cd /tmp
sha256sum -c "$sidecar"
python3 - <<'PY_SAFE_TAR'
from pathlib import Path
import inspect
import os
import tarfile
archive = Path({json.dumps("/tmp/" + archive_name)})
target = Path({json.dumps(f"/home/surgepilot/runtime-compat/runtimes/{version}")})
target_root = target.resolve()
with tarfile.open(archive, 'r:gz') as tar:
    for member in tar.getmembers():
        if member.issym() or member.islnk() or not (member.isdir() or member.isfile()):
            raise SystemExit(f'unsafe tar member: {{member.name}}')
        member_target = (target / member.name).resolve()
        if member_target != target_root and not str(member_target).startswith(str(target_root) + os.sep):
            raise SystemExit(f'unsafe tar member: {{member.name}}')
    extract_kwargs = {{'filter': 'data'}} if 'filter' in inspect.signature(tar.extractall).parameters else {{}}
    tar.extractall(target, **extract_kwargs)
PY_SAFE_TAR
ln -s "runtimes/{shlex.quote(version)}" "$work/current"
cd "$work"
python3 - <<'PY_METADATA'
import json
from pathlib import Path
expected = {metadata_json}
metadata = json.loads(Path('current/metadata.json').read_text())
for key, value in expected.items():
    if metadata.get(key) != value:
        raise SystemExit(f'metadata {{key}} mismatch: expected {{value!r}}, got {{metadata.get(key)!r}}')
expected_plugins = {expected_plugins}
if metadata.get('plugins') != expected_plugins:
    raise SystemExit(f'metadata plugins mismatch: expected {{expected_plugins!r}}, got {{metadata.get("plugins")!r}}')
PY_METADATA
test -L current
test -x current/bin/bzt
test -x current/apache-jmeter-{JMETER_VERSION}/bin/surgepilot-jmeter-wrapper
test -x current/apache-jmeter-{JMETER_VERSION}/bin/jmeter
test -x current/python/bin/python3
current/bin/bzt -h >/tmp/surgepilot-runtime-compat-bzt-help.txt
current/apache-jmeter-{JMETER_VERSION}/bin/jmeter --version | grep -F '{JMETER_VERSION}'
python3 - <<'PY_PLUGINS'
from pathlib import Path
import zipfile
required = {plugin_classes}
plugin_dir = Path('current/apache-jmeter-{JMETER_VERSION}/lib/ext')
for plugin, contract in required.items():
    matches = sorted(plugin_dir.glob(contract['jarPrefix'] + '-*.jar'))
    if len(matches) != 1:
        raise SystemExit(f'missing or ambiguous plugin jar: {{plugin}}')
    with zipfile.ZipFile(matches[0]) as jar:
        names = set(jar.namelist())
    for required_class in contract['classes']:
        if required_class not in names:
            raise SystemExit(f'plugin class missing for {{plugin}}: {{required_class}}')
PY_PLUGINS
cat > server.py <<'PY_SERVER'
from gzip import decompress
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        with Path('requests.log').open('a', encoding='utf-8') as log:
            log.write(self.path + '\\n')
        body = b'{{"ok": true, "value": "ready"}}'
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get('Content-Length', '0'))
        body = self.rfile.read(length)
        if self.headers.get('Content-Encoding', '').lower() == 'gzip':
            body = decompress(body)
        with Path('influx-writes.log').open('ab') as log:
            log.write(self.path.encode() + b'\\t' + body + b'\\n')
        self.send_response(204)
        self.end_headers()

    def log_message(self, *_args):
        return

ThreadingHTTPServer(('127.0.0.1', 18081), Handler).serve_forever()
PY_SERVER
python3 server.py >/tmp/surgepilot-runtime-compat-http.log 2>&1 &
server_pid=$!
trap 'kill "$server_pid" >/dev/null 2>&1 || true' EXIT
mkdir -p secrets
cat > secrets/monitoring.properties <<'EOF_MONITORING'
SURGEPILOT_RUN_ID=runtime-compat-smoke-run
SURGEPILOT_NODE_ID=runtime-compat-node
SURGEPILOT_INFLUXDB_URL=http://127.0.0.1:18081
SURGEPILOT_INFLUXDB_ORG=surgepilot
SURGEPILOT_INFLUXDB_BUCKET=jmeter
SURGEPILOT_INFLUXDB_TOKEN=surgepilot-compat-token-do-not-log
SURGEPILOT_MONITORING_SAMPLERS_LIST=.*
SURGEPILOT_MONITORING_USE_REGEX=true
SURGEPILOT_MONITORING_SUMMARY_ONLY=false
SURGEPILOT_MONITORING_SAVE_RESPONSE_BODY_OF_FAILURES=false
SURGEPILOT_MONITORING_RESPONSE_BODY_LENGTH=0
SURGEPILOT_MONITORING_FLUSH_INTERVAL_MS=500
SURGEPILOT_MONITORING_MAX_BATCH_SIZE=2000
SURGEPILOT_MONITORING_THRESHOLD_ERROR_COUNT=5
EOF_MONITORING
chmod 600 secrets/monitoring.properties
python3 - <<'PY_SMOKE'
from pathlib import Path
Path('data.csv').write_text('alpha\\nbeta\\n')
Path('smoke.yml').write_text('''provisioning: local
execution:
  - executor: jmeter
    concurrency: 2
    ramp-up: 6s
    hold-for: 3s
    throughput: 2
    steps: 3
    scenario: plugin-smoke
  - executor: jmeter
    concurrency: 1
    iterations: 1
    scenario: monitoring-reuse
scenarios:
  plugin-smoke:
    data-sources:
      - path: data.csv
        variable-names: item
        random-order: true
        loop: true
    requests:
      - url: http://127.0.0.1:18081/?item=${{item}}
        label: random-csv-jsonpath
        method: GET
        extract-jsonpath:
          extracted_value:
            jsonpath: $.value
            default: missing
        assert-jsonpath:
          - jsonpath: $.ok
      - url: http://127.0.0.1:18081/?extracted=${{extracted_value}}
        label: extracted-jsonpath
        method: GET
  monitoring-reuse:
    requests:
      - url: http://127.0.0.1:18081/?sequential=second
        label: monitoring-reuse
        method: GET
modules:
  local:
    class: bzt.modules.provisioning.Local
    sequential: true
  consolidator:
    class: bzt.modules.aggregator.ConsolidatingAggregator
  jmeter:
    class: bzt.modules.jmeter.JMeterExecutor
    path: /home/surgepilot/runtime-compat/current/apache-jmeter-5.6.3/bin/surgepilot-jmeter-wrapper
    version: '5.6.3'
    detect-plugins: false
    fix-log4j: false
    fix-jars: false
    force-ctg: true
    protocol-handlers:
      http: bzt.jmx.http.HTTPProtocolHandler
settings:
  check-updates: false
  aggregator: consolidator
  artifacts-dir: artifacts
''')
PY_SMOKE
current/bin/bzt -n smoke.yml -o settings.check-updates=false \
    >/tmp/surgepilot-runtime-compat-bzt-smoke.log 2>&1
python3 - <<'PY_JMX'
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile

expected = set({expected_external_jmx_classes})
qualified_class = re.compile(r'^(?:[A-Za-z_$][A-Za-z0-9_$]*\\.)+[A-Za-z_$][A-Za-z0-9_$]*$')
jmx_files = sorted(Path('artifacts').rglob('*.jmx'))
jmx_files.extend(sorted(Path('/home/surgepilot/work').glob('*.jmx')))
if not jmx_files:
    raise SystemExit('final Taurus JMX is missing')

classes = set()
for jmx_file in jmx_files:
    root = ET.parse(jmx_file).getroot()
    for element in root.iter():
        candidates = [str(element.tag), element.get('testclass', ''), element.get('guiclass', '')]
        if element.tag == 'stringProp' and element.get('name') == 'classname':
            candidates.append(element.text or '')
        classes.update(candidate for candidate in candidates if qualified_class.fullmatch(candidate))

missing_expected = sorted(expected - classes)
if missing_expected:
    raise SystemExit(f'expected external JMX class is missing: {{missing_expected[0]}}')

jar_classes = set()
for jar_path in Path('current/apache-jmeter-{JMETER_VERSION}').rglob('*.jar'):
    with zipfile.ZipFile(jar_path) as jar:
        jar_classes.update(name for name in jar.namelist() if name.endswith('.class'))
for class_name in sorted(classes):
    class_path = class_name.replace('.', '/') + '.class'
    if class_path not in jar_classes:
        raise SystemExit(f'unresolved external JMX class: {{class_name}}')
PY_JMX
python3 - <<'PY_BEHAVIOR'
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
import xml.etree.ElementTree as ET

requests_path = Path('requests.log')
if not requests_path.is_file():
    raise SystemExit('Runtime smoke did not execute HTTP samples')
request_paths = requests_path.read_text(encoding='utf-8').splitlines()
plugin_requests = [path for path in request_paths if 'sequential=second' not in path]
if not plugin_requests:
    raise SystemExit('Concurrency Thread Group did not execute samples')
if not 4 <= len(plugin_requests) <= 40:
    raise SystemExit(
        f'Target RPS sample count is outside the expected bound: {{len(plugin_requests)}}'
    )

items = {{
    value
    for path in plugin_requests
    for value in parse_qs(urlsplit(path).query).get('item', [])
}}
if not items or not items.issubset({{'alpha', 'beta'}}):
    raise SystemExit(f'Random CSV substitution was not observed: {{sorted(items)}}')
if not any(
    parse_qs(urlsplit(path).query).get('extracted') == ['ready'] for path in plugin_requests
):
    raise SystemExit('JSONPath extraction was not observed')
if not any('sequential=second' in path for path in request_paths):
    raise SystemExit('Sequential JMeter execution did not reach the second Scenario item')

jmx_files = sorted(Path('artifacts').rglob('*.jmx'))
jmx_files.extend(sorted(Path('/home/surgepilot/work').glob('*.jmx')))
monitoring_jmx = []
for jmx_file in jmx_files:
    root = ET.parse(jmx_file).getroot()
    if any(
        element.tag == 'stringProp'
        and element.get('name') == 'classname'
        and (element.text or '').endswith('InfluxDatabaseBackendListenerClient')
        for element in root.iter()
    ):
        monitoring_jmx.append(jmx_file)
if len(monitoring_jmx) < 2:
    raise SystemExit(
        'expected Monitoring injection for two sequential JMeter processes, '
        f'got {{len(monitoring_jmx)}} from {{[str(path) for path in jmx_files]}}'
    )

properties = Path('secrets/monitoring.properties')
if not properties.is_file():
    raise SystemExit(
        'Monitoring properties were removed before sequential execution completed'
    )
writes_path = Path('influx-writes.log')
if not writes_path.is_file():
    raise SystemExit('InfluxDB writes are missing')
writes = [line for line in writes_path.read_bytes().splitlines() if b'/api/v2/write' in line]
if len(writes) < 2:
    raise SystemExit(f'expected at least two Monitoring writes, got {{len(writes)}}')

token = b'surgepilot-compat-token-do-not-log'
scan_paths = [
    Path('/tmp/surgepilot-runtime-compat-bzt-smoke.log'),
    Path('/tmp/surgepilot-runtime-compat-http.log'),
]
for root in (Path('artifacts'), Path('/home/surgepilot/work')):
    if root.exists():
        scan_paths.extend(path for path in root.rglob('*') if path.is_file())
scan_paths.extend(path for path in Path('.').glob('*.jmx') if path.is_file())
for path in scan_paths:
    if token in path.read_bytes():
        raise SystemExit(f'monitoring token leaked into Runtime smoke output: {{path}}')
PY_BEHAVIOR
"""


def verify(args: argparse.Namespace) -> None:
    validate_version(args.version)
    _artifact_arch, metadata_arch = normalize_arch()
    archive, sidecar = artifact_paths(args)
    remote_archive = f"/tmp/{archive.name}"
    remote_sidecar = f"/tmp/{sidecar.name}"
    run(compose_command(args, "cp", str(archive), f"{args.service}:{remote_archive}"))
    run(compose_command(args, "cp", str(sidecar), f"{args.service}:{remote_sidecar}"))
    run(
        compose_command(
            args,
            "exec",
            "-T",
            args.service,
            "chown",
            "surgepilot:surgepilot",
            remote_archive,
            remote_sidecar,
        )
    )
    script = node_script(
        archive_name=archive.name,
        sidecar_name=sidecar.name,
        version=args.version,
        metadata_arch=metadata_arch,
    )
    run(
        compose_command(
            args,
            "exec",
            "-T",
            "--user",
            "surgepilot",
            args.service,
            "bash",
            "-lc",
            script,
        )
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify runtime compatibility on one compose service."
    )
    parser.add_argument("--service", required=True)
    parser.add_argument("--artifact-dir", required=True, type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--compose-project")
    parser.add_argument("--compose-file", action="append", type=Path, required=True)
    parser.add_argument("--profile", action="append", default=[])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        verify(args)
    except Exception as exc:  # noqa: BLE001 - CLI prints actionable failure.
        print(
            f"Runtime compatibility verification failed for {args.service}: {exc}", file=sys.stderr
        )
        return 1
    print(f"Runtime compatibility verified for {args.service}: version={args.version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
