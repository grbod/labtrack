"""Product management page for COA Management System."""

import streamlit as st
from sqlalchemy.orm import Session
import pandas as pd
import io

from app.services.product_service import ProductService
from app.services.lab_test_type_service import LabTestTypeService
from app.models import Product, LabTestType
from app.ui.components.auth import require_role, get_current_user
from app.models.enums import UserRole


def show(db: Session):
    """Display the product management page."""
    st.title("📦 Product Management")

    # Initialize service
    product_service = ProductService()
    
    # Clean up modal states when navigating to the page
    if 'page_loaded' not in st.session_state or st.session_state.page_loaded != 'products':
        # Clear all product-related session states more aggressively
        keys_to_clear = ['viewing_product_specs', 'editing_product_id', 'selected_product_id', 'test_selection']
        for key in list(st.session_state.keys()):
            # Clear any keys that start with product-related prefixes
            if any(key.startswith(prefix) for prefix in ['select_product_', 'edit_', 'del_', 'toggle_', 'confirm_delete_', 'editing_spec_', 'save_spec_', 'cancel_spec_', 'remove_spec_']):
                del st.session_state[key]
        # Clear the specific keys we know about
        for key in keys_to_clear:
            if key in st.session_state:
                del st.session_state[key]
        st.session_state.page_loaded = 'products'
        # Force a rerun to apply the cleanup
        st.rerun()

    # Tabs for different actions
    tab1, tab2, tab3 = st.tabs(["View Products", "Add Product", "Bulk Import"])

    with tab1:
        show_products_list(db, product_service)

    with tab2:
        add_product_form(db, product_service)

    with tab3:
        bulk_import_products(db, product_service)
    
    # Show modals at page level (not within tabs) - only if we're sure the page is fully loaded
    if st.session_state.get('page_loaded') == 'products':
        if "viewing_product_specs" in st.session_state:
            product_id = st.session_state.viewing_product_specs
            # Validate product exists and ID is valid
            if product_id and isinstance(product_id, int) and product_service.get(db, product_id):
                show_test_specs_modal(db, product_service, product_id)
            else:
                # Product doesn't exist or invalid ID, clear the session state
                if 'viewing_product_specs' in st.session_state:
                    del st.session_state.viewing_product_specs
                st.error("Product not found")
                st.rerun()
        elif "editing_product_id" in st.session_state:
            product_id = st.session_state.editing_product_id
            # Validate product exists and ID is valid
            if product_id and isinstance(product_id, int) and product_service.get(db, product_id):
                show_edit_product_modal(db, product_service, product_id)
            else:
                # Product doesn't exist or invalid ID, clear the session state
                if 'editing_product_id' in st.session_state:
                    del st.session_state.editing_product_id
                st.error("Product not found")
                st.rerun()


