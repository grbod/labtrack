"""Lab Test Types management page."""

import streamlit as st
from sqlalchemy.orm import Session
import pandas as pd
from app.services.lab_test_type_service import LabTestTypeService
from app.models import LabTestType
from app.ui.components.auth import require_role
from app.models.enums import UserRole


def show(db: Session):
    """Display lab test types management page."""
    
    # Check permissions
    require_role([UserRole.ADMIN, UserRole.QC_MANAGER])
    
    st.title("🧪 Lab Test Types")
    
    # Initialize service
    service = LabTestTypeService()
    
    # Tabs
    tab1, tab2, tab3 = st.tabs(["View Test Types", "Add New Test", "Import/Export"])
    
    with tab1:
        view_test_types(db, service)
    
    with tab2:
        add_test_type(db, service)
        
    with tab3:
        import_export_tests(db, service)


def view_test_types(db: Session, service: LabTestTypeService):
    """View and manage existing test types."""
    
    # Get all tests grouped by category (include inactive for filtering)
    grouped_tests = service.get_all_grouped(db, include_inactive=True)
    
    if not grouped_tests:
        st.info("No lab test types defined yet. Add some to get started!")
        return
    
    # Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Category filter
        categories = ["All"] + list(grouped_tests.keys())
        selected_category = st.selectbox("Filter by Category", categories)
    
    with col2:
        # Status filter
        status_filter = st.selectbox(
            "Show Tests", 
            ["Active Only", "All Tests", "Inactive Only"],
            help="Choose which tests to display"
        )
    
    with col3:
        # Search
        search_term = st.text_input("Search test types", placeholder="E.g., E. coli, Lead")
    
    # Help text for inactive tests
    if status_filter == "Inactive Only":
        st.info("💡 **Inactive tests** are hidden from product specifications but can be reactivated using the ▶️ button.")
    elif status_filter == "All Tests":
        st.info("💡 Use the **Toggle** column to activate (▶️) or deactivate (⏸️) tests. Only active tests appear when adding specs to products.")
    
    # Display tests by category
    for category, tests in grouped_tests.items():
        if selected_category != "All" and category != selected_category:
            continue
        
        # Filter by status
        if status_filter == "Active Only":
            tests = [t for t in tests if t.is_active]
        elif status_filter == "Inactive Only":
            tests = [t for t in tests if not t.is_active]
        # "All Tests" shows everything - no filtering needed
            
        # Filter by search
        if search_term:
            tests = [t for t in tests if search_term.lower() in t.test_name.lower()]
            
        if not tests:
            continue
            
        st.subheader(f"📁 {category}")
        
        # Create DataFrame for this category
        df_data = []
        for test in tests:
            df_data.append({
                "ID": test.id,
                "Test Name": test.test_name,
                "Unit": test.default_unit or "-",
                "Default Spec": test.default_specification or "-",
                "Method": test.test_method or "-",
                "Active": "✓" if test.is_active else "✗",
            })
        
        df = pd.DataFrame(df_data)
        
        # Display table
        cols = st.columns([0.4, 2.2, 1, 1.3, 1.8, 0.7, 0.7, 0.7, 0.7])
        
        # Header
        cols[0].markdown("**ID**")
        cols[1].markdown("**Test Name**")
        cols[2].markdown("**Unit**")
        cols[3].markdown("**Default Spec**")
        cols[4].markdown("**Method**")
        cols[5].markdown("**Active**")
        cols[6].markdown("**Edit**")
        cols[7].markdown("**Toggle**")
        cols[8].markdown("**Remove**")
        
        # Add a separator
        st.markdown("---")
        
        # Data rows
        for idx, (_, row) in enumerate(df.iterrows()):
            test = tests[idx]
            cols = st.columns([0.4, 2.2, 1, 1.3, 1.8, 0.7, 0.7, 0.7, 0.7])
            
            cols[0].write(row["ID"])
            cols[1].write(row["Test Name"])
            cols[2].write(row["Unit"])
            cols[3].write(row["Default Spec"])
            cols[4].write(row["Method"])
            cols[5].write(row["Active"])
            
            # Edit button
            if cols[6].button("✏️", key=f"edit_{test.id}", help=f"Edit {test.test_name}"):
                st.session_state.editing_test_id = test.id
                st.rerun()
            
            # Toggle active/inactive button
            if test.is_active:
                toggle_icon = "⏸️"
                toggle_help = f"Deactivate {test.test_name}"
                toggle_action = "deactivate"
            else:
                toggle_icon = "▶️"
                toggle_help = f"Activate {test.test_name}"
                toggle_action = "activate"
            
            if cols[7].button(toggle_icon, key=f"toggle_{test.id}", help=toggle_help):
                try:
                    service.update_lab_test_type(
                        db=db,
                        test_type_id=test.id,
                        is_active=not test.is_active
                    )
                    action_text = "activated" if toggle_action == "activate" else "deactivated"
                    st.success(f"{action_text.title()} {test.test_name}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {str(e)}")
            
            # Delete button
            if cols[8].button("🗑️", key=f"del_{test.id}", help=f"Delete {test.test_name}"):
                if st.session_state.get(f"confirm_delete_{test.id}", False):
                    try:
                        service.delete_lab_test_type(db, test.id)
                        st.success(f"Deleted {test.test_name}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Cannot delete: {str(e)}")
                else:
                    st.session_state[f"confirm_delete_{test.id}"] = True
                    st.warning("Click again to confirm deletion")
        
        st.markdown("")  # Add some spacing between categories
    
    # Edit modal
    if "editing_test_id" in st.session_state:
        edit_test_modal(db, service, st.session_state.editing_test_id)


