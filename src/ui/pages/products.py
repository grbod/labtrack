"""Product management page for COA Management System."""

import streamlit as st
from sqlalchemy.orm import Session
import pandas as pd
import io

from src.services.product_service import ProductService
from src.models import Product
from src.ui.components.auth import require_role, get_current_user
from src.models.enums import UserRole


def show(db: Session):
    """Display the product management page."""
    st.title("📦 Product Management")

    # Initialize service
    product_service = ProductService()

    # Tabs for different actions
    tab1, tab2, tab3 = st.tabs(["View Products", "Add Product", "Bulk Import"])

    with tab1:
        show_products_list(db, product_service)

    with tab2:
        add_product_form(db, product_service)

    with tab3:
        bulk_import_products(db, product_service)


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
                    "Display Name": p.display_name,
                    "Created": p.created_at.strftime("%Y-%m-%d"),
                }
                for p in products
            ]
        )

        # Display with selection
        selected_rows = st.data_editor(
            df,
            hide_index=True,
            use_container_width=True,
            num_rows="fixed",
            disabled=["ID", "Created"],
            column_config={
                "ID": st.column_config.NumberColumn("ID", width="small"),
                "Created": st.column_config.DateColumn("Created", width="small"),
            },
        )

        # Edit selected product
        if st.button("Edit Selected"):
            # TODO: Implement edit functionality
            st.info("Edit functionality coming soon")

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
        "Upload an Excel file with columns: Brand, Product Name, Flavor, Size, Display Name"
    )

    # Create sample template
    template_df = pd.DataFrame(
        {
            "Brand": ["Truvani", "TTP Nutrition", "Tiger"],
            "Product Name": ["Organic Whey Protein", "Plant Protein", "Protein Powder"],
            "Flavor": ["Vanilla", "Chocolate", "Unflavored"],
            "Size": ["20 serving", "30 serving", "2 lb"],
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

                        product_service.create(
                            brand=row["Brand"],
                            product_name=row["Product Name"],
                            flavor=(
                                row.get("Flavor")
                                if not pd.isna(row.get("Flavor"))
                                else None
                            ),
                            size=(
                                row.get("Size")
                                if not pd.isna(row.get("Size"))
                                else None
                            ),
                            display_name=display_name,
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