def show_products_list(db: Session, product_service: ProductService):
    """Display list of products with search and edit capabilities."""
    st.subheader("Product Catalog")

    # Search filters
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        search_brand = st.text_input("Search by Brand")
    with col2:
        search_name = st.text_input("Search by Name")
    with col3:
        search_flavor = st.text_input("Search by Flavor")
    with col4:
        search_size = st.text_input("Search by Size")

    # Get products
    if any([search_brand, search_name, search_flavor, search_size]):
        products = product_service.search_products(
            db,
            brand=search_brand or None,
            name=search_name or None,
            flavor=search_flavor or None,
            size=search_size or None,
        )
    else:
        products = product_service.get_multi(db)

    if products:
        # Convert to DataFrame for display
        df = pd.DataFrame(
            [
                {
                    "ID": p.id,
                    "Brand": p.brand,
                    "Product Name": p.product_name,
                    "Flavor": p.flavor or "-",
                    "Size": p.size or "-",
                    "Serving Size": f"{float(p.serving_size):.2f}g" if p.serving_size else "-",
                    "Display Name": p.display_name,
                    "Expiry Duration": p.expiry_duration_display,
                    "Test Specs": f"{len([s for s in p.test_specifications if s.is_required])} required, {len([s for s in p.test_specifications if not s.is_required])} optional",
                    "Created": p.created_at.strftime("%Y-%m-%d"),
                }
                for p in products
            ]
        )

        # Initialize session state for selected product
        if 'selected_product_id' not in st.session_state:
            st.session_state.selected_product_id = None
        
        # Display products with selection
        st.markdown("**Select a product to view specs or edit:**")
        
        # Create selection and display
        cols = st.columns([0.5, 0.5, 2, 1.5, 1, 1, 1, 1.5, 1.5, 1])
        
        # Header
        cols[0].markdown("**Select**")
        cols[1].markdown("**ID**")
        cols[2].markdown("**Brand**")
        cols[3].markdown("**Product Name**")
        cols[4].markdown("**Flavor**")
        cols[5].markdown("**Size**")
        cols[6].markdown("**Serving**")
        cols[7].markdown("**Expiry**")
        cols[8].markdown("**Test Specs**")
        cols[9].markdown("**Created**")
        
        # Product rows
        for i, (_, product) in enumerate(df.iterrows()):
            cols = st.columns([0.5, 0.5, 2, 1.5, 1, 1, 1, 1.5, 1.5, 1])
            
            # Selection checkbox
            is_selected = st.session_state.selected_product_id == product['ID']
            checkbox_val = cols[0].checkbox(
                "",
                value=is_selected,
                key=f"select_product_{i}",
                label_visibility="collapsed"
            )
            
            # Handle selection changes
            if checkbox_val and not is_selected:
                # Newly selected
                st.session_state.selected_product_id = product['ID']
                st.rerun()
            elif not checkbox_val and is_selected:
                # Deselected
                st.session_state.selected_product_id = None
                st.rerun()
            
            cols[1].markdown(str(product['ID']))
            cols[2].markdown(product['Brand'])
            cols[3].markdown(product['Product Name'])
            cols[4].markdown(product['Flavor'])
            cols[5].markdown(product['Size'])
            cols[6].markdown(product['Serving Size'])
            cols[7].markdown(product.get('Expiry Duration', '3 years'))  # Will be added to df
            cols[8].markdown(product['Test Specs'])
            cols[9].markdown(product['Created'])

        st.markdown("---")
        
        # Action buttons
        col1, col2, col3 = st.columns([1, 1, 3])
        
        with col1:
            if st.button("View Test Specs", use_container_width=True, disabled=st.session_state.selected_product_id is None):
                if st.session_state.selected_product_id:
                    # Clear any other modal states
                    if 'editing_product_id' in st.session_state:
                        del st.session_state.editing_product_id
                    st.session_state.viewing_product_specs = st.session_state.selected_product_id
                    st.rerun()
                else:
                    st.warning("Please select a product first")
        
        with col2:
            if st.button("Edit Product", use_container_width=True, disabled=st.session_state.selected_product_id is None):
                if st.session_state.selected_product_id:
                    # Clear any other modal states
                    if 'viewing_product_specs' in st.session_state:
                        del st.session_state.viewing_product_specs
                    st.session_state.editing_product_id = st.session_state.selected_product_id
                    st.rerun()
                else:
                    st.warning("Please select a product first")

        # Export products
        if st.button("Export to Excel"):
            # Convert to Excel using BytesIO
            buffer = io.BytesIO()
            df.to_excel(buffer, index=False)
            excel_data = buffer.getvalue()
            st.download_button(
                label="Download Excel",
                data=excel_data,
                file_name="products_export.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
    else:
        st.info("No products found. Add some products to get started!")


def add_product_form(db: Session, product_service: ProductService):
    """Form to add a new product."""
    st.subheader("Add New Product")

    with st.form("add_product_form"):
        col1, col2 = st.columns(2)

        with col1:
            brand = st.text_input("Brand *", help="e.g., Truvani")
            product_name = st.text_input(
                "Product Name *", help="e.g., Organic Whey Protein"
            )
            flavor = st.text_input("Flavor", help="e.g., Chocolate Peanut Butter")

        with col2:
            size = st.text_input("Size", help="e.g., 20 serving")
            serving_size = st.number_input(
                "Serving Size (g)",
                min_value=0.01,
                max_value=999.99,
                value=28.0,
                step=0.01,
                format="%.2f",
                help="Serving size in grams"
            )
            
            # Expiry duration dropdown
            expiry_options = {
                "6 months": 6,
                "1 year": 12,
                "18 months": 18,
                "2 years": 24,
                "3 years": 36,
                "5 years": 60
            }
            expiry_duration = st.selectbox(
                "Expiry Duration *",
                options=list(expiry_options.keys()),
                index=4,  # Default to 3 years
                help="How long the product is valid from manufacturing date"
            )
            display_name = st.text_input(
                "Display Name *",
                help="Standardized name for COAs",
                placeholder="Auto-generated if left blank",
            )

        submitted = st.form_submit_button("Add Product", type="primary")

        if submitted:
            if not brand or not product_name:
                st.error("Brand and Product Name are required")
            else:
                try:
                    # Auto-generate display name if not provided
                    if not display_name:
                        display_name = f"{brand} {product_name}"
                        if flavor:
                            display_name += f" - {flavor}"
                        if size:
                            display_name += f" ({size})"

                    # Create product
                    product = product_service.create(
                        db,
                        obj_in={
                            "brand": brand,
                            "product_name": product_name,
                            "flavor": flavor,
                            "size": size,
                            "display_name": display_name,
                            "serving_size": serving_size,
                            "expiry_duration_months": expiry_options[expiry_duration],
                        }
                    )

                    st.success(f"✅ Product added successfully: {product.display_name}")
                    st.balloons()

                except Exception as e:
                    st.error(f"Error adding product: {str(e)}")


def bulk_import_products(db: Session, product_service: ProductService):
    """Bulk import products from Excel."""
    st.subheader("Bulk Import Products")

    # Download template
    st.info(
        "Upload an Excel file with columns: Brand, Product Name, Flavor, Size, Serving Size, Expiry Duration (months), Display Name"
    )

    # Create sample template
    template_df = pd.DataFrame(
        {
            "Brand": ["Truvani", "TTP Nutrition", "Tiger"],
            "Product Name": ["Organic Whey Protein", "Plant Protein", "Protein Powder"],
            "Flavor": ["Vanilla", "Chocolate", "Unflavored"],
            "Size": ["20 serving", "30 serving", "2 lb"],
            "Serving Size": [28.5, 31.0, 25.5],
            "Expiry Duration (months)": [36, 24, 36],
            "Display Name": [
                "Truvani Organic Whey Protein - Vanilla (20 serving)",
                "",
                "",
            ],
        }
    )

    # Convert to Excel for download
    @st.cache_data
    def convert_df_to_excel(df):
        buffer = io.BytesIO()
        df.to_excel(buffer, index=False)
        return buffer.getvalue()

    excel_template = convert_df_to_excel(template_df)

    st.download_button(
        label="Download Template",
        data=excel_template,
        file_name="product_import_template.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    # File upload
    uploaded_file = st.file_uploader(
        "Choose Excel file",
        type=["xlsx", "xls"],
        help="File should have the same columns as the template",
    )

    if uploaded_file:
        try:
            df = pd.read_excel(uploaded_file)

            # Validate columns
            required_cols = ["Brand", "Product Name"]
            if not all(col in df.columns for col in required_cols):
                st.error(f"Missing required columns. File must have: {required_cols}")
                return

            # Preview data
            st.write("Preview of data to import:")
            st.dataframe(df.head(10))

            if st.button("Import Products", type="primary"):
                success_count = 0
                error_count = 0
                errors = []

                progress_bar = st.progress(0)
                status_text = st.empty()

                for idx, row in df.iterrows():
                    try:
                        # Auto-generate display name if not provided
                        display_name = row.get("Display Name", "")
                        if not display_name or pd.isna(display_name):
                            display_name = f"{row['Brand']} {row['Product Name']}"
                            if not pd.isna(row.get("Flavor")):
                                display_name += f" - {row['Flavor']}"
                            if not pd.isna(row.get("Size")):
                                display_name += f" ({row['Size']})"

                        # Get expiry duration, default to 36 months if not provided
                        expiry_months = 36  # default
                        if "Expiry Duration (months)" in row and not pd.isna(row.get("Expiry Duration (months)")):
                            expiry_months = int(row["Expiry Duration (months)"])
                        
                        product_service.create(
                            db,
                            obj_in={
                                "brand": row["Brand"],
                                "product_name": row["Product Name"],
                                "flavor": (
                                    row.get("Flavor")
                                    if not pd.isna(row.get("Flavor"))
                                    else None
                                ),
                                "size": (
                                    row.get("Size")
                                    if not pd.isna(row.get("Size"))
                                    else None
                                ),
                                "serving_size": (
                                    row.get("Serving Size")
                                    if not pd.isna(row.get("Serving Size"))
                                    else None
                                ),
                                "expiry_duration_months": expiry_months,
                                "display_name": display_name,
                            }
                        )
                        success_count += 1
                    except Exception as e:
                        error_count += 1
                        errors.append(f"Row {idx + 2}: {str(e)}")

                    # Update progress
                    progress = (idx + 1) / len(df)
                    progress_bar.progress(progress)
                    status_text.text(f"Processing... {idx + 1}/{len(df)}")

                progress_bar.empty()
                status_text.empty()

                # Show results
                if success_count > 0:
                    st.success(f"✅ Successfully imported {success_count} products")

                if error_count > 0:
                    st.error(f"❌ Failed to import {error_count} products")
                    with st.expander("Show errors"):
                        for error in errors:
                            st.write(f"- {error}")

        except Exception as e:
            st.error(f"Error reading file: {str(e)}")


def show_test_specs_modal(db: Session, product_service: ProductService, product_id: int):
    """Show modal for managing product test specifications."""
    
    @st.dialog("Product Test Specifications", width="large")
    def test_specs_dialog():
        product = product_service.get(db, product_id)
        if not product:
            st.error("Product not found")
            return
            
        st.subheader(f"🧪 Test Specifications for {product.display_name}")
        
        # Initialize services
        lab_test_service = LabTestTypeService()
        
        # Tabs for viewing and editing
        tab1, tab2 = st.tabs(["Current Specifications", "Add/Edit Specifications"])
        
        with tab1:
            show_current_specs(db, product, product_service)
            
        with tab2:
            edit_test_specs(db, product, product_service, lab_test_service)
            
        # Close button
        if st.button("Close", use_container_width=True):
            del st.session_state.viewing_product_specs
            st.rerun()
    
    test_specs_dialog()


def show_current_specs(db: Session, product: Product, product_service: ProductService):
    """Display current test specifications for a product."""
    
    if not product.test_specifications:
        st.info("No test specifications defined for this product yet.")
        return
        
    # Group by required/optional
    required_specs = [s for s in product.test_specifications if s.is_required]
    optional_specs = [s for s in product.test_specifications if not s.is_required]
    
    if required_specs:
        st.markdown("### Required Tests")
        df_required = pd.DataFrame([
            {
                "Test Name": spec.lab_test_type.test_name,
                "Category": spec.lab_test_type.test_category,
                "Specification": spec.specification,
                "Unit": spec.lab_test_type.default_unit,
                "Method": spec.lab_test_type.test_method or "-"
            }
            for spec in required_specs
        ])
        st.dataframe(df_required, hide_index=True, use_container_width=True)
    
    if optional_specs:
        st.markdown("### Optional Tests")
        df_optional = pd.DataFrame([
            {
                "Test Name": spec.lab_test_type.test_name,
                "Category": spec.lab_test_type.test_category,
                "Specification": spec.specification,
                "Unit": spec.lab_test_type.default_unit,
                "Method": spec.lab_test_type.test_method or "-"
            }
            for spec in optional_specs
        ])
        st.dataframe(df_optional, hide_index=True, use_container_width=True)
    
    # Summary metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Tests", len(product.test_specifications))
    with col2:
        st.metric("Required", len(required_specs))
    with col3:
        st.metric("Optional", len(optional_specs))


def edit_test_specs(db: Session, product: Product, product_service: ProductService, lab_test_service: LabTestTypeService):
    """Edit test specifications for a product."""
    
    # Get all active lab test types grouped by category
    grouped_tests = lab_test_service.get_all_grouped(db)
    
    # Current specs for reference
    current_spec_ids = {spec.lab_test_type_id for spec in product.test_specifications}
    
    st.info("Select tests to add to this product's specifications. You can set whether each test is required or optional.")
    
    # Test selection (outside form for reactivity)
    all_tests = []
    test_options = []
    for category, tests in grouped_tests.items():
        for test in tests:
            if test.id not in current_spec_ids:  # Only show tests not already added
                all_tests.append(test)
                test_options.append(f"{category} - {test.test_name} ({test.default_unit})")
    
    if test_options:
        selected_test_idx = st.selectbox(
            "Select Test to Add",
            range(len(test_options)),
            format_func=lambda x: test_options[x],
            key="test_selection"
        )
        
        # Get the selected test to pre-populate specification
        selected_test = all_tests[selected_test_idx]
        default_spec_value = selected_test.default_specification or ""
        
        # Add new specification form
        with st.form("add_spec_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                specification = st.text_input(
                    "Specification",
                    value=default_spec_value,
                    placeholder="e.g., <10 CFU/g, Not Detected, <100 ppm",
                    help="The acceptance criteria for this test (pre-populated from default)"
                )
            
            with col2:
                test_type = st.radio(
                    "Test Type *",
                    options=["REQUIRED", "OPTIONAL"],
                    index=None,  # No default selection - forces user to choose
                    help="Required tests must be completed for lot approval. Optional tests are for additional quality assurance."
                )
            
            if st.form_submit_button("Add Test Specification", type="primary"):
                if not specification:
                    st.error("Please enter a specification")
                elif test_type is None:
                    st.error("Please select whether this test is REQUIRED or OPTIONAL")
                else:
                    try:
                        is_required = test_type == "REQUIRED"
                        product_service.add_test_specification(
                            db=db,
                            product_id=product.id,
                            test_type_id=selected_test.id,
                            specification=specification,
                            is_required=is_required
                        )
                        st.success(f"Added {selected_test.test_name} as {test_type.lower()} test")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error adding specification: {str(e)}")
    else:
        st.info("All available tests have been added to this product.")
    
    # Manage specifications
    if product.test_specifications:
        st.divider()
        st.subheader("Manage Specifications")
        
        # Group specifications by required/optional
        required_specs = [s for s in product.test_specifications if s.is_required]
        optional_specs = [s for s in product.test_specifications if not s.is_required]
        
        # Display required tests
        if required_specs:
            st.markdown("#### Required Tests")
            for spec in required_specs:
                display_specification_row(db, product_service, product, spec)
        
        # Display optional tests
        if optional_specs:
            st.markdown("#### Optional Tests")
            for spec in optional_specs:
                display_specification_row(db, product_service, product, spec)


def display_specification_row(db: Session, product_service: ProductService, product: Product, spec):
    """Display a single specification row with edit and delete buttons."""
    
    # Check if this specification is being edited
    editing_key = f"editing_spec_{spec.id}"
    is_editing = st.session_state.get(editing_key, False)
    
    if is_editing:
        # Edit mode - show form inputs
        col1, col2, col3, col4, col5 = st.columns([2.5, 2, 1.2, 0.6, 0.6])
        
        with col1:
            st.write(f"**{spec.lab_test_type.test_name}**")
        
        with col2:
            new_specification = st.text_input(
                "Specification",
                value=spec.specification,
                key=f"edit_spec_value_{spec.id}",
                label_visibility="collapsed"
            )
        
        with col3:
            new_test_type = st.radio(
                "Type",
                options=["REQUIRED", "OPTIONAL"],
                index=0 if spec.is_required else 1,
                key=f"edit_spec_type_{spec.id}",
                horizontal=True,
                label_visibility="collapsed"
            )
        
        with col4:
            # Save button
            if st.button("💾", key=f"save_spec_{spec.id}", help="Save changes"):
                if new_specification.strip():
                    try:
                        is_required = new_test_type == "REQUIRED"
                        product_service.update_test_specification(
                            db=db,
                            product_id=product.id,
                            test_type_id=spec.lab_test_type_id,
                            specification=new_specification.strip(),
                            is_required=is_required
                        )
                        # Clear editing state
                        del st.session_state[editing_key]
                        st.success(f"Updated {spec.lab_test_type.test_name} specification")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error updating: {str(e)}")
                else:
                    st.error("Specification cannot be empty")
        
        with col5:
            # Cancel button
            if st.button("❌", key=f"cancel_spec_{spec.id}", help="Cancel editing"):
                del st.session_state[editing_key]
                st.rerun()
    
    else:
        # Display mode - show current values with edit/delete buttons
        col1, col2, col3, col4, col5 = st.columns([2.5, 2, 1.2, 0.6, 0.6])
        
        with col1:
            st.write(f"**{spec.lab_test_type.test_name}**")
        
        with col2:
            st.write(spec.specification)
        
        with col3:
            st.write("Required" if spec.is_required else "Optional")
        
        with col4:
            # Edit button
            if st.button("✏️", key=f"edit_spec_{spec.id}", help="Edit this specification"):
                st.session_state[editing_key] = True
                st.rerun()
        
        with col5:
            # Delete button
            if st.button("🗑️", key=f"remove_spec_{spec.id}", help="Remove this specification"):
                try:
                    product_service.remove_test_specification(
                        db=db,
                        product_id=product.id,
                        test_type_id=spec.lab_test_type_id
                    )
                    st.success("Removed specification")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error removing: {str(e)}")


def show_edit_product_modal(db: Session, product_service: ProductService, product_id: int):
    """Show modal for editing a product."""
    
    @st.dialog("Edit Product", width="large")
    def edit_product_dialog():
        product = product_service.get(db, product_id)
        if not product:
            st.error("Product not found")
            return
            
        st.subheader(f"📦 Edit Product: {product.display_name}")
        
        with st.form("edit_product_form"):
            col1, col2 = st.columns(2)

            with col1:
                brand = st.text_input("Brand *", value=product.brand)
                product_name = st.text_input("Product Name *", value=product.product_name)
                flavor = st.text_input("Flavor", value=product.flavor or "")

            with col2:
                size = st.text_input("Size", value=product.size or "")
                # Convert Decimal to float for number_input
                current_serving_size = float(product.serving_size) if product.serving_size else 28.0
                serving_size = st.number_input(
                    "Serving Size (g)",
                    min_value=0.01,
                    max_value=999.99,
                    value=current_serving_size,
                    step=0.01,
                    format="%.2f"
                )
                
                # Expiry duration dropdown
                expiry_options = {
                    "6 months": 6,
                    "1 year": 12,
                    "18 months": 18,
                    "2 years": 24,
                    "3 years": 36,
                    "5 years": 60
                }
                # Find current value in options
                current_months = product.expiry_duration_months or 36
                current_index = list(expiry_options.values()).index(current_months) if current_months in expiry_options.values() else 4
                
                expiry_duration = st.selectbox(
                    "Expiry Duration *",
                    options=list(expiry_options.keys()),
                    index=current_index,
                    help="How long the product is valid from manufacturing date"
                )
                
                display_name = st.text_input("Display Name *", value=product.display_name)

            col1, col2 = st.columns(2)
            
            with col1:
                if st.form_submit_button("Update Product", type="primary"):
                    if not brand or not product_name or not display_name:
                        st.error("Brand, Product Name, and Display Name are required")
                    else:
                        try:
                            # Update product
                            updated_product = product_service.update(
                                db,
                                db_obj=product,
                                obj_in={
                                    "brand": brand,
                                    "product_name": product_name,
                                    "flavor": flavor if flavor else None,
                                    "size": size if size else None,
                                    "display_name": display_name,
                                    "serving_size": serving_size,
                                    "expiry_duration_months": expiry_options[expiry_duration],
                                }
                            )

                            st.success(f"✅ Product updated successfully: {updated_product.display_name}")
                            st.balloons()
                            
                            # Clear the editing state
                            del st.session_state.editing_product_id
                            st.rerun()

                        except Exception as e:
                            st.error(f"Error updating product: {str(e)}")
            
            with col2:
                if st.form_submit_button("Cancel"):
                    del st.session_state.editing_product_id
                    st.rerun()
    
    edit_product_dialog()
