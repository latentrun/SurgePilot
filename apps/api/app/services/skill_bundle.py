from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


CONTAINER_SKILL_BUNDLE_DIR = Path("/opt/surgepilot/ai-skills/surgepilot-public-api")
ARCHIVE_ROOT = "surgepilot-public-api"
ALLOWED_ROOT_ENTRIES = ("SKILL.md", "references", "scripts", "tests")
EXCLUDED_DIR_NAMES = {"__pycache__", ".pytest_cache"}
EXCLUDED_FILE_SUFFIXES = {".pyc", ".pyo", ".tmp", ".temp"}


class SkillBundleUnavailable(Exception):
    pass


def repo_skill_bundle_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "packages" / "ai-skills" / "surgepilot-public-api"
        if (candidate / "SKILL.md").is_file():
            return candidate
    return Path("packages/ai-skills/surgepilot-public-api")


def default_skill_bundle_dir() -> Path:
    for candidate in (CONTAINER_SKILL_BUNDLE_DIR, repo_skill_bundle_dir()):
        if (candidate / "SKILL.md").is_file():
            return candidate
    return CONTAINER_SKILL_BUNDLE_DIR


def _excluded(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    current = root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            return True
    try:
        if not path.resolve(strict=True).is_relative_to(root.resolve(strict=True)):
            return True
    except OSError:
        return True
    return (
        any(part in EXCLUDED_DIR_NAMES for part in relative.parts)
        or path.name.startswith(".env")
        or path.name.endswith("~")
        or path.suffix.lower() in EXCLUDED_FILE_SUFFIXES
    )


class SkillBundle:
    def __init__(self, bundle_dir: Path | None = None) -> None:
        self.bundle_dir = bundle_dir or default_skill_bundle_dir()

    def build_zip(self) -> BytesIO:
        root = self.bundle_dir
        try:
            skill_markdown = root / "SKILL.md"
            if not skill_markdown.is_file() or skill_markdown.is_symlink():
                raise SkillBundleUnavailable("AI skill source is not available.")

            files: list[Path] = [skill_markdown]
            for entry_name in ALLOWED_ROOT_ENTRIES[1:]:
                entry = root / entry_name
                if not entry.is_dir() or entry.is_symlink():
                    continue
                files.extend(
                    path
                    for path in entry.rglob("*")
                    if path.is_file() and not _excluded(path, root)
                )

            stream = BytesIO()
            with ZipFile(stream, mode="w", compression=ZIP_DEFLATED) as archive:
                for path in sorted(files, key=lambda item: item.relative_to(root).as_posix()):
                    relative = path.relative_to(root)
                    archive.writestr(f"{ARCHIVE_ROOT}/{relative.as_posix()}", path.read_bytes())
            stream.seek(0)
            return stream
        except SkillBundleUnavailable:
            raise
        except (OSError, ValueError) as exc:
            raise SkillBundleUnavailable("AI skill source is not available.") from exc
