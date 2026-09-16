from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[2]
DOCS_SITE = ROOT / "docs" / "site"
DOCS_ROOT = DOCS_SITE / "docs"
LOCALE_DIRS = ("zh-CN", "ja")
PUBLIC_REPOSITORY = "https://github.com/latentrun/SurgePilot"
EXPECTED_PAGES = {
    "configuration.md",
    "faq.md",
    "first-run.md",
    "index.md",
    "quickstart.md",
    "startup-modes.md",
}
MARKDOWN_TARGET_PATTERN = re.compile(r"!?(?:\[[^\]]*\])\(([^)]+)\)")


def test_localized_user_guides_mirror_the_exact_authorized_page_set() -> None:
    english_pages = {path.name for path in DOCS_ROOT.glob("*.md")}
    assert english_pages == EXPECTED_PAGES

    for locale in LOCALE_DIRS:
        locale_dir = DOCS_ROOT / locale
        actual = {path.name for path in locale_dir.glob("*.md")}

        assert actual == EXPECTED_PAGES, locale


def test_public_site_keeps_user_guides_only_below_docs() -> None:
    assert (DOCS_SITE / "index.md").is_file()
    assert not (DOCS_SITE / "quickstart.md").exists()
    assert not (DOCS_SITE / "zh-CN").exists()
    assert not (DOCS_SITE / "ja").exists()


def test_localized_markdown_targets_resolve_within_their_locale_or_shared_public_assets() -> None:
    for locale in LOCALE_DIRS:
        locale_dir = DOCS_ROOT / locale
        for page_name in EXPECTED_PAGES:
            page = locale_dir / page_name
            for raw_target in MARKDOWN_TARGET_PATTERN.findall(page.read_text(encoding="utf-8")):
                target = unquote(raw_target.split("#", maxsplit=1)[0])
                if not target or "://" in target or target.startswith("mailto:"):
                    continue

                if target.startswith("/"):
                    resolved = DOCS_SITE / "public" / target.removeprefix("/")
                else:
                    resolved = page.parent / target

                assert resolved.exists(), f"{page.relative_to(ROOT)} -> {raw_target}"


def test_public_quickstarts_use_the_public_release_installer_target() -> None:
    public_installer = f"{PUBLIC_REPOSITORY}/releases/latest/download/install.sh"

    for locale in ("en", *LOCALE_DIRS):
        page = DOCS_ROOT / (locale if locale != "en" else "") / "quickstart.md"
        content = page.read_text(encoding="utf-8")

        assert public_installer in content, page.relative_to(ROOT)


def test_public_docs_home_explains_core_workflow_without_inactive_skill_reference() -> None:
    workflow_markers = {
        "en": (
            "## Core workflow",
            "**Scenario**",
            "**Env Group**",
            "**Test Plan**",
            "**Load Node**",
            "**Run Report**",
        ),
        "zh-CN": (
            "## 核心工作流",
            "**Scenario**",
            "**Env Group**",
            "**Test Plan**",
            "**Load Node**",
            "**Run Report**",
        ),
        "ja": (
            "## コアワークフロー",
            "**Scenario**",
            "**Env Group**",
            "**Test Plan**",
            "**Load Node**",
            "**Run Report**",
        ),
    }
    removed_authorship_markers = {
        "en": (
            "## 🤖 Original AI-authored baseline",
            "Human responsibilities",
            "AI-agent responsibilities",
        ),
        "zh-CN": ("## 🤖 原始 AI 构建基线", "人类职责", "AI Agent 职责"),
        "ja": ("## 🤖 最初の AI 作成ベースライン", "人間の責任", "AI Agent の責任"),
    }

    for locale in ("en", *LOCALE_DIRS):
        page = DOCS_ROOT / (locale if locale != "en" else "") / "index.md"
        content = page.read_text(encoding="utf-8")

        for marker in workflow_markers[locale]:
            assert marker in content, page.relative_to(ROOT)
        for marker in removed_authorship_markers[locale]:
            assert marker not in content, page.relative_to(ROOT)
        assert "AI Skill" not in content, page.relative_to(ROOT)
