from __future__ import annotations

import argparse
from pathlib import Path
import re


REQUIRED_SECTIONS = (
    "Highlights",
    "Install",
    "Upgrade",
    "Compatibility and breaking changes",
    "Full changelog",
)
HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


def validate_release_notes(*, tag: str, path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    expected_title = f"# SurgePilot {tag}"
    lines = text.splitlines()
    if not lines or lines[0] != expected_title:
        raise ValueError(f"release notes must start with exactly: {expected_title}")

    headings: list[tuple[str, int]] = []
    for index, line in enumerate(lines[1:], start=1):
        if line.startswith("## "):
            headings.append((line[3:], index))

    actual_sections = tuple(heading for heading, _ in headings)
    if actual_sections != REQUIRED_SECTIONS:
        expected = ", ".join(REQUIRED_SECTIONS)
        raise ValueError(f"release notes must contain these sections in order: {expected}")

    for section_index, (heading, line_index) in enumerate(headings):
        next_index = (
            headings[section_index + 1][1] if section_index + 1 < len(headings) else len(lines)
        )
        body = "\n".join(lines[line_index + 1 : next_index])
        substantive_body = HTML_COMMENT.sub("", body).strip()
        if not substantive_body:
            raise ValueError(f"{heading} must contain substantive content")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a versioned SurgePilot release note")
    parser.add_argument("--tag", required=True)
    parser.add_argument("--path", required=True, type=Path)
    args = parser.parse_args()

    try:
        validate_release_notes(tag=args.tag, path=args.path)
    except (OSError, UnicodeError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
