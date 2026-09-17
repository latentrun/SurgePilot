from __future__ import annotations

import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _tracked_paths() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return [ROOT / item.decode() for item in result.stdout.split(b"\0") if item]


def _forbidden_patterns() -> tuple[re.Pattern[bytes], ...]:
    legacy_lower = ("load" + "pilot").encode()
    malformed_brand = ("Surge" + "pilot").encode()
    legacy_short_upper = ("L" + "P").encode()
    legacy_short_lower = ("l" + "p").encode()
    return (
        re.compile(re.escape(legacy_lower), re.IGNORECASE),
        re.compile(re.escape(malformed_brand)),
        re.compile(rb"(?<![A-Za-z0-9])" + re.escape(legacy_short_upper) + rb"(?![A-Za-z0-9])"),
        re.compile(rb"(?<![A-Za-z0-9])" + re.escape(legacy_short_lower) + rb"(?![A-Za-z0-9])"),
    )


def test_tracked_tree_uses_only_surgepilot_identity() -> None:
    patterns = _forbidden_patterns()
    findings: list[str] = []

    for path in _tracked_paths():
        relative = path.relative_to(ROOT)
        encoded_path = relative.as_posix().encode()
        if any(pattern.search(encoded_path) for pattern in patterns):
            findings.append(f"path:{relative}")

        content = path.read_bytes()
        try:
            content.decode("utf-8")
        except UnicodeDecodeError:
            content_patterns = patterns[:2]
        else:
            content_patterns = patterns
        if any(pattern.search(content) for pattern in content_patterns):
            findings.append(f"content:{relative}")

    assert not findings, "Legacy product identity remains:\n" + "\n".join(findings[:100])
