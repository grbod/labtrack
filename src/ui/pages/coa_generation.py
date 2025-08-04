"""COA generation page."""

import streamlit as st
from sqlalchemy.orm import Session
import pandas as pd
from datetime import datetime
from pathlib import Path

from src.services.lot_service import LotService
from src.services.sample_service import SampleService
from src.models import Lot, LotStatus, TestResultStatus
from src.ui.components.auth import get_current_user


def show(db: Session):
    """Display the COA generation page."""
    st.title("🏭 COA Generation")

    # Initialize services
    lot_service = LotService()
    sample_service = SampleService()

    # Get lots ready for COA generation
    ready_lots = (
        db.query(Lot)
        .filter(Lot.status == LotStatus.APPROVED, Lot.generate_coa == True)
        .all()
    )

    # Stats
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Ready for COA", len(ready_lots))

    with col2:
        # Mock stat - would need COA history service
        st.metric("Generated Today", "5")

    with col3:
        # Mock stat
        st.metric("Templates Available", "2")

    st.divider()

    # Tabs
    tab1, tab2, tab3 = st.tabs(["Generate COA", "Batch Generation", "COA History"])

    with tab1:
        single_coa_generation(db, lot_service, ready_lots)

    with tab2:
        batch_coa_generation(db, lot_service, ready_lots)

    with tab3:
        coa_history(db)


def single_coa_generation(db: Session, lot_service: LotService, ready_lots: list[Lot]):
    """Generate COA for a single lot."""
    st.subheader("Generate Single COA")

    if not ready_lots:
        st.info(
            "No lots are ready for COA generation. Lots must have all test results approved."
        )
        return

    # Select lot
    lot_options = {
        f"{lot.lot_number} - {lot.reference_number} ({', '.join([lp.product.display_name for lp in lot.lot_products])})": lot
        for lot in ready_lots
    }

    selected_lot_key = st.selectbox(
        "Select Lot",
        options=list(lot_options.keys()),
        help="Choose a lot to generate COA",
    )

    if selected_lot_key:
        selected_lot = lot_options[selected_lot_key]

        # Display lot details
        col1, col2 = st.columns(2)

        with col1:
            st.write("**Lot Information:**")
            st.write(f"- Lot Number: {selected_lot.lot_number}")
            st.write(f"- Reference: {selected_lot.reference_number}")
            st.write(f"- Type: {selected_lot.lot_type.value}")
            st.write(
                f"- Mfg Date: {selected_lot.mfg_date.strftime('%Y-%m-%d') if selected_lot.mfg_date else 'N/A'}"
            )
            st.write(
                f"- Exp Date: {selected_lot.exp_date.strftime('%Y-%m-%d') if selected_lot.exp_date else 'N/A'}"
            )

        with col2:
            st.write("**Products:**")
            for lp in selected_lot.lot_products:
                if lp.percentage:
                    st.write(f"- {lp.product.display_name} ({lp.percentage}%)")
                else:
                    st.write(f"- {lp.product.display_name}")

        # Test results summary
        st.write("**Test Results Summary:**")

        test_results = selected_lot.test_results
        if test_results:
            results_data = []
            for result in test_results:
                results_data.append(
                    {
                        "Test": result.test_type,
                        "Result": f"{result.result_value} {result.unit}".strip(),
                        "Status": (
                            "✅" if result.status == TestResultStatus.APPROVED else "⏳"
                        ),
                        "Test Date": (
                            result.test_date.strftime("%Y-%m-%d")
                            if result.test_date
                            else "-"
                        ),
                    }
                )

            df = pd.DataFrame(results_data)
            st.dataframe(df, use_container_width=True, hide_index=True)

        # COA options
        st.divider()

        col1, col2 = st.columns(2)

        with col1:
            template = st.selectbox(
                "COA Template",
                options=["Standard COA", "Composite COA"],
                help="Select the template to use",
            )

            output_format = st.selectbox(
                "Output Format",
                options=["PDF", "Word (DOCX)", "Both"],
                help="Choose the output format",
            )

        with col2:
            include_logo = st.checkbox("Include Company Logo", value=True)
            include_qr = st.checkbox("Include QR Code", value=False)

            # Preview button
            if st.button("👁️ Preview COA", use_container_width=True):
                with st.spinner("Generating preview..."):
                    # TODO: Implement COA preview
                    st.info("COA preview would be displayed here")

        # Generate button
        if st.button("🏭 Generate COA", type="primary", use_container_width=True):
            with st.spinner("Generating COA..."):
                try:
                    # TODO: Implement actual COA generation
                    # For now, mock the process

                    # Update lot status
                    selected_lot.status = LotStatus.RELEASED
                    db.commit()

                    st.success(
                        f"✅ COA generated successfully for Lot {selected_lot.lot_number}"
                    )

                    # Mock file path
                    filename = f"COA_{selected_lot.lot_number}_{datetime.now().strftime('%Y%m%d')}.pdf"

                    col1, col2 = st.columns(2)

                    with col1:
                        st.download_button(
                            label="📥 Download COA",
                            data=b"Mock COA content",  # TODO: Real file content
                            file_name=filename,
                            mime="application/pdf",
                            use_container_width=True,
                        )

                    with col2:
                        if st.button("📧 Email COA", use_container_width=True):
                            st.info("Email functionality coming soon")

                except Exception as e:
                    st.error(f"Error generating COA: {str(e)}")


