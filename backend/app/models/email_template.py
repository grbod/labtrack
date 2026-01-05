"""EmailTemplate model for COA email configuration."""

from sqlalchemy import Column, String, Text
from app.models.base import BaseModel


class EmailTemplate(BaseModel):
    """
    EmailTemplate model for configuring COA email content.

    Supports template variables:
    - {product}: Product name
    - {lot_number}: Lot number
    - {brand}: Product brand
    - {reference_number}: Reference number
    - {customer_name}: Customer contact name
    - {company_name}: Customer company name

    Attributes:
        name: Template identifier (e.g., "coa_email")
        subject: Email subject line with template variables
        body: Email body with template variables
    """

    __tablename__ = "email_templates"

    # Core fields
    name = Column(String(100), unique=True, nullable=False, default="coa_email")
    subject = Column(String(500), nullable=False)
    body = Column(Text, nullable=False)

    # Default template content
    DEFAULT_SUBJECT = "Certificate of Analysis - {product} - Lot {lot_number}"
    DEFAULT_BODY = """Dear {customer_name},

Please find attached the Certificate of Analysis for:

Product: {product}
Brand: {brand}
Lot Number: {lot_number}
Reference: {reference_number}

If you have any questions, please don't hesitate to contact us.

Best regards,
Quality Assurance Team"""

    @classmethod
    def get_default_template(cls):
        """Get default template values."""
        return {
            "name": "coa_email",
            "subject": cls.DEFAULT_SUBJECT,
            "body": cls.DEFAULT_BODY
        }

    def render_subject(self, context: dict) -> str:
        """Render subject line with context variables."""
        return self._render_template(self.subject, context)

    def render_body(self, context: dict) -> str:
        """Render body with context variables."""
        return self._render_template(self.body, context)

    def _render_template(self, template: str, context: dict) -> str:
        """Render template string with context variables."""
        result = template
        for key, value in context.items():
            result = result.replace(f"{{{key}}}", str(value) if value else "")
        return result

    @staticmethod
    def get_available_variables():
        """Get list of available template variables."""
        return [
            {"key": "product", "description": "Product name"},
            {"key": "lot_number", "description": "Lot number"},
            {"key": "brand", "description": "Product brand"},
            {"key": "reference_number", "description": "Reference number"},
            {"key": "customer_name", "description": "Customer contact name"},
            {"key": "company_name", "description": "Customer company name"},
        ]

    def __repr__(self):
        """String representation of EmailTemplate."""
        return f"<EmailTemplate(id={self.id}, name='{self.name}')>"
