"""Email template service for managing COA email configuration."""

from typing import Dict, List, Tuple

from sqlalchemy.orm import Session

from app.models.email_template import EmailTemplate
from app.services.base import BaseService
from app.utils.logger import logger


class EmailTemplateService(BaseService[EmailTemplate]):
    """
    Service for managing email templates.

    Provides methods for:
    - Getting or creating the default template
    - Updating template content
    - Rendering templates with context variables
    - Listing available template variables
    """

    def __init__(self):
        """Initialize email template service."""
        super().__init__(EmailTemplate)

    def get_or_create_default(self, db: Session) -> EmailTemplate:
        """
        Get the default email template, creating it if it doesn't exist.

        Args:
            db: Database session

        Returns:
            EmailTemplate instance
        """
        template = db.query(EmailTemplate).filter(
            EmailTemplate.name == "coa_email"
        ).first()

        if not template:
            logger.info("Creating default email template")
            defaults = EmailTemplate.get_default_template()
            template = EmailTemplate(
                name=defaults["name"],
                subject=defaults["subject"],
                body=defaults["body"],
            )
            db.add(template)
            db.commit()
            db.refresh(template)
            logger.info(f"Created default email template with id {template.id}")

        return template

    def update_template(
        self,
        db: Session,
        subject: str,
        body: str,
        user_id: int = None,
    ) -> EmailTemplate:
        """
        Update the default email template.

        Args:
            db: Database session
            subject: New subject line
            body: New body content
            user_id: ID of user making the change

        Returns:
            Updated EmailTemplate instance
        """
        template = self.get_or_create_default(db)

        update_data = {
            "subject": subject,
            "body": body,
        }

        return self.update(
            db=db,
            db_obj=template,
            obj_in=update_data,
            user_id=user_id,
        )

    def reset_to_defaults(
        self,
        db: Session,
        user_id: int = None,
    ) -> EmailTemplate:
        """
        Reset the email template to default values.

        Args:
            db: Database session
            user_id: ID of user making the change

        Returns:
            Reset EmailTemplate instance
        """
        defaults = EmailTemplate.get_default_template()
        return self.update_template(
            db=db,
            subject=defaults["subject"],
            body=defaults["body"],
            user_id=user_id,
        )

    def render(
        self,
        template: EmailTemplate,
        context: Dict[str, str],
    ) -> Tuple[str, str]:
        """
        Render the template with context variables.

        Args:
            template: EmailTemplate instance
            context: Dictionary of variable key-value pairs

        Returns:
            Tuple of (rendered_subject, rendered_body)
        """
        return (
            template.render_subject(context),
            template.render_body(context),
        )

    @staticmethod
    def get_available_variables() -> List[Dict[str, str]]:
        """
        Get list of available template variables with descriptions.

        Returns:
            List of dictionaries with 'key' and 'description' fields
        """
        return EmailTemplate.get_available_variables()

    @staticmethod
    def get_sample_context() -> Dict[str, str]:
        """
        Get sample context data for template preview.

        Returns:
            Dictionary with sample values for all template variables
        """
        return {
            "product": "Premium Whey Protein",
            "lot_number": "LOT-2024-001",
            "brand": "NutraFit",
            "reference_number": "REF-240115-001",
            "customer_name": "John Smith",
            "company_name": "Health Foods Co.",
        }
