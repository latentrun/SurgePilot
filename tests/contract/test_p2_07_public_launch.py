from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
WEB_ROOT = ROOT / "apps" / "web"
NOINDEX_DIRECTIVES = {"noindex", "nofollow", "noarchive"}
PUBLIC_REPOSITORY = "https://github.com/latentrun/SurgePilot"
PUBLIC_SITE = "https://latentrun.github.io/SurgePilot/"
README_PATHS = (ROOT / "README.md", ROOT / "README.zh-CN.md", ROOT / "README.ja.md")
LAUNCH_ROOT = ROOT / "docs" / "launch"
PREVIOUS_OWNER_NAMESPACE = "william" + "-best" + "/SurgePilot"


class _MetaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.meta: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "meta":
            return
        values = dict(attrs)
        name = values.get("name")
        content = values.get("content")
        if name and content:
            self.meta[name.lower()] = content


def _directives(value: str) -> set[str]:
    return {directive.strip().lower() for directive in value.split(",")}


def test_self_hosted_web_is_noindex_before_react_boots() -> None:
    parser = _MetaParser()
    parser.feed((WEB_ROOT / "index.html").read_text(encoding="utf-8"))

    assert _directives(parser.meta["robots"]) == NOINDEX_DIRECTIVES
    assert _directives(parser.meta["googlebot"]) == NOINDEX_DIRECTIVES


def test_self_hosted_web_sends_noindex_for_every_nginx_response() -> None:
    nginx = (WEB_ROOT / "nginx.conf").read_text(encoding="utf-8")

    assert 'add_header X-Robots-Tag "noindex, nofollow, noarchive" always;' in nginx


def test_self_hosted_web_does_not_publish_a_crawler_blocking_robots_file() -> None:
    robots = WEB_ROOT / "public" / "robots.txt"
    if robots.exists():
        assert "Disallow: /" not in robots.read_text(encoding="utf-8")


def test_docs_home_preserves_original_desktop_hero_scale() -> None:
    css = (ROOT / "docs" / "site" / ".vitepress" / "theme" / "custom.css").read_text(
        encoding="utf-8"
    )
    desktop_rules = re.search(
        r"@media \(min-width: 960px\)\s*\{"
        r"(?P<rules>(?:[^{}]|\{[^{}]*\})*)\}",
        css,
        re.DOTALL,
    )

    assert desktop_rules is not None
    rules = desktop_rules.group("rules")
    assert re.search(
        r"\.VPHero\.has-image \.image\s*\{[^}]*max-width: 520px !important;",
        rules,
        re.DOTALL,
    )
    assert re.search(
        r"\.VPHero \.image-container\s*\{[^}]*width: 480px !important;"
        r"[^}]*height: 480px !important;",
        rules,
        re.DOTALL,
    )
    assert re.search(r"\.VPHero \.image-src\s*\{[^}]*width: 480px;", rules, re.DOTALL)


def test_docs_home_offsets_wide_hero_from_copy() -> None:
    css = (ROOT / "docs" / "site" / ".vitepress" / "theme" / "custom.css").read_text(
        encoding="utf-8"
    )

    assert re.search(
        r"@media \(min-width: 1152px\)\s*\{\s*"
        r"\.VPHero \.image-container\s*\{[^}]*left: 48px;",
        css,
        re.DOTALL,
    )


