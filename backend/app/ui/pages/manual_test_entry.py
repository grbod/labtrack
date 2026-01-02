"""Manual test entry page for QC directors to override test results."""

import streamlit as st
from sqlalchemy.orm import Session
from sqlalchemy import and_
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional, Any

from app.models import (
    Lot, 
    LotStatus, 
    TestResult, 
    TestResultStatus,
    LabTestType,
    Product,
    LotProduct,
    User
)
from app.services.lot_service import LotService
from app.services.sample_service import SampleService
from app.services.lab_test_type_service import LabTestTypeService
from app.services.audit_service import AuditService
from app.ui.components.auth import require_role, get_current_user
from app.models.enums import UserRole
from app.utils.logger import logger


def show(db: Session):
    """Display manual test entry page."""
    
    # Check permissions - only QC Manager and Admin
    require_role([UserRole.ADMIN, UserRole.QC_MANAGER])
    
    st.title("🔬 Manual Entry")
    st.markdown("Override or enter test results for any editable lot")
    
    # Initialize services
    lot_service = LotService()
    sample_service = SampleService()
    lab_test_service = LabTestTypeService()
    audit_service = AuditService()
    
    # Add ultra-compact CSS
    add_compact_styles()
    
    # Get current user
    current_user = get_current_user()
    
    # Lot selector section
    st.markdown("### Select Lot to Edit")
    
    # Get editable lots (pending, partial results, under review)
    editable_statuses = [LotStatus.PENDING, LotStatus.PARTIAL_RESULTS, LotStatus.UNDER_REVIEW]
    editable_lots = (
        db.query(Lot)
        .filter(Lot.status.in_(editable_statuses))
        .order_by(Lot.created_at.desc())
        .all()
    )
    
    if not editable_lots:
        st.info("No lots available for editing. Only lots with status: Pending, Partial Results, or Under Review can be edited.")
        return
    
    # Create lot options for selectbox
    lot_options = {}
    for lot in editable_lots:
        # Get products for display
        products = [lp.product.display_name for lp in lot.lot_products] if lot.lot_products else ["No product"]
        product_str = ", ".join(products[:2])  # Show first 2 products
        if len(products) > 2:
            product_str += f" (+{len(products)-2} more)"
        
        display_text = f"{lot.lot_number} | Ref: {lot.reference_number} | {lot.status.value} | {product_str}"
        lot_options[display_text] = lot
    
    # Lot selector with search
    col1, col2 = st.columns([3, 1])
    
    with col1:
        selected_lot_key = st.selectbox(
            "Select Lot",
            options=list(lot_options.keys()),
            help="Only lots with Pending, Partial Results, or Under Review status can be edited"
        )
    
    with col2:
        # Quick filter by status
        status_filter = st.selectbox(
            "Filter by Status",
            options=["All"] + [s.value for s in editable_statuses],
            index=0
        )
    
    if selected_lot_key:
        selected_lot = lot_options[selected_lot_key]
        
        # Display lot information
        display_lot_info(selected_lot)
        
        st.markdown("---")
        
        # Test entry section
        st.markdown("### Test Results Entry")
        st.markdown("Enter or modify test results. Required tests are marked with ⚠️")
        
        # Get only the configured test types for this lot's products (both required and optional)
        configured_test_types = get_configured_tests_for_lot(db, selected_lot)
        
        # Get existing test results for this lot
        existing_results = {
            tr.test_type: tr for tr in 
            db.query(TestResult).filter(TestResult.lot_id == selected_lot.id).all()
        }
        
        # Get required tests based on product specifications
        required_tests = get_required_tests_for_lot(db, selected_lot)
        
        # Track changes for saving
        if 'test_changes' not in st.session_state:
            st.session_state.test_changes = {}
        
        # Check if there are any configured tests for this lot
        if not configured_test_types:
            st.warning(
                "⚠️ **No test specifications configured for this lot's products.**\n\n"
                "Please configure test specifications for the products in this lot using the "
                "**Product Management** page before entering test results."
            )
        else:
            # Display test entry grid by category
            for category, test_types in configured_test_types.items():
                display_category_tests(
                    category=category,
                    test_types=test_types,
                    existing_results=existing_results,
                    required_tests=required_tests,
                    lot_id=selected_lot.id
                )
        
        # Save buttons (only show if there are configured tests)
        if configured_test_types:
            st.markdown("---")
            col1, col2, col3 = st.columns([1, 1, 2])
            
            with col1:
                if st.button("💾 Save All Changes", type="primary", use_container_width=True):
                    save_test_results(db, selected_lot, st.session_state.test_changes, current_user["id"])
            
            with col2:
                if st.button("❌ Cancel", use_container_width=True):
                    st.session_state.test_changes = {}
                    st.rerun()
            
            with col3:
                if st.session_state.test_changes:
                    st.info(f"📝 {len(st.session_state.test_changes)} changes pending")


