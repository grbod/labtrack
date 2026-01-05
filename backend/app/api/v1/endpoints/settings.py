"""Settings management endpoints."""

from fastapi import APIRouter

from app.dependencies import DbSession, CurrentUser, AdminUser
from app.services.email_template_service import EmailTemplateService
from app.schemas.email_template import (
    EmailTemplateResponse,
    EmailTemplateUpdate,
    EmailTemplateVariablesResponse,
    EmailTemplateVariable,
    EmailTemplatePreview,
)

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
