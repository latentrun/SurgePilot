from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
import re
from typing import Any
from uuid import uuid4

SAFE_NAME_CHARS = re.compile(r"[^A-Za-z0-9 ._-]+")


def new_ulid_like() -> str:
    """Return a 26-character identifier accepted by SurgePilot ULID-shaped test fields."""

    return uuid4().hex[:26].upper()


def unique_suffix() -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    return f"{stamp}-{uuid4().hex[:8]}"


def unique_name(prefix: str, *, max_length: int = 96) -> str:
    """Build a bounded, human-readable unique name for E2E-created resources."""

    if max_length < 24:
        raise ValueError("max_length must leave room for a unique suffix")
    safe_prefix = SAFE_NAME_CHARS.sub("-", prefix).strip(" -._") or "SurgePilot E2E"
    suffix = unique_suffix()
    available = max_length - len(suffix) - 1
    bounded_prefix = safe_prefix[:available].rstrip(" -._") or "SurgePilot E2E"
    return f"{bounded_prefix} {suffix}"


def _require_text(draft: dict[str, Any], field: str) -> str:
    value = draft.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"missing required draft field: {field}")
    return value


def _materialize_named_values(
    values: list[dict[str, Any]] | None, *, id_factory: Callable[[], str]
) -> list[dict[str, Any]]:
    materialized: list[dict[str, Any]] = []
    for item in values or []:
        materialized.append(
            {
                "id": id_factory(),
                "name": str(item.get("name", "")),
                "value": str(item.get("value", "")),
                "enabled": bool(item.get("enabled", True)),
            }
        )
    return materialized


def materialize_openapi_step_draft(
    draft: dict[str, Any], *, id_factory: Callable[[], str] = new_ulid_like
) -> dict[str, Any]:
    """Convert a P2-01 OpenAPI Step draft preview into a Scenario PATCH-safe Step.

    P2-01 intentionally returns preview drafts without persistent child IDs. Web materializes
    these IDs before saving. API/E2E verifiers that bypass Web must do the same to avoid
    validating preview-only drafts as persisted Scenario steps.
    """

    body = draft.get("body") or {}
    settings = draft.get("settings") or {}
    return {
        "id": id_factory(),
        "enabled": bool(draft.get("enabled", True)),
        "name": _require_text(draft, "name"),
        "method": _require_text(draft, "method"),
        "path": _require_text(draft, "path"),
        "queryParams": _materialize_named_values(draft.get("queryParams"), id_factory=id_factory),
        "headers": _materialize_named_values(draft.get("headers"), id_factory=id_factory),
        "body": {
            "type": body.get("type") or "none",
            "contentType": body.get("contentType"),
            "rawText": body.get("rawText"),
            "formFields": _materialize_named_values(body.get("formFields"), id_factory=id_factory),
        },
        "uploadFiles": [],
        "extractors": [],
        "assertions": [],
        "scripts": [],
        "settings": {
            "thinkTimeMs": None,
            "timeoutMs": settings.get("timeoutMs"),
            "followRedirects": settings.get("followRedirects"),
            "keepAlive": settings.get("keepAlive"),
        },
    }


__all__ = [
    "materialize_openapi_step_draft",
    "new_ulid_like",
    "unique_name",
    "unique_suffix",
]
