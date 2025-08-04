"""Create Sample Submission page for COA Management System."""

import streamlit as st
from sqlalchemy.orm import Session
import pandas as pd
from datetime import datetime, date
import uuid

from src.services.lot_service import LotService
from src.services.product_service import ProductService
from src.models.enums import LotType, LotStatus
from src.ui.components.auth import get_current_user


def show(db: Session):
    """Display the create sample submission page."""
    st.title("🧫 Sample Submission")

    # Initialize services
    lot_service = LotService()
    product_service = ProductService()

    # Create tabs for submission and viewing
    tab1, tab2 = st.tabs(["Create Submission", "View Samples"])

    with tab1:
        create_submission(db, lot_service, product_service)

    with tab2:
        view_samples(db, lot_service)


def create_submission(
    db: Session, lot_service: LotService, product_service: ProductService
):
    """Main submission creation interface."""
    # Get products for dropdowns
    products = product_service.get_multi(db)
    if not products:
        st.warning("No products found. Please add products first.")
        return

    # Create tabs for different submission types
    tab1, tab2, tab3 = st.tabs([
        "Single Lot/Single SKU",
        "Master Lot with Sub-Batches", 
        "Composite Lot with Multiple SKUs"
    ])

    with tab1:
        single_lot_form(db, lot_service, products)
    
    with tab2:
        master_lot_form(db, lot_service, products)
    
    with tab3:
        composite_lot_form(db, lot_service, products)


def single_lot_form(db: Session, lot_service: LotService, products):
    """Form for Single Lot/Single SKU submission."""

    with st.form("single_lot_form"):
        col1, col2 = st.columns(2)

        with col1:
            # Product selection
            product_options = {f"{p.display_name} (ID: {p.id})": p.id for p in products}
            selected_product = st.selectbox(
                "Product *",
                options=list(product_options.keys()),
                help="Select the product for this sample"
            )

            # Lot number
            lot_number = st.text_input(
                "Lot # *",
                help="Enter the production lot number"
            )

        with col2:
            # Manufacturing date
            mfg_date = st.date_input(
                "Manufacturing Date *",
                value=date.today(),
                help="Date of manufacture"
            )

        # Notes
        notes = st.text_area(
            "Notes",
            help="Any additional notes about this sample"
        )

        # Reference number input
        st.divider()
        manual_ref = st.text_input(
            "Reference Number (Optional)",
            placeholder="Leave blank to auto-generate (YYMMDD-XXX)",
            help="Enter a custom reference number or leave blank for automatic generation"
        )
        
        if manual_ref:
            st.info(f"Will use reference number: **{manual_ref}**")
        else:
            st.info("A unique reference number will be automatically generated upon submission.")

        submitted = st.form_submit_button("Submit Sample", type="primary")

        if submitted:
            if not lot_number:
                st.error("Lot number is required")
            else:
                try:
                    # Get product ID
                    product_id = product_options[selected_product]

                    # Prepare lot data
                    lot_data = {
                        "lot_number": lot_number,
                        "lot_type": LotType.STANDARD,
                        "mfg_date": mfg_date,
                        "exp_date": mfg_date.replace(year=mfg_date.year + 3),
                    }
                    
                    # Add manual reference number if provided
                    if manual_ref:
                        lot_data["reference_number"] = manual_ref

                    # Create lot
                    lot = lot_service.create_lot(
                        db,
                        lot_data=lot_data,
                        product_ids=[product_id],
                    )

                    st.success(f"✅ Sample submitted successfully!")
                    st.info(f"Reference Number: **{lot.reference_number}**")
                    st.write("Use this reference number on lab samples")

                except Exception as e:
                    st.error(f"Error creating sample: {str(e)}")