def test_public_readmes_open_with_accurate_conversion_and_evidence_links() -> None:
    unsupported_positioning = re.compile(
        r"production-grade|enterprise-grade|生产级|企业级|プロダクショングレード|"
        r"エンタープライズグレード",
        re.IGNORECASE,
    )
    ai_tool_evidence_headers = {
        "README.md": "| Stage | AI-produced artifact | AI tools used | Evidence in this repo |",
        "README.zh-CN.md": "| 阶段 | AI 产物 | 使用的 AI 工具 | 仓库中的依据 |",
        "README.ja.md": "| ステージ | AI が作成したもの | 使用した AI ツール | リポジトリ内の根拠 |",
    }
    ai_tool_evidence_rows = {
        "README.md": (
            "| 1. Product | Product requirements | GPT · Gemini |",
            "| 2. UI/UX | Frontend interface and experience | Claude · Gemini · Google Stitch |",
            "| 3. System design | SDD, scope gates, ADRs, and accepted Slices | GPT · Claude |",
            "| 4. Implementation | Application code and API contracts | GPT |",
            "| 5. Verification | Review fixes, tests, and gates | GPT · Claude |",
            "| 6. Release | Startup, deployment, and release assets | GPT |",
        ),
        "README.zh-CN.md": (
            "| 1. 产品 | 产品需求文档 | GPT · Gemini |",
            "| 2. UI/UX | 前端界面与体验 | Claude · Gemini · Google Stitch |",
            "| 3. 系统设计 | SDD、范围门禁、ADR 和已接受的 Slice | GPT · Claude |",
            "| 4. 编码实现 | 应用代码与 API 契约 | GPT |",
            "| 5. 验证 | Review 修复、测试和门禁 | GPT · Claude |",
            "| 6. 发布 | 启动、部署与发布资产 | GPT |",
        ),
        "README.ja.md": (
            "| 1. プロダクト | プロダクト要件 | GPT · Gemini |",
            "| 2. UI/UX | フロントエンドのインターフェースと体験 | Claude · Gemini · Google Stitch |",
            "| 3. システム設計 | SDD、Scope Gate、ADR、承認済み Slice | GPT · Claude |",
            "| 4. 実装 | アプリケーションコードと API Contract | GPT |",
            "| 5. 検証 | Review 修正、テスト、ゲート | GPT · Claude |",
            "| 6. リリース | 起動、デプロイ、リリース資産 | GPT |",
        ),
    }

    for path in README_PATHS:
        content = path.read_text(encoding="utf-8")
        opening = content[:6000]

        assert PUBLIC_REPOSITORY in opening, path.name
        assert PUBLIC_SITE in opening, path.name
        assert f"{PUBLIC_SITE}docs/" in opening, path.name
        assert f"{PUBLIC_REPOSITORY}/releases" in opening, path.name
        assert "AI-AUTHORSHIP.md" in opening, path.name
        assert (
            "original public baseline" in content
            or "原始公开基线" in content
            or "最初の公開ベースライン" in content
        )
        assert PREVIOUS_OWNER_NAMESPACE not in content, path.name
        assert not unsupported_positioning.search(content), path.name
        assert ai_tool_evidence_headers[path.name] in content, path.name
        for row in ai_tool_evidence_rows[path.name]:
            assert row in content, path.name


def test_ai_authorship_evidence_defines_scope_and_v1_baseline_tag() -> None:
    evidence = (ROOT / "AI-AUTHORSHIP.md").read_text(encoding="utf-8")

    for human_responsibility in (
        "product intent",
        "requirements discussion",
        "product use",
        "usage feedback",
        "result acceptance",
    ):
        assert human_responsibility in evidence
    for ai_responsibility in (
        "product and engineering-process design",
        "quality-gate design and enforcement",
        "verification-failure resolution",
        "deployment and release assets",
    ):
        assert ai_responsibility in evidence

    assert "Baseline tag: `v1.0.0`, selected for immutable publication" in evidence
    assert "releases/tag/v1.0.0" in evidence
    assert "actions/workflows/release-validation.yml" in evidence
    assert "actions/workflows/release.yml" in evidence
    for relative_target in (
        "AGENTS.md",
        "docs/prd/PRD.md",
        "docs/sdd/README.md",
        "packages/contracts/openapi/public-api.openapi.json",
    ):
        assert f"]({relative_target})" in evidence
        assert (ROOT / relative_target).exists(), relative_target
    assert "Future contributions may be human- or AI-authored" in evidence
    assert "model, prompt, or provenance attestation" in evidence


def test_repository_has_mit_security_and_open_contribution_policies() -> None:
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert license_text.startswith("MIT License\n")
    assert "Permission is hereby granted, free of charge" in license_text

    security = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
    assert f"{PUBLIC_REPOSITORY}/security/advisories/new" in security
    assert "public issue" in security.lower()
    assert "response-time SLA" in security

    contributing = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    normalized_contributing = " ".join(contributing.split())
    assert "human- or AI-authored" in contributing
    assert (
        "No model, prompt, transcript, or provenance attestation is required"
        in normalized_contributing
    )
    assert "make verify" in contributing
    assert "main" in contributing

    code_of_conduct = (ROOT / "CODE_OF_CONDUCT.md").read_text(encoding="utf-8")
    assert "Contributor Covenant" in code_of_conduct
    assert "Version 2.1" in code_of_conduct


def test_demo_recording_guide_is_reproducible_and_does_not_claim_a_video_exists() -> None:
    guide = (LAUNCH_ROOT / "demo-recording-guide.md").read_text(encoding="utf-8")

    assert "60–120 seconds" in guide
    assert "make start-full-stack" in guide
    assert "OBS Studio" in guide
    assert "ffmpeg" in guide
    assert "-movflags +faststart" in guide
    for sensitive_item in (".env", "Personal Access Token", "email", "private IP"):
        assert sensitive_item in guide
    assert "No demo video is included" in guide
    assert "Do not claim that a recording exists" in guide


def test_launch_runbook_keeps_every_public_action_behind_manual_gates() -> None:
    runbook = (LAUNCH_ROOT / "public-launch-runbook.md").read_text(encoding="utf-8")
    normalized_runbook = " ".join(runbook.split())

    required_gates = (
        "Freeze private writes",
        "privacy, license, and repository gate",
        "latentrun/SurgePilot",
        "make verify",
        "immutable baseline tag",
        "anonymous installation",
        "GitHub Pages",
        "public visibility",
        "Rollback",
    )
    for gate in required_gates:
        assert gate in normalized_runbook
    assert (
        "Do not run any public-activation step without the repository owner's approval"
        in normalized_runbook
    )
    assert "AI-AUTHORSHIP.md" in runbook
    assert "release.yml" in runbook


def test_community_drafts_are_english_first_and_forbid_fake_or_mass_distribution() -> None:
    drafts = (LAUNCH_ROOT / "community-launch-drafts.md").read_text(encoding="utf-8")

    for channel in ("Show HN", "Reddit", "X / LinkedIn"):
        assert channel in drafts
    assert drafts.index("## English launch core") < drafts.index("## Optional Chinese adaptation")
    assert "Do not cross-post every channel at once" in drafts
    assert "Do not invent benchmarks, adoption, users, Stars, or production status" in drafts
    assert PUBLIC_REPOSITORY in drafts
    assert PUBLIC_SITE in drafts
    assert not re.search(
        r"\b\d[\d,.]*[kKmM]?\+?\s+(?:users|customers|stars|requests per second)\b",
        drafts,
        re.IGNORECASE,
    )


def test_repository_metadata_is_ready_for_manual_github_configuration() -> None:
    metadata = (LAUNCH_ROOT / "repository-metadata.md").read_text(encoding="utf-8")

    assert "About description" in metadata
    assert "Topics" in metadata
    assert "ai-agents" in metadata
    assert "distributed-systems" in metadata
    assert "load-testing" in metadata
    assert "docs/site/public/surgepilot-architecture.jpg" in metadata
    assert "Website" in metadata
    assert PUBLIC_SITE in metadata
    assert "GitHub Discussions: disabled at launch" in metadata


def test_pages_workflow_builds_pull_requests_and_deploys_main_only() -> None:
    workflow = (ROOT / ".github" / "workflows" / "pages-build.yml").read_text(encoding="utf-8")

    assert "contents: read" in workflow
    assert "pull_request:" in workflow
    assert "branches: [main]" in workflow
    assert "pnpm install --frozen-lockfile" in workflow
    assert "pnpm --filter @surgepilot/docs test" in workflow
    assert "docs/site/.vitepress/dist" in workflow
    for required in (
        "pages: write",
        "id-token: write",
        "actions/deploy-pages@d6db90164ac5ed86f2b6aed7e0febac5b3c0c03e",
        "actions/configure-pages@983d7736d9b0ae728b81ab479565c72886d7745b",
        "actions/upload-pages-artifact@7b1f4a764d45c48632c6b24a0339c27f5614fb0b",
        "name: github-pages",
        "url: ${{ steps.deployment.outputs.page_url }}",
        "if: ${{ github.event_name == 'push' && github.ref == 'refs/heads/main' }}",
    ):
        assert required in workflow
    assert workflow.index("needs: build") < workflow.index("actions/deploy-pages")
    assert "cancel-in-progress: false" in workflow
    for forbidden in ("tags:", "release:"):
        assert forbidden not in workflow


def test_docs_browser_is_playwright_managed_across_local_and_release_validation() -> None:
    verifier = (ROOT / "docs" / "site" / "tests" / "verify-browser.mjs").read_text(encoding="utf-8")
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    install_command = "pnpm --filter @surgepilot/docs exec playwright install --with-deps chromium"

    assert "chromium.launch(browserLaunchOptions)" in verifier
    assert "process.env.CHROME_PATH" in verifier
    assert "chromium.executablePath()" not in verifier
    assert '"/usr/bin/google-chrome"' not in verifier
    assert "setup-docs-browser:" in makefile
    assert "pnpm --filter @surgepilot/docs exec playwright install chromium" in makefile

    for workflow_path in (
        ROOT / ".github" / "workflows" / "pages-build.yml",
        ROOT / ".github" / "workflows" / "release-validation.yml",
        ROOT / ".github" / "workflows" / "release.yml",
    ):
        workflow = workflow_path.read_text(encoding="utf-8")
        assert install_command in workflow
        if "make verify" in workflow:
            assert workflow.index(install_command) < workflow.index("make verify")


def test_public_readiness_audit_records_approved_v1_release_gates() -> None:
    audit = (LAUNCH_ROOT / "public-readiness-audit.md").read_text(encoding="utf-8")

    assert "Overall status: RELEASE CANDIDATE APPROVED" in audit
    for category in (
        "Credential filenames and secret material",
        "Private endpoints and IP addresses",
        "Personal filesystem paths",
        "Git author emails",
        "Asset and license provenance",
        "Repository and package namespace migration",
    ):
        assert category in audit
    assert "Raw matches are intentionally not copied" in audit
    assert "owner explicitly accepted public exposure" in audit
    assert "latentrun/SurgePilot" in audit
    assert "`v1.0.0` is the owner-selected original public baseline" in audit
    assert "Gitleaks 8.28.0" in audit
    for replaced_command in ("git ls-files", "git grep", "git log"):
        assert replaced_command not in audit


def test_secret_scan_allowlist_is_exact_and_font_licenses_are_vendored() -> None:
    allowlist = (ROOT / ".gitleaksignore").read_text(encoding="utf-8")
    fingerprints = [
        line.strip()
        for line in allowlist.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]

    assert len(fingerprints) == 36
    assert len(set(fingerprints)) == 36
    history_fingerprints = [item for item in fingerprints if len(item.split(":")) == 4]
    tree_fingerprints = [item for item in fingerprints if len(item.split(":")) == 3]
    assert len(history_fingerprints) == 18
    assert len(tree_fingerprints) == 18
    assert all(
        len(fingerprint.split(":", maxsplit=1)[0]) == 40 for fingerprint in history_fingerprints
    )

    font_licenses = (
        ROOT / "apps" / "web" / "src" / "assets" / "fonts" / "geist" / "OFL.txt",
        ROOT / "apps" / "web" / "src" / "assets" / "fonts" / "jetbrains-mono" / "OFL.txt",
    )
    for license_path in font_licenses:
        license_text = license_path.read_text(encoding="utf-8")
        assert "SIL OPEN FONT LICENSE Version 1.1" in license_text
        assert "Copyright" in license_text
