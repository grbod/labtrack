"""Settings management endpoints."""

from typing import List

from fastapi import APIRouter, HTTPException, UploadFile, File, status

from app.dependencies import DbSession, CurrentUser, AdminUser
from app.services.email_template_service import EmailTemplateService
from app.services.coa_category_order_service import coa_category_order_service
from app.services.lab_info_service import lab_info_service
from app.schemas.email_template import (
    EmailTemplateResponse,
    EmailTemplateUpdate,
    EmailTemplateVariablesResponse,
    EmailTemplateVariable,
    EmailTemplatePreview,
)
from app.schemas.coa_category_order import (
    COACategoryOrderResponse,
    COACategoryOrderUpdate,
)
from app.schemas.lab_info import (
    LabInfoResponse,
    LabInfoUpdate,
)
from app.schemas.daane_mapping import (
    DaaneTestMappingListResponse,
    DaaneTestMappingItem,
)
from app.services.daane_coc_service import daane_coc_service

router = APIRouter()
email_template_service = EmailTemplateService()


@router.get("/email-template", response_model=EmailTemplateResponse)
async def get_email_template(
    db: DbSession,
    current_user: CurrentUser,
) -> EmailTemplateResponse:
    """Get the current email template configuration."""
    template = email_template_service.get_or_create_default(db)
    return EmailTemplateResponse.model_validate(template)


@router.put("/email-template", response_model=EmailTemplateResponse)
async def update_email_template(
    template_in: EmailTemplateUpdate,
    db: DbSession,
    current_user: AdminUser,
) -> EmailTemplateResponse:
    """Update the email template (admin only)."""
    template = email_template_service.update_template(
        db=db,
        subject=template_in.subject,
        body=template_in.body,
        user_id=current_user.id,
    )
    return EmailTemplateResponse.model_validate(template)


@router.post("/email-template/reset", response_model=EmailTemplateResponse)
async def reset_email_template(
    db: DbSession,
    current_user: AdminUser,
) -> EmailTemplateResponse:
    """Reset the email template to defaults (admin only)."""
    template = email_template_service.reset_to_defaults(
        db=db,
        user_id=current_user.id,
    )
    return EmailTemplateResponse.model_validate(template)


@router.get("/email-template/variables", response_model=EmailTemplateVariablesResponse)
async def get_email_template_variables(
    current_user: CurrentUser,
) -> EmailTemplateVariablesResponse:
    """Get available template variables."""
    variables = email_template_service.get_available_variables()
    return EmailTemplateVariablesResponse(
        variables=[
            EmailTemplateVariable(key=v["key"], description=v["description"])
            for v in variables
        ]
    )


