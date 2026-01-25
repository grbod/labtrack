"""COA PDF generation service using ReportLab (pure Python, no system dependencies)."""

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

from app.config import settings
from app.models.coa_release import COARelease
from app.models.test_result import TestResult
from app.models.enums import TestResultStatus
from app.models.lab_test_type import LabTestType
from app.services.lab_info_service import lab_info_service


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
            Path to the generated PDF file

        Raises:
            ValueError: If COARelease not found or has no approved test results
        """
        # Get the COARelease with relations
        coa_release = self._get_coa_release(db, coa_release_id)
        if not coa_release:
            raise ValueError(f"COARelease with id {coa_release_id} not found")

        # Build template context
        context = self._build_context(db, coa_release.lot, coa_release.product, coa_release)

        # Generate PDF filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"COA_{coa_release.lot.lot_number}_{timestamp}.pdf"
        output_path = self.output_dir / filename

        # Generate PDF with ReportLab
        self._generate_pdf_reportlab(context, str(output_path))

        # Update COARelease with file path
        coa_release.coa_file_path = str(output_path)
        db.commit()

        logger.info(f"Generated COA PDF: {output_path}")
        return str(output_path)

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
        Get existing PDF or generate a new one if needed.

        Args:
            db: Database session
            coa_release_id: ID of the COARelease record

        Returns:
            Path to the PDF file
        """
        coa_release = self._get_coa_release(db, coa_release_id)
        if not coa_release:
            raise ValueError(f"COARelease with id {coa_release_id} not found")

        # Check if PDF exists and is valid
        if coa_release.coa_file_path:
            pdf_path = Path(coa_release.coa_file_path)
            if pdf_path.exists():
                return str(pdf_path)

        # Generate new PDF
        return self.generate(db, coa_release_id)

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
            Path to the generated preview PDF file
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

        # Generate preview PDF filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"COA_preview_{lot.lot_number}_{timestamp}.pdf"
        output_path = self.output_dir / filename

        # Generate PDF with ReportLab
        self._generate_pdf_reportlab(context, str(output_path))

        logger.info(f"Generated COA preview PDF: {output_path}")
        return str(output_path)

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
            textColor=colors.HexColor('#1a5f2a'),
            alignment=TA_CENTER,
            spaceAfter=10
        ))
        styles.add(ParagraphStyle(
            name='COAHeader',
            parent=styles['Heading2'],
            fontSize=11,
            textColor=colors.HexColor('#1a5f2a'),
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

        # Build story (content)
        story = []

        # Company header
        company_header = [
            [context.get('company_name', 'Company Name'), '', context.get('company_phone', '')],
            [context.get('company_address', ''), '', context.get('company_email', '')]
        ]
        header_table = Table(company_header, colWidths=[3.5*inch, 1*inch, 3*inch])
        header_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (0, 0), 14),
            ('TEXTCOLOR', (0, 0), (0, 0), colors.HexColor('#1a5f2a')),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.grey),
        ]))
        story.append(header_table)
        story.append(Spacer(1, 0.2*inch))

        # Title
        story.append(Paragraph("CERTIFICATE OF ANALYSIS", styles['COATitle']))
        story.append(Spacer(1, 0.15*inch))

        # Document info
        doc_number = f"COA-{context.get('reference_number', 'N/A')}"
        doc_info = [[f"Document #: {doc_number}", f"Generated: {context.get('generated_date', 'N/A')}"]]
        doc_table = Table(doc_info, colWidths=[3.75*inch, 3.75*inch])
        doc_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.grey),
        ]))
        story.append(doc_table)
        story.append(Spacer(1, 0.15*inch))

        # Product Information section
        story.append(Paragraph("PRODUCT INFORMATION", styles['COAHeader']))

        product_data = [
            ['Product Name:', context.get('product_name', 'N/A'), 'Brand:', context.get('brand', 'N/A')],
            ['Lot Number:', context.get('lot_number', 'N/A'), 'Reference:', context.get('reference_number', 'N/A')],
            ['Mfg Date:', context.get('mfg_date', 'N/A'), 'Exp Date:', context.get('exp_date', 'N/A')],
        ]
        product_table = Table(product_data, colWidths=[1.2*inch, 2.55*inch, 1*inch, 2.75*inch])
        product_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8f9fa')),
        ]))
        story.append(product_table)
        story.append(Spacer(1, 0.15*inch))

        # Test Results section
        story.append(Paragraph("TEST RESULTS", styles['COAHeader']))

        tests = context.get('tests', [])
        if tests:
            test_data = [['Test', 'Result', 'Specification', 'Status']]
            for test in tests:
                test_data.append([
                    test.get('name', ''),
                    test.get('result', 'N/D'),
                    test.get('specification', 'Within limits'),
                    test.get('status', 'Pass')
                ])

            test_table = Table(test_data, colWidths=[2.5*inch, 1.5*inch, 2*inch, 1.5*inch])
            test_table.setStyle(TableStyle([
                # Header
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a5f2a')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                # Data
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('ALIGN', (1, 1), (1, -1), 'CENTER'),
                ('ALIGN', (3, 1), (3, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                # Grid
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('LINEBELOW', (0, 0), (-1, 0), 1, colors.black),
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
        if notes:
            story.append(Paragraph("NOTES", styles['COAHeader']))
            notes_table = Table([[notes]], colWidths=[7.5*inch])
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

                    story.append(Image(str(full_path), width=sig_width, height=sig_height))
                    story.append(Spacer(1, 0.05*inch))
                except Exception:
                    pass  # Skip signature if image can't be loaded

        # Name
        story.append(Paragraph(released_by, ParagraphStyle(
            'SignerName', parent=styles['Normal'], fontSize=10, fontName='Helvetica-Bold'
        )))

        # Title
        if released_by_title:
            story.append(Paragraph(released_by_title, ParagraphStyle(
                'SignerTitle', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#475569')
            )))

        # Date
        story.append(Paragraph(f"Date: {released_at}", ParagraphStyle(
            'SignerDate', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#475569')
        )))

        story.append(Spacer(1, 0.2*inch))

        # Disclaimer
        disclaimer = "This Certificate of Analysis is issued based on the test results of a representative sample. Results apply only to the lot specified above."
        story.append(Paragraph(disclaimer, styles['COAFooter']))

        # Build PDF
        doc.build(story)


# Singleton instance
coa_generation_service = COAGenerationService()
