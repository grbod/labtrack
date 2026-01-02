"""Utilities for PDF processing and text extraction."""

import hashlib
from pathlib import Path
from typing import List, Optional, Dict, Any
import re

import PyPDF2
import pdfplumber
from PIL import Image
from loguru import logger


def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract text from a PDF file using multiple methods."""
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    text = ""

    # Try pdfplumber first (better for tables)
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"

        if text.strip():
            logger.debug(
                f"Successfully extracted text using pdfplumber from {pdf_path.name}"
            )
            return clean_extracted_text(text)
    except Exception as e:
        logger.warning(f"pdfplumber extraction failed: {e}")

    # Fallback to PyPDF2
    try:
        with open(pdf_path, "rb") as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"

        if text.strip():
            logger.debug(
                f"Successfully extracted text using PyPDF2 from {pdf_path.name}"
            )
            return clean_extracted_text(text)
    except Exception as e:
        logger.error(f"PyPDF2 extraction failed: {e}")

    raise ValueError(f"Failed to extract text from PDF: {pdf_path.name}")


def clean_extracted_text(text: str) -> str:
    """Clean extracted text to improve parsing."""
    # Remove excessive whitespace
    text = re.sub(r"\s+", " ", text)

    # Fix common OCR issues
    text = text.replace("|", "I")  # Common OCR mistake
    text = text.replace("O", "0")  # For numbers

    # Normalize line breaks
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def extract_tables_from_pdf(pdf_path: Path) -> List[Dict[str, Any]]:
    """Extract tables from PDF preserving structure and metadata."""
    tables = []

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                page_tables = page.extract_tables()
                
                for table_idx, table in enumerate(page_tables):
                    if table and len(table) > 1:  # Has headers + data
                        tables.append({
                            'page': page_num + 1,
                            'table_index': table_idx + 1,
                            'headers': [str(cell or '') for cell in table[0]],
                            'rows': [[str(cell or '') for cell in row] for row in table[1:]],
                            'formatted': format_table_for_ai(table)
                        })

        logger.debug(f"Extracted {len(tables)} tables from {pdf_path.name}")
        return tables
    except Exception as e:
        logger.error(f"Failed to extract tables from PDF: {e}")
        return []


def format_table_for_ai(table: List[List[str]]) -> str:
    """Format table for AI comprehension."""
    if not table:
        return ""
    
    lines = []
    headers = [str(cell or '') for cell in table[0]]
    lines.append(" | ".join(headers))
    lines.append("-" * (len(" | ".join(headers))))
    
    for row in table[1:]:
        row_str = " | ".join(str(cell or '') for cell in row)
        lines.append(row_str)
    
    return "\n".join(lines)


def extract_text_with_tables(pdf_path: Path) -> str:
    """Extract text and tables, formatting for AI processing."""
    # Regular text extraction
    text = extract_text_from_pdf(pdf_path)
    
    # Table extraction
    tables = extract_tables_from_pdf(pdf_path)
    
    # Combine text with formatted tables
    if tables:
        text += "\n\n=== EXTRACTED TABLES ===\n"
        for table_info in tables:
            text += f"\nPage {table_info['page']} - Table {table_info['table_index']}:\n"
            text += table_info['formatted']
            text += "\n"
    
    return text


def extract_images_from_pdf(
    pdf_path: Path, output_dir: Optional[Path] = None
) -> List[Path]:
    """Extract images from a PDF file."""
    if output_dir is None:
        output_dir = pdf_path.parent / "extracted_images"

    output_dir.mkdir(exist_ok=True)
    extracted_images = []

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                images = page.images
                for j, img in enumerate(images):
                    image_obj = page.within_bbox(
                        (img["x0"], img["top"], img["x1"], img["bottom"])
                    )
                    image_path = output_dir / f"{pdf_path.stem}_page{i+1}_img{j+1}.png"

                    # Extract and save image
                    im = image_obj.to_image()
                    im.save(image_path, format="PNG")
                    extracted_images.append(image_path)

        logger.debug(f"Extracted {len(extracted_images)} images from {pdf_path.name}")
        return extracted_images
    except Exception as e:
        logger.error(f"Failed to extract images from PDF: {e}")
        return []


def get_pdf_metadata(pdf_path: Path) -> Dict[str, Any]:
    """Extract metadata from a PDF file."""
    metadata = {}

    try:
        with open(pdf_path, "rb") as file:
            pdf_reader = PyPDF2.PdfReader(file)

            # Basic info
            metadata["num_pages"] = len(pdf_reader.pages)
            metadata["is_encrypted"] = pdf_reader.is_encrypted

            # Document info
            if pdf_reader.metadata:
                info = pdf_reader.metadata
                metadata["title"] = info.get("/Title", "")
                metadata["author"] = info.get("/Author", "")
                metadata["subject"] = info.get("/Subject", "")
                metadata["creator"] = info.get("/Creator", "")
                metadata["producer"] = info.get("/Producer", "")
                metadata["creation_date"] = info.get("/CreationDate", "")
                metadata["modification_date"] = info.get("/ModDate", "")

        # File info
        metadata["file_size"] = pdf_path.stat().st_size
        metadata["file_hash"] = calculate_file_hash(pdf_path)

        return metadata
    except Exception as e:
        logger.error(f"Failed to extract PDF metadata: {e}")
        return {}


def calculate_file_hash(file_path: Path, algorithm: str = "sha256") -> str:
    """Calculate hash of a file."""
    hash_func = hashlib.new(algorithm)

    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_func.update(chunk)

    return hash_func.hexdigest()


def validate_pdf(pdf_path: Path) -> bool:
    """Validate that a file is a valid PDF."""
    try:
        with open(pdf_path, "rb") as file:
            # Check PDF header
            header = file.read(5)
            if header != b"%PDF-":
                return False

            # Try to read with PyPDF2
            pdf_reader = PyPDF2.PdfReader(file)
            _ = len(pdf_reader.pages)

        return True
    except Exception as e:
        logger.error(f"PDF validation failed: {e}")
        return False


def search_text_in_pdf(
    pdf_path: Path, search_terms: List[str], case_sensitive: bool = False
) -> Dict[str, List[int]]:
    """Search for text in a PDF and return page numbers where found."""
    results = {term: [] for term in search_terms}

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text()
                if not text:
                    continue

                if not case_sensitive:
                    text = text.lower()

                for term in search_terms:
                    search_term = term if case_sensitive else term.lower()
                    if search_term in text:
                        results[term].append(page_num)

        return results
    except Exception as e:
        logger.error(f"Failed to search PDF: {e}")
        return results


def split_pdf(pdf_path: Path, output_dir: Path, pages_per_file: int = 1) -> List[Path]:
    """Split a PDF into multiple files."""
    output_files = []

    try:
        with open(pdf_path, "rb") as file:
            pdf_reader = PyPDF2.PdfReader(file)
            total_pages = len(pdf_reader.pages)

            for start_page in range(0, total_pages, pages_per_file):
                pdf_writer = PyPDF2.PdfWriter()
                end_page = min(start_page + pages_per_file, total_pages)

                for page_num in range(start_page, end_page):
                    pdf_writer.add_page(pdf_reader.pages[page_num])

                output_path = (
                    output_dir / f"{pdf_path.stem}_pages_{start_page+1}-{end_page}.pdf"
                )
                with open(output_path, "wb") as output_file:
                    pdf_writer.write(output_file)

                output_files.append(output_path)

        logger.info(f"Split {pdf_path.name} into {len(output_files)} files")
        return output_files
    except Exception as e:
        logger.error(f"Failed to split PDF: {e}")
        return []