def add_compact_styles():
    """Add ultra-compact CSS styles."""
    st.markdown("""
    <style>
    /* Ultra-compact test entry grid */
    .test-grid {
        margin: 0;
        padding: 0;
    }
    
    /* Compact input fields */
    .stNumberInput > div > div > input,
    .stTextInput > div > div > input {
        padding: 2px 6px !important;
        height: 24px !important;
        font-size: 12px !important;
    }
    
    /* Remove margins from columns */
    [data-testid="column"] {
        padding: 0 2px !important;
    }
    
    /* Compact selectbox */
    .stSelectbox > div > div {
        min-height: 24px !important;
    }
    
    /* Ultra-thin rows */
    .element-container {
        margin: 0 !important;
        padding: 0 !important;
    }
    
    /* Compact checkboxes */
    .stCheckbox {
        margin: 0 !important;
        padding: 0 !important;
    }
    
    .stCheckbox > label {
        font-size: 12px !important;
        margin: 0 !important;
    }
    </style>
    """, unsafe_allow_html=True)


def display_lot_info(lot: Lot):
    """Display lot information in compact format."""
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"**Lot #:** {lot.lot_number}")
        st.markdown(f"**Type:** {lot.lot_type.value}")
    
    with col2:
        st.markdown(f"**Reference:** {lot.reference_number}")
        st.markdown(f"**Status:** {lot.status.value}")
    
    with col3:
        st.markdown(f"**Mfg Date:** {lot.mfg_date.strftime('%Y-%m-%d') if lot.mfg_date else 'N/A'}")
        st.markdown(f"**Exp Date:** {lot.exp_date.strftime('%Y-%m-%d') if lot.exp_date else 'N/A'}")
    
    with col4:
        products = [lp.product.display_name for lp in lot.lot_products] if lot.lot_products else []
        st.markdown(f"**Products:** {', '.join(products) if products else 'None'}")
        st.markdown(f"**Tests:** {len(lot.test_results)} recorded")


def get_required_tests_for_lot(db: Session, lot: Lot) -> set:
    """Get required test types for a lot based on its products."""
    required_test_ids = set()
    
    # Get all products for this lot
    for lot_product in lot.lot_products:
        product = lot_product.product
        
        # Get required test specifications for this product
        for spec in product.test_specifications:
            if spec.is_required:
                required_test_ids.add(spec.lab_test_type_id)
    
    return required_test_ids


def get_configured_tests_for_lot(db: Session, lot: Lot) -> Dict[str, List[LabTestType]]:
    """Get all configured test types for a lot based on its products (both required and optional)."""
    configured_test_ids = set()
    
    # Get all products for this lot
    for lot_product in lot.lot_products:
        product = lot_product.product
        
        # Get all test specifications for this product (both required and optional)
        for spec in product.test_specifications:
            configured_test_ids.add(spec.lab_test_type_id)
    
    # If no configured tests found, return empty dict
    if not configured_test_ids:
        return {}
    
    # Get the actual LabTestType objects and group by category
    configured_tests = db.query(LabTestType).filter(
        LabTestType.id.in_(configured_test_ids),
        LabTestType.is_active == True
    ).order_by(
        LabTestType.test_category,
        LabTestType.test_name
    ).all()
    
    # Group by category
    grouped = {}
    for test in configured_tests:
        if test.test_category not in grouped:
            grouped[test.test_category] = []
        grouped[test.test_category].append(test)
    
    return grouped


