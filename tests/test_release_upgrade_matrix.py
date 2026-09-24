from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

from scripts.release_upgrade_matrix import main, upgrade_matrix


def release(tag: str, *, draft: bool = False, prerelease: bool = False) -> dict[str, object]:
    return {"tag_name": tag, "draft": draft, "prerelease": prerelease}


def test_v1_matrix_covers_every_published_source_and_latest_clean_down() -> None:
    matrix = upgrade_matrix(
        "v1.2.4",
        [
            [release("v1.2.3"), release("v2.0.0"), release("v1.1.0")],
            [
                release("v1.0.0"),
                release("v1.2.2", draft=True),
                release("v1.2.1", prerelease=True),
                release("v01.2.0"),
            ],
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


@pytest.mark.parametrize(
    "pages",
    [
        [],
        [{"message": "rate limit"}],
        [[{"tag_name": "v1.0.0", "draft": False}]],
        [[release("v1.0.0")], [release("v1.0.0")]],
    ],
)
def test_matrix_rejects_incomplete_or_duplicate_listing(pages: object) -> None:
    with pytest.raises(ValueError):
        upgrade_matrix("v1.2.4", pages)


def test_first_new_major_has_no_upgrade_sources() -> None:
    assert upgrade_matrix("v2.0.0", [[]]) == {"include": []}
    assert upgrade_matrix("v2.0.0", [[release("v1.2.3")]]) == {"include": []}


def test_missing_advertised_source_fails_closed() -> None:
    with pytest.raises(ValueError, match="No published source"):
        upgrade_matrix("v1.2.4", [[release("v2.0.0"), release("v1.2.3", draft=True)]])


def test_matrix_cli_emits_compact_json_and_fails_on_bad_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    releases = tmp_path / "releases.json"
    releases.write_text(json.dumps([[release("v1.0.0")]]), encoding="utf-8")
    monkeypatch.setattr(
        sys, "argv", ["release_upgrade_matrix", "--target", "v1.2.4", "--releases", str(releases)]
    )
    assert main() == 0
    assert json.loads(capsys.readouterr().out)["include"][0]["source"] == "v1.0.0"

    releases.write_text('{"message":"rate limit"}', encoding="utf-8")
    assert main() == 1
    assert "Upgrade matrix failed" in capsys.readouterr().err
