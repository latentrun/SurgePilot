"""Select formal release upgrade smoke sources from published GitHub Releases."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

from scripts.build_release_bundle import minimum_upgrade_version


VERSION_PATTERN = re.compile(r"v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\Z")


def version_parts(version: str) -> tuple[int, int, int]:
    match = VERSION_PATTERN.fullmatch(version)
    if match is None:
        raise ValueError(f"Noncanonical release version: {version}")
    return tuple(int(part) for part in match.groups())


def upgrade_matrix(target: str, pages: object) -> dict[str, list[dict[str, str]]]:
    target_parts = version_parts(target)
    minimum = minimum_upgrade_version(target)
    minimum_parts = version_parts(minimum)
    if not isinstance(pages, list) or not pages:
        raise ValueError("GitHub Releases listing is missing or incomplete")

    sources: list[tuple[tuple[int, int, int], str]] = []
    seen: set[str] = set()
    for page in pages:
        if not isinstance(page, list):
            raise ValueError("GitHub Releases page is not an array")
        for release in page:
            if not isinstance(release, dict):
                raise ValueError("GitHub Release entry is invalid")
            tag = release.get("tag_name")
            draft = release.get("draft")
            prerelease = release.get("prerelease")
            if (
                not isinstance(tag, str)
                or not isinstance(draft, bool)
                or not isinstance(prerelease, bool)
            ):
                raise ValueError("GitHub Release entry is incomplete")
            if VERSION_PATTERN.fullmatch(tag) is None:
                continue
            if tag in seen:
                raise ValueError(f"Duplicate GitHub Release version: {tag}")
            seen.add(tag)
            if draft or prerelease:
                continue
            parts = version_parts(tag)
            if parts[0] == target_parts[0] and minimum_parts <= parts < target_parts:
                sources.append((parts, tag))

    sources.sort()
    if not sources and minimum_parts < target_parts:
        raise ValueError("No published source covers the advertised upgrade range")

    include = [
        {
            "source": tag,
            "source_product_version": "0.1.0" if tag == "v1.0.0" else tag[1:],
            "source_mode": "running",
        }
        for _, tag in sources
    ]
    if sources:
        latest = include[-1].copy()
        latest["source_mode"] = "clean_down"
        include.append(latest)
    return {"include": include}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True)
    parser.add_argument("--releases", type=Path, required=True)
    args = parser.parse_args()
    try:
        pages = json.loads(args.releases.read_text(encoding="utf-8"))
        matrix = upgrade_matrix(args.target, pages)
    except (OSError, ValueError) as exc:
        print(f"Upgrade matrix failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(matrix, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