def batch_coa_generation(db: Session, lot_service: LotService, ready_lots: list[Lot]):
    """Batch generate COAs."""
    st.subheader("Batch COA Generation")

    if not ready_lots:
        st.info("No lots are ready for COA generation.")
        return

    st.info(f"{len(ready_lots)} lots are ready for COA generation")

    # Create selectable table
    data = []
    for lot in ready_lots:
        products = ", ".join([lp.product.display_name for lp in lot.lot_products])
        data.append(
            {
                "Select": True,
                "Lot Number": lot.lot_number,
                "Reference": lot.reference_number,
                "Product(s)": products,
                "Type": lot.lot_type.value,
                "Mfg Date": lot.mfg_date.strftime("%Y-%m-%d") if lot.mfg_date else "-",
                "Exp Date": lot.exp_date.strftime("%Y-%m-%d") if lot.exp_date else "-",
            }
        )

    df = pd.DataFrame(data)

    # Editable dataframe
    edited_df = st.data_editor(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Select": st.column_config.CheckboxColumn(
                "Select", help="Select lots to generate COAs", default=True
            )
        },
        disabled=[
            "Lot Number",
            "Reference",
            "Product(s)",
            "Type",
            "Mfg Date",
            "Exp Date",
        ],
    )

    # Get selected lots
    selected_lots = edited_df[edited_df["Select"]]

    if len(selected_lots) > 0:
        st.write(f"**{len(selected_lots)} lots selected for COA generation**")

        # Batch options
        col1, col2 = st.columns(2)

        with col1:
            batch_template = st.selectbox(
                "Template for All",
                options=["Standard COA", "Auto-detect (Standard/Composite)"],
            )

        with col2:
            batch_format = st.selectbox(
                "Output Format", options=["PDF", "Word (DOCX)", "Both"]
            )

        # Generate button
        if st.button(
            f"🏭 Generate {len(selected_lots)} COAs",
            type="primary",
            use_container_width=True,
        ):
            progress_bar = st.progress(0)
            status_text = st.empty()

            generated = 0
            errors = []

            for idx, row in selected_lots.iterrows():
                try:
                    status_text.text(f"Generating COA for {row['Lot Number']}...")

                    # TODO: Implement actual COA generation
                    # Mock delay
                    import time

                    time.sleep(0.5)

                    # Update lot status
                    lot = next(
                        l for l in ready_lots if l.lot_number == row["Lot Number"]
                    )
                    lot.status = LotStatus.RELEASED

                    generated += 1

                except Exception as e:
                    errors.append(f"{row['Lot Number']}: {str(e)}")

                # Update progress
                progress = (idx + 1) / len(selected_lots)
                progress_bar.progress(progress)

            db.commit()

            progress_bar.empty()
            status_text.empty()

            # Show results
            if generated > 0:
                st.success(f"✅ Successfully generated {generated} COAs")

            if errors:
                st.error(f"❌ Failed to generate {len(errors)} COAs")
                with st.expander("Show errors"):
                    for error in errors:
                        st.write(f"- {error}")

            # Download all button
            if generated > 0:
                st.download_button(
                    label=f"📥 Download All {generated} COAs (ZIP)",
                    data=b"Mock ZIP content",  # TODO: Create actual ZIP
                    file_name=f"COAs_batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                    mime="application/zip",
                    use_container_width=True,
                )

    else:
        st.info("Select lots using the checkboxes to generate COAs")


def coa_history(db: Session):
    """Show COA generation history."""
    st.subheader("COA Generation History")

    # Date filter
    col1, col2 = st.columns(2)

    with col1:
        start_date = st.date_input("From Date", datetime.now().date().replace(day=1))

    with col2:
        end_date = st.date_input("To Date", datetime.now().date())

    # Mock history data - TODO: Implement with real COA history
    history_data = [
        {
            "Date": "2024-01-15 14:30",
            "Lot Number": "ABC123",
            "Reference": "240115-001",
            "Product": "Organic Whey Protein - Vanilla",
            "Template": "Standard COA",
            "Generated By": "admin",
            "Status": "✅ Success",
        },
        {
            "Date": "2024-01-15 13:15",
            "Lot Number": "XYZ789",
            "Reference": "240115-002",
            "Product": "Plant Protein - Chocolate",
            "Template": "Standard COA",
            "Generated By": "admin",
            "Status": "✅ Success",
        },
    ]

    if history_data:
        df = pd.DataFrame(history_data)

        st.dataframe(df, use_container_width=True, hide_index=True)

        # Summary stats
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Total Generated", len(df))

        with col2:
            success_rate = len(
                [h for h in history_data if "Success" in h["Status"]]
            ) / len(history_data)
            st.metric("Success Rate", f"{success_rate:.0%}")

        with col3:
            # Most common template
            st.metric("Most Used Template", "Standard COA")

        # Export
        if st.button("Export History"):
            excel_data = df.to_excel(index=False)
            st.download_button(
                label="Download Excel",
                data=excel_data,
                file_name=f"coa_history_{start_date}_{end_date}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

    else:
        st.info("No COA generation history found for the selected date range")
