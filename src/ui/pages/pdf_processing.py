"""PDF processing page for COA Management System."""

import streamlit as st
from sqlalchemy.orm import Session
import pandas as pd
from pathlib import Path
import asyncio
from datetime import datetime
from streamlit_pdf_viewer import pdf_viewer

from src.services.pdf_parser_service import PDFParserService
from src.services.pdf_watcher_service import PDFWatcherService
from src.models import ParsingQueue, ParsingStatus
from src.config import settings


def show(db: Session):
    """Display the PDF processing page."""
    st.title("📄 PDF Processing")

    # Initialize services
    parser_service = PDFParserService()
    watcher_service = PDFWatcherService(db)

    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs(
        ["Upload PDF", "Processing Queue", "Folder Monitoring", "Parsing History"]
    )

    with tab1:
        upload_pdf(db, parser_service)

    with tab2:
        show_processing_queue(db, parser_service)

    with tab3:
        folder_monitoring(db, watcher_service)

    with tab4:
        parsing_history(db)


def upload_pdf(db: Session, parser_service: PDFParserService):
    """Manual PDF upload interface."""
    st.subheader("Upload Lab PDF")

    uploaded_file = st.file_uploader(
        "Choose a PDF file",
        type=["pdf"],
        help="Upload a lab test report PDF for parsing",
    )

    if uploaded_file:
        # File info
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("File Name", uploaded_file.name)
        with col2:
            st.metric("File Size", f"{uploaded_file.size / 1024:.1f} KB")
        with col3:
            st.metric("Type", "PDF Document")

        # Parse button
        if st.button("🔍 Parse PDF", type="primary", use_container_width=True):
            with st.spinner("Parsing PDF... This may take a moment."):
                try:
                    # Save uploaded file temporarily
                    temp_path = Path(f"/tmp/{uploaded_file.name}")
                    with open(temp_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())

                    # Parse the PDF
                    result = asyncio.run(parser_service.parse_pdf(db, temp_path))

                    # Show results
                    if result["status"] == "success":
                        st.success("✅ PDF parsed successfully!")

                        # Create two-column layout for PDF preview and parsed results
                        st.divider()
                        st.subheader("PDF Comparison")
                        
                        pdf_col, results_col = st.columns([1, 1])
                        
                        with pdf_col:
                            st.write("### 📄 Original PDF")
                            # Display the PDF using streamlit-pdf-viewer
                            # Read the uploaded file content for PDF viewer
                            pdf_content = uploaded_file.read()
                            uploaded_file.seek(0)  # Reset the file pointer
                            pdf_viewer(pdf_content)
                        
                        with results_col:
                            st.write("### 📊 Parsed Results")
                            
                            # Display extracted data
                            data = result["data"]
                            
                            # Basic Information
                            st.write("**Basic Information:**")
                            info_col1, info_col2 = st.columns(2)
                            
                            with info_col1:
                                st.write(f"📌 Reference Number: `{data.get('reference_number', 'N/A')}`")
                                st.write(f"📦 Lot Number: `{data.get('lot_number', 'N/A')}`")
                            
                            with info_col2:
                                st.write(f"📅 Test Date: `{data.get('test_date', 'N/A')}`")
                                st.write(f"🏢 Lab: `{data.get('lab_name', 'N/A')}`")
                            
                            # Confidence Score
                            st.write("")  # Add spacing
                            st.write(f"**Confidence Score: {result['confidence']:.1%}**")
                            if result["confidence"] >= 0.7:
                                st.progress(result["confidence"], text="High confidence")
                            else:
                                st.progress(
                                    result["confidence"],
                                    text="Low confidence - Manual review recommended",
                                )
                            
                            # Show any warnings from extraction
                            metadata = data.get("_extraction_metadata", {})
                            if metadata.get("warnings"):
                                st.warning("⚠️ **Extraction Warnings:**")
                                for warning in metadata["warnings"]:
                                    st.write(f"- {warning}")
                            
                            # Show test results
                            st.write("")  # Add spacing
                            st.write("**Test Results:**")
                            
                            test_results = data.get("test_results", {})
                            if test_results:
                                results_data = []
                                for test_name, test_data in test_results.items():
                                    results_data.append(
                                        {
                                            "Test": test_name,
                                            "Value": test_data["value"],
                                            "Unit": test_data.get("unit", ""),
                                            "Spec": test_data.get("specification", ""),
                                            "Status": test_data.get("status", ""),
                                            "Confidence": f"{test_data.get('confidence', 0):.1%}",
                                        }
                                    )
                                
                                df = pd.DataFrame(results_data)
                                st.dataframe(df, use_container_width=True, hide_index=True)

                    elif result["status"] == "review_needed":
                        st.warning("⚠️ PDF parsed but requires manual review")
                        
                        # Create two-column layout for PDF preview and issues
                        st.divider()
                        st.subheader("PDF Review")
                        
                        pdf_col, issues_col = st.columns([1, 1])
                        
                        with pdf_col:
                            st.write("### 📄 Original PDF")
                            # Display the PDF using streamlit-pdf-viewer
                            pdf_content = uploaded_file.read()
                            uploaded_file.seek(0)  # Reset the file pointer
                            pdf_viewer(pdf_content)
                        
                        with issues_col:
                            st.write("### ⚠️ Review Required")
                            
                            # Show specific issues
                            data = result.get("data", {})
                            metadata = data.get("_extraction_metadata", {})
                            
                            if metadata.get("errors"):
                                st.error("🔍 **Issues Found:**")
                                for error in metadata["errors"]:
                                    st.write(f"- {error}")
                            
                            if metadata.get("warnings"):
                                st.info("💡 **Warnings:**")
                                for warning in metadata["warnings"]:
                                    st.write(f"- {warning}")
                            
                            st.info(
                                f"Queue ID: {result['queue_id']} - Please check the Manual Review Queue"
                            )

                    else:
                        st.error(
                            f"❌ Failed to parse PDF: {result.get('error', 'Unknown error')}"
                        )
                        
                        # Create two-column layout for PDF preview and error details
                        st.divider()
                        st.subheader("PDF Error Details")
                        
                        pdf_col, error_col = st.columns([1, 1])
                        
                        with pdf_col:
                            st.write("### 📄 Original PDF")
                            # Display the PDF using streamlit-pdf-viewer
                            pdf_content = uploaded_file.read()
                            uploaded_file.seek(0)  # Reset the file pointer
                            pdf_viewer(pdf_content)
                        
                        with error_col:
                            st.write("### ❌ Error Details")
                            
                            # Show detailed error info if available
                            if "data" in result:
                                data = result.get("data", {})
                                metadata = data.get("_extraction_metadata", {})
                                errors = metadata.get("errors", [])
                                
                                if errors:
                                    st.error("**Specific Errors:**")
                                    for error in errors:
                                        st.write(f"- {error}")
                            
                            # Show the main error message
                            st.error(f"**Main Error:** {result.get('error', 'Unknown error')}")

                    # Clean up temp file
                    temp_path.unlink(missing_ok=True)

                except Exception as e:
                    st.error(f"Error processing PDF: {str(e)}")


