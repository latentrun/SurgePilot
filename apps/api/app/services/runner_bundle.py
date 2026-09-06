from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class RunnerBundleFile:
    relative_path: str
    content: bytes
    mode: int = 0o644


class RunnerBundle:
    def __init__(self, bundle_dir: Path | None = None) -> None:
        self.bundle_dir = bundle_dir or default_runner_bundle_dir()

    def files(self) -> list[RunnerBundleFile]:
        root = self.bundle_dir
        required = [root / "runner.py", root / "surgepilot_runner" / "cli.py"]
        missing = [str(path) for path in required if not path.exists()]
        if missing:
            raise FileNotFoundError("Runner bundle is missing required files.")
        files: list[RunnerBundleFile] = []
        for path in [root / "runner.py", *sorted((root / "surgepilot_runner").glob("*.py"))]:
            files.append(
                RunnerBundleFile(
                    relative_path=path.relative_to(root).as_posix(),
                    content=path.read_bytes(),
                    mode=0o755 if path.name == "runner.py" else 0o644,
                )
            )
        return files


def default_runner_bundle_dir() -> Path:
    configured = os.environ.get("SURGEPILOT_RUNNER_BUNDLE_DIR")
    candidates = []
    if configured:
        candidates.append(Path(configured))
    candidates.append(Path("/opt/surgepilot/runner-bundle"))
    for parent in Path(__file__).resolve().parents:
        repo_candidate = parent / "apps" / "runner"
        if (repo_candidate / "runner.py").exists():
            candidates.append(repo_candidate)
            break
    for candidate in candidates:
        if (candidate / "runner.py").exists():
            return candidate
    return candidates[0]
