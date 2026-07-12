"""Results importer endpoints."""

import secrets
import time
from collections import deque

from fastapi import (
    APIRouter,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)

from app.config import settings
from app.core.rate_limit import limiter
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
from app.services.result_import_service import ResultImportService
from app.services.result_import_worker import enqueue_result_import
from app.services.sender_allowlist import sender_allowed
from app.services.user_service import UserService
from app.utils.logger import logger

router = APIRouter()
service = ResultImportService()

# Per-sender sliding-window counter for the intake webhook. Keyed by normalized
# sender, each entry is the monotonic timestamp of one ACCEPTED (created) PDF.
# In-process and per-process (resets on restart) — a coarse backstop against a
# single forwarder driving up paid LLM calls, layered under the slowapi per-IP
# limit. Usage is recorded only AFTER a successful upload (so malformed/rejected
# requests can't burn a sender's quota — Codex #3), and expired/empty windows are
# swept so a stream of distinct senders can't grow the dict unbounded (Codex #4).
_INTAKE_WINDOW_SECONDS = 3600
_INTAKE_MAX_TRACKED_SENDERS = 10_000
_intake_sender_window: dict[str, deque] = {}


def _prune_window(window: deque, cutoff: float) -> None:
    while window and window[0] < cutoff:
        window.popleft()


def _sweep_intake_windows(now: float) -> None:
    """Drop expired/empty sender windows (and bound total tracked senders)."""
    cutoff = now - _INTAKE_WINDOW_SECONDS
    for key in list(_intake_sender_window.keys()):
        window = _intake_sender_window[key]
        _prune_window(window, cutoff)
        if not window:
            _intake_sender_window.pop(key, None)
    # Final backstop against a unique-sender flood within a single window.
    overflow = len(_intake_sender_window) - _INTAKE_MAX_TRACKED_SENDERS
    if overflow > 0:
        for key in list(_intake_sender_window.keys())[:overflow]:
            _intake_sender_window.pop(key, None)


def _intake_sender_count(sender: str) -> int:
    """Current in-window accepted-PDF count for `sender` (peek; prunes expired)."""
    now = time.monotonic()
    key = (sender or "").strip().lower()
    window = _intake_sender_window.get(key)
    if window is None:
        return 0
    _prune_window(window, now - _INTAKE_WINDOW_SECONDS)
    if not window:
        _intake_sender_window.pop(key, None)
        return 0
    return len(window)


def _intake_record(sender: str, num: int) -> None:
    """Record `num` accepted PDFs for `sender` in the sliding window."""
    if num <= 0:
        return
    now = time.monotonic()
    _sweep_intake_windows(now)
    key = (sender or "").strip().lower()
    window = _intake_sender_window.setdefault(key, deque())
    window.extend(now for _ in range(num))


def _reset_intake_sender_window() -> None:
    """Clear the in-process per-sender counter (used by tests)."""
    _intake_sender_window.clear()


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
@limiter.limit("30/minute")
async def intake_result_imports(
    request: Request,
    db: DbSession,
    files: list[UploadFile] = File(...),
    sender: str = Form(""),
    x_intake_token: str = Header(default=""),
    x_intake_auth_results: str = Header(default=""),
) -> ResultImportUploadResponse:
    """Machine intake for forwarded lab reports (Cloudflare Email Worker).

    Auth is a shared secret, not a JWT: the caller is a mail pipeline, not a
    user. Uploads are attributed to EMAIL_INTAKE_UPLOAD_USERNAME and the
    forwarding sender must pass the EMAIL_INTAKE_ALLOWED_SENDERS allowlist.

    `request` is required by the slowapi @limiter.limit decorator (per-IP);
    note the caller is Cloudflare's IPs, so it is a coarse backstop only.
    """
    if not settings.intake_webhook_token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Intake is not enabled"
        )
    if not secrets.compare_digest(x_intake_token, settings.intake_webhook_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid intake token"
        )
    # Fix #2 defense-in-depth: the worker already enforces dmarc=pass and only
    # forwards on a pass, but log the verdict it hands us as an audit signal.
    if x_intake_auth_results:
        logger.info(
            f"Email intake webhook: auth-results for '{sender}': "
            f"{x_intake_auth_results}"
        )
    if not sender_allowed(sender):
        # Generic reply to avoid confirming the address is live or probing the
        # allowlist (backscatter/enumeration). Real reason is logged only.
        logger.warning(f"Email intake webhook: sender '{sender}' not on allowlist")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Message not accepted."
        )
    # Peek only — usage is charged after a successful upload (below) so a
    # malformed request can't burn the sender's quota (Codex #3).
    if _intake_sender_count(sender) >= settings.email_intake_sender_hourly_cap:
        logger.warning(
            f"Email intake webhook: sender '{sender}' exceeded hourly cap "
            f"({settings.email_intake_sender_hourly_cap})"
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Submission rate exceeded; try again later.",
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
        created, duplicates = service.create_uploads(
            db, payload, upload_user.id, source="email", sender=sender
        )
        # Charge the sender only for PDFs actually accepted (each drives a paid
        # LLM extraction); duplicates are deduped and cost nothing (Codex #3).
        _intake_record(sender, len(created))
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
