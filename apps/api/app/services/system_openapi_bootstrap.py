from __future__ import annotations

from collections.abc import Callable
from hashlib import sha256
import json
import logging
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.time import utc_now
from app.db.session import SessionLocal
from app.models.api_catalog import ApiCatalogSpec
from app.models.auth import DEFAULT_WORKSPACE_ID
from app.services.api_catalog import UploadedApiSpec, create_api_catalog_spec
from app.services.openapi_export import _export_document
from app.services.storage import StorageClient, get_storage_client

if TYPE_CHECKING:
    from fastapi import FastAPI


logger = logging.getLogger(__name__)
SessionFactory = Callable[[], Session]
SYSTEM_OPENAPI_KEY = "surgepilot_api"


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
    if workspace_id != DEFAULT_WORKSPACE_ID:
        raise ValueError("System OpenAPI must belong to the Default Workspace")
    payload = build_curated_openapi_payload(application)
    payload_sha256 = sha256(payload).hexdigest()
    created_object: tuple[str, str] | None = None
    commit_succeeded = False

    with session_factory() as db:
        try:
            active_system_specs = db.scalars(
                select(ApiCatalogSpec.id)
                .where(
                    ApiCatalogSpec.workspace_id == DEFAULT_WORKSPACE_ID,
                    ApiCatalogSpec.system_key == SYSTEM_OPENAPI_KEY,
                    ApiCatalogSpec.status != "deleted",
                )
                .limit(2)
            ).all()
            if active_system_specs:
                logger.info(
                    "System OpenAPI bootstrap skipped: active system asset already exists",
                    extra={
                        "admin_user_id": admin_user_id,
                        "workspace_id": workspace_id,
                        "openapi_sha256_prefix": payload_sha256[:12],
                    },
                )
                return False

            settings = get_settings()
            storage_client = storage or get_storage_client()
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
            spec.system_key = SYSTEM_OPENAPI_KEY
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
                try:
                    cleanup_succeeded = storage_client.delete_object_best_effort(
                        bucket=bucket, object_key=object_key
                    )
                except Exception:
                    cleanup_succeeded = False
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


def reconcile_system_openapi(
    *,
    application: FastAPI,
    session_factory: SessionFactory = SessionLocal,
    storage: StorageClient | None = None,
) -> bool:
    with session_factory() as db:
        system_specs = db.scalars(
            select(ApiCatalogSpec)
            .where(
                ApiCatalogSpec.workspace_id == DEFAULT_WORKSPACE_ID,
                ApiCatalogSpec.system_key == SYSTEM_OPENAPI_KEY,
                ApiCatalogSpec.status != "deleted",
            )
            .limit(2)
        ).all()
        if not system_specs:
            return False
        if len(system_specs) > 1:
            logger.warning(
                "System OpenAPI reconciliation skipped: multiple active system assets",
                extra={"workspace_id": DEFAULT_WORKSPACE_ID},
            )
            return False

        previous = system_specs[0]
        payload = build_curated_openapi_payload(application)
        payload_sha256 = sha256(payload).hexdigest()
        if previous.sha256 == payload_sha256:
            return False

        settings = get_settings()
        storage_client = storage or get_storage_client()
        created_object: tuple[str, str] | None = None
        committed = False
        try:
            replacement = create_api_catalog_spec(
                db,
                workspace_id=DEFAULT_WORKSPACE_ID,
                actor_user_id=previous.created_by,
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
            created_object = (replacement.storage_bucket, replacement.storage_object_key)
            replacement.system_key = SYSTEM_OPENAPI_KEY
            now = utc_now()
            previous.status = "deleted"
            previous.deleted_at = now
            previous.updated_at = now
            previous.deleted_by = None
            db.commit()
            committed = True
        except Exception:
            db.rollback()
            if created_object is not None and not committed:
                bucket, object_key = created_object
                try:
                    cleanup_succeeded = storage_client.delete_object_best_effort(
                        bucket=bucket, object_key=object_key
                    )
                except Exception:
                    cleanup_succeeded = False
                logger.info(
                    "System OpenAPI replacement commit compensation attempted",
                    extra={
                        "workspace_id": DEFAULT_WORKSPACE_ID,
                        "openapi_sha256_prefix": payload_sha256[:12],
                        "storage_cleanup_succeeded": cleanup_succeeded,
                    },
                )
            raise

        try:
            cleanup_succeeded = storage_client.delete_object_best_effort(
                bucket=previous.storage_bucket, object_key=previous.storage_object_key
            )
        except Exception:
            cleanup_succeeded = False
        if not cleanup_succeeded:
            logger.warning(
                "System OpenAPI previous object cleanup failed",
                extra={"workspace_id": DEFAULT_WORKSPACE_ID, "api_catalog_spec_id": previous.id},
            )
        logger.info(
            "System OpenAPI reconciliation completed",
            extra={
                "workspace_id": DEFAULT_WORKSPACE_ID,
                "old_spec_id": previous.id,
                "new_spec_id": replacement.id,
                "openapi_sha256_prefix": payload_sha256[:12],
            },
        )
        return True


def reconcile_system_openapi_best_effort(*, application: FastAPI) -> None:
    try:
        reconcile_system_openapi(application=application)
    except Exception as exc:
        logger.warning(
            "System OpenAPI reconciliation failed",
            extra={
                "workspace_id": DEFAULT_WORKSPACE_ID,
                "reconcile_error_type": type(exc).__name__,
            },
        )


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
