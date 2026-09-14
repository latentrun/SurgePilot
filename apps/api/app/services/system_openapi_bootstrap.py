from __future__ import annotations

from collections.abc import Callable
from hashlib import sha256
import json
import logging
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.api_catalog import ApiCatalogSpec
from app.services.api_catalog import UploadedApiSpec, create_api_catalog_spec
from app.services.openapi_export import _export_document
from app.services.storage import StorageClient, get_storage_client

if TYPE_CHECKING:
    from fastapi import FastAPI


logger = logging.getLogger(__name__)
SessionFactory = Callable[[], Session]


def build_curated_openapi_payload(application: FastAPI) -> bytes:
    document = _export_document(application.openapi(), public=False)
    return json.dumps(document, sort_keys=True).encode("utf-8")


def import_system_openapi(
    *,
    application: FastAPI,
    workspace_id: str,
    admin_user_id: str,
    session_factory: SessionFactory = SessionLocal,
    storage: StorageClient | None = None,
) -> bool:
    payload = build_curated_openapi_payload(application)
    payload_sha256 = sha256(payload).hexdigest()
    settings = get_settings()
    storage_client = storage or get_storage_client()
    created_object: tuple[str, str] | None = None
    commit_succeeded = False

    with session_factory() as db:
        try:
            existing = db.scalar(
                select(ApiCatalogSpec.id).where(
                    ApiCatalogSpec.workspace_id == workspace_id,
                    ApiCatalogSpec.sha256 == payload_sha256,
                    ApiCatalogSpec.status != "deleted",
                )
            )
            if existing is not None:
                logger.info(
                    "System OpenAPI bootstrap skipped: same SHA already exists",
                    extra={
                        "admin_user_id": admin_user_id,
                        "workspace_id": workspace_id,
                        "openapi_sha256_prefix": payload_sha256[:12],
                    },
                )
                return False

            spec = create_api_catalog_spec(
                db,
                workspace_id=workspace_id,
                actor_user_id=admin_user_id,
                upload=UploadedApiSpec(
                    filename="surgepilot-api.openapi.json",
                    content_type="application/json",
                    payload=payload,
                    name="SurgePilot API",
                ),
                storage=storage_client,
                bucket=settings.minio_bucket,
                max_bytes=settings.api_catalog_spec_max_bytes,
            )
            created_object = (spec.storage_bucket, spec.storage_object_key)
            db.commit()
            commit_succeeded = True
            logger.info(
                "System OpenAPI bootstrap completed",
                extra={
                    "admin_user_id": admin_user_id,
                    "workspace_id": workspace_id,
                    "api_catalog_spec_id": spec.id,
                    "openapi_sha256_prefix": payload_sha256[:12],
                },
            )
            return True
        except Exception:
            db.rollback()
            if created_object is not None and not commit_succeeded:
                bucket, object_key = created_object
                cleanup_succeeded = storage_client.delete_object_best_effort(
                    bucket=bucket, object_key=object_key
                )
                logger.info(
                    "System OpenAPI bootstrap commit compensation attempted",
                    extra={
                        "admin_user_id": admin_user_id,
                        "workspace_id": workspace_id,
                        "openapi_sha256_prefix": payload_sha256[:12],
                        "storage_cleanup_succeeded": cleanup_succeeded,
                    },
                )
            raise


def bootstrap_system_openapi_best_effort(
    *, application: FastAPI, workspace_id: str, admin_user_id: str
) -> None:
    try:
        import_system_openapi(
            application=application,
            workspace_id=workspace_id,
            admin_user_id=admin_user_id,
        )
    except Exception as exc:
        logger.warning(
            "System OpenAPI bootstrap failed",
            extra={
                "admin_user_id": admin_user_id,
                "workspace_id": workspace_id,
                "bootstrap_error_type": type(exc).__name__,
            },
        )