def display_category_tests(
    category: str,
    test_types: List[LabTestType],
    existing_results: Dict[str, TestResult],
    required_tests: set,
    lot_id: int
):
    """Display test entry grid for a category."""
    
    # Category header
    st.markdown(f"<h4 style='margin: 8px 0 4px 0; font-size: 14px;'>📁 {category}</h4>", unsafe_allow_html=True)
    
    # Create columns for header
    header_cols = st.columns([0.5, 3, 1.5, 1.5, 2, 1])
    
    with header_cols[0]:
        st.markdown("<span style='font-size: 11px; font-weight: bold;'>Include</span>", unsafe_allow_html=True)
    with header_cols[1]:
        st.markdown("<span style='font-size: 11px; font-weight: bold;'>Test Name</span>", unsafe_allow_html=True)
    with header_cols[2]:
        st.markdown("<span style='font-size: 11px; font-weight: bold;'>Value</span>", unsafe_allow_html=True)
    with header_cols[3]:
        st.markdown("<span style='font-size: 11px; font-weight: bold;'>Unit</span>", unsafe_allow_html=True)
    with header_cols[4]:
        st.markdown("<span style='font-size: 11px; font-weight: bold;'>Method</span>", unsafe_allow_html=True)
    with header_cols[5]:
        st.markdown("<span style='font-size: 11px; font-weight: bold;'>Status</span>", unsafe_allow_html=True)
    
    # Separator
    st.markdown("<div style='height: 1px; background: #444; margin: 2px 0;'></div>", unsafe_allow_html=True)
    
    # Display each test
    for test_type in test_types:
        display_test_row(test_type, existing_results, required_tests, lot_id)
    
    # Category spacing
    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)


def display_test_row(
    test_type: LabTestType,
    existing_results: Dict[str, TestResult],
    required_tests: set,
    lot_id: int
):
    """Display a single test row with input fields."""
    
    # Check if this test is required
    is_required = test_type.id in required_tests
    
    # Get existing result if any
    existing_result = existing_results.get(test_type.test_name)
    
    # Create unique keys for this test
    key_prefix = f"test_{lot_id}_{test_type.id}"
    
    # Create columns
    cols = st.columns([0.5, 3, 1.5, 1.5, 2, 1])
    
    # Include checkbox
    with cols[0]:
        # Default checked if required or has existing value
        default_checked = is_required or existing_result is not None
        include = st.checkbox(
            "",
            value=default_checked,
            key=f"{key_prefix}_include",
            disabled=is_required,  # Cannot uncheck required tests
            label_visibility="collapsed"
        )
    
    # Test name with required indicator
    with cols[1]:
        name_display = test_type.test_name
        if is_required:
            name_display = f"⚠️ {name_display}"
        st.markdown(f"<span style='font-size: 12px;'>{name_display}</span>", unsafe_allow_html=True)
    
    # Value input
    with cols[2]:
        if include:
            current_value = existing_result.result_value if existing_result else ""
            new_value = st.text_input(
                "",
                value=current_value,
                key=f"{key_prefix}_value",
                placeholder="Enter value",
                label_visibility="collapsed"
            )
            
            # Track changes
            if new_value != current_value:
                if key_prefix not in st.session_state.test_changes:
                    st.session_state.test_changes[key_prefix] = {}
                st.session_state.test_changes[key_prefix]['value'] = new_value
        else:
            st.markdown("<span style='font-size: 11px; color: #666;'>-</span>", unsafe_allow_html=True)
    
    # Unit
    with cols[3]:
        if include:
            # Common units based on test type
            if test_type.default_unit == "Positive/Negative":
                units = ["Positive/Negative", "Present/Absent", "Detected/Not Detected"]
            elif test_type.default_unit in ["CFU/g", "CFU/mL"]:
                units = ["CFU/g", "CFU/mL", "CFU/25g"]
            elif test_type.default_unit in ["ppm", "ppb"]:
                units = ["ppm", "ppb", "mg/kg", "μg/kg"]
            else:
                units = [test_type.default_unit, "%", "mg/g", "IU/g"]
            
            current_unit = existing_result.unit if existing_result else test_type.default_unit
            unit = st.selectbox(
                "",
                options=units,
                index=units.index(current_unit) if current_unit in units else 0,
                key=f"{key_prefix}_unit",
                label_visibility="collapsed"
            )
            
            # Track changes
            if unit != current_unit:
                if key_prefix not in st.session_state.test_changes:
                    st.session_state.test_changes[key_prefix] = {}
                st.session_state.test_changes[key_prefix]['unit'] = unit
        else:
            st.markdown("<span style='font-size: 11px; color: #666;'>-</span>", unsafe_allow_html=True)
    
    # Method
    with cols[4]:
        if include:
            current_method = existing_result.method if existing_result else test_type.test_method
            method = st.text_input(
                "",
                value=current_method or "",
                key=f"{key_prefix}_method",
                placeholder="Test method",
                label_visibility="collapsed"
            )
            
            # Track changes
            if method != current_method:
                if key_prefix not in st.session_state.test_changes:
                    st.session_state.test_changes[key_prefix] = {}
                st.session_state.test_changes[key_prefix]['method'] = method
        else:
            st.markdown("<span style='font-size: 11px; color: #666;'>-</span>", unsafe_allow_html=True)
    
    # Status
    with cols[5]:
        if existing_result:
            status_color = "#4CAF50" if existing_result.status == TestResultStatus.APPROVED else "#FFA500"
            st.markdown(
                f"<span style='font-size: 11px; color: {status_color};'>{existing_result.status.value}</span>", 
                unsafe_allow_html=True
            )
        else:
            st.markdown("<span style='font-size: 11px; color: #666;'>New</span>", unsafe_allow_html=True)


