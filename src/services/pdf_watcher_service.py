"""Service for watching PDF folders and processing new files."""

import asyncio
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, Set

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent
from sqlalchemy.orm import Session
from loguru import logger

from ..config import settings
from .pdf_parser_service import PDFParserService
from ..utils.pdf_utils import validate_pdf, calculate_file_hash


class PDFHandler(FileSystemEventHandler):
    """Handler for PDF file events."""

    def __init__(self, watcher_service: "PDFWatcherService"):
        self.watcher_service = watcher_service
        self.processing_files: Set[str] = set()

    def on_created(self, event: FileSystemEvent) -> None:
        """Handle new file creation."""
        if event.is_directory:
            return

        file_path = Path(event.src_path)
        if file_path.suffix.lower() == ".pdf":
            # Add a small delay to ensure file is fully written
            asyncio.create_task(self._process_with_delay(file_path))

    async def _process_with_delay(self, file_path: Path, delay: float = 2.0) -> None:
        """Process file after a delay to ensure it's fully written."""
        await asyncio.sleep(delay)

        if file_path.name not in self.processing_files:
            self.processing_files.add(file_path.name)
            try:
                await self.watcher_service.process_pdf(file_path)
            finally:
                self.processing_files.discard(file_path.name)


class PDFWatcherService:
    """Service for watching and processing PDF files."""

    def __init__(self, session: Session, watch_dir: Optional[Path] = None):
        self.session = session
        self.watch_dir = watch_dir or Path(settings.pdf_watch_folder)
        self.processed_dir = self.watch_dir / "processed"
        self.error_dir = self.watch_dir / "error"
        self.parser_service = PDFParserService()
        self.observer: Optional[Observer] = None
        self._processed_hashes: Set[str] = set()

        # Create directories
        self._setup_directories()

    def _setup_directories(self) -> None:
        """Create necessary directories."""
        self.watch_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(exist_ok=True)
        self.error_dir.mkdir(exist_ok=True)

        logger.info(f"PDF watch directory: {self.watch_dir}")
        logger.info(f"Processed directory: {self.processed_dir}")
        logger.info(f"Error directory: {self.error_dir}")

    def start_watching(self) -> None:
        """Start watching for new PDFs."""
        if self.observer and self.observer.is_alive():
            logger.warning("Watcher already running")
            return

        self.observer = Observer()
        event_handler = PDFHandler(self)
        self.observer.schedule(event_handler, str(self.watch_dir), recursive=False)
        self.observer.start()

        logger.info(f"Started watching {self.watch_dir} for new PDFs")

        # Process any existing PDFs
        asyncio.create_task(self._process_existing_pdfs())

    def stop_watching(self) -> None:
        """Stop watching for PDFs."""
        if self.observer and self.observer.is_alive():
            self.observer.stop()
            self.observer.join()
            logger.info("Stopped PDF watcher")

    async def _process_existing_pdfs(self) -> None:
        """Process any PDFs already in the watch folder."""
        pdf_files = list(self.watch_dir.glob("*.pdf"))
        if pdf_files:
            logger.info(f"Found {len(pdf_files)} existing PDFs to process")
            for pdf_file in pdf_files:
                await self.process_pdf(pdf_file)

    async def process_pdf(self, pdf_path: Path) -> None:
        """Process a single PDF file."""
        logger.info(f"Processing PDF: {pdf_path.name}")

        try:
            # Validate PDF
            if not validate_pdf(pdf_path):
                raise ValueError("Invalid PDF file")

            # Check for duplicates
            file_hash = calculate_file_hash(pdf_path)
            if file_hash in self._processed_hashes:
                logger.warning(f"Duplicate PDF detected: {pdf_path.name}")
                self._move_to_processed(pdf_path, duplicate=True)
                return

            # Parse the PDF
            result = await self.parser_service.parse_pdf(pdf_path)

            if result["status"] == "success":
                logger.success(f"Successfully processed {pdf_path.name}")
                self._processed_hashes.add(file_hash)
                self._move_to_processed(pdf_path)
            elif result["status"] == "review_needed":
                logger.warning(f"Manual review needed for {pdf_path.name}")
                # Keep in watch folder for manual processing
            else:
                logger.error(
                    f"Failed to process {pdf_path.name}: {result.get('error')}"
                )
                self._move_to_error(pdf_path)

        except Exception as e:
            logger.error(f"Error processing {pdf_path.name}: {e}")
            self._move_to_error(pdf_path)

    def _move_to_processed(self, pdf_path: Path, duplicate: bool = False) -> None:
        """Move PDF to processed directory."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            suffix = "_DUP" if duplicate else ""
            new_name = f"{timestamp}_{pdf_path.stem}{suffix}{pdf_path.suffix}"
            dest_path = self.processed_dir / new_name

            shutil.move(str(pdf_path), str(dest_path))
            logger.debug(f"Moved {pdf_path.name} to processed directory")
        except Exception as e:
            logger.error(f"Failed to move PDF to processed: {e}")

    def _move_to_error(self, pdf_path: Path) -> None:
        """Move PDF to error directory."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            new_name = f"{timestamp}_{pdf_path.name}"
            dest_path = self.error_dir / new_name

            shutil.move(str(pdf_path), str(dest_path))
            logger.debug(f"Moved {pdf_path.name} to error directory")
        except Exception as e:
            logger.error(f"Failed to move PDF to error: {e}")

    def get_status(self) -> dict:
        """Get watcher status."""
        return {
            "watching": self.observer and self.observer.is_alive(),
            "watch_directory": str(self.watch_dir),
            "pending_pdfs": len(list(self.watch_dir.glob("*.pdf"))),
            "processed_count": len(self._processed_hashes),
            "error_count": len(list(self.error_dir.glob("*.pdf"))),
        }

    def reprocess_errors(self) -> int:
        """Move error PDFs back to watch folder for reprocessing."""
        error_pdfs = list(self.error_dir.glob("*.pdf"))
        count = 0

        for pdf_path in error_pdfs:
            try:
                # Remove timestamp prefix
                original_name = "_".join(pdf_path.name.split("_")[2:])
                dest_path = self.watch_dir / original_name

                shutil.move(str(pdf_path), str(dest_path))
                count += 1
                logger.info(f"Moved {pdf_path.name} back to watch folder")
            except Exception as e:
                logger.error(f"Failed to reprocess {pdf_path.name}: {e}")

        return count
