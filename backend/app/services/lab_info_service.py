"""Lab info service for managing company information on COAs."""

import os
import shutil
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.lab_info import LabInfo
from app.services.base import BaseService
from app.utils.logger import logger
from app.config import settings


class LabInfoService(BaseService[LabInfo]):
    """
    Service for managing lab information.

    Provides methods for:
    - Getting or creating the default lab info
    - Updating lab info fields
    - Managing logo upload and deletion
    """

    def __init__(self):
        """Initialize lab info service."""
        super().__init__(LabInfo)

    def get_or_create_default(self, db: Session) -> LabInfo:
        """
        Get the lab info record, creating it with defaults if it doesn't exist.

        Args:
            db: Database session

        Returns:
            LabInfo instance
        """
        lab_info = db.query(LabInfo).first()

        if not lab_info:
            logger.info("Creating default lab info")
            defaults = LabInfo.get_defaults()
            lab_info = LabInfo(
                company_name=defaults["company_name"],
                address=defaults["address"],
                phone=defaults["phone"],
                email=defaults["email"],
                logo_path=defaults["logo_path"],
            )
            db.add(lab_info)
            db.commit()
            db.refresh(lab_info)
            logger.info(f"Created default lab info with id {lab_info.id}")

        return lab_info

    def update_info(
        self,
        db: Session,
        company_name: str,
        address: str,
        phone: Optional[str],
        email: Optional[str],
        city: str,
        state: str,
        zip_code: str,
        require_pdf_for_submission: bool = None,
        show_spec_preview_on_sample: bool = None,
        user_id: int = None,
    ) -> LabInfo:
        """
        Update the lab info text fields.

        Args:
            db: Database session
            company_name: Company name
            address: Street address
            phone: Phone number
            email: Email address
            city: City
            state: State
            zip_code: ZIP code
            require_pdf_for_submission: Whether PDF is required before submission
            user_id: ID of user making the change

        Returns:
            Updated LabInfo instance
        """
        lab_info = self.get_or_create_default(db)

        update_data = {
            "company_name": company_name,
            "address": address,
            "city": city,
            "state": state,
            "zip_code": zip_code,
        }

        if phone is not None:
            update_data["phone"] = phone
        if email is not None:
            update_data["email"] = email

        if require_pdf_for_submission is not None:
            update_data["require_pdf_for_submission"] = require_pdf_for_submission
        if show_spec_preview_on_sample is not None:
            update_data["show_spec_preview_on_sample"] = show_spec_preview_on_sample

        return self.update(
            db=db,
            db_obj=lab_info,
            obj_in=update_data,
            user_id=user_id,
        )

    def update_logo(
        self,
        db: Session,
        file_content: bytes,
        filename: str,
        content_type: str,
        user_id: int = None,
    ) -> LabInfo:
        """
        Upload and update the company logo.

        Args:
            db: Database session
            file_content: Raw file content
            filename: Original filename
            content_type: MIME type of the file
            user_id: ID of user making the change

        Returns:
            Updated LabInfo instance with new logo path
        """
        lab_info = self.get_or_create_default(db)

        # Delete old logo if exists
        if lab_info.logo_path:
            self._delete_logo_file(lab_info.logo_path)

        # Generate unique filename
        ext = os.path.splitext(filename)[1].lower()
        new_filename = f"logo_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}{ext}"

        # Ensure logos directory exists
        logos_dir = os.path.join(settings.upload_path, "logos")
        os.makedirs(logos_dir, exist_ok=True)

        # Save file
        file_path = os.path.join(logos_dir, new_filename)
        with open(file_path, "wb") as f:
            f.write(file_content)

        logger.info(f"Saved logo to {file_path}")

        # Update database with relative path
        relative_path = f"logos/{new_filename}"
        return self.update(
            db=db,
            db_obj=lab_info,
            obj_in={"logo_path": relative_path},
            user_id=user_id,
        )

    def delete_logo(
        self,
        db: Session,
        user_id: int = None,
    ) -> LabInfo:
        """
        Delete the company logo.

        Args:
            db: Database session
            user_id: ID of user making the change

        Returns:
            Updated LabInfo instance with logo_path set to None
        """
        lab_info = self.get_or_create_default(db)

        if lab_info.logo_path:
            self._delete_logo_file(lab_info.logo_path)

        return self.update(
            db=db,
            db_obj=lab_info,
            obj_in={"logo_path": None},
            user_id=user_id,
        )

    def _delete_logo_file(self, logo_path: str) -> None:
        """
        Delete a logo file from disk.

        Args:
            logo_path: Relative path to logo file
        """
        try:
            full_path = os.path.join(settings.upload_path, logo_path)
            if os.path.exists(full_path):
                os.remove(full_path)
                logger.info(f"Deleted logo file: {full_path}")
        except Exception as e:
            logger.error(f"Error deleting logo file {logo_path}: {e}")

    def get_logo_url(self, logo_path: Optional[str]) -> Optional[str]:
        """
        Get the full URL for a logo path.

        Args:
            logo_path: Relative path to logo file (e.g., "logos/logo_xxx.png")

        Returns:
            Full URL to access the logo, or None if no logo
        """
        if not logo_path:
            return None
        return f"/uploads/{logo_path}"

    def get_logo_full_path(self, logo_path: Optional[str]) -> Optional[str]:
        """
        Get the full filesystem path for a logo (used for PDF generation).

        Args:
            logo_path: Relative path to logo file

        Returns:
            Full filesystem path, or None if no logo
        """
        if not logo_path:
            return None
        full_path = os.path.join(settings.upload_path, logo_path)
        if os.path.exists(full_path):
            return full_path
        return None

    def update_signature(
        self,
        db: Session,
        file_content: bytes,
        filename: str,
        content_type: str,
        user_id: int = None,
    ) -> LabInfo:
        """
        Upload and update the signature image.

        Args:
            db: Database session
            file_content: Raw file content
            filename: Original filename
            content_type: MIME type of the file
            user_id: ID of user making the change

        Returns:
            Updated LabInfo instance with new signature path
        """
        lab_info = self.get_or_create_default(db)

        # Delete old signature if exists
        if lab_info.signature_path:
            self._delete_file(lab_info.signature_path)

        # Generate unique filename
        ext = os.path.splitext(filename)[1].lower()
        new_filename = f"signature_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}{ext}"

        # Ensure signatures directory exists
        signatures_dir = os.path.join(settings.upload_path, "signatures")
        os.makedirs(signatures_dir, exist_ok=True)

        # Save file
        file_path = os.path.join(signatures_dir, new_filename)
        with open(file_path, "wb") as f:
            f.write(file_content)

        logger.info(f"Saved signature to {file_path}")

        # Update database with relative path
        relative_path = f"signatures/{new_filename}"
        return self.update(
            db=db,
            db_obj=lab_info,
            obj_in={"signature_path": relative_path},
            user_id=user_id,
        )

    def delete_signature(
        self,
        db: Session,
        user_id: int = None,
    ) -> LabInfo:
        """
        Delete the signature image.

        Args:
            db: Database session
            user_id: ID of user making the change

        Returns:
            Updated LabInfo instance with signature_path set to None
        """
        lab_info = self.get_or_create_default(db)

        if lab_info.signature_path:
            self._delete_file(lab_info.signature_path)

        return self.update(
            db=db,
            db_obj=lab_info,
            obj_in={"signature_path": None},
            user_id=user_id,
        )

    def _delete_file(self, file_path: str) -> None:
        """
        Delete a file from disk.

        Args:
            file_path: Relative path to file
        """
        try:
            full_path = os.path.join(settings.upload_path, file_path)
            if os.path.exists(full_path):
                os.remove(full_path)
                logger.info(f"Deleted file: {full_path}")
        except Exception as e:
            logger.error(f"Error deleting file {file_path}: {e}")

    def get_signature_url(self, signature_path: Optional[str]) -> Optional[str]:
        """
        Get the full URL for a signature path.

        Args:
            signature_path: Relative path to signature file

        Returns:
            Full URL to access the signature, or None if no signature
        """
        if not signature_path:
            return None
        return f"/uploads/{signature_path}"


# Singleton instance
lab_info_service = LabInfoService()