def add_test_type(db: Session, service: LabTestTypeService):
    """Add new lab test type."""
    
    st.subheader("Add New Lab Test Type")
    
    with st.form("add_test_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            name = st.text_input(
                "Test Name *",
                placeholder="E.g., E. coli, Total Plate Count",
                help="Official name of the test"
            )
            
            # Define categories manually since we can't access class constants
            categories = [
                "Microbiological",
                "Heavy Metals", 
                "Nutritional",
                "Allergens",
                "Physical",
                "Chemical",
                "Pesticides",
                "Organoleptic"
            ]
            
            category = st.selectbox(
                "Category *",
                options=categories,
                help="Test category for grouping"
            )
            
            # Define units manually
            units = [
                "CFU/g",
                "CFU/mL",
                "ppm",
                "ppb",
                "%",
                "mg/g",
                "Positive/Negative",
                "Present/Absent",
                "IU/g",
                "Qualitative"
            ]
            
            unit = st.selectbox(
                "Unit of Measurement *",
                options=units,
                help="How results are measured"
            )
        
        with col2:
            method = st.text_input(
                "Default Method",
                placeholder="E.g., USP <2021>, AOAC 991.14",
                help="Standard test method (optional)"
            )
            
            default_spec = st.text_input(
                "Default Specification",
                placeholder="E.g., < 10,000 CFU/g, Negative, < 0.5 ppm",
                help="Default specification that pre-populates when adding to products"
            )
            
            # Abbreviations
            abbrev_input = st.text_area(
                "Alternative Names/Abbreviations",
                placeholder="One per line\nE.g., for E. coli:\nE.coli\nEscherichia coli\nE coli",
                help="Alternative names for PDF parsing"
            )
            
            is_active = st.checkbox(
                "Active",
                value=True,
                help="Whether this test type is currently available"
            )
        
        description = st.text_area(
            "Description",
            placeholder="Optional description or notes about this test",
            help="Additional information about the test"
        )
        
        submitted = st.form_submit_button("Add Test Type", type="primary")
        
        if submitted:
            if not name:
                st.error("Test name is required")
            else:
                try:
                    # Parse abbreviations
                    abbreviations = None
                    if abbrev_input:
                        abbreviations = [
                            line.strip() 
                            for line in abbrev_input.split('\n') 
                            if line.strip()
                        ]
                    
                    # Create test type
                    test_type = service.create_lab_test_type(
                        db=db,
                        name=name,
                        category=category,
                        unit_of_measurement=unit,
                        default_method=method,
                        default_specification=default_spec if default_spec else None,
                        description=description,
                        abbreviations=abbreviations,
                        is_active=is_active
                    )
                    
                    st.success(f"✅ Added lab test type: {name}")
                    st.balloons()
                    
                    # Clear form
                    st.rerun()
                    
                except ValueError as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"Error adding test type: {str(e)}")


