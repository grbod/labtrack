"""COA PDF generation service using WeasyPrint."""

from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

from jinja2 import Environment, FileSystemLoader
from sqlalchemy.orm import Session
from loguru import logger

from app.config import settings
from app.models.coa_release import COARelease
from app.models.test_result import TestResult
from app.models.enums import TestResultStatus


class COAGenerationService:
    """
    Service for generating COA PDFs from COARelease records.

    Uses WeasyPrint for HTML to PDF conversion with Jinja2 templates.
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
        Generate a COA PDF for a given COARelease.

        Args:
            db: Database session
            coa_release_id: ID of the COARelease record

        Returns:
            Path to the generated PDF file

        Raises:
            ValueError: If COARelease not found or has no approved test results
        """
        # Import WeasyPrint here to avoid import errors if not installed
        try:
            from weasyprint import HTML
        except ImportError:
            raise RuntimeError(
                "WeasyPrint is not installed. Please install it with: "
                "pip install weasyprint"
            )

        # Get the COARelease with relations
        coa_release = self._get_coa_release(db, coa_release_id)
        if not coa_release:
            raise ValueError(f"COARelease with id {coa_release_id} not found")

        # Build template context
        context = self._build_context(db, coa_release)

        # Render HTML template
        template = self.env.get_template("coa_template.html")
        html_content = template.render(**context)

        # Generate PDF filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"COA_{coa_release.lot.lot_number}_{timestamp}.pdf"
        output_path = self.output_dir / filename

        # Generate PDF with WeasyPrint
        html = HTML(string=html_content, base_url=str(self.template_dir))
        html.write_pdf(str(output_path))

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

        return self._build_context(db, coa_release)

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

    def _build_context(self, db: Session, coa_release: COARelease) -> Dict[str, Any]:
        """
        Build the template context dictionary for COA generation.

        Args:
            db: Database session
            coa_release: The COARelease record

        Returns:
            Dictionary with all template variables
        """
        lot = coa_release.lot
        product = coa_release.product

        # Get approved test results for this lot
        test_results = (
            db.query(TestResult)
            .filter(
                TestResult.lot_id == lot.id,
                TestResult.status == TestResultStatus.APPROVED
            )
            .order_by(TestResult.test_type)
            .all()
        )

        # Format test results for template
        tests = []
        for result in test_results:
            tests.append({
                "name": result.test_type,
                "result": result.result_value or "N/D",
                "unit": result.unit or "",
                "specification": result.specification or self._get_default_spec(result.test_type),
                "status": self._determine_status(result),
            })

        # Build context
        context = {
            # Company info from settings
            "company_name": settings.company_name,
            "company_address": settings.company_address,
            "company_phone": settings.company_phone,
            "company_email": settings.company_email,

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

            # Notes
            "notes": coa_release.notes,

            # Generation info
            "generated_date": datetime.now().strftime("%B %d, %Y"),
            "released_by": coa_release.released_by.username if coa_release.released_by else None,
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

        context = self._build_context(db, coa_release)
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
        # Import WeasyPrint here to avoid import errors if not installed
        try:
            from weasyprint import HTML
        except ImportError:
            raise RuntimeError(
                "WeasyPrint is not installed. Please install it with: "
                "pip install weasyprint"
            )

        from app.models import Lot, Product

        # Get lot and product
        lot = db.query(Lot).filter(Lot.id == lot_id).first()
        if not lot:
            raise ValueError(f"Lot with id {lot_id} not found")

        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise ValueError(f"Product with id {product_id} not found")

        # Build context without COARelease
        context = self._build_context_for_preview(db, lot, product)

        # Render HTML template
        template = self.env.get_template("coa_template.html")
        html_content = template.render(**context)

        # Generate preview PDF filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"COA_preview_{lot.lot_number}_{timestamp}.pdf"
        output_path = self.output_dir / filename

        # Generate PDF with WeasyPrint
        html = HTML(string=html_content, base_url=str(self.template_dir))
        html.write_pdf(str(output_path))

        logger.info(f"Generated COA preview PDF: {output_path}")
        return str(output_path)

    def _build_context_for_preview(self, db: Session, lot, product) -> Dict[str, Any]:
        """
        Build template context for preview (without COARelease).

        Args:
            db: Database session
            lot: The Lot record
            product: The Product record

        Returns:
            Dictionary with all template variables
        """
        # Get approved test results for this lot
        test_results = (
            db.query(TestResult)
            .filter(
                TestResult.lot_id == lot.id,
                TestResult.status == TestResultStatus.APPROVED
            )
            .order_by(TestResult.test_type)
            .all()
        )

        # Format test results for template
        tests = []
        for result in test_results:
            tests.append({
                "name": result.test_type,
                "result": result.result_value or "N/D",
                "unit": result.unit or "",
                "specification": result.specification or self._get_default_spec(result.test_type),
                "status": self._determine_status(result),
            })

        # Build context
        context = {
            # Company info from settings
            "company_name": settings.company_name,
            "company_address": settings.company_address,
            "company_phone": settings.company_phone,
            "company_email": settings.company_email,

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

            # Notes - empty for preview
            "notes": None,

            # Generation info
            "generated_date": datetime.now().strftime("%B %d, %Y"),
            "released_by": "(Preview)",
        }

        return context


# Singleton instance
coa_generation_service = COAGenerationService()
