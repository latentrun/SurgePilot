from fastapi import APIRouter, Response, status

from app.api.deps import CsrfDep, CurrentUserDep, DbDep
from app.core.errors import AppError
from app.core.ids import is_ulid
from app.schemas.api_tokens import (
    ApiTokenCreateRequest,
    ApiTokenCreateResponse,
    ApiTokenCreated,
    ApiTokenListResponse,
    ApiTokenMetadata,
)
from app.schemas.common import ErrorResponse
from app.services.api_tokens import create_api_token, list_api_tokens, revoke_api_token

router = APIRouter(prefix="/api/v1/account/api-tokens", tags=["account-api-tokens"])
ERROR_RESPONSE = {"model": ErrorResponse}


def token_metadata(token) -> ApiTokenMetadata:
    return ApiTokenMetadata(
        id=token.id,
        public_id=token.public_id,
        name=token.name,
        scopes=token.scopes,
        workspace_allowlist=token.workspace_allowlist,
        created_at=token.created_at,
        expires_at=token.expires_at,
        revoked_at=token.revoked_at,
        last_used_at=token.last_used_at,
    )


@router.get(
    "",
    operation_id="listAccountApiTokens",
    response_model=ApiTokenListResponse,
    response_model_by_alias=True,
    responses={401: ERROR_RESPONSE, 422: ERROR_RESPONSE},
)
def list_account_api_tokens(db: DbDep, user: CurrentUserDep) -> ApiTokenListResponse:
    tokens = list_api_tokens(db, actor_user_id=user.id)
    db.commit()
    return ApiTokenListResponse(items=[token_metadata(token) for token in tokens])


@router.post(
    "",
    operation_id="createAccountApiToken",
    response_model=ApiTokenCreateResponse,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
    responses={400: ERROR_RESPONSE, 401: ERROR_RESPONSE, 403: ERROR_RESPONSE, 422: ERROR_RESPONSE},
)
def create_account_api_token(
    payload: ApiTokenCreateRequest,
    db: DbDep,
    user: CurrentUserDep,
    _csrf: CsrfDep,
) -> ApiTokenCreateResponse:
    created = create_api_token(
        db,
        actor=user,
        name=payload.name,
        scopes=list(payload.scopes),
        workspace_allowlist=payload.workspace_allowlist,
        expires_at=payload.expires_at,
    )
    db.commit()
    metadata = token_metadata(created.token)
    return ApiTokenCreateResponse(
        token=ApiTokenCreated(**metadata.model_dump(), plaintext=created.plaintext)
    )


@router.delete(
    "/{tokenId}",
    operation_id="deleteAccountApiToken",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
    responses={401: ERROR_RESPONSE, 403: ERROR_RESPONSE, 404: ERROR_RESPONSE, 422: ERROR_RESPONSE},
)
def delete_account_api_token(
    tokenId: str,
    db: DbDep,
    user: CurrentUserDep,
    _csrf: CsrfDep,
) -> Response:
    if not is_ulid(tokenId):
        raise AppError(
            "VALIDATION_ERROR",
            "Validation failed.",
            422,
            [{"field": "tokenId", "code": "INVALID_FIELD", "message": "Invalid API token ID."}],
        )
    revoke_api_token(db, actor_user_id=user.id, token_id=tokenId)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