def edit_test_modal(db: Session, service: LabTestTypeService, test_id: int):
    """Edit test type in modal."""
    
    @st.dialog("Edit Lab Test Type")
    def edit_dialog():
        test = service.get(db, test_id)
        if not test:
            st.error("Test type not found")
            return
        
        with st.form("edit_test_form"):
            name = st.text_input("Test Name *", value=test.test_name)
            
            # Define categories manually
            categories = [
                "Microbiological",
                "Heavy Metals", 
                "Nutritional",
                "Allergens",
                "Physical",
                "Chemical",
                "Pesticides",
                "Organoleptic"
            ]
            
            category = st.selectbox(
                "Category *",
                options=categories,
                index=categories.index(test.test_category) if test.test_category in categories else 0
            )
            
            # Define units manually
            units = [
                "CFU/g",
                "CFU/mL",
                "ppm",
                "ppb",
                "%",
                "mg/g",
                "Positive/Negative",
                "Present/Absent",
                "IU/g",
                "Qualitative"
            ]
            
            unit = st.selectbox(
                "Unit of Measurement *",
                options=units,
                index=units.index(test.default_unit) if test.default_unit in units else 0
            )
            
            method = st.text_input(
                "Default Method",
                value=test.test_method or ""
            )
            
            default_spec = st.text_input(
                "Default Specification",
                value=test.default_specification or "",
                placeholder="E.g., < 10,000 CFU/g, Negative, < 0.5 ppm",
                help="Default specification that pre-populates when adding to products"
            )
            
            # Load abbreviations with null check
            abbrev_text = ""
            if hasattr(test, 'abbreviations') and test.abbreviations:
                try:
                    import json
                    abbrevs = json.loads(test.abbreviations)
                    abbrev_text = "\n".join(abbrevs)
                except:
                    pass
            
            abbrev_input = st.text_area(
                "Alternative Names/Abbreviations",
                value=abbrev_text
            )
            
            is_active = st.checkbox(
                "Active",
                value=test.is_active
            )
            
            description = st.text_area(
                "Description",
                value=test.description or ""
            )
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.form_submit_button("Save Changes", type="primary"):
                    try:
                        # Parse abbreviations
                        abbreviations = None
                        if abbrev_input:
                            abbreviations = [
                                line.strip() 
                                for line in abbrev_input.split('\n') 
                                if line.strip()
                            ]
                        
                        # Update test type
                        service.update_lab_test_type(
                            db=db,
                            test_type_id=test_id,
                            test_name=name,
                            test_category=category,
                            default_unit=unit,
                            test_method=method,
                            default_specification=default_spec if default_spec else None,
                            description=description,
                            is_active=is_active
                        )
                        
                        # Update abbreviations if field exists
                        if hasattr(test, 'abbreviations'):
                            if abbreviations:
                                import json
                                test.abbreviations = json.dumps(abbreviations)
                            else:
                                test.abbreviations = None
                            db.commit()
                        
                        st.success("Updated successfully!")
                        del st.session_state.editing_test_id
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"Error updating: {str(e)}")
            
            with col2:
                if st.form_submit_button("Cancel"):
                    del st.session_state.editing_test_id
                    st.rerun()
    
    edit_dialog()