def master_lot_form(db: Session, lot_service: LotService, products):
    """Form for Master Lot with Sub-Batches submission."""
    
    st.info("⚠️ This will generate ONE COA for each Master Lot and will NOT generate COA for each sub-batch")

    # Master lot input
    master_lot_number = st.text_input(
        "Master Lot # *",
        help="Enter the master lot number"
    )

    # Initialize session state for sub-batches
    if 'sub_batches' not in st.session_state:
        st.session_state.sub_batches = pd.DataFrame({
            'Product': [''],
            'Mfg Date': [date.today()],
            'Batch #': ['']
        })

    # Create product options for dropdown
    product_names = [p.display_name for p in products]
    product_map = {p.display_name: p.id for p in products}

    # Excel-style editor
    st.write("**Sub-Batch Details:**")
    
    # Configure columns
    column_config = {
        "Product": st.column_config.SelectboxColumn(
            "Product",
            options=product_names,
            required=True,
            width="medium"
        ),
        "Mfg Date": st.column_config.DateColumn(
            "Mfg Date",
            min_value=date(2020, 1, 1),
            max_value=date(2030, 12, 31),
            format="YYYY-MM-DD",
            required=True,
            width="small"
        ),
        "Batch #": st.column_config.TextColumn(
            "Batch #",
            required=True,
            width="medium"
        )
    }

    # Data editor
    edited_df = st.data_editor(
        st.session_state.sub_batches,
        column_config=column_config,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key="master_lot_data_editor"
    )

    # Update session state
    st.session_state.sub_batches = edited_df

    # Notes section
    notes = st.text_area(
        "Notes",
        help="Any additional notes about this master lot"
    )

    # Reference number input
    st.divider()
    manual_ref = st.text_input(
        "Reference Number (Optional)",
        placeholder="Leave blank to auto-generate (YYMMDD-XXX)",
        help="Enter a custom reference number or leave blank for automatic generation",
        key="master_ref_input"
    )
    
    if manual_ref:
        st.info(f"Will use reference number: **{manual_ref}**")
    else:
        st.info("A unique reference number will be automatically generated upon submission.")

    # Submit button
    if st.button("Submit Master Lot", type="primary"):
        if not master_lot_number:
            st.error("Master lot number is required")
        elif len(edited_df) == 0:
            st.error("Please add at least one sub-batch")
        elif edited_df['Product'].isna().any() or edited_df['Batch #'].eq('').any():
            st.error("Please fill in all required fields")
        else:
            try:
                # Prepare parent lot data
                parent_lot_data = {
                    "lot_number": master_lot_number,
                    "lot_type": LotType.PARENT_LOT,
                    "mfg_date": edited_df['Mfg Date'].min(),
                    "exp_date": edited_df['Mfg Date'].min().replace(
                        year=edited_df['Mfg Date'].min().year + 3
                    ),
                }
                
                # Add manual reference number if provided
                if manual_ref:
                    parent_lot_data["reference_number"] = manual_ref
                
                # Create parent lot
                parent_lot = lot_service.create_lot(
                    db,
                    lot_data=parent_lot_data,
                    product_ids=[product_map[edited_df.iloc[0]['Product']]],
                )

                # Create sublots
                sublots_created = []
                for idx, row in edited_df.iterrows():
                    sublot = lot_service.create_sublot(
                        db,
                        parent_lot_id=parent_lot.id,
                        sublot_data={
                            "sublot_number": f"{master_lot_number}-{row['Batch #']}",
                            "production_date": row['Mfg Date'],
                            "quantity_lbs": None,  # Can be added if needed
                        }
                    )
                    sublots_created.append(sublot)

                st.success(f"✅ Master lot submitted successfully!")
                st.info(f"Reference Number: **{parent_lot.reference_number}**")
                st.write(f"Created {len(sublots_created)} sub-batches under master lot {master_lot_number}")

                # Clear the form
                st.session_state.sub_batches = pd.DataFrame({
                    'Product': [''],
                    'Mfg Date': [date.today()],
                    'Batch #': ['']
                })

            except Exception as e:
                st.error(f"Error creating master lot: {str(e)}")


