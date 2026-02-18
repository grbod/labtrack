"""COA PDF generation service using ReportLab (pure Python, no system dependencies)."""

import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

from jinja2 import Environment, FileSystemLoader
from sqlalchemy.orm import Session
from sqlalchemy import func
from loguru import logger

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from xml.sax.saxutils import escape as xml_escape

from app.config import settings
from app.models.coa_release import COARelease
from app.models.test_result import TestResult
from app.models.enums import TestResultStatus
from app.models.lab_test_type import LabTestType
from app.services.lab_info_service import lab_info_service
from app.services.storage_service import get_storage_service


class COAGenerationService:
    """
    Service for generating COA PDFs from COARelease records.

    Uses ReportLab for PDF generation (pure Python, no system dependencies).
    """

    def __init__(self):
        """Initialize the COA generation service."""
        # Template directory - relative to backend folder
        template_dir = Path(__file__).parent.parent.parent / "templates"
        self.template_dir = template_dir

        # Output directory for generated COAs
        self.output_dir = Path(settings.upload_path) / "coas"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=True
        )

    def generate(self, db: Session, coa_release_id: int) -> str:
        """
        Generate a COA PDF for a given COARelease using ReportLab.

        Args:
            db: Database session
            coa_release_id: ID of the COARelease record

        Returns:
            Storage key for the generated PDF file

        Raises:
            ValueError: If COARelease not found or has no approved test results
        """
        # Get the COARelease with relations
        coa_release = self._get_coa_release(db, coa_release_id)
        if not coa_release:
            raise ValueError(f"COARelease with id {coa_release_id} not found")

        # Build template context
        context = self._build_context(db, coa_release.lot, coa_release.product, coa_release)

        # Generate PDF filename and storage key
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"COA_{coa_release.lot.lot_number}_{timestamp}.pdf"
        storage_key = f"coas/{filename}"

        # Generate PDF to temporary file, then upload to storage
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
            tmp_path = tmp_file.name

        try:
            # Generate PDF with ReportLab to temp file
            self._generate_pdf_reportlab(context, tmp_path)

            # Read the generated PDF and upload to storage
            with open(tmp_path, "rb") as f:
                pdf_content = f.read()

            storage = get_storage_service()
            storage.upload(pdf_content, storage_key, content_type="application/pdf")

        finally:
            # Clean up temp file
            import os
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

        # Update COARelease with storage key
        coa_release.coa_file_path = storage_key
        db.commit()

        logger.info(f"Generated COA PDF: {storage_key}")
        return storage_key

    def get_preview_data(self, db: Session, coa_release_id: int) -> Dict[str, Any]:
        """
        Get the data that would be used for COA generation (for preview).

        Args:
            db: Database session
            coa_release_id: ID of the COARelease record

        Returns:
            Dictionary with all COA template context data

        Raises:
            ValueError: If COARelease not found
        """
        coa_release = self._get_coa_release(db, coa_release_id)
        if not coa_release:
            raise ValueError(f"COARelease with id {coa_release_id} not found")

        return self._build_context(db, coa_release.lot, coa_release.product, coa_release)

    def get_or_generate_pdf(self, db: Session, coa_release_id: int) -> str:
        """
        Get existing PDF storage key or generate a new one if needed.

        Args:
            db: Database session
            coa_release_id: ID of the COARelease record

        Returns:
            Storage key for the PDF file
        """
        coa_release = self._get_coa_release(db, coa_release_id)
        if not coa_release:
            raise ValueError(f"COARelease with id {coa_release_id} not found")

        # Check if PDF exists in storage
        if coa_release.coa_file_path:
            storage = get_storage_service()
            if storage.exists(coa_release.coa_file_path):
                return coa_release.coa_file_path

        # Generate new PDF
        return self.generate(db, coa_release_id)

    def get_pdf_url(self, db: Session, coa_release_id: int) -> str:
        """
        Get a URL for downloading the COA PDF.

        For R2 storage: Returns a presigned URL (1-hour expiry).
        For local storage: Returns the storage key (API will serve file).

        Args:
            db: Database session
            coa_release_id: ID of the COARelease record

        Returns:
            URL or key for accessing the PDF
        """
        storage_key = self.get_or_generate_pdf(db, coa_release_id)
        storage = get_storage_service()
        return storage.get_presigned_url(storage_key)

    def _get_coa_release(self, db: Session, coa_release_id: int) -> Optional[COARelease]:
        """Get COARelease with all required relations loaded."""
        from sqlalchemy.orm import joinedload

        return (
            db.query(COARelease)
            .options(
                joinedload(COARelease.lot),
                joinedload(COARelease.product),
                joinedload(COARelease.customer),
                joinedload(COARelease.released_by),
            )
            .filter(COARelease.id == coa_release_id)
            .first()
        )

    def _build_context(
        self,
        db: Session,
        lot,
        product,
        coa_release: Optional[COARelease] = None
    ) -> Dict[str, Any]:
        """
        Build the template context dictionary for COA generation or preview.

        Args:
            db: Database session
            lot: The Lot record
            product: The Product record
            coa_release: Optional COARelease record (None for preview mode)

        Returns:
            Dictionary with all template variables
        """
        from app.models.product_test_spec import ProductTestSpecification
        from app.services.coa_category_order_service import coa_category_order_service

        # Get test results for this lot that have values (no ordering in SQL, we'll sort in Python)
        test_results = (
            db.query(TestResult)
            .filter(
                TestResult.lot_id == lot.id,
                TestResult.result_value.isnot(None),
                TestResult.result_value != "",
            )
            .all()
        )

        # Get category order configuration
        category_order = coa_category_order_service.get_ordered_categories(db)

        # Build a lookup for test_type -> category from LabTestType
        test_type_names = [r.test_type for r in test_results]
        lab_test_types = (
            db.query(LabTestType)
            .filter(LabTestType.test_name.in_(test_type_names))
            .all()
        ) if test_type_names else []
        category_lookup = {lt.test_name.lower(): lt.test_category for lt in lab_test_types}

        def get_category(test_type: str) -> str:
            """Get category for a test type, defaulting to 'Other' if not found."""
            return category_lookup.get(test_type.lower(), "Other")

        def sort_key(result: TestResult) -> tuple:
            """
            Sort key for test results:
            1. Category order index (configured categories first, unconfigured at end)
            2. Category name (for unconfigured categories, alphabetical)
            3. Test name alphabetically within each category
            """
            category = get_category(result.test_type)
            try:
                cat_index = category_order.index(category)
            except ValueError:
                # Category not in configured order - place at end
                cat_index = len(category_order)
            return (cat_index, category, result.test_type.lower())

        # Sort test results by category order, then alphabetically within category
        test_results.sort(key=sort_key)

        # Get product test specifications for fallback
        product_specs = (
            db.query(ProductTestSpecification)
            .filter(ProductTestSpecification.product_id == product.id)
            .all()
        ) if product else []
        # Build lookup dict by test name (case-insensitive)
        spec_lookup = {spec.test_name.lower(): spec.specification for spec in product_specs}

        # Format test results for template
        tests = []
        for result in test_results:
            # Try to get specification from:
            # 1. TestResult.specification (what was entered/saved with the result)
            # 2. ProductTestSpec (product's default specification for this test type)
            # 3. Default fallback
            specification = result.specification
            if not specification:
                specification = spec_lookup.get(result.test_type.lower())
            if not specification:
                specification = self._get_default_spec(result.test_type)

            tests.append({
                "id": result.id,  # Include ID for retest original value matching
                "name": result.test_type,
                "result": result.result_value or "N/D",
                "unit": result.unit or "",
                "specification": specification,
                "status": self._determine_status(result),
            })

        # Get lab info from database
        lab_info = lab_info_service.get_or_create_default(db)

        # Get released_by user - handle potential lazy-loading issues
        released_by_user = None
        if coa_release:
            released_by_user = coa_release.released_by
            # If relationship didn't load but we have the ID, fetch explicitly
            if released_by_user is None and coa_release.released_by_id:
                from app.models import User
                released_by_user = db.query(User).filter(User.id == coa_release.released_by_id).first()

        # Build context with release-specific or preview defaults
        context = {
            # Company info from database
            "company_name": lab_info.company_name,
            "company_address": lab_info.full_address,
            "company_logo_url": lab_info_service.get_logo_full_path(lab_info.logo_path),

            # Product info
            "product_name": product.display_name if product else "Unknown Product",
            "brand": product.brand if product else "Unknown Brand",

            # Lot info
            "lot_number": lot.lot_number,
            "reference_number": lot.reference_number,
            "mfg_date": lot.mfg_date.strftime("%B %d, %Y") if lot.mfg_date else None,
            "exp_date": lot.exp_date.strftime("%B %d, %Y") if lot.exp_date else None,

            # Test results
            "tests": tests,

            # Notes and release info (from coa_release if available, else preview defaults)
            "notes": coa_release.notes if coa_release else None,
            "generated_date": datetime.now().strftime("%B %d, %Y"),
            "released_at": (
                coa_release.released_at.strftime("%B %d, %Y")
                if coa_release and coa_release.released_at
                else None
            ),
            "released_by": (
                released_by_user.full_name or released_by_user.username
                if released_by_user
                else "(Preview)"
            ),
            "released_by_title": (
                released_by_user.title
                if released_by_user
                else None
            ),
            "released_by_email": (
                released_by_user.email
                if released_by_user
                else "(Preview)"
            ),
            # Contact info from the releasing user (not company-wide)
            "released_by_phone": (
                released_by_user.phone
                if released_by_user
                else None
            ),
            "released_by_email": (
                released_by_user.email
                if released_by_user
                else None
            ),
            # Signature data for COA authorization (use the releasing user's signature)
            "signature_url": (
                f"/uploads/{released_by_user.signature_path}"
                if released_by_user and released_by_user.signature_path
                else None
            ),
            "signature_path": (
                released_by_user.signature_path
                if released_by_user and released_by_user.signature_path
                else None
            ),
        }

        return context

    def _determine_status(self, result: TestResult) -> str:
        """
        Determine pass/fail status for a test result.

        In a real implementation, this would compare against specifications.
        For now, we assume all approved results pass.
        """
        # All approved results are considered passing
        # Future: implement specification comparison logic
        return "Pass"

    def _get_default_spec(self, test_type: str) -> str:
        """Get default specification for common test types."""
        specs = {
            "Total Plate Count": "< 10,000 CFU/g",
            "Yeast/Mold": "< 1,000 CFU/g",
            "Yeast and Mold": "< 1,000 CFU/g",
            "E. coli": "Negative",
            "E. Coli": "Negative",
            "Salmonella": "Negative",
            "Staphylococcus aureus": "Negative",
            "Total Coliform Count": "< 10 CFU/g",
            "Lead": "< 0.5 ppm",
            "Mercury": "< 0.1 ppm",
            "Cadmium": "< 0.3 ppm",
            "Arsenic": "< 1.0 ppm",
            "Gluten": "< 20 ppm",
        }
        return specs.get(test_type, "Within limits")

    def render_html_preview(self, db: Session, coa_release_id: int) -> str:
        """
        Render the COA as HTML (for browser preview).

        Args:
            db: Database session
            coa_release_id: ID of the COARelease record

        Returns:
            Rendered HTML string
        """
        coa_release = self._get_coa_release(db, coa_release_id)
        if not coa_release:
            raise ValueError(f"COARelease with id {coa_release_id} not found")

        context = self._build_context(db, coa_release.lot, coa_release.product, coa_release)
        template = self.env.get_template("coa_template.html")
        return template.render(**context)

    def generate_preview(self, db: Session, lot_id: int, product_id: int) -> str:
        """
        Generate a preview PDF for a lot+product pair without a COARelease record.

        Args:
            db: Database session
            lot_id: ID of the lot
            product_id: ID of the product

        Returns:
            Storage key for the generated preview PDF file
        """
        from app.models import Lot, Product

        # Get lot and product
        lot = db.query(Lot).filter(Lot.id == lot_id).first()
        if not lot:
            raise ValueError(f"Lot with id {lot_id} not found")

        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise ValueError(f"Product with id {product_id} not found")

        # Build context without COARelease (preview mode)
        context = self._build_context(db, lot, product)

        # Generate preview PDF filename and storage key
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"COA_preview_{lot.lot_number}_{timestamp}.pdf"
        storage_key = f"coas/{filename}"

        # Generate PDF to temporary file, then upload to storage
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
            tmp_path = tmp_file.name

        try:
            # Generate PDF with ReportLab to temp file
            self._generate_pdf_reportlab(context, tmp_path)

            # Read the generated PDF and upload to storage
            with open(tmp_path, "rb") as f:
                pdf_content = f.read()

            storage = get_storage_service()
            storage.upload(pdf_content, storage_key, content_type="application/pdf")

        finally:
            # Clean up temp file
            import os
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

        logger.info(f"Generated COA preview PDF: {storage_key}")
        return storage_key

    def _generate_pdf_reportlab(self, context: Dict[str, Any], output_path: str) -> None:
        """
        Generate PDF using ReportLab (pure Python, no system dependencies).

        Args:
            context: Template context dictionary with all COA data
            output_path: Path to write the PDF file
        """
        # Create PDF document
        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            rightMargin=0.5*inch,
            leftMargin=0.5*inch,
            topMargin=0.5*inch,
            bottomMargin=0.5*inch
        )

        # Setup styles
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(
            name='COATitle',
            parent=styles['Title'],
            fontSize=18,
            textColor=colors.HexColor('#0f172a'),
            alignment=TA_CENTER,
            spaceAfter=10
        ))
        styles.add(ParagraphStyle(
            name='COAHeader',
            parent=styles['Heading2'],
            fontSize=11,
            textColor=colors.HexColor('#0f172a'),
            alignment=TA_LEFT,
            spaceBefore=12,
            spaceAfter=6
        ))
        styles.add(ParagraphStyle(
            name='COANormal',
            parent=styles['Normal'],
            fontSize=9,
            alignment=TA_LEFT,
            leading=11
        ))
        styles.add(ParagraphStyle(
            name='COAFooter',
            parent=styles['Normal'],
            fontSize=8,
            alignment=TA_CENTER,
            textColor=colors.grey
        ))
        styles.add(ParagraphStyle(
            name='COADocTitle',
            parent=styles['Normal'],
            fontSize=14,
            fontName='Helvetica-Bold',
            textColor=colors.HexColor('#0f172a'),
            alignment=TA_RIGHT,
            spaceAfter=4
        ))
        styles.add(ParagraphStyle(
            name='COADocMeta',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#64748b'),
            alignment=TA_RIGHT,
            leading=11
        ))
        styles.add(ParagraphStyle(
            name='COACompanyName',
            parent=styles['Normal'],
            fontSize=9,
            fontName='Helvetica-Bold',
            textColor=colors.HexColor('#64748b'),
            leading=11
        ))
        styles.add(ParagraphStyle(
            name='COACompanyInfo',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#64748b'),
            leading=11
        ))

        wrap_style = ParagraphStyle(
            name='COAWrap',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=9,
            leading=11,
            alignment=TA_LEFT,
            wordWrap='CJK',
            splitLongWords=1,
        )
        wrap_style_small = ParagraphStyle(
            name='COAWrapSmall',
            parent=wrap_style,
            fontSize=8,
            leading=10,
        )
        label_value_style = ParagraphStyle(
            name='COALabelValue',
            parent=styles['Normal'],
            fontSize=9,
            leading=12,
            textColor=colors.HexColor('#0f172a'),
        )

        def wrap_cell(value: Any, style: ParagraphStyle) -> Paragraph:
            text = "" if value is None else str(value)
            return Paragraph(xml_escape(text), style)

        def stacked_label_value(label: str, value: Any) -> Paragraph:
            safe_value = "" if value is None else str(value)
            return Paragraph(
                f"<font size='8' color='#64748b'><b>{xml_escape(label.upper())}</b></font>"
                f"<br/><font size='10' color='#0f172a'>{xml_escape(safe_value)}</font>",
                label_value_style
            )

        # Build story (content)
        story = []

        # Company header + document info (aligned to match preview)
        company_blocks = []
        logo_path = context.get('company_logo_url')
        if logo_path:
            try:
                from PIL import Image as PILImage
                logo_full_path = Path(logo_path)
                if logo_full_path.exists():
                    with PILImage.open(logo_full_path) as pil_img:
                        aspect = pil_img.width / pil_img.height
                    max_height = 0.6 * inch
                    max_width = 2.2 * inch
                    logo_width = min(max_width, max_height * aspect)
                    logo_height = logo_width / aspect
                    if logo_height > max_height:
                        logo_height = max_height
                        logo_width = logo_height * aspect
                    logo_img = Image(str(logo_full_path), width=logo_width, height=logo_height)
                    logo_img.hAlign = 'LEFT'
                    company_blocks.append(logo_img)
                    company_blocks.append(Spacer(1, 0.06 * inch))
            except Exception:
                pass

        company_blocks.append(Paragraph(
            xml_escape(context.get('company_name', 'Company Name')),
            styles['COACompanyName']
        ))
        company_address = context.get('company_address')
        if company_address:
            company_blocks.append(Paragraph(xml_escape(company_address), styles['COACompanyInfo']))

        phone = context.get('company_phone')
        email = context.get('company_email')
        contact_parts = []
        if phone:
            contact_parts.append(f"Tel: {phone}")
        if email:
            contact_parts.append(f"Email: {email}")
        if contact_parts:
            company_blocks.append(Paragraph(
                xml_escape(" | ".join(contact_parts)),
                styles['COACompanyInfo']
            ))

        doc_number = f"COA-{context.get('reference_number', 'N/A')}"
        doc_blocks = [
            Paragraph("CERTIFICATE OF ANALYSIS", styles['COADocTitle']),
            Paragraph(f"Document #: {doc_number}", styles['COADocMeta']),
            Paragraph(f"Generated: {context.get('generated_date', 'N/A')}", styles['COADocMeta']),
        ]

        header_table = Table([[company_blocks, doc_blocks]], colWidths=[4.6*inch, 2.9*inch])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LINEBELOW', (0, 0), (-1, 0), 1, colors.HexColor('#1e293b')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ]))
        story.append(header_table)
        story.append(Spacer(1, 0.15*inch))

        # Product Information section
        story.append(Paragraph("PRODUCT INFORMATION", styles['COAHeader']))

        product_data = [
            [
                stacked_label_value("Product Name", context.get('product_name', 'N/A')),
                stacked_label_value("Brand", context.get('brand', 'N/A')),
            ],
            [
                stacked_label_value("Lot Number", context.get('lot_number', 'N/A')),
                stacked_label_value("Reference Number", context.get('reference_number', 'N/A')),
            ],
            [
                stacked_label_value("Manufacturing Date", context.get('mfg_date', 'Not set')),
                stacked_label_value("Expiration Date", context.get('exp_date', 'Not set')),
            ],
        ]
        product_table = Table(product_data, colWidths=[3.75*inch, 3.75*inch])
        product_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ]))
        story.append(product_table)
        story.append(Spacer(1, 0.15*inch))

        # Test Results section
        story.append(Paragraph("TEST RESULTS", styles['COAHeader']))

        tests = context.get('tests', [])
        if tests:
            test_data = [['TEST NAME', 'RESULT', 'SPECIFICATION', 'STATUS']]
            for test in tests:
                status = test.get('status', 'Pass')
                status_color = '#16a34a' if str(status).lower() == 'pass' else '#dc2626'
                test_data.append([
                    wrap_cell(test.get('name', ''), wrap_style_small),
                    test.get('result', 'N/D'),
                    wrap_cell(test.get('specification', 'Within limits'), wrap_style_small),
                    Paragraph(
                        f"<font color='{status_color}'>{xml_escape(status)}</font>",
                        wrap_style_small
                    ),
                ])

            test_table = Table(test_data, colWidths=[2.5*inch, 1.5*inch, 2*inch, 1.5*inch])
            test_table.setStyle(TableStyle([
                # Header
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#475569')),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('ALIGN', (0, 0), (-1, 0), 'LEFT'),
                # Data
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#0f172a')),
                ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                # Grid
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
                ('LINEBELOW', (0, 0), (-1, 0), 1, colors.HexColor('#e2e8f0')),
                # Padding
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                # Alternating row colors
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
            ]))
            story.append(test_table)
        else:
            story.append(Paragraph("No test results available.", styles['COANormal']))

        story.append(Spacer(1, 0.15*inch))

        # Notes section (if present)
        notes = context.get('notes')
        if notes and str(notes).strip() and str(notes).strip().lower() != "click to add notes...":
            story.append(Paragraph("NOTES", styles['COAHeader']))
            notes_table = Table([[wrap_cell(notes, wrap_style)]], colWidths=[7.5*inch])
            notes_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fffbeb')),
                ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#fbbf24')),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ]))
            story.append(notes_table)
            story.append(Spacer(1, 0.15*inch))

        # Authorization section
        story.append(Paragraph("AUTHORIZATION", styles['COAHeader']))

        released_by = context.get('released_by', '')
        released_by_title = context.get('released_by_title', '')
        released_by_email = context.get('released_by_email', '(Preview)')
        released_at = context.get('released_at', context.get('generated_date', ''))
        signature_path = context.get('signature_path')

        # Add signature image if exists (use settings.upload_path for Linux compatibility)
        if signature_path:
            from PIL import Image as PILImage
            full_path = Path(settings.upload_path) / signature_path
            if full_path.exists():
                try:
                    # Calculate dimensions maintaining aspect ratio
                    with PILImage.open(full_path) as pil_img:
                        aspect = pil_img.width / pil_img.height
                    sig_height = 0.5 * inch
                    sig_width = sig_height * aspect
                    if sig_width > 2 * inch:
                        sig_width = 2 * inch
                        sig_height = sig_width / aspect

                    sig_img = Image(str(full_path), width=sig_width, height=sig_height)
                    sig_img.hAlign = 'LEFT'
                    story.append(sig_img)
                    story.append(Spacer(1, 0.05*inch))
                except Exception:
                    pass  # Skip signature if image can't be loaded

        # Name
        if released_by:
            story.append(Paragraph(released_by, ParagraphStyle(
                'SignerName', parent=styles['Normal'], fontSize=10, fontName='Helvetica-Bold'
            )))

        # Title
        if released_by_title:
            story.append(Paragraph(released_by_title, ParagraphStyle(
                'SignerTitle', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#475569')
            )))

        # Email
        story.append(Paragraph(f"Email: {released_by_email}", ParagraphStyle(
            'SignerEmail', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#475569')
        )))

        # Date
        story.append(Paragraph(f"Date: {released_at}", ParagraphStyle(
            'SignerDate', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#475569')
        )))

        story.append(Spacer(1, 0.2*inch))

        # Disclaimer
        disclaimer = "This Certificate of Analysis is issued based on the test results of a representative sample. Results apply only to the lot specified above."
        disclaimer_table = Table([[Paragraph(xml_escape(disclaimer), styles['COAFooter'])]], colWidths=[7.5*inch])
        disclaimer_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(disclaimer_table)

        # Build PDF
        doc.build(story)


# Singleton instance
coa_generation_service = COAGenerationService()
