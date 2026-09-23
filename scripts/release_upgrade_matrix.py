"""Build the formal release upgrade smoke matrix from published GitHub Releases."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

from scripts.build_release_bundle import minimum_upgrade_version


VERSION_PATTERN = re.compile(r"v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\Z")


class ReleaseUpgradeMatrixError(ValueError):
    """Published release evidence cannot yield a complete upgrade matrix."""


def _version(tag: str) -> tuple[int, int, int] | None:
    match = VERSION_PATTERN.fullmatch(tag)
    if match is None:
        return None
    return int(match[1]), int(match[2]), int(match[3])


def build_upgrade_matrix(target: str, pages: object) -> dict[str, list[dict[str, str]]]:
    target_version = _version(target)
    if target_version is None:
        raise ReleaseUpgradeMatrixError("target must be a canonical vX.Y.Z tag")
    minimum_version = _version(minimum_upgrade_version(target))
    if minimum_version is None:
        raise ReleaseUpgradeMatrixError("minimum upgrade version is invalid")
    if not isinstance(pages, list) or not pages:
        raise ReleaseUpgradeMatrixError("published release listing is empty or invalid")

    sources: dict[str, tuple[int, int, int]] = {}
    for page in pages:
        if not isinstance(page, list):
            raise ReleaseUpgradeMatrixError("published release page is invalid")
        for release in page:
            if not isinstance(release, dict):
                raise ReleaseUpgradeMatrixError("published release entry is invalid")
            tag = release.get("tag_name")
            draft = release.get("draft")
            prerelease = release.get("prerelease")
            if (
                not isinstance(tag, str)
                or not isinstance(draft, bool)
                or not isinstance(prerelease, bool)
            ):
                raise ReleaseUpgradeMatrixError("published release metadata is incomplete")
            if draft or prerelease:
                continue
            version = _version(tag)
            if version is None or version[0] != target_version[0]:
                continue
            if not minimum_version <= version < target_version:
                continue
            if tag in sources:
                raise ReleaseUpgradeMatrixError(f"published release {tag} appears twice")
            sources[tag] = version

    if not sources:
        raise ReleaseUpgradeMatrixError("no published source release in the supported range")

    ordered_sources = sorted(sources, key=sources.__getitem__)
    include = [
        {
            "source": source,
            "source_product_version": "0.1.0" if source == "v1.0.0" else source[1:],
            "source_mode": "running",
        }
        for source in ordered_sources
    ]
    include.append({**include[-1], "source_mode": "clean_down"})
    if len(include) > 256:
        raise ReleaseUpgradeMatrixError("upgrade matrix exceeds the GitHub Actions job limit")
    return {"include": include}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True)
    parser.add_argument("--releases", type=Path, required=True)
    arguments = parser.parse_args()
    try:
        pages = json.loads(arguments.releases.read_text(encoding="utf-8"))
        matrix = build_upgrade_matrix(arguments.target, pages)
    except (OSError, json.JSONDecodeError, ReleaseUpgradeMatrixError) as exc:
        parser.error(str(exc))
    print(f"matrix={json.dumps(matrix, separators=(',', ':'))}")


if __name__ == "__main__":
    main()
