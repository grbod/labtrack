"""Manual review queue page for failed PDF parsing."""

import streamlit as st
from sqlalchemy.orm import Session
import json
import pandas as pd
from datetime import datetime

from app.services.pdf_parser_service import PDFParserService
from app.models import ParsingQueue, ParsingStatus
from app.ui.components.auth import get_current_user


def show(db: Session):
    """Display the manual review queue page."""
    st.title("👁️ Manual Review Queue")

    # Initialize service
    parser_service = PDFParserService()

    # Get pending items
    pending_items = parser_service.review_parsing_queue(db, ParsingStatus.PENDING)
    failed_items = parser_service.review_parsing_queue(db, ParsingStatus.FAILED)

    # Stats
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Pending Review", len(pending_items))

    with col2:
        st.metric("Failed Parsing", len(failed_items))

    with col3:
        total_reviewed = (
            db.query(ParsingQueue)
            .filter_by(
                status=ParsingStatus.RESOLVED,
                assigned_to=(
                    str(get_current_user()["id"]) if get_current_user() else None
                ),
            )
            .count()
        )
        st.metric("Reviewed by You", total_reviewed)

    st.divider()

    # Combine pending and failed items
    review_items = pending_items + failed_items

    if review_items:
        # Select item to review
        item_options = {
            f"{item.pdf_filename} (ID: {item.id}) - {item.status.value}": item.id
            for item in review_items
        }

        selected_item = st.selectbox(
            "Select PDF to Review",
            options=list(item_options.keys()),
            help="Choose a PDF that needs manual review",
        )

        if selected_item:
            item_id = item_options[selected_item]
            item = next(i for i in review_items if i.id == item_id)

            # Display item details
            review_item(db, parser_service, item)

    else:
        st.success("🎉 No items pending review!")
        st.info(
            "All PDFs have been successfully processed or are currently being processed."
        )


def review_item(db: Session, parser_service: PDFParserService, item: ParsingQueue):
    """Review a single parsing queue item."""

    st.subheader(f"Reviewing: {item.pdf_filename}")

    # Item info
    col1, col2, col3 = st.columns(3)

    with col1:
        st.write(f"**Status:** {item.status.value}")
        st.write(f"**Created:** {item.created_at.strftime('%Y-%m-%d %H:%M')}")

    with col2:
        if item.confidence_score:
            st.write(f"**Confidence:** {item.confidence_score:.1%}")
            st.progress(item.confidence_score)
        else:
            st.write("**Confidence:** N/A")

    with col3:
        if item.error_message:
            st.write(f"**Error:** {item.error_message}")

    st.divider()

    # Two column layout
    col1, col2 = st.columns([1, 1])

    with col1:
        st.write("### 📄 PDF Preview")
        st.info("PDF preview would be displayed here")
        # TODO: Implement PDF preview using pdf.js or similar

        if item.notes:
            st.write("**Notes:**")
            st.write(item.notes)

    with col2:
        st.write("### 📝 Extracted Data")

        # Load existing extracted data if available
        existing_data = {}
        if item.extracted_data:
            try:
                existing_data = json.loads(item.extracted_data)
            except:
                pass

        # Manual data entry form
        with st.form("manual_review_form"):
            st.write("**Basic Information**")

            reference_number = st.text_input(
                "Reference Number *",
                value=existing_data.get("reference_number", ""),
                placeholder="YYMMDD-XXX",
            )

            lot_number = st.text_input(
                "Lot Number *", value=existing_data.get("lot_number", "")
            )

            test_date = st.date_input(
                "Test Date *",
                value=(
                    datetime.strptime(
                        existing_data.get("test_date", ""), "%Y-%m-%d"
                    ).date()
                    if existing_data.get("test_date")
                    else datetime.now().date()
                ),
            )

            lab_name = st.text_input(
                "Lab Name", value=existing_data.get("lab_name", "")
            )

            st.write("**Test Results**")

            # Common test fields
            test_fields = [
                ("Total Plate Count", "CFU/g"),
                ("Yeast/Mold", "CFU/g"),
                ("E. Coli", ""),
                ("Salmonella", ""),
                ("Lead", "ppm"),
                ("Mercury", "ppm"),
                ("Cadmium", "ppm"),
                ("Arsenic", "ppm"),
            ]

            test_results = {}

            # Get existing test results
            existing_tests = existing_data.get("test_results", {})

            for test_name, default_unit in test_fields:
                col1, col2, col3 = st.columns([2, 1, 1])

                existing_test = existing_tests.get(test_name, {})

                with col1:
                    value = st.text_input(
                        test_name,
                        value=existing_test.get("value", ""),
                        key=f"value_{test_name}",
                    )

                with col2:
                    unit = st.text_input(
                        "Unit",
                        value=existing_test.get("unit", default_unit),
                        key=f"unit_{test_name}",
                    )

                with col3:
                    confidence = st.slider(
                        "Conf",
                        0.0,
                        1.0,
                        value=existing_test.get("confidence", 1.0),
                        step=0.1,
                        key=f"conf_{test_name}",
                    )

                if value:  # Only add if value is provided
                    test_results[test_name] = {
                        "value": value,
                        "unit": unit,
                        "confidence": confidence,
                    }

            # Additional notes
            review_notes = st.text_area(
                "Review Notes", placeholder="Any additional notes about this review"
            )

            # Submit buttons
            col1, col2 = st.columns(2)

            with col1:
                save_draft = st.form_submit_button(
                    "💾 Save Draft", use_container_width=True
                )

            with col2:
                submit_review = st.form_submit_button(
                    "✅ Submit Review", type="primary", use_container_width=True
                )

            if save_draft or submit_review:
                if not reference_number or not lot_number:
                    st.error("Reference Number and Lot Number are required")
                else:
                    # Prepare data
                    data = {
                        "reference_number": reference_number,
                        "lot_number": lot_number,
                        "test_date": test_date.strftime("%Y-%m-%d"),
                        "lab_name": lab_name,
                        "test_results": test_results,
                    }

                    try:
                        if submit_review:
                            # Submit for processing
                            success = parser_service.update_parsed_data(
                                item.id, data, get_current_user()["id"]
                            )

                            if success:
                                st.success("✅ Review submitted successfully!")
                                st.balloons()
                                st.info(
                                    "Test results have been created. Redirecting..."
                                )
                                # TODO: Implement redirect
                            else:
                                st.error("Failed to submit review")

                        else:
                            # Just save draft
                            item.extracted_data = json.dumps(data)
                            item.notes = review_notes
                            db.commit()
                            st.success("💾 Draft saved successfully!")
                            st.rerun()

                    except Exception as e:
                        st.error(f"Error: {str(e)}")

    # Action buttons
    st.divider()

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("⏭️ Skip to Next", use_container_width=True):
            st.rerun()

    with col2:
        if st.button("🔄 Retry AI Parsing", use_container_width=True):
            with st.spinner("Retrying AI parsing..."):
                # TODO: Implement retry with different prompts
                st.info("Retry functionality coming soon")

    with col3:
        if st.button("❌ Mark as Failed", use_container_width=True):
            item.status = ParsingStatus.FAILED
            item.notes = "Marked as failed during manual review"
            db.commit()
            st.error("Marked as failed")
            st.rerun()