def composite_lot_form(db: Session, lot_service: LotService, products):
    """Form for Composite Lot with Multiple SKUs submission."""
    
    st.info("⚠️ This will generate a COA for each Item")

    # Initialize session state for composite batches
    if 'composite_batches' not in st.session_state:
        st.session_state.composite_batches = pd.DataFrame({
            'Product': [''],
            'Mfg Date': [date.today()],
            'Batch #': ['']
        })

    # Create product options for dropdown
    product_names = [p.display_name for p in products]
    product_map = {p.display_name: p.id for p in products}

    # Excel-style editor
    st.write("**Composite Batch Details:**")
    
    # Configure columns
    column_config = {
        "Product": st.column_config.SelectboxColumn(
            "Product",
            options=product_names,
            required=True,
            width="medium"
        ),
        "Mfg Date": st.column_config.DateColumn(
            "Mfg Date",
            min_value=date(2020, 1, 1),
            max_value=date(2030, 12, 31),
            format="YYYY-MM-DD",
            required=True,
            width="small"
        ),
        "Batch #": st.column_config.TextColumn(
            "Batch #",
            required=True,
            width="medium"
        )
    }

    # Data editor
    edited_df = st.data_editor(
        st.session_state.composite_batches,
        column_config=column_config,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key="composite_lot_data_editor"
    )

    # Update session state
    st.session_state.composite_batches = edited_df

    # Notes section
    notes = st.text_area(
        "Notes",
        help="Any additional notes about this composite lot"
    )

    # Reference number input
    st.divider()
    manual_ref = st.text_input(
        "Reference Number (Optional)",
        placeholder="Leave blank to auto-generate (YYMMDD-XXX)",
        help="Enter a custom reference number or leave blank for automatic generation",
        key="composite_ref_input"
    )
    
    if manual_ref:
        st.info(f"Will use reference number: **{manual_ref}**")
    else:
        st.info("A unique reference number will be automatically generated upon submission.")

    # Submit button
    if st.button("Submit Composite Lot", type="primary"):
        if len(edited_df) == 0:
            st.error("Please add at least one batch")
        elif edited_df['Product'].isna().any() or edited_df['Batch #'].eq('').any():
            st.error("Please fill in all required fields")
        else:
            try:
                # Generate composite lot number from batch numbers
                composite_lot_number = "COMP-" + "-".join(edited_df['Batch #'].tolist())

                # Calculate percentages (equal distribution for now)
                percentage_per_product = 100.0 / len(edited_df)
                product_percentages = {}
                product_ids = []

                for _, row in edited_df.iterrows():
                    product_id = product_map[row['Product']]
                    if product_id not in product_ids:
                        product_ids.append(product_id)
                        product_percentages[product_id] = percentage_per_product
                    else:
                        product_percentages[product_id] += percentage_per_product

                # Prepare composite lot data
                composite_lot_data = {
                    "lot_number": composite_lot_number,
                    "lot_type": LotType.MULTI_SKU_COMPOSITE,
                    "mfg_date": edited_df['Mfg Date'].min(),
                    "exp_date": edited_df['Mfg Date'].min().replace(
                        year=edited_df['Mfg Date'].min().year + 3
                    ),
                }
                
                # Add manual reference number if provided
                if manual_ref:
                    composite_lot_data["reference_number"] = manual_ref
                
                # Create composite lot
                composite_lot = lot_service.create_lot(
                    db,
                    lot_data=composite_lot_data,
                    product_ids=product_ids,
                    product_percentages=product_percentages,
                )

                st.success(f"✅ Composite lot submitted successfully!")
                st.info(f"Reference Number: **{composite_lot.reference_number}**")
                st.write("**Component Breakdown:**")
                for lp in composite_lot.lot_products:
                    st.write(f"- {lp.product.display_name}: {lp.percentage:.1f}%")

                # Clear the form
                st.session_state.composite_batches = pd.DataFrame({
                    'Product': [''],
                    'Mfg Date': [date.today()],
                    'Batch #': ['']
                })

            except Exception as e:
                st.error(f"Error creating composite lot: {str(e)}")


def view_samples(db: Session, lot_service: LotService):
    """View and manage existing samples."""
    st.subheader("Sample List")

    # Filters
    col1, col2, col3 = st.columns(3)

    with col1:
        filter_status = st.selectbox(
            "Status",
            options=["All"] + [s.value for s in LotStatus],
            help="Filter by lot status",
        )

    with col2:
        filter_ref = st.text_input(
            "Reference Number", help="Search by reference number"
        )

    with col3:
        filter_lot = st.text_input("Lot Number", help="Search by lot number")

    # Get lots
    lots = lot_service.get_multi(db)

    # Apply filters
    if filter_status != "All":
        lots = [l for l in lots if l.status.value == filter_status]
    if filter_ref:
        lots = [l for l in lots if filter_ref.lower() in l.reference_number.lower()]
    if filter_lot:
        lots = [l for l in lots if filter_lot.lower() in l.lot_number.lower()]

    if lots:
        # Create DataFrame
        df_data = []
        for lot in lots:
            products = ", ".join([lp.product.display_name for lp in lot.lot_products])
            df_data.append(
                {
                    "Reference #": lot.reference_number,
                    "Lot Number": lot.lot_number,
                    "Type": lot.lot_type.value,
                    "Product(s)": products,
                    "Status": lot.status.value,
                    "Mfg Date": (
                        lot.mfg_date.strftime("%Y-%m-%d") if lot.mfg_date else "-"
                    ),
                    "Exp Date": (
                        lot.exp_date.strftime("%Y-%m-%d") if lot.exp_date else "-"
                    ),
                    "Created": lot.created_at.strftime("%Y-%m-%d %H:%M"),
                }
            )

        df = pd.DataFrame(df_data)

        # Display table
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Status": st.column_config.SelectboxColumn(
                    "Status", options=[s.value for s in LotStatus], width="small"
                ),
                "Type": st.column_config.TextColumn("Type", width="small"),
            },
        )

        # Export option
        if st.button("Export to Excel"):
            import io
            buffer = io.BytesIO()
            df.to_excel(buffer, index=False)
            excel_data = buffer.getvalue()
            st.download_button(
                label="Download Excel",
                data=excel_data,
                file_name=f"samples_export_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
    else:
        st.info("No samples found matching the criteria")