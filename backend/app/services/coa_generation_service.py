"""COA PDF generation service using ReportLab (pure Python, no system dependencies).

The render context is built by the canonical ``coa_context_builder`` — the same
builder that feeds the on-screen preview — so the PDF and the preview can never
drift. This service is responsible only for turning a ``COAContext`` into a PDF
(and the legacy HTML preview).
"""

import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from xml.sax.saxutils import escape as xml_escape

from jinja2 import Environment, FileSystemLoader
from loguru import logger
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy.orm import Session

from app.config import settings
from app.models.coa_release import COARelease
from app.services.coa_context_builder import COAContext, build_context
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
            autoescape=True,
        )

    def generate(self, db: Session, coa_release_id: int) -> str:
        """
        Generate a COA PDF for a given COARelease using ReportLab.

        Returns the storage key for the generated PDF file.
        """
        coa_release = self._get_coa_release(db, coa_release_id)
        if not coa_release:
            raise ValueError(f"COARelease with id {coa_release_id} not found")

        context = self._build_context(
            db, coa_release.lot, coa_release.product, coa_release
        )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"COA_{coa_release.lot.lot_number}_{timestamp}.pdf"
        storage_key = f"coas/{filename}"

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
            tmp_path = tmp_file.name

        try:
            self._generate_pdf_reportlab(context, tmp_path)
            with open(tmp_path, "rb") as f:
                pdf_content = f.read()
            storage = get_storage_service()
            storage.upload(pdf_content, storage_key, content_type="application/pdf")
        finally:
            import os

            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

        coa_release.coa_file_path = storage_key
        db.commit()

        logger.info(f"Generated COA PDF: {storage_key}")
        return storage_key

    def get_preview_data(self, db: Session, coa_release_id: int) -> Dict[str, Any]:
        """Get the render context as a JSON-serialisable dict (for preview)."""
        coa_release = self._get_coa_release(db, coa_release_id)
        if not coa_release:
            raise ValueError(f"COARelease with id {coa_release_id} not found")

        context = self._build_context(
            db, coa_release.lot, coa_release.product, coa_release
        )
        return context.model_dump()

    def get_or_generate_pdf(self, db: Session, coa_release_id: int) -> str:
        """Get existing PDF storage key or generate a new one if needed."""
        coa_release = self._get_coa_release(db, coa_release_id)
        if not coa_release:
            raise ValueError(f"COARelease with id {coa_release_id} not found")

        if coa_release.coa_file_path:
            storage = get_storage_service()
            if storage.exists(coa_release.coa_file_path):
                return coa_release.coa_file_path

        return self.generate(db, coa_release_id)

    def get_pdf_url(self, db: Session, coa_release_id: int) -> str:
        """Get a URL for downloading the COA PDF."""
        storage_key = self.get_or_generate_pdf(db, coa_release_id)
        storage = get_storage_service()
        return storage.get_presigned_url(storage_key)

    def _get_coa_release(
        self, db: Session, coa_release_id: int
    ) -> Optional[COARelease]:
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
        coa_release: Optional[COARelease] = None,
    ) -> COAContext:
        """Build the canonical COA render context (delegates to the shared builder)."""
        return build_context(db, lot.id, product.id, release=coa_release)

    def render_html_preview(self, db: Session, coa_release_id: int) -> str:
        """Render the COA as HTML (legacy browser preview)."""
        coa_release = self._get_coa_release(db, coa_release_id)
        if not coa_release:
            raise ValueError(f"COARelease with id {coa_release_id} not found")

        context = self._build_context(
            db, coa_release.lot, coa_release.product, coa_release
        )
        template = self.env.get_template("coa_template.html")
        return template.render(**self._context_to_template_dict(context))

    def generate_preview(self, db: Session, lot_id: int, product_id: int) -> str:
        """Generate a preview PDF for a lot+product pair without a COARelease record."""
        from app.models import Lot, Product

        lot = db.query(Lot).filter(Lot.id == lot_id).first()
        if not lot:
            raise ValueError(f"Lot with id {lot_id} not found")

        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise ValueError(f"Product with id {product_id} not found")

        context = self._build_context(db, lot, product)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"COA_preview_{lot.lot_number}_{timestamp}.pdf"
        storage_key = f"coas/{filename}"

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
            tmp_path = tmp_file.name

        try:
            self._generate_pdf_reportlab(context, tmp_path)
            with open(tmp_path, "rb") as f:
                pdf_content = f.read()
            storage = get_storage_service()
            storage.upload(pdf_content, storage_key, content_type="application/pdf")
        finally:
            import os

            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

        logger.info(f"Generated COA preview PDF: {storage_key}")
        return storage_key

    # ------------------------------------------------------------------
    # Adapters
    # ------------------------------------------------------------------
    @staticmethod
    def _context_to_template_dict(context: COAContext) -> Dict[str, Any]:
        """Flatten a COAContext into the variables the legacy jinja template expects."""
        tests = [
            {
                "name": row.name,
                "result": row.result_value,
                "unit": row.unit or "",
                # Missing spec renders as an em dash rather than a fabricated limit.
                "specification": row.spec_text or "—",
                "status": row.status_display,
            }
            for row in context.test_rows
        ]
        # Surface not-tested rows in the same table so the HTML preview does not
        # look complete when it isn't.
        for row in context.not_tested_rows:
            tests.append(
                {
                    "name": row.name,
                    "result": "Not Tested",
                    "unit": "",
                    "specification": row.spec_text or "—",
                    "status": row.status_display,
                }
            )
        return {
            "company_name": context.lab.company_name,
            "company_address": context.lab.address,
            "company_logo_url": context.lab.logo_url,
            "product_name": context.product.product_name,
            "brand": context.product.brand,
            "lot_number": context.lot.lot_number,
            "reference_number": context.lot.reference_number,
            "mfg_date": context.lot.mfg_date,
            "exp_date": context.lot.exp_date,
            "tests": tests,
            "notes": context.notes,
            "generated_date": context.document.generated_date,
            "released_at": context.document.release_date,
            "released_by": context.approver.name,
            "released_by_title": context.approver.title,
            "released_by_email": context.approver.email,
            "signature_url": context.approver.signature_url,
        }

    # ------------------------------------------------------------------
    # PDF rendering
    # ------------------------------------------------------------------
    @staticmethod
    def _status_color(status: str) -> str:
        lowered = (status or "").lower()
        if lowered == "pass":
            return "#16a34a"
        if lowered == "fail":
            return "#dc2626"
        return "#64748b"  # neutral for "—" / "Not Tested"

    def _generate_pdf_reportlab(self, context: COAContext, output_path: str) -> None:
        """Generate the COA PDF from a canonical COAContext."""
        document_id = context.document.document_id

        def _draw_footer(canvas, doc):
            canvas.saveState()
            canvas.setFont("Helvetica", 8)
            canvas.setFillColor(colors.grey)
            page_num = canvas.getPageNumber()
            total = getattr(canvas, "_coa_total_pages", None)
            if total:
                text = f"Page {page_num} of {total} — {document_id}"
            else:
                text = f"Page {page_num} — {document_id}"
            canvas.drawCentredString(letter[0] / 2.0, 0.3 * inch, text)
            canvas.restoreState()

        # Two-pass build so we can print "Page X of Y".
        class _NumberedDocTemplate(SimpleDocTemplate):
            def build(self, flowables, **kwargs):  # type: ignore[override]
                from copy import deepcopy

                counter = {"pages": 0}

                def _count(canvas, doc):
                    counter["pages"] = canvas.getPageNumber()

                probe = deepcopy(flowables)
                super().build(probe, onFirstPage=_count, onLaterPages=_count)
                total_pages = counter["pages"]

                def _footer_with_total(canvas, doc):
                    canvas._coa_total_pages = total_pages
                    _draw_footer(canvas, doc)

                super().build(
                    flowables,
                    onFirstPage=_footer_with_total,
                    onLaterPages=_footer_with_total,
                )

        doc = _NumberedDocTemplate(
            output_path,
            pagesize=letter,
            rightMargin=0.5 * inch,
            leftMargin=0.5 * inch,
            topMargin=0.5 * inch,
            bottomMargin=0.6 * inch,
        )

        styles = getSampleStyleSheet()
        styles.add(
            ParagraphStyle(
                name="COAHeader",
                parent=styles["Heading2"],
                fontSize=11,
                textColor=colors.HexColor("#0f172a"),
                alignment=TA_LEFT,
                spaceBefore=12,
                spaceAfter=6,
            )
        )
        styles.add(
            ParagraphStyle(
                name="COANormal",
                parent=styles["Normal"],
                fontSize=9,
                alignment=TA_LEFT,
                leading=11,
            )
        )
        styles.add(
            ParagraphStyle(
                name="COAFooter",
                parent=styles["Normal"],
                fontSize=8,
                alignment=TA_CENTER,
                textColor=colors.grey,
            )
        )
        styles.add(
            ParagraphStyle(
                name="COADocTitle",
                parent=styles["Normal"],
                fontSize=14,
                fontName="Helvetica-Bold",
                textColor=colors.HexColor("#0f172a"),
                alignment=TA_RIGHT,
                spaceAfter=4,
            )
        )
        styles.add(
            ParagraphStyle(
                name="COADocMeta",
                parent=styles["Normal"],
                fontSize=9,
                textColor=colors.HexColor("#64748b"),
                alignment=TA_RIGHT,
                leading=11,
            )
        )
        styles.add(
            ParagraphStyle(
                name="COACompanyName",
                parent=styles["Normal"],
                fontSize=9,
                fontName="Helvetica-Bold",
                textColor=colors.HexColor("#64748b"),
                leading=11,
            )
        )
        styles.add(
            ParagraphStyle(
                name="COACompanyInfo",
                parent=styles["Normal"],
                fontSize=9,
                textColor=colors.HexColor("#64748b"),
                leading=11,
            )
        )

        wrap_style = ParagraphStyle(
            name="COAWrap",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=11,
            alignment=TA_LEFT,
            wordWrap="CJK",
            splitLongWords=1,
        )
        wrap_style_small = ParagraphStyle(
            name="COAWrapSmall",
            parent=wrap_style,
            fontSize=8,
            leading=10,
        )
        label_value_style = ParagraphStyle(
            name="COALabelValue",
            parent=styles["Normal"],
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#0f172a"),
        )

        def wrap_cell(value: Any, style: ParagraphStyle) -> Paragraph:
            text = "" if value is None else str(value)
            return Paragraph(xml_escape(text), style)

        def stacked_label_value(label: str, value: Any) -> Paragraph:
            safe_value = "" if value is None else str(value)
            return Paragraph(
                f"<font size='8' color='#64748b'><b>{xml_escape(label.upper())}</b></font>"
                f"<br/><font size='10' color='#0f172a'>{xml_escape(safe_value)}</font>",
                label_value_style,
            )

        story = []

        # --- Header: company block + document block ---
        company_blocks = []
        logo_full = None
        if context.lab.logo_path:
            import os

            candidate = os.path.join(settings.upload_path, context.lab.logo_path)
            if os.path.exists(candidate):
                logo_full = candidate
        if logo_full:
            try:
                from PIL import Image as PILImage

                with PILImage.open(logo_full) as pil_img:
                    aspect = pil_img.width / pil_img.height
                max_height = 0.6 * inch
                max_width = 2.2 * inch
                logo_width = min(max_width, max_height * aspect)
                logo_height = logo_width / aspect
                if logo_height > max_height:
                    logo_height = max_height
                    logo_width = logo_height * aspect
                logo_img = Image(logo_full, width=logo_width, height=logo_height)
                logo_img.hAlign = "LEFT"
                company_blocks.append(logo_img)
                company_blocks.append(Spacer(1, 0.06 * inch))
            except Exception:
                pass

        company_blocks.append(
            Paragraph(
                xml_escape(context.lab.company_name or "Company Name"),
                styles["COACompanyName"],
            )
        )
        if context.lab.address:
            company_blocks.append(
                Paragraph(xml_escape(context.lab.address), styles["COACompanyInfo"])
            )
        contact_parts = []
        if context.lab.phone:
            contact_parts.append(f"Tel: {context.lab.phone}")
        if context.lab.email:
            contact_parts.append(f"Email: {context.lab.email}")
        if contact_parts:
            company_blocks.append(
                Paragraph(
                    xml_escape(" | ".join(contact_parts)), styles["COACompanyInfo"]
                )
            )

        doc_blocks = [
            Paragraph("CERTIFICATE OF ANALYSIS", styles["COADocTitle"]),
            Paragraph(f"Document #: {xml_escape(document_id)}", styles["COADocMeta"]),
            Paragraph(
                f"Generated: {xml_escape(context.document.generated_date)}",
                styles["COADocMeta"],
            ),
        ]

        header_table = Table(
            [[company_blocks, doc_blocks]], colWidths=[4.6 * inch, 2.9 * inch]
        )
        header_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LINEBELOW", (0, 0), (-1, 0), 1, colors.HexColor("#1e293b")),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                ]
            )
        )
        story.append(header_table)
        story.append(Spacer(1, 0.15 * inch))

        # --- Product information ---
        story.append(Paragraph("PRODUCT INFORMATION", styles["COAHeader"]))
        product_rows = [
            [
                stacked_label_value("Product Name", context.product.product_name),
                stacked_label_value("Brand", context.product.brand or "N/A"),
            ],
            [
                stacked_label_value("Lot Number", context.lot.lot_number),
                stacked_label_value("Reference Number", context.lot.reference_number),
            ],
            [
                stacked_label_value(
                    "Manufacturing Date", context.lot.mfg_date or "Not set"
                ),
                stacked_label_value(
                    "Expiration Date", context.lot.exp_date or "Not set"
                ),
            ],
        ]
        if context.lot.component_batch_number:
            product_rows.append(
                [
                    stacked_label_value(
                        "Component Batch", context.lot.component_batch_number
                    ),
                    stacked_label_value("", ""),
                ]
            )
        product_table = Table(product_rows, colWidths=[3.75 * inch, 3.75 * inch])
        product_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 12),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                    ("TOPPADDING", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ]
            )
        )
        story.append(product_table)
        story.append(Spacer(1, 0.15 * inch))

        # --- Deviation note (release-gate override) ---
        if context.document.deviation_note:
            story.append(Paragraph("DEVIATION", styles["COAHeader"]))
            dev_table = Table(
                [[wrap_cell(context.document.deviation_note, wrap_style)]],
                colWidths=[7.5 * inch],
            )
            dev_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fef2f2")),
                        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#f87171")),
                        ("FONTSIZE", (0, 0), (-1, -1), 9),
                        ("TOPPADDING", (0, 0), (-1, -1), 8),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                        ("LEFTPADDING", (0, 0), (-1, -1), 8),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ]
                )
            )
            story.append(dev_table)
            story.append(Spacer(1, 0.15 * inch))

        # --- Test results ---
        story.append(Paragraph("TEST RESULTS", styles["COAHeader"]))
        col_widths = [1.9 * inch, 1.3 * inch, 1.4 * inch, 1.6 * inch, 1.3 * inch]
        table_data = [["TEST NAME", "METHOD", "RESULT", "SPECIFICATION", "STATUS"]]

        has_rows = bool(context.test_rows) or bool(context.not_tested_rows)
        for row in context.test_rows:
            result_text = row.result_value
            if row.unit:
                result_text = f"{row.result_value} {row.unit}"
            status_color = self._status_color(row.status_display)
            table_data.append(
                [
                    wrap_cell(row.name, wrap_style_small),
                    wrap_cell(row.method or "—", wrap_style_small),
                    wrap_cell(result_text, wrap_style_small),
                    wrap_cell(row.spec_text or "—", wrap_style_small),
                    Paragraph(
                        f"<font color='{status_color}'>{xml_escape(row.status_display)}</font>",
                        wrap_style_small,
                    ),
                ]
            )
        for row in context.not_tested_rows:
            status_color = self._status_color(row.status_display)
            table_data.append(
                [
                    wrap_cell(row.name, wrap_style_small),
                    wrap_cell(row.method or "—", wrap_style_small),
                    wrap_cell("Not Tested", wrap_style_small),
                    wrap_cell(row.spec_text or "—", wrap_style_small),
                    Paragraph(
                        f"<font color='{status_color}'>{xml_escape(row.status_display)}</font>",
                        wrap_style_small,
                    ),
                ]
            )

        if has_rows:
            test_table = Table(table_data, colWidths=col_widths)
            test_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#475569")),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, 0), 8),
                        ("ALIGN", (0, 0), (-1, 0), "LEFT"),
                        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                        ("FONTSIZE", (0, 1), (-1, -1), 8),
                        ("TEXTCOLOR", (0, 1), (-1, -1), colors.HexColor("#0f172a")),
                        ("ALIGN", (0, 1), (-1, -1), "LEFT"),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                        ("LINEBELOW", (0, 0), (-1, 0), 1, colors.HexColor("#e2e8f0")),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                        (
                            "ROWBACKGROUNDS",
                            (0, 1),
                            (-1, -1),
                            [colors.white, colors.HexColor("#f8f9fa")],
                        ),
                    ]
                )
            )
            story.append(test_table)
        else:
            story.append(Paragraph("No test results available.", styles["COANormal"]))
        story.append(Spacer(1, 0.15 * inch))

        # --- Notes ---
        notes = context.notes
        if (
            notes
            and str(notes).strip()
            and str(notes).strip().lower() != "click to add notes..."
        ):
            story.append(Paragraph("NOTES", styles["COAHeader"]))
            notes_table = Table(
                [[wrap_cell(notes, wrap_style)]], colWidths=[7.5 * inch]
            )
            notes_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fffbeb")),
                        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#fbbf24")),
                        ("FONTSIZE", (0, 0), (-1, -1), 9),
                        ("TOPPADDING", (0, 0), (-1, -1), 8),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                        ("LEFTPADDING", (0, 0), (-1, -1), 8),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ]
                )
            )
            story.append(notes_table)
            story.append(Spacer(1, 0.15 * inch))

        # --- Authorization (approver strictly from the release record) ---
        story.append(Paragraph("AUTHORIZATION", styles["COAHeader"]))
        approver = context.approver
        signature_path = approver.signature_path
        if signature_path:
            from PIL import Image as PILImage

            full_path = Path(settings.upload_path) / signature_path
            if full_path.exists():
                try:
                    with PILImage.open(full_path) as pil_img:
                        aspect = pil_img.width / pil_img.height
                    sig_height = 0.5 * inch
                    sig_width = sig_height * aspect
                    if sig_width > 2 * inch:
                        sig_width = 2 * inch
                        sig_height = sig_width / aspect
                    sig_img = Image(str(full_path), width=sig_width, height=sig_height)
                    sig_img.hAlign = "LEFT"
                    story.append(sig_img)
                    story.append(Spacer(1, 0.05 * inch))
                except Exception:
                    pass

        # Name line always renders (may be empty for a pre-release preview).
        story.append(
            Paragraph(
                xml_escape(approver.name or ""),
                ParagraphStyle(
                    "SignerName",
                    parent=styles["Normal"],
                    fontSize=10,
                    fontName="Helvetica-Bold",
                ),
            )
        )
        if approver.title:
            story.append(
                Paragraph(
                    xml_escape(approver.title),
                    ParagraphStyle(
                        "SignerTitle",
                        parent=styles["Normal"],
                        fontSize=9,
                        textColor=colors.HexColor("#475569"),
                    ),
                )
            )
        if approver.email:
            story.append(
                Paragraph(
                    f"Email: {xml_escape(approver.email)}",
                    ParagraphStyle(
                        "SignerEmail",
                        parent=styles["Normal"],
                        fontSize=9,
                        textColor=colors.HexColor("#475569"),
                    ),
                )
            )
        release_date = context.document.release_date or context.document.generated_date
        story.append(
            Paragraph(
                f"Date: {xml_escape(release_date)}",
                ParagraphStyle(
                    "SignerDate",
                    parent=styles["Normal"],
                    fontSize=9,
                    textColor=colors.HexColor("#475569"),
                ),
            )
        )
        story.append(Spacer(1, 0.2 * inch))

        # --- Disclaimer ---
        disclaimer = (
            "This Certificate of Analysis is issued based on the test results of a "
            "representative sample. Results apply only to the lot specified above."
        )
        disclaimer_table = Table(
            [[Paragraph(xml_escape(disclaimer), styles["COAFooter"])]],
            colWidths=[7.5 * inch],
        )
        disclaimer_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        story.append(disclaimer_table)

        # --- Accreditation footer (only when populated) ---
        acc_body = getattr(context.lab, "accreditation_body", None)
        acc_number = getattr(context.lab, "accreditation_number", None)
        acc_statement = getattr(context.lab, "accreditation_statement", None)
        acc_line_parts = []
        if acc_body:
            acc_line_parts.append(f"{acc_body} Accredited")
        if acc_number:
            acc_line_parts.append(f"Cert #{acc_number}")
        if acc_line_parts or (acc_statement and acc_statement.strip()):
            story.append(Spacer(1, 0.1 * inch))
            acc_style = ParagraphStyle(
                "COAAccreditation",
                parent=styles["COAFooter"],
                fontSize=7.5,
            )
            if acc_line_parts:
                story.append(
                    Paragraph(xml_escape("  •  ".join(acc_line_parts)), acc_style)
                )
            if acc_statement and acc_statement.strip():
                story.append(Paragraph(xml_escape(acc_statement.strip()), acc_style))

        doc.build(story)


# Singleton instance
coa_generation_service = COAGenerationService()
