from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import BinaryIO

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.services.debug_http_trace import inject_debug_http_trace
from app.services.env_groups import internal_env_values
from app.models.dependency_files import DependencyFile
from app.models.runs import Run, RunSnapshot
from app.services.scenarios import (
    build_debug_taurus_yaml_from_content,
    bundle_file_path,
)
from app.services.test_plans import build_test_plan_taurus_document_from_snapshot
import yaml
from app.services.storage import get_storage_client

SAFE_BUNDLE_SEGMENT = re.compile(r"^[A-Za-z0-9._-]+$")
RUNTIME_JMETER_VERSION = "5.6.3"


def runtime_jmeter_path(runner_home: str) -> str:
    return f"{runner_home.rstrip('/')}/apache-jmeter/bin/jmeter"


@dataclass(frozen=True)
class StoredBundleObject:
    stream: BinaryIO
    size_bytes: int | None


@dataclass(frozen=True)
class ExecutionBundleFile:
    relative_path: str
    mode: int = 0o644
    content: bytes | None = None
    stream: BinaryIO | None = None

    @classmethod
    def text(cls, relative_path: str, content: str, *, mode: int = 0o644) -> ExecutionBundleFile:
        return cls(
            relative_path=validate_bundle_relative_path(relative_path),
            content=content.encode("utf-8"),
            mode=mode,
        )

    @classmethod
    def stream_file(
        cls, relative_path: str, stream: BinaryIO, *, mode: int = 0o644
    ) -> ExecutionBundleFile:
        return cls(
            relative_path=validate_bundle_relative_path(relative_path),
            stream=stream,
            mode=mode,
        )


def validate_bundle_relative_path(path: str) -> str:
    if not path or path.startswith("/") or "\\" in path or ":" in path or "//" in path:
        raise AppError("BUNDLE_INVALID", "Execution bundle is invalid.", 500)
    parts = path.split("/")
    if any(part in {"", ".", ".."} or not SAFE_BUNDLE_SEGMENT.fullmatch(part) for part in parts):
        raise AppError("BUNDLE_INVALID", "Execution bundle is invalid.", 500)
    return path


def _snapshot_for_run(db: Session, *, run_id: str) -> tuple[Run, RunSnapshot]:
    run = db.scalar(select(Run).where(Run.id == run_id))
    snapshot = db.scalar(select(RunSnapshot).where(RunSnapshot.run_id == run_id))
    if run is None or snapshot is None:
        raise AppError("BUNDLE_INVALID", "Execution bundle is invalid.", 500)
    if run.source_type not in {"debug_scenario", "test_plan"}:
        raise AppError("BUNDLE_INVALID", "Execution bundle is invalid.", 500)
    if snapshot.snapshot_json.get("sourceType") != run.source_type:
        raise AppError("BUNDLE_INVALID", "Execution bundle is invalid.", 500)
    return run, snapshot


def _env_variables(snapshot_payload: dict) -> dict[str, str]:
    env_group = snapshot_payload.get("envGroup")
    if not env_group:
        return {}
    return internal_env_values(dict(env_group.get("variables") or {}))


def _snapshot_jmeter_memory_xmx(snapshot_payload: dict) -> str:
    value = snapshot_payload.get("jmeterMemoryXmx")
    if isinstance(value, str) and value:
        return value
    return get_settings().jmeter_memory_xmx


def _dependency_file_ids(snapshot_payload: dict) -> list[str]:
    ids: list[str] = []
    for item in snapshot_payload.get("dependencyFiles") or []:
        dependency_file_id = item.get("id")
        if isinstance(dependency_file_id, str) and dependency_file_id not in ids:
            ids.append(dependency_file_id)
    return ids


def _dependency_files(
    db: Session, *, workspace_id: str, snapshot_payload: dict
) -> list[DependencyFile]:
    ids = _dependency_file_ids(snapshot_payload)
    if not ids:
        return []
    rows = db.scalars(
        select(DependencyFile).where(
            DependencyFile.workspace_id == workspace_id,
            DependencyFile.id.in_(ids),
        )
    ).all()
    by_id = {row.id: row for row in rows}
    ordered: list[DependencyFile] = []
    snapshot_by_id = {item["id"]: item for item in snapshot_payload.get("dependencyFiles") or []}
    for dependency_file_id in ids:
        row = by_id.get(dependency_file_id)
        snap = snapshot_by_id.get(dependency_file_id) or {}
        if row is None:
            raise AppError("BUNDLE_INVALID", "Execution bundle is invalid.", 500)
        if (
            row.filename != snap.get("filename")
            or row.size_bytes != snap.get("sizeBytes")
            or row.sha256.lower() != str(snap.get("sha256", "")).lower()
        ):
            raise AppError("BUNDLE_INVALID", "Execution bundle is invalid.", 500)
        ordered.append(row)
    return ordered


