"""Results importer endpoints."""

import secrets

from fastapi import (
    APIRouter,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    UploadFile,
    status,
)

from app.config import settings
from app.dependencies import CurrentUser, DbSession, LabTechOrAbove
from app.models import ResultImport
from app.schemas.result_import import (
    ConfirmResultImportRequest,
    ConfirmResultImportResponse,
    LinkCandidateRead,
    ResultImportList,
    ResultImportPreview,
    ResultImportPreviewRequest,
    ResultImportRead,
    ResultImportUploadResponse,
)
from app.services.email_intake_service import EmailIntakeService
from app.services.result_import_service import ResultImportService
from app.services.result_import_worker import enqueue_result_import
from app.services.user_service import UserService
from app.utils.logger import logger

router = APIRouter()
service = ResultImportService()


def _serialize(item: ResultImport) -> ResultImportRead:
    data = ResultImportRead.model_validate(item)
    if hasattr(item.status, "value"):
        data.status = item.status.value
    status_value = item.status.value if hasattr(item.status, "value") else item.status
    if status_value == "confirmed":
        data.duplicate_summary = service.duplicate_summary(item)
    return data


@router.post(
    "", response_model=ResultImportUploadResponse, status_code=status.HTTP_201_CREATED
)
async def upload_result_imports(
    db: DbSession,
    current_user: LabTechOrAbove,
    files: list[UploadFile] = File(...),
) -> ResultImportUploadResponse:
    try:
        payload = []
        for file in files:
            payload.append(
                (
                    file.filename or "result.pdf",
                    await file.read(),
                    file.content_type or "",
                )
            )
        created, duplicates = service.create_uploads(db, payload, current_user.id)
        for item in created:
            await enqueue_result_import(item.id)
        return ResultImportUploadResponse(
            items=[_serialize(item) for item in created],
            duplicates=[_serialize(item) for item in duplicates],
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/intake",
    response_model=ResultImportUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def intake_result_imports(
    db: DbSession,
    files: list[UploadFile] = File(...),
    sender: str = Form(""),
    x_intake_token: str = Header(default=""),
) -> ResultImportUploadResponse:
    """Machine intake for forwarded lab reports (Cloudflare Email Worker).

    Auth is a shared secret, not a JWT: the caller is a mail pipeline, not a
    user. Uploads are attributed to EMAIL_INTAKE_UPLOAD_USERNAME and the
    forwarding sender must pass the EMAIL_INTAKE_ALLOWED_SENDERS allowlist.
    """
    if not settings.intake_webhook_token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Intake is not enabled"
        )
    if not secrets.compare_digest(x_intake_token, settings.intake_webhook_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid intake token"
        )
    if not EmailIntakeService._sender_allowed(sender):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Sender '{sender}' is not allowed to submit results",
        )
    upload_user = UserService().get_by_username(
        db, settings.email_intake_upload_username
    )
    if upload_user is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Intake upload user is not configured",
        )
    try:
        payload = []
        for file in files:
            payload.append(
                (
                    file.filename or "result.pdf",
                    await file.read(),
                    file.content_type or "application/pdf",
                )
            )
        created, duplicates = service.create_uploads(db, payload, upload_user.id)
        for item in created:
            await enqueue_result_import(item.id)
        logger.info(
            f"Email intake webhook: ingested {len(created)} PDF(s) "
            f"({len(duplicates)} duplicate(s)) from '{sender}'"
        )
        return ResultImportUploadResponse(
            items=[_serialize(item) for item in created],
            duplicates=[_serialize(item) for item in duplicates],
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("", response_model=ResultImportList)
async def list_result_imports(
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
) -> ResultImportList:
    items, total = service.list_imports(db, page, page_size)
    total_pages = (total + page_size - 1) // page_size if page_size else 0
    return ResultImportList(
        items=[_serialize(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/link-candidates", response_model=list[LinkCandidateRead])
async def link_candidates(
    db: DbSession,
    current_user: CurrentUser,
    search: str = Query(..., min_length=2),
) -> list[LinkCandidateRead]:
    return [LinkCandidateRead(**item) for item in service.link_candidates(db, search)]


@router.get("/{import_id}", response_model=ResultImportRead)
async def get_result_import(
    import_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> ResultImportRead:
    item = service.get(db, import_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Import not found"
        )
    return _serialize(item)


@router.get("/{import_id}/preview", response_model=ResultImportPreview)
async def preview_result_import(
    import_id: int,
    db: DbSession,
    current_user: CurrentUser,
    lot_id: int = Query(..., ge=1),
) -> ResultImportPreview:
    try:
        return ResultImportPreview(**service.preview_rows(db, import_id, lot_id))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/{import_id}/preview", response_model=ResultImportPreview)
async def preview_result_import_with_overrides(
    import_id: int,
    db: DbSession,
    current_user: LabTechOrAbove,
    request: ResultImportPreviewRequest | None = None,
    lot_id: int = Query(..., ge=1),
) -> ResultImportPreview:
    try:
        return ResultImportPreview(
            **service.preview_rows(
                db, import_id, lot_id, request.overrides if request else None
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/{import_id}/confirm", response_model=ConfirmResultImportResponse)
async def confirm_result_import(
    import_id: int,
    request: ConfirmResultImportRequest,
    db: DbSession,
    current_user: LabTechOrAbove,
) -> ConfirmResultImportResponse:
    try:
        return ConfirmResultImportResponse(
            **service.confirm(
                db, import_id, request.lot_id, request.row_actions, current_user.id
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/{import_id}/retry", response_model=ResultImportRead)
async def retry_result_import(
    import_id: int,
    db: DbSession,
    current_user: LabTechOrAbove,
) -> ResultImportRead:
    try:
        item = service.retry(db, import_id, current_user.id)
        await enqueue_result_import(item.id)
        return _serialize(item)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/{import_id}/cancel", response_model=ResultImportRead)
async def cancel_result_import(
    import_id: int,
    db: DbSession,
    current_user: LabTechOrAbove,
) -> ResultImportRead:
    try:
        return _serialize(service.cancel(db, import_id, current_user.id))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/{import_id}/revert", response_model=ResultImportRead)
async def revert_result_import(
    import_id: int,
    db: DbSession,
    current_user: LabTechOrAbove,
) -> ResultImportRead:
    try:
        return _serialize(
            service.revert(db, import_id, current_user.id, current_user.role)
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