def show_processing_queue(db: Session, parser_service: PDFParserService):
    """Show current processing queue."""
    st.subheader("Processing Queue")

    # Get queue entries
    queue_entries = (
        db.query(ParsingQueue).order_by(ParsingQueue.created_at.desc()).limit(50).all()
    )

    if queue_entries:
        # Status filter
        status_filter = st.selectbox(
            "Filter by Status", options=["All"] + [s.value for s in ParsingStatus]
        )

        # Filter entries
        if status_filter != "All":
            filtered_entries = [
                e for e in queue_entries if e.status.value == status_filter
            ]
        else:
            filtered_entries = queue_entries

        # Display queue
        queue_data = []
        for entry in filtered_entries:
            queue_data.append(
                {
                    "ID": entry.id,
                    "PDF File": entry.pdf_filename,
                    "Reference #": entry.reference_number or "-",
                    "Status": entry.status.value,
                    "Confidence": (
                        f"{entry.confidence_score:.1%}"
                        if entry.confidence_score
                        else "-"
                    ),
                    "Created": entry.created_at.strftime("%Y-%m-%d %H:%M"),
                    "Assigned To": entry.assigned_to or "-",
                }
            )

        df = pd.DataFrame(queue_data)

        # Color code by status
        def highlight_status(row):
            colors = {
                "pending": "background-color: #FFE5B4",
                "processing": "background-color: #B4E5FF",
                "resolved": "background-color: #B4FFB4",
                "failed": "background-color: #FFB4B4",
            }
            return [colors.get(row["Status"], "")] * len(row)

        styled_df = df.style.apply(highlight_status, axis=1)
        st.dataframe(styled_df, use_container_width=True, hide_index=True)

        # Actions
        col1, col2 = st.columns(2)

        with col1:
            if st.button("🔄 Refresh Queue"):
                st.rerun()

        with col2:
            if st.button("♻️ Reprocess Failed"):
                failed_count = (
                    db.query(ParsingQueue)
                    .filter_by(status=ParsingStatus.FAILED)
                    .update({"status": ParsingStatus.PENDING})
                )
                db.commit()
                st.success(f"Queued {failed_count} items for reprocessing")
                st.rerun()

    else:
        st.info("No items in the processing queue")


