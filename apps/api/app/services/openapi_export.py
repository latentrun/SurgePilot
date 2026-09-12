from __future__ import annotations

import copy
from typing import Any


PUBLIC_PRUNED_ERROR_CODES = {
    "LOAD_NODE_SSH_HOST_KEY_SCAN_FAILED",
    "LOAD_NODE_SSH_HOST_KEY_MISMATCH",
    "LOAD_NODE_SSH_HOST_KEY_UNTRUSTED",
    "LOAD_NODE_SSH_HOST_KEY_CHANGED",
}


def _normalize_path(path: str) -> str | None:
    if path.startswith("/api/v1/"):
        return path.removeprefix("/api")
    if path.startswith("/api/public/v1/"):
        return path.removeprefix("/api")
    if path.startswith("/api/"):
        return None
    return path


def _filter_paths(openapi: dict[str, Any], *, public: bool) -> dict[str, Any]:
    paths = openapi.get("paths", {})
    normalized: dict[str, Any] = {}
    for path, value in paths.items():
        normalized_path = _normalize_path(path)
        if normalized_path is None:
            continue
        is_public_path = normalized_path.startswith("/public/v1/")
        if public and is_public_path:
            normalized[normalized_path] = value
        elif not public and normalized_path.startswith("/v1/"):
            normalized[normalized_path] = value
    openapi["paths"] = normalized
    openapi["servers"] = [{"url": "/api"}]
    return openapi


def _schema_name_from_ref(ref: str) -> str | None:
    prefix = "#/components/schemas/"
    if ref.startswith(prefix):
        return ref.removeprefix(prefix)
    return None


def _collect_schema_refs(value: Any, names: set[str]) -> None:
    if isinstance(value, dict):
        ref = value.get("$ref")
        if isinstance(ref, str):
            name = _schema_name_from_ref(ref)
            if name:
                names.add(name)
        for child in value.values():
            _collect_schema_refs(child, names)
    elif isinstance(value, list):
        for child in value:
            _collect_schema_refs(child, names)


def _prune_schemas(openapi: dict[str, Any]) -> dict[str, Any]:
    components = openapi.get("components")
    if not isinstance(components, dict):
        return openapi
    schemas = components.get("schemas")
    if not isinstance(schemas, dict):
        return openapi

    needed: set[str] = set()
    _collect_schema_refs(openapi.get("paths", {}), needed)
    processed: set[str] = set()
    while needed - processed:
        name = (needed - processed).pop()
        processed.add(name)
        schema = schemas.get(name)
        if schema is not None:
            _collect_schema_refs(schema, needed)

    components["schemas"] = {name: schemas[name] for name in sorted(needed) if name in schemas}
    return openapi


def _prune_error_codes(value: Any, pruned_codes: set[str]) -> None:
    if isinstance(value, dict):
        enum_value = value.get("enum")
        if isinstance(enum_value, list):
            value["enum"] = [
                item for item in enum_value if not (isinstance(item, str) and item in pruned_codes)
            ]
        for child in value.values():
            _prune_error_codes(child, pruned_codes)
    elif isinstance(value, list):
        value[:] = [item for item in value if not (isinstance(item, str) and item in pruned_codes)]
        for child in value:
            _prune_error_codes(child, pruned_codes)


def _prune_public_error_codes(openapi: dict[str, Any]) -> dict[str, Any]:
    info = openapi.setdefault("info", {})
    error_codes = info.get("x-surgepilot-error-codes")
    if isinstance(error_codes, list):
        info["x-surgepilot-error-codes"] = [
            code for code in error_codes if code not in PUBLIC_PRUNED_ERROR_CODES
        ]
    _prune_error_codes(openapi.get("components", {}), PUBLIC_PRUNED_ERROR_CODES)
    return openapi


def _export_document(source: dict[str, Any], *, public: bool) -> dict[str, Any]:
    document = _filter_paths(copy.deepcopy(source), public=public)
    if public:
        document = _prune_schemas(document)
        document = _prune_public_error_codes(document)
    return document
