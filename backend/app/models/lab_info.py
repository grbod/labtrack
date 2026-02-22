"""LabInfo model for company/lab information displayed on COAs."""

from sqlalchemy import Column, String, Text, Boolean
from app.models.base import BaseModel


class LabInfo(BaseModel):
    """
    LabInfo model for storing company information displayed on COA documents.

    This is a singleton-style table that stores the lab's company information
    including name, address, contact details, and logo.

    Attributes:
        company_name: Company/lab name displayed on COAs
        address: Full address displayed on COAs
        phone: Contact phone number
        email: Contact email address
        logo_path: Path to uploaded logo file (relative to uploads directory)
    """

    __tablename__ = "lab_info"

    # Company information fields
    company_name = Column(String(200), nullable=False, default="Your Company Name")
    address = Column(String(500), nullable=False, default="123 Quality Street")
    city = Column(String(100), nullable=False, default="Lab City")
    state = Column(String(50), nullable=False, default="FL")
    zip_code = Column(String(20), nullable=False, default="12345")
    phone = Column(String(50), nullable=False, default="(555) 123-4567")
    email = Column(String(200), nullable=False, default="lab@company.com")
    logo_path = Column(String(500), nullable=True)  # Path to uploaded logo
    signature_path = Column(String(500), nullable=True)  # Path to uploaded signature
    signer_name = Column(String(200), nullable=True)  # Name to display under signature

    # Submission settings
    require_pdf_for_submission = Column(Boolean, nullable=False, default=True)  # Require PDF before submit
    show_spec_preview_on_sample = Column(Boolean, nullable=False, default=True)  # Show spec preview on sample creation

    # Default values
    DEFAULT_COMPANY_NAME = "Your Company Name"
    DEFAULT_ADDRESS = "123 Quality Street"
    DEFAULT_CITY = "Lab City"
    DEFAULT_STATE = "FL"
    DEFAULT_ZIP_CODE = "12345"
    DEFAULT_PHONE = "(555) 123-4567"
    DEFAULT_EMAIL = "lab@company.com"

    @classmethod
    def get_defaults(cls) -> dict:
        """Get default lab info values."""
        return {
            "company_name": cls.DEFAULT_COMPANY_NAME,
            "address": cls.DEFAULT_ADDRESS,
            "city": cls.DEFAULT_CITY,
            "state": cls.DEFAULT_STATE,
            "zip_code": cls.DEFAULT_ZIP_CODE,
            "phone": cls.DEFAULT_PHONE,
            "email": cls.DEFAULT_EMAIL,
            "logo_path": None,
        }

    @property
    def full_address(self) -> str:
        """Get the full formatted address."""
        return f"{self.address}, {self.city}, {self.state} {self.zip_code}"

    def __repr__(self):
        """String representation of LabInfo."""
        return f"<LabInfo(id={self.id}, company_name='{self.company_name}')>"