@router.post("/email-template/preview", response_model=EmailTemplatePreview)
async def preview_email_template(
    template_in: EmailTemplateUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> EmailTemplatePreview:
    """Preview the email template with sample data."""
    # Get or create a temporary template object for rendering
    from app.models.email_template import EmailTemplate as EmailTemplateModel

    temp_template = EmailTemplateModel(
        subject=template_in.subject,
        body=template_in.body,
    )

    sample_context = email_template_service.get_sample_context()
    subject, body = email_template_service.render(temp_template, sample_context)

    return EmailTemplatePreview(subject=subject, body=body)


# COA Category Order Endpoints


@router.get("/coa-category-order", response_model=COACategoryOrderResponse)
async def get_coa_category_order(
    db: DbSession,
    current_user: CurrentUser,
) -> COACategoryOrderResponse:
    """Get the current COA category display order."""
    order = coa_category_order_service.get_or_create_default(db)
    return COACategoryOrderResponse.model_validate(order)


@router.put("/coa-category-order", response_model=COACategoryOrderResponse)
async def update_coa_category_order(
    order_in: COACategoryOrderUpdate,
    db: DbSession,
    current_user: AdminUser,
) -> COACategoryOrderResponse:
    """Update the COA category display order (admin only)."""
    order = coa_category_order_service.update_order(
        db=db,
        category_order=order_in.category_order,
        user_id=current_user.id,
    )
    return COACategoryOrderResponse.model_validate(order)


@router.post("/coa-category-order/reset", response_model=COACategoryOrderResponse)
async def reset_coa_category_order(
    db: DbSession,
    current_user: AdminUser,
) -> COACategoryOrderResponse:
    """Reset the COA category order to defaults (admin only)."""
    order = coa_category_order_service.reset_to_defaults(
        db=db,
        user_id=current_user.id,
    )
    return COACategoryOrderResponse.model_validate(order)


@router.get("/coa-category-order/active-categories", response_model=List[str])
async def get_active_categories_ordered(
    db: DbSession,
    current_user: CurrentUser,
) -> List[str]:
    """Get all active categories in configured display order."""
    return coa_category_order_service.get_all_active_categories_ordered(db)


# Lab Info Endpoints

def _build_lab_info_response(lab_info) -> LabInfoResponse:
    """Build LabInfoResponse with computed logo_url and signature_url."""
    return LabInfoResponse(
        id=lab_info.id,
        company_name=lab_info.company_name,
        address=lab_info.address,
        city=lab_info.city,
        state=lab_info.state,
        zip_code=lab_info.zip_code,
        phone=lab_info.phone,
        email=lab_info.email,
        logo_url=lab_info_service.get_logo_url(lab_info.logo_path),
        signature_url=lab_info_service.get_signature_url(lab_info.signature_path),
        signer_name=lab_info.signer_name,
        require_pdf_for_submission=lab_info.require_pdf_for_submission,
        show_spec_preview_on_sample=lab_info.show_spec_preview_on_sample,
        created_at=lab_info.created_at,
        updated_at=lab_info.updated_at,
    )


@router.get("/lab-mapping", response_model=DaaneTestMappingListResponse)
async def get_lab_mapping(
    db: DbSession,
    current_user: CurrentUser,
) -> DaaneTestMappingListResponse:
    """Get the current Daane Labs test mappings."""
    mappings = daane_coc_service.list_mappings(db)
    items = [
        DaaneTestMappingItem(
            lab_test_type_id=mapping.lab_test_type_id,
            test_name=mapping.lab_test_type.test_name if mapping.lab_test_type else "",
            test_method=mapping.lab_test_type.test_method if mapping.lab_test_type else None,
            default_unit=mapping.lab_test_type.default_unit if mapping.lab_test_type else None,
            daane_method=mapping.daane_method,
            match_type=mapping.match_type,
            match_reason=mapping.match_reason,
        )
        for mapping in mappings
    ]
    return DaaneTestMappingListResponse(items=items, total=len(items))


@router.post("/lab-mapping/rebuild", response_model=DaaneTestMappingListResponse)
async def rebuild_lab_mapping(
    db: DbSession,
    current_user: AdminUser,
) -> DaaneTestMappingListResponse:
    """Rebuild the Daane Labs test mappings from the template."""
    daane_coc_service.rebuild_mappings(db)
    mappings = daane_coc_service.list_mappings(db)
    items = [
        DaaneTestMappingItem(
            lab_test_type_id=mapping.lab_test_type_id,
            test_name=mapping.lab_test_type.test_name if mapping.lab_test_type else "",
            test_method=mapping.lab_test_type.test_method if mapping.lab_test_type else None,
            default_unit=mapping.lab_test_type.default_unit if mapping.lab_test_type else None,
            daane_method=mapping.daane_method,
            match_type=mapping.match_type,
            match_reason=mapping.match_reason,
        )
        for mapping in mappings
    ]
    return DaaneTestMappingListResponse(items=items, total=len(items))


@router.get("/lab-info", response_model=LabInfoResponse)
async def get_lab_info(
    db: DbSession,
    current_user: CurrentUser,
) -> LabInfoResponse:
    """Get the current lab information for COAs."""
    lab_info = lab_info_service.get_or_create_default(db)
    return _build_lab_info_response(lab_info)


@router.put("/lab-info", response_model=LabInfoResponse)
async def update_lab_info(
    lab_info_in: LabInfoUpdate,
    db: DbSession,
    current_user: AdminUser,
) -> LabInfoResponse:
    """Update lab information (admin only)."""
    lab_info = lab_info_service.update_info(
        db=db,
        company_name=lab_info_in.company_name,
        address=lab_info_in.address,
        phone=lab_info_in.phone,
        email=lab_info_in.email,
        city=lab_info_in.city,
        state=lab_info_in.state,
        zip_code=lab_info_in.zip_code,
        require_pdf_for_submission=lab_info_in.require_pdf_for_submission,
        show_spec_preview_on_sample=lab_info_in.show_spec_preview_on_sample,
        user_id=current_user.id,
    )
    return _build_lab_info_response(lab_info)


@router.post("/lab-info/logo", response_model=LabInfoResponse)
async def upload_logo(
    db: DbSession,
    current_user: AdminUser,
    file: UploadFile = File(...),
) -> LabInfoResponse:
    """Upload company logo (admin only)."""
    # Validate file type
    allowed_types = ["image/jpeg", "image/png", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed types: {', '.join(allowed_types)}",
        )

    # Validate file size (max 2MB)
    max_size = 2 * 1024 * 1024  # 2MB
    content = await file.read()
    if len(content) > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File too large. Maximum size is 2MB.",
        )

    lab_info = lab_info_service.update_logo(
        db=db,
        file_content=content,
        filename=file.filename or "logo.png",
        content_type=file.content_type,
        user_id=current_user.id,
    )
    return _build_lab_info_response(lab_info)


@router.delete("/lab-info/logo", response_model=LabInfoResponse)
async def delete_logo(
    db: DbSession,
    current_user: AdminUser,
) -> LabInfoResponse:
    """Delete company logo (admin only)."""
    lab_info = lab_info_service.delete_logo(
        db=db,
        user_id=current_user.id,
    )
    return _build_lab_info_response(lab_info)


@router.post("/lab-info/signature", response_model=LabInfoResponse)
async def upload_signature(
    db: DbSession,
    current_user: AdminUser,
    file: UploadFile = File(...),
) -> LabInfoResponse:
    """Upload signature image (admin only)."""
    # Validate file type
    allowed_types = ["image/jpeg", "image/png", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed types: {', '.join(allowed_types)}",
        )

    # Validate file size (max 2MB)
    max_size = 2 * 1024 * 1024  # 2MB
    content = await file.read()
    if len(content) > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File too large. Maximum size is 2MB.",
        )

    lab_info = lab_info_service.update_signature(
        db=db,
        file_content=content,
        filename=file.filename or "signature.png",
        content_type=file.content_type,
        user_id=current_user.id,
    )
    return _build_lab_info_response(lab_info)


@router.delete("/lab-info/signature", response_model=LabInfoResponse)
async def delete_signature(
    db: DbSession,
    current_user: AdminUser,
) -> LabInfoResponse:
    """Delete signature image (admin only)."""
    lab_info = lab_info_service.delete_signature(
        db=db,
        user_id=current_user.id,
    )
    return _build_lab_info_response(lab_info)