def import_export_tests(db: Session, service: LabTestTypeService):
    """Import/export lab test types."""
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Export Test Types")
        
        export_option = st.radio(
            "Export which tests?",
            ["Active Only", "All Tests"],
            horizontal=True
        )
        
        if st.button("📥 Export to Excel", use_container_width=True):
            # Get tests based on selection
            query = db.query(LabTestType)
            if export_option == "Active Only":
                query = query.filter(LabTestType.is_active == True)
            
            all_tests = query.order_by(
                LabTestType.test_category,
                LabTestType.test_name
            ).all()
            
            if all_tests:
                # Create dataframe
                df_data = []
                for test in all_tests:
                    # Get abbreviations with null check
                    abbrev_str = ""
                    if hasattr(test, 'abbreviations') and test.abbreviations:
                        try:
                            import json
                            abbrevs = json.loads(test.abbreviations)
                            abbrev_str = "; ".join(abbrevs)
                        except:
                            pass
                    
                    df_data.append({
                        "Name": test.test_name,
                        "Category": test.test_category,
                        "Unit": test.default_unit,
                        "Default Specification": test.default_specification or "",
                        "Method": test.test_method or "",
                        "Abbreviations": abbrev_str,
                        "Description": test.description or "",
                        "Active": test.is_active
                    })
                
                df = pd.DataFrame(df_data)
                
                # Export
                import io
                buffer = io.BytesIO()
                df.to_excel(buffer, index=False)
                
                st.download_button(
                    label="Download Excel",
                    data=buffer.getvalue(),
                    file_name="lab_test_types.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.info("No test types to export")
    
    with col2:
        st.subheader("Import Test Types")
        
        uploaded_file = st.file_uploader(
            "Choose Excel file",
            type=["xlsx", "xls"],
            help="File should have columns: Name, Category, Unit, Default Specification, Method, Abbreviations, Description, Active"
        )
        
        if uploaded_file:
            try:
                df = pd.read_excel(uploaded_file)
                
                st.write("Preview:")
                st.dataframe(df.head(), use_container_width=True)
                
                if st.button("Import Test Types", type="primary"):
                    imported = 0
                    errors = []
                    
                    for _, row in df.iterrows():
                        try:
                            # Parse abbreviations
                            abbreviations = None
                            if pd.notna(row.get("Abbreviations")):
                                abbreviations = [
                                    a.strip() 
                                    for a in str(row["Abbreviations"]).split(";")
                                    if a.strip()
                                ]
                            
                            # Get default specification and active status  
                            default_spec = None
                            if "Default Specification" in row and pd.notna(row["Default Specification"]):
                                default_spec = str(row["Default Specification"]).strip()
                                if not default_spec:
                                    default_spec = None
                            
                            is_active = True  # Default to active
                            if "Active" in row and pd.notna(row["Active"]):
                                # Handle both boolean and string representations
                                active_val = row["Active"]
                                if isinstance(active_val, str):
                                    is_active = active_val.lower() in ['true', '1', 'yes', 'active']
                                else:
                                    is_active = bool(active_val)
                            
                            service.create_lab_test_type(
                                db=db,
                                name=row["Name"],
                                category=row["Category"],
                                unit_of_measurement=row["Unit"],
                                default_method=row.get("Method") if pd.notna(row.get("Method")) else None,
                                default_specification=default_spec,
                                description=row.get("Description") if pd.notna(row.get("Description")) else None,
                                abbreviations=abbreviations,
                                is_active=is_active
                            )
                            imported += 1
                            
                        except Exception as e:
                            errors.append(f"{row['Name']}: {str(e)}")
                    
                    st.success(f"✅ Imported {imported} test types")
                    
                    if errors:
                        with st.expander("Import Errors"):
                            for error in errors:
                                st.error(error)
                    
                    st.rerun()
                    
            except Exception as e:
                st.error(f"Error reading file: {str(e)}")