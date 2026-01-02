"""COA generation page."""

import streamlit as st
from sqlalchemy.orm import Session
import pandas as pd
from datetime import datetime, date, timedelta
from pathlib import Path

from app.services.lot_service import LotService
from app.services.sample_service import SampleService
from app.models import Lot, LotStatus, TestResultStatus, TestResult
from app.ui.components.auth import get_current_user


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
    
    # Debug: Show all lots and their status
    with st.expander("Debug: All Lots"):
        all_lots = db.query(Lot).all()
        for lot in all_lots:
            st.write(f"Lot {lot.lot_number}: Status={lot.status.value}, Generate COA={lot.generate_coa}")

    # Stats
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Ready for COA", len(ready_lots))

    with col2:
        # Count actual COAs generated today
        today_count = 0  # TODO: Implement with real COA history tracking
        st.metric("Generated Today", today_count)

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
                    # Import COA generator service
                    from app.services.coa_generator_service import COAGeneratorService
                    
                    # Get current user
                    current_user = get_current_user()
                    
                    # Initialize service and generate COA
                    coa_service = COAGeneratorService()
                    
                    # Determine output format based on selection
                    format_map = {
                        "PDF": "pdf",
                        "Word (DOCX)": "docx",
                        "Both": "both"
                    }
                    output_format = format_map.get(output_format, "pdf")
                    
                    # Determine template
                    template_name = "standard" if template == "Standard COA" else "composite"
                    
                    # Generate COA
                    result = coa_service.generate_coa(
                        db=db,
                        lot_id=selected_lot.id,
                        template=template_name,
                        output_format=output_format,
                        user_id=current_user["id"]
                    )

                    st.success(
                        f"✅ COA generated successfully for Lot {selected_lot.lot_number}"
                    )

                    # Handle file downloads
                    col1, col2 = st.columns(2)

                    with col1:
                        # Get the generated file(s)
                        for file_path in result["files"]:
                            if file_path.exists():
                                with open(file_path, "rb") as f:
                                    file_data = f.read()
                                
                                st.download_button(
                                    label=f"📥 Download {file_path.suffix.upper()}",
                                    data=file_data,
                                    file_name=file_path.name,
                                    mime=("application/pdf" if file_path.suffix == ".pdf" 
                                          else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
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

    # Date filter - default to last 30 days
    col1, col2 = st.columns(2)

    with col1:
        default_start = datetime.now().date() - timedelta(days=30)
        start_date = st.date_input("From Date", default_start)

    with col2:
        end_date = st.date_input("To Date", datetime.now().date())

    # Get released lots (those that have had COAs generated)
    released_lots = (
        db.query(Lot)
        .filter(
            Lot.status == LotStatus.RELEASED,
            Lot.created_at >= start_date,
            Lot.created_at <= datetime.combine(end_date, datetime.max.time())
        )
        .order_by(Lot.created_at.desc())
        .all()
    )
    
    if released_lots:
        history_data = []
        for lot in released_lots:
            products = ", ".join([lp.product.display_name for lp in lot.lot_products])
            history_data.append({
                "Date": lot.updated_at.strftime("%Y-%m-%d") if lot.updated_at else "-",
                "Lot Number": lot.lot_number,
                "Product": products,
                "lot_id": lot.id,  # Hidden for internal use
            })
        
        df = pd.DataFrame(history_data)
        
        # Create action buttons as separate columns
        view_buttons = []
        regen_buttons = []
        
        for idx, row in df.iterrows():
            view_buttons.append("👁️ View Results")
            regen_buttons.append("🔄 Regenerate")
        
        df["View Results"] = view_buttons
        df["Actions"] = regen_buttons
        
        # Display the dataframe
        st.dataframe(
            df[["Date", "Lot Number", "Product", "View Results", "Actions"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Date": st.column_config.TextColumn("Date", width="small"),
                "Lot Number": st.column_config.TextColumn("Lot Number", width="medium"),
                "Product": st.column_config.TextColumn("Product", width="large"),
                "View Results": st.column_config.TextColumn("View Results", width="small"),
                "Actions": st.column_config.TextColumn("Actions", width="small"),
            }
        )
        
        # Handle actions below the grid
        st.write("### Actions")
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            lot_options = {f"{row['Lot Number']} - {row['Product']}": row['lot_id'] for idx, row in df.iterrows()}
            selected_lot = st.selectbox(
                "Select a lot:",
                options=list(lot_options.keys()) if lot_options else ["No lots available"]
            )
        
        with col2:
            if st.button("👁️ View Results", use_container_width=True):
                if selected_lot and selected_lot != "No lots available":
                    lot_id = lot_options[selected_lot]
                    lot = db.query(Lot).filter(Lot.id == lot_id).first()
                    
                    # Show test results in a dialog
                    @st.dialog(f"Test Results - {lot.lot_number}")
                    def show_test_results():
                        st.write(f"**Lot:** {lot.lot_number}")
                        st.write(f"**Reference:** {lot.reference_number}")
                        st.write(f"**Products:** {', '.join([lp.product.display_name for lp in lot.lot_products])}")
                        st.divider()
                        
                        if lot.test_results:
                            results_data = []
                            for result in lot.test_results:
                                results_data.append({
                                    "Test": result.test_type,
                                    "Result": f"{result.result_value} {result.unit or ''}".strip(),
                                    "Specification": result.specification or "-",
                                    "Test Date": result.test_date.strftime("%Y-%m-%d") if result.test_date else "-",
                                    "Status": "✅" if result.status == TestResultStatus.APPROVED else "❌"
                                })
                            
                            results_df = pd.DataFrame(results_data)
                            st.dataframe(results_df, use_container_width=True, hide_index=True)
                        else:
                            st.info("No test results found")
                        
                        if st.button("Close"):
                            st.rerun()
                    
                    show_test_results()
        
        with col3:
            if st.button("🔄 Regenerate", type="primary", use_container_width=True):
                if selected_lot and selected_lot != "No lots available":
                    lot_id = lot_options[selected_lot]
                    
                    with st.spinner("Regenerating COA..."):
                        try:
                            # Import COA generator service
                            from app.services.coa_generator_service import COAGeneratorService
                            
                            lot = db.query(Lot).filter(Lot.id == lot_id).first()
                            if lot:
                                # Get current user
                                current_user = get_current_user()
                                
                                # Initialize service and regenerate COA
                                coa_service = COAGeneratorService()
                                result = coa_service.generate_coa(
                                    db=db,
                                    lot_id=lot.id,
                                    template="standard",
                                    output_format="pdf",
                                    user_id=current_user["id"]
                                )
                                
                                # Get the generated PDF
                                if result["files"]:
                                    pdf_file = result["files"][0]
                                    if pdf_file.exists():
                                        with open(pdf_file, "rb") as f:
                                            file_data = f.read()
                                        
                                        st.success(f"✅ COA regenerated: {pdf_file.name}")
                                        st.download_button(
                                            label="📥 Download COA",
                                            data=file_data,
                                            file_name=pdf_file.name,
                                            mime="application/pdf",
                                        )
                            else:
                                st.error("Lot not found")
                        except Exception as e:
                            st.error(f"Error regenerating COA: {str(e)}")
    else:
        st.info(f"No COAs generated between {start_date} and {end_date}")

    # Summary stats
    if released_lots:
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Total Generated", len(released_lots))

        with col2:
            st.metric("Success Rate", "100%")  # All released lots are successful

        with col3:
            # Most common template
            st.metric("Most Used Template", "Standard COA")

        # Export
        if st.button("Export History"):
            import io
            buffer = io.BytesIO()
            # Remove the lot_id column before exporting
            export_df = df.drop(columns=['lot_id'])
            export_df.to_excel(buffer, index=False)
            excel_data = buffer.getvalue()
            st.download_button(
                label="Download Excel",
                data=excel_data,
                file_name=f"coa_history_{start_date}_{end_date}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
