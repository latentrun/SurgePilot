from __future__ import annotations

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate_release_notes.py"


def _run_validator(tmp_path: Path, content: str) -> subprocess.CompletedProcess[str]:
    notes_path = tmp_path / "v1.2.3.md"
    notes_path.write_text(content, encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(VALIDATOR), "--tag", "v1.2.3", "--path", str(notes_path)],
        check=False,
        capture_output=True,
        text=True,
    )


def test_accepts_complete_release_notes(tmp_path: Path) -> None:
    result = _run_validator(
        tmp_path,
        """# SurgePilot v1.2.3

## Highlights

- Adds a user-visible improvement.

## Install

Run the version-pinned installer.

## Upgrade

No migration is required.

## Compatibility and breaking changes

None.

## Full changelog

Compare v1.2.2 with v1.2.3.
""",
    )

    assert result.returncode == 0, result.stderr


def test_rejects_wrong_title(tmp_path: Path) -> None:
    result = _run_validator(tmp_path, "# SurgePilot v9.9.9\n")

    assert result.returncode != 0
    assert "must start with exactly" in result.stderr


def test_rejects_missing_or_empty_required_section(tmp_path: Path) -> None:
    result = _run_validator(
        tmp_path,
        """# SurgePilot v1.2.3

## Highlights

<!-- TODO -->

## Install

Install it.

## Upgrade

No migration is required.

## Compatibility and breaking changes

None.

## Full changelog

Compare the tags.
""",
    )

    assert result.returncode != 0
    assert "Highlights must contain substantive content" in result.stderr