def _manifest(*, run: Run, snapshot_payload: dict, dependency_files: list[DependencyFile]) -> str:
    manifest: dict[str, object] = {
        "schemaVersion": 1,
        "runId": run.id,
        "sourceType": run.source_type,
        "sourceId": snapshot_payload.get("sourceId"),
        "sourceRevision": snapshot_payload.get("sourceRevision"),
        "slaEvaluationMode": snapshot_payload.get("slaEvaluationMode", "not_evaluated"),
        "dependencyFiles": [
            {
                "id": file.id,
                "filename": file.filename,
                "sizeBytes": file.size_bytes,
                "sha256": file.sha256,
                "bundlePath": bundle_file_path(file),
            }
            for file in dependency_files
        ],
    }
    if run.source_type == "debug_scenario":
        scenario = snapshot_payload["scenario"]
        manifest["scenario"] = {
            "id": scenario.get("id"),
            "name": scenario.get("name"),
            "scenarioType": scenario.get("scenarioType"),
        }
    else:
        manifest["testPlan"] = {
            "id": (snapshot_payload.get("testPlan") or {}).get("id"),
            "name": (snapshot_payload.get("testPlan") or {}).get("name"),
            "revision": (snapshot_payload.get("testPlan") or {}).get("revision"),
        }
    return json.dumps(manifest, sort_keys=True, separators=(",", ":"))


def build_debug_scenario_execution_bundle(
    db: Session, *, run_id: str, runner_home: str, settings: Settings | None = None
) -> list[ExecutionBundleFile]:
    settings = settings or get_settings()
    run, snapshot = _snapshot_for_run(db, run_id=run_id)
    snapshot_payload = snapshot.snapshot_json
    scenario = snapshot_payload.get("scenario")
    if not isinstance(scenario, dict):
        raise AppError("BUNDLE_INVALID", "Execution bundle is invalid.", 500)
    dependency_files = _dependency_files(
        db, workspace_id=run.workspace_id, snapshot_payload=snapshot_payload
    )
    yaml_text = build_debug_taurus_yaml_from_content(
        scenario_content=scenario,
        env_variables=_env_variables(snapshot_payload),
        dependency_files=dependency_files,
        jmeter_path=runtime_jmeter_path(runner_home),
        jmeter_version=RUNTIME_JMETER_VERSION,
        memory_xmx=_snapshot_jmeter_memory_xmx(snapshot_payload),
    )
    if run.run_type == "debug":
        document = yaml.safe_load(yaml_text)
        if isinstance(document, dict):
            yaml_text = yaml.safe_dump(
                inject_debug_http_trace(
                    document,
                    max_requests=settings.debug_trace_max_requests,
                    body_max_bytes=settings.debug_trace_body_max_bytes,
                    artifact_max_bytes=settings.debug_trace_artifact_max_bytes,
                    record_max_bytes=settings.debug_trace_record_max_bytes,
                    body_blob_max_bytes=settings.debug_trace_body_blob_max_bytes,
                    body_blob_total_max_bytes=settings.debug_trace_body_blob_total_max_bytes,
                ),
                sort_keys=False,
                allow_unicode=False,
            )
    files = [
        ExecutionBundleFile.text("surgepilot.yml", yaml_text),
        ExecutionBundleFile.text(
            "manifest.json",
            _manifest(
                run=run, snapshot_payload=snapshot_payload, dependency_files=dependency_files
            ),
        ),
    ]
    storage = get_storage_client()
    for dependency_file in dependency_files:
        stored = storage.get_stream(
            bucket=dependency_file.storage_bucket,
            object_key=dependency_file.storage_object_key,
        )
        files.append(
            ExecutionBundleFile.stream_file(
                bundle_file_path(dependency_file),
                stored.stream,
            )
        )
    return files


def build_test_plan_execution_bundle(
    db: Session, *, run_id: str, runner_home: str, settings: Settings | None = None
) -> list[ExecutionBundleFile]:
    settings = settings or get_settings()
    run, snapshot = _snapshot_for_run(db, run_id=run_id)
    if run.source_type != "test_plan":
        raise AppError("BUNDLE_INVALID", "Execution bundle is invalid.", 500)
    snapshot_payload = snapshot.snapshot_json
    dependency_files = _dependency_files(
        db, workspace_id=run.workspace_id, snapshot_payload=snapshot_payload
    )
    document = build_test_plan_taurus_document_from_snapshot(
        snapshot_payload,
        jmeter_path=runtime_jmeter_path(runner_home),
        jmeter_version=RUNTIME_JMETER_VERSION,
    )
    if run.run_type == "debug":
        document = inject_debug_http_trace(
            document,
            max_requests=settings.debug_trace_max_requests,
            body_max_bytes=settings.debug_trace_body_max_bytes,
            artifact_max_bytes=settings.debug_trace_artifact_max_bytes,
            record_max_bytes=settings.debug_trace_record_max_bytes,
            body_blob_max_bytes=settings.debug_trace_body_blob_max_bytes,
            body_blob_total_max_bytes=settings.debug_trace_body_blob_total_max_bytes,
        )
    yaml_text = yaml.safe_dump(document, sort_keys=False, allow_unicode=False)
    files = [
        ExecutionBundleFile.text("surgepilot.yml", yaml_text),
        ExecutionBundleFile.text("execution/generated.yml", yaml_text),
        ExecutionBundleFile.text(
            "manifest.json",
            _manifest(
                run=run, snapshot_payload=snapshot_payload, dependency_files=dependency_files
            ),
        ),
    ]
    storage = get_storage_client()
    for dependency_file in dependency_files:
        stored = storage.get_stream(
            bucket=dependency_file.storage_bucket,
            object_key=dependency_file.storage_object_key,
        )
        files.append(
            ExecutionBundleFile.stream_file(bundle_file_path(dependency_file), stored.stream)
        )
    return files