def save_test_results(db: Session, lot: Lot, changes: Dict[str, Dict], user_id: int):
    """Save all test result changes."""
    
    if not changes:
        st.warning("No changes to save")
        return
    
    try:
        # Process each changed test
        updated_count = 0
        created_count = 0
        
        for key, change_data in changes.items():
            # Parse the key to get lot_id and test_type_id
            parts = key.split('_')
            test_type_id = int(parts[-1])
            
            # Get the test type
            test_type = db.query(LabTestType).filter(LabTestType.id == test_type_id).first()
            if not test_type:
                continue
            
            # Check if test result already exists
            existing = db.query(TestResult).filter(
                and_(
                    TestResult.lot_id == lot.id,
                    TestResult.test_type == test_type.test_name
                )
            ).first()
            
            # Get the form values
            include_key = f"test_{lot.id}_{test_type_id}_include"
            value_key = f"test_{lot.id}_{test_type_id}_value"
            unit_key = f"test_{lot.id}_{test_type_id}_unit"
            method_key = f"test_{lot.id}_{test_type_id}_method"
            
            include = st.session_state.get(include_key, False)
            value = st.session_state.get(value_key, "")
            unit = st.session_state.get(unit_key, test_type.default_unit)
            method = st.session_state.get(method_key, test_type.test_method)
            
            if include and value:  # Only save if included and has value
                if existing:
                    # Update existing
                    existing.result_value = value
                    existing.unit = unit
                    existing.method = method
                    existing.status = TestResultStatus.DRAFT
                    updated_count += 1
                else:
                    # Create new
                    new_result = TestResult(
                        lot_id=lot.id,
                        test_type=test_type.test_name,
                        result_value=value,
                        unit=unit,
                        method=method,
                        status=TestResultStatus.DRAFT,
                        test_date=datetime.now().date(),
                        confidence_score=1.0  # Manual entry = high confidence
                    )
                    db.add(new_result)
                    created_count += 1
            elif existing and not include:
                # Delete if unchecked
                db.delete(existing)
        
        # Update lot status based on test completeness
        update_lot_status(db, lot)
        
        # Commit changes
        db.commit()
        
        # Clear changes
        st.session_state.test_changes = {}
        
        # Log audit
        logger.info(f"User {user_id} manually updated test results for lot {lot.lot_number}: "
                   f"{updated_count} updated, {created_count} created")
        
        st.success(f"✅ Saved successfully! {updated_count} updated, {created_count} created")
        st.balloons()
        st.rerun()
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error saving test results: {e}")
        st.error(f"Error saving: {str(e)}")


def update_lot_status(db: Session, lot: Lot):
    """Update lot status based on test completeness."""
    
    # Get all test results
    test_results = db.query(TestResult).filter(TestResult.lot_id == lot.id).all()
    
    if not test_results:
        lot.status = LotStatus.PENDING
    else:
        # Check if all required tests have results
        required_tests = get_required_tests_for_lot(db, lot)
        
        # Get test type names for required tests
        required_test_names = set()
        for test_id in required_tests:
            test_type = db.query(LabTestType).filter(LabTestType.id == test_id).first()
            if test_type:
                required_test_names.add(test_type.test_name)
        
        # Check which required tests have results
        completed_test_names = {tr.test_type for tr in test_results if tr.result_value}
        
        if required_test_names.issubset(completed_test_names):
            # All required tests completed
            lot.status = LotStatus.UNDER_REVIEW
        else:
            # Some tests missing
            lot.status = LotStatus.PARTIAL_RESULTS