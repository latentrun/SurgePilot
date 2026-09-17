from __future__ import annotations

from datetime import timedelta
import importlib
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.time import as_utc, utc_now
from app.models.auth import SessionRecord


def make_skill_source(tmp_path: Path) -> Path:
    root = tmp_path / "surgepilot-public-api"
    (root / "references").mkdir(parents=True)
    (root / "scripts" / "__pycache__").mkdir(parents=True)
    (root / "tests" / ".pytest_cache").mkdir(parents=True)
    (root / "SKILL.md").write_text("# SurgePilot Public API\n")
    (root / "references" / "public-api.openapi.json").write_text("{}\n")
    (root / "references" / ".env.local").write_text("SURGEPILOT_PAT=secret")
    (root / "scripts" / "surgepilot_call.py").write_text("print('call')\n")
    (root / "scripts" / ".env").write_text("SURGEPILOT_PAT=secret")
    (root / "scripts" / "ignored.pyc").write_bytes(b"bytecode")
    (root / "scripts" / "scratch.tmp").write_text("temporary")
    (root / "scripts" / "backup~").write_text("backup")
    (root / "scripts" / "__pycache__" / "cached.py").write_text("cached")
    (root / "tests" / "test_contract.py").write_text("def test_contract(): pass\n")
    (root / "tests" / ".pytest_cache" / "state").write_text("cache")
    (root / ".env").write_text("SURGEPILOT_PAT=secret")
    return root


def zip_names(stream: BytesIO) -> list[str]:
    with ZipFile(stream) as archive:
        return sorted(archive.namelist())


def test_skill_bundle_builds_safe_source_archive(tmp_path: Path) -> None:
    module = importlib.import_module("app.services.skill_bundle")
    root = make_skill_source(tmp_path)
    try:
        (root / "scripts" / "linked.py").symlink_to(root / "scripts" / "surgepilot_call.py")
    except OSError:
        pass

    stream = module.SkillBundle(root).build_zip()

    assert zip_names(stream) == [
        "surgepilot-public-api/SKILL.md",
        "surgepilot-public-api/references/public-api.openapi.json",
        "surgepilot-public-api/scripts/surgepilot_call.py",
        "surgepilot-public-api/tests/test_contract.py",
    ]


def test_skill_bundle_requires_skill_markdown(tmp_path: Path) -> None:
    module = importlib.import_module("app.services.skill_bundle")
    root = tmp_path / "empty"
    root.mkdir()

    try:
        module.SkillBundle(root).build_zip()
    except module.SkillBundleUnavailable as exc:
        assert str(exc) == "AI skill source is not available."
    else:
        raise AssertionError("missing SKILL.md must fail closed")


def test_skill_bundle_builds_independent_archives_per_request(tmp_path: Path) -> None:
    module = importlib.import_module("app.services.skill_bundle")
    root = make_skill_source(tmp_path)

    first = module.SkillBundle(root).build_zip()
    second = module.SkillBundle(root).build_zip()

    assert first is not second
    assert zip_names(first) == zip_names(second)


def test_skill_bundle_excludes_files_reached_through_symlinked_directory(
    tmp_path: Path,
) -> None:
    module = importlib.import_module("app.services.skill_bundle")
    root = make_skill_source(tmp_path / "source")
    external = tmp_path / "external"
    external.mkdir()
    external_file = external / "outside.py"
    external_file.write_text("print('outside')\n")
    linked_directory = root / "scripts" / "linked-directory"
    try:
        linked_directory.symlink_to(external, target_is_directory=True)
    except OSError:
        return

    assert module._excluded(linked_directory / external_file.name, root) is True


def test_skill_bundle_excludes_resolved_escape_and_missing_entry(tmp_path: Path) -> None:
    module = importlib.import_module("app.services.skill_bundle")
    root = make_skill_source(tmp_path / "source")
    external = root.parent / "external"
    external.mkdir()
    external_file = external / "outside.py"
    external_file.write_text("print('outside')\n")
    lexical_escape = root / "scripts" / ".." / ".." / "external" / external_file.name

    assert module._excluded(lexical_escape, root) is True
    assert module._excluded(root / "scripts" / "missing.py", root) is True


def test_default_skill_bundle_dir_prefers_container_then_repo(tmp_path: Path, monkeypatch) -> None:
    module = importlib.import_module("app.services.skill_bundle")
    container = make_skill_source(tmp_path / "container")
    repo = make_skill_source(tmp_path / "repo")
    monkeypatch.setattr(module, "CONTAINER_SKILL_BUNDLE_DIR", container)
    monkeypatch.setattr(module, "repo_skill_bundle_dir", lambda: repo)

    assert module.default_skill_bundle_dir() == container

    (container / "SKILL.md").unlink()
    assert module.default_skill_bundle_dir() == repo


async def register_user(client: AsyncClient, *, email: str) -> dict:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "displayName": "AI Skill User",
            "password": "password123",
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.mark.anyio
async def test_ai_skill_download_requires_session(client: AsyncClient) -> None:
    response = await client.get("/api/v1/account/ai-skill/download")

    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"


@pytest.mark.anyio
async def test_ai_skill_download_returns_private_zip_without_workspace_resolution(
    client: AsyncClient, tmp_path: Path, monkeypatch
) -> None:
    module = importlib.import_module("app.routes.account_ai_skill")
    service = importlib.import_module("app.services.skill_bundle")
    root = make_skill_source(tmp_path)
    monkeypatch.setattr(module, "SkillBundle", lambda: service.SkillBundle(root))
    await register_user(client, email="skill-user@example.com")

    response = await client.get(
        "/api/v1/account/ai-skill/download",
        headers={"x-workspace-id": "not-a-workspace-id"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert response.headers["content-disposition"] == (
        'attachment; filename="surgepilot-public-api-skill.zip"'
    )
    assert response.headers["cache-control"] == "private, no-store"
    assert "x-workspace-id" not in response.headers
    assert zip_names(BytesIO(response.content))[0] == "surgepilot-public-api/SKILL.md"


@pytest.mark.anyio
async def test_ai_skill_download_source_failure_is_safe_and_route_local(
    client: AsyncClient, monkeypatch
) -> None:
    module = importlib.import_module("app.routes.account_ai_skill")
    service = importlib.import_module("app.services.skill_bundle")

    class MissingBundle:
        def build_zip(self):
            raise service.SkillBundleUnavailable("AI skill source is not available.")

    monkeypatch.setattr(module, "SkillBundle", MissingBundle)
    await register_user(client, email="missing-skill@example.com")

    response = await client.get("/api/v1/account/ai-skill/download")

    assert response.status_code == 503
    assert response.json() == {
        "code": "AI_SKILL_SOURCE_NOT_AVAILABLE",
        "message": "AI skill source is not available.",
        "requestId": response.headers["x-request-id"],
    }
    assert "x-workspace-id" not in response.headers
    assert "/opt/surgepilot" not in response.text


@pytest.mark.anyio
async def test_ai_skill_download_allows_normal_user(
    client: AsyncClient, tmp_path: Path, monkeypatch
) -> None:
    module = importlib.import_module("app.routes.account_ai_skill")
    service = importlib.import_module("app.services.skill_bundle")
    root = make_skill_source(tmp_path)
    monkeypatch.setattr(module, "SkillBundle", lambda: service.SkillBundle(root))
    await register_user(client, email="first-admin@example.com")
    registered = await register_user(client, email="normal-user@example.com")

    response = await client.get("/api/v1/account/ai-skill/download")

    assert registered["user"]["role"] == "user"
    assert response.status_code == 200


@pytest.mark.anyio
async def test_ai_skill_download_persists_sliding_session_activity(
    client: AsyncClient,
    db_session: Session,
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = importlib.import_module("app.routes.account_ai_skill")
    service = importlib.import_module("app.services.skill_bundle")
    root = make_skill_source(tmp_path)
    monkeypatch.setattr(module, "SkillBundle", lambda: service.SkillBundle(root))
    await register_user(client, email="session-activity@example.com")
    session = db_session.scalar(select(SessionRecord))
    assert session is not None
    previous_last_seen = utc_now() - timedelta(hours=1)
    session.last_seen_at = previous_last_seen
    db_session.commit()

    response = await client.get("/api/v1/account/ai-skill/download")
    db_session.rollback()
    db_session.expire_all()
    refreshed = db_session.scalar(select(SessionRecord))

    assert response.status_code == 200
    assert refreshed is not None
    assert as_utc(refreshed.last_seen_at) > as_utc(previous_last_seen)
