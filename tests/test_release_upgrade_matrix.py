"""Formal release upgrade sources must cover the published supported range."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from scripts import release_upgrade_matrix
from scripts.release_upgrade_matrix import ReleaseUpgradeMatrixError, build_upgrade_matrix


def release(tag: str, *, draft: bool = False, prerelease: bool = False) -> dict[str, object]:
    return {"tag_name": tag, "draft": draft, "prerelease": prerelease}


def test_matrix_includes_every_published_source_and_latest_clean_down() -> None:
    matrix = build_upgrade_matrix(
        "v1.2.4",
        [
            [release("v1.2.3"), release("v1.1.0"), release("v1.0.0")],
            [release("v1.2.4", draft=True), release("v1.2.5", prerelease=True)],
        ],
    )

    assert matrix == {
        "include": [
            {"source": "v1.0.0", "source_product_version": "0.1.0", "source_mode": "running"},
            {"source": "v1.1.0", "source_product_version": "1.1.0", "source_mode": "running"},
            {"source": "v1.2.3", "source_product_version": "1.2.3", "source_mode": "running"},
            {"source": "v1.2.3", "source_product_version": "1.2.3", "source_mode": "clean_down"},
        ]
    }


def test_first_upgrade_capable_release_keeps_historical_matrix() -> None:
    matrix = build_upgrade_matrix("v1.2.3", [[release("v1.1.0"), release("v1.0.0")]])
    assert [entry["source"] for entry in matrix["include"]] == [
        "v1.0.0",
        "v1.1.0",
        "v1.1.0",
    ]


@pytest.mark.parametrize(
    "pages",
    [
        [],
        [[release("v1.2.3")], {"not": "a page"}],
        [[release("v1.2.3"), release("v1.2.3")]],
        [[{"tag_name": "v1.2.3", "draft": False}]],
    ],
)
def test_matrix_fails_closed_on_incomplete_release_listing(pages: object) -> None:
    with pytest.raises(ReleaseUpgradeMatrixError):
        build_upgrade_matrix("v1.2.4", pages)


def test_matrix_excludes_other_majors_and_versions_outside_supported_range() -> None:
    matrix = build_upgrade_matrix(
        "v1.2.4",
        [[release("v0.9.9"), release("v1.2.3"), release("v1.2.4"), release("v2.0.0")]],
    )
    assert [entry["source"] for entry in matrix["include"]] == ["v1.2.3", "v1.2.3"]


def test_matrix_rejects_invalid_target_and_no_supported_sources() -> None:
    with pytest.raises(ReleaseUpgradeMatrixError, match="canonical"):
        build_upgrade_matrix("validation-123", [[release("v1.2.3")]])
    with pytest.raises(ReleaseUpgradeMatrixError, match="no published source"):
        build_upgrade_matrix("v1.2.4", [[release("v0.9.9")]])


def test_matrix_rejects_invalid_release_entry_and_excess_jobs() -> None:
    with pytest.raises(ReleaseUpgradeMatrixError, match="entry is invalid"):
        build_upgrade_matrix("v1.2.4", [[None]])
    versions = [release(f"v1.0.{index}") for index in range(256)]
    with pytest.raises(ReleaseUpgradeMatrixError, match="job limit"):
        build_upgrade_matrix("v1.2.4", [versions])


def test_matrix_fails_if_bundle_minimum_is_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(release_upgrade_matrix, "minimum_upgrade_version", lambda _target: "bad")
    with pytest.raises(ReleaseUpgradeMatrixError, match="minimum upgrade version"):
        build_upgrade_matrix("v1.2.4", [[release("v1.2.3")]])


def test_cli_emits_one_github_output_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    releases = tmp_path / "releases.json"
    releases.write_text(json.dumps([[release("v1.2.3")]]), encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        ["release_upgrade_matrix", "--target", "v1.2.4", "--releases", str(releases)],
    )
    release_upgrade_matrix.main()
    output = capsys.readouterr().out
    assert output.startswith('matrix={"include":')
    assert json.loads(output.removeprefix("matrix="))["include"][0]["source"] == "v1.2.3"


def test_cli_rejects_unreadable_release_listing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["release_upgrade_matrix", "--target", "v1.2.4", "--releases", str(tmp_path)],
    )
    with pytest.raises(SystemExit) as exc_info:
        release_upgrade_matrix.main()
    assert exc_info.value.code == 2


def test_module_entrypoint_emits_github_output(tmp_path: Path) -> None:
    releases = tmp_path / "releases.json"
    releases.write_text(json.dumps([[release("v1.2.3")]]), encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.release_upgrade_matrix",
            "--target",
            "v1.2.4",
            "--releases",
            str(releases),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith('matrix={"include":')