def folder_monitoring(db: Session, watcher_service: PDFWatcherService):
    """Configure and monitor PDF folder watching."""
    st.subheader("Folder Monitoring")

    # Get current status
    status = watcher_service.get_status()

    # Status display
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if status["watching"]:
            st.metric("Status", "🟢 Active", "Watching for PDFs")
        else:
            st.metric("Status", "🔴 Inactive", "Not watching")

    with col2:
        st.metric("Watch Folder", status["watch_directory"].split("/")[-1])

    with col3:
        st.metric("Pending PDFs", status["pending_pdfs"])

    with col4:
        st.metric("Processed", status["processed_count"])

    st.divider()

    # Controls
    col1, col2, col3 = st.columns(3)

    with col1:
        if not status["watching"]:
            if st.button(
                "▶️ Start Monitoring", type="primary", use_container_width=True
            ):
                watcher_service.start_watching()
                st.success("Started monitoring folder")
                st.rerun()
        else:
            if st.button(
                "⏹️ Stop Monitoring", type="secondary", use_container_width=True
            ):
                watcher_service.stop_watching()
                st.info("Stopped monitoring")
                st.rerun()

    with col2:
        if st.button("📁 Open Folder", use_container_width=True):
            # This would open the folder in the OS file explorer
            st.info(f"Watch folder: {status['watch_directory']}")

    with col3:
        if status["error_count"] > 0:
            if st.button(
                f"♻️ Retry Errors ({status['error_count']})", use_container_width=True
            ):
                count = watcher_service.reprocess_errors()
                st.success(f"Moved {count} PDFs back to watch folder")
                st.rerun()

    # Folder structure info
    with st.expander("📂 Folder Structure"):
        st.write(
            f"""
        **Watch Folder:** `{status['watch_directory']}`
        - Drop PDF files here for automatic processing
        
        **Processed Folder:** `{status['watch_directory']}/processed`
        - Successfully processed PDFs are moved here
        
        **Error Folder:** `{status['watch_directory']}/error`
        - PDFs that failed processing are moved here
        """
        )


def parsing_history(db: Session):
    """Show parsing history and statistics."""
    st.subheader("Parsing History")

    # Date range filter
    col1, col2 = st.columns(2)

    with col1:
        start_date = st.date_input(
            "From Date", value=datetime.now().date().replace(day=1)
        )

    with col2:
        end_date = st.date_input("To Date", value=datetime.now().date())

    # Get history
    history = (
        db.query(ParsingQueue)
        .filter(
            ParsingQueue.created_at >= start_date,
            ParsingQueue.created_at <= datetime.combine(end_date, datetime.max.time()),
        )
        .order_by(ParsingQueue.created_at.desc())
        .all()
    )

    if history:
        # Statistics
        st.write("**Statistics:**")

        col1, col2, col3, col4 = st.columns(4)

        total = len(history)
        resolved = len([h for h in history if h.status == ParsingStatus.RESOLVED])
        failed = len([h for h in history if h.status == ParsingStatus.FAILED])
        avg_confidence = sum(
            h.confidence_score or 0 for h in history if h.confidence_score
        ) / max(1, len([h for h in history if h.confidence_score]))

        with col1:
            st.metric("Total Parsed", total)

        with col2:
            st.metric("Success Rate", f"{resolved/max(1, total):.1%}")

        with col3:
            st.metric("Failed", failed)

        with col4:
            st.metric("Avg Confidence", f"{avg_confidence:.1%}")

        # Chart
        st.write("**Daily Parsing Volume:**")

        # Group by date
        daily_counts = {}
        for h in history:
            date_key = h.created_at.date()
            if date_key not in daily_counts:
                daily_counts[date_key] = {"success": 0, "failed": 0}

            if h.status == ParsingStatus.RESOLVED:
                daily_counts[date_key]["success"] += 1
            elif h.status == ParsingStatus.FAILED:
                daily_counts[date_key]["failed"] += 1

        # Create chart data
        chart_data = []
        for date, counts in sorted(daily_counts.items()):
            chart_data.append(
                {"Date": date, "Success": counts["success"], "Failed": counts["failed"]}
            )

        if chart_data:
            df = pd.DataFrame(chart_data)
            st.bar_chart(df.set_index("Date"))

        # Export option
        if st.button("Export History"):
            export_data = []
            for h in history:
                export_data.append(
                    {
                        "Date": h.created_at.strftime("%Y-%m-%d %H:%M"),
                        "PDF File": h.pdf_filename,
                        "Reference Number": h.reference_number,
                        "Status": h.status.value,
                        "Confidence": (
                            f"{h.confidence_score:.1%}" if h.confidence_score else "-"
                        ),
                        "Error": h.error_message or "-",
                    }
                )

            export_df = pd.DataFrame(export_data)
            excel_data = export_df.to_excel(index=False)

            st.download_button(
                label="Download Excel",
                data=excel_data,
                file_name=f"parsing_history_{start_date}_{end_date}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

    else:
        st.info("No parsing history found for the selected date range")
