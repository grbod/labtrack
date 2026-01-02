"""Approval dashboard for test results."""

import streamlit as st
from sqlalchemy.orm import Session
import pandas as pd
from datetime import datetime

from app.services.approval_service import ApprovalService
from app.services.sample_service import SampleService
from app.models import TestResult, TestResultStatus, Lot
from app.ui.components.auth import get_current_user, require_role
from app.models.enums import UserRole


def check_test_result_pass(result: TestResult) -> bool:
    """Check if a test result passes based on specification."""
    if not result.specification:
        return True  # If no spec, assume pass
    
    # Get the specification and result value
    spec = result.specification.strip().lower()
    value = result.result_value.strip().lower() if result.result_value else ""
    
    # Handle common "pass" values
    if value in ["nd", "not detected", "absent", "negative", "none", "nil"]:
        return True
    
    # Handle "< X" specifications
    if spec.startswith("<"):
        # If result also starts with "<", it's passing
        if value.startswith("<"):
            return True
        # Try to extract numeric values
        try:
            spec_limit = float(spec[1:].strip())
            if value.replace(".", "").replace("-", "").isdigit():
                result_val = float(value)
                return result_val < spec_limit
        except:
            pass
    
    # Handle "> X" specifications
    if spec.startswith(">"):
        # If result also starts with ">", it's passing
        if value.startswith(">"):
            return True
        # Try to extract numeric values
        try:
            spec_limit = float(spec[1:].strip())
            if value.replace(".", "").replace("-", "").isdigit():
                result_val = float(value)
                return result_val > spec_limit
        except:
            pass
    
    # Handle range specifications (e.g., "10-20")
    if "-" in spec and not spec.startswith("-"):
        try:
            parts = spec.split("-")
            if len(parts) == 2:
                min_val = float(parts[0].strip())
                max_val = float(parts[1].strip())
                if value.replace(".", "").replace("-", "").isdigit():
                    result_val = float(value)
                    return min_val <= result_val <= max_val
        except:
            pass
    
    # Handle exact match specifications
    if spec == value:
        return True
    
    # Handle "absent" specifications
    if "absent" in spec and value in ["nd", "not detected", "absent", "negative"]:
        return True
    
    # Handle "negative" specifications
    if "negative" in spec and value in ["negative", "nd", "not detected", "absent"]:
        return True
    
    # Default: if we can't determine pass/fail, assume pass
    # This prevents false rejections for complex specifications
    return True


def show(db: Session):
    """Display the approval dashboard page."""
    st.title("✅ Approval Dashboard")

    # Check role
    user = get_current_user()
    if user["role"] not in [UserRole.ADMIN, UserRole.QC_MANAGER]:
        st.error("You don't have permission to approve test results")
        return

    # Initialize services
    approval_service = ApprovalService()
    sample_service = SampleService()

    # Stats
    col1, col2, col3, col4 = st.columns(4)

    pending = approval_service.get_pending_approvals(db)

    with col1:
        st.metric("Pending Approval", len(pending))

    with col2:
        # Get today's approvals from history
        today_history = approval_service.get_approval_history(db, days_back=1)
        today_approved = len([h for h in today_history if h.get('action') == 'approve' and 
                            h.get('timestamp') and h['timestamp'].date() == datetime.now().date()])
        st.metric("Approved Today", today_approved)

    with col3:
        # Get today's rejections from history
        today_rejected = len([h for h in today_history if h.get('action') == 'reject' and 
                            h.get('timestamp') and h['timestamp'].date() == datetime.now().date()])
        st.metric("Rejected Today", today_rejected)

    with col4:
        # Get user's total approvals from history
        user_history = approval_service.get_approval_history(db, user_id=user["id"], days_back=365)
        my_approvals = len(user_history)
        st.metric("Your Total Approvals", my_approvals)

    st.divider()

    # Tabs
    tab1, tab2, tab3 = st.tabs(
        ["Pending Approvals", "Approval History", "Bulk Approval"]
    )

    with tab1:
        show_pending_approvals(db, approval_service)

    with tab2:
        show_approval_history(db, approval_service)

    with tab3:
        bulk_approval(db, approval_service)


def show_pending_approvals(db: Session, approval_service: ApprovalService):
    """Show test results pending approval with card-based layout."""
    st.subheader("Test Results Pending Approval")

    # Get pending test results grouped by lot
    pending_results = (
        db.query(TestResult)
        .filter(
            TestResult.status == TestResultStatus.DRAFT
        )
        .order_by(TestResult.created_at.desc())
        .all()
    )

    if not pending_results:
        st.success("No test results pending approval!")
        return

    # Group by lot
    lots_with_pending = {}
    for result in pending_results:
        lot_id = result.lot_id
        if lot_id not in lots_with_pending:
            lots_with_pending[lot_id] = {"lot": result.lot, "results": []}
        lots_with_pending[lot_id]["results"].append(result)

    # Display each lot as a card
    for lot_id, lot_data in lots_with_pending.items():
        lot = lot_data["lot"]
        results = lot_data["results"]
        
        # Create a card-like container
        with st.container():
            # Card styling
            st.markdown("""
                <style>
                    .lot-card {
                        border: 1px solid #333;
                        border-radius: 10px;
                        padding: 20px;
                        margin-bottom: 20px;
                        background-color: #0E1117;
                    }
                </style>
            """, unsafe_allow_html=True)
            
            # Card header with lot info
            col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
            
            with col1:
                st.markdown(f"### Lot: {lot.lot_number}")
                st.markdown(f"**Reference:** {lot.reference_number}")
                products = ", ".join([lp.product.display_name for lp in lot.lot_products])
                st.markdown(f"**Product(s):** {products}")
            
            with col2:
                st.markdown("**Dates**")
                st.text(f"Mfg: {lot.mfg_date.strftime('%Y-%m-%d') if lot.mfg_date else 'N/A'}")
                st.text(f"Exp: {lot.exp_date.strftime('%Y-%m-%d') if lot.exp_date else 'N/A'}")
            
            with col3:
                # Check if all tests are passing
                passing_tests = [r for r in results if check_test_result_pass(r)]
                failing_tests = [r for r in results if not check_test_result_pass(r)]
                all_passing = len(failing_tests) == 0
                
                if all_passing:
                    st.success("✓ All Tests Passing")
                else:
                    st.error(f"✗ {len(failing_tests)} Tests Failing")
            
            with col4:
                draft_count = len([r for r in results if r.status == TestResultStatus.DRAFT])
                st.metric("Status", f"{draft_count} Draft")
            
            st.divider()
            
            # Check test completeness and show missing required tests if any
            completeness = approval_service.check_test_completeness(db, lot_id)
            if not completeness["is_complete"]:
                with st.expander("Missing Required Tests", expanded=True):
                    st.error("⚠️ The following required tests are missing:")
                    for test_name in completeness["missing_required"]:
                        st.write(f"• {test_name}")
            
            # Test results using AG-Grid
            st.markdown("#### Test Results")
            
            # Prepare data for AG-Grid
            results_data = []
            for result in results:
                is_passing = check_test_result_pass(result)
                results_data.append({
                    "Test Name": result.test_type,
                    "Value": result.result_value,
                    "Unit": result.unit,
                    "Specification": result.specification or "-",
                    "Pass/Fail": "Pass" if is_passing else "Fail",
                    "Confidence": f"{result.confidence_score:.1%}" if result.confidence_score else "-",
                    "Test Date": result.test_date.strftime("%Y-%m-%d") if result.test_date else "-",
                    "Source": result.pdf_source or "-"
                })
            
            df = pd.DataFrame(results_data)
            
            # Style the dataframe with custom CSS
            def style_pass_fail(row):
                """Style rows based on Pass/Fail status."""
                styles = [''] * len(row)
                pass_fail_idx = df.columns.get_loc('Pass/Fail')
                
                if row['Pass/Fail'] == 'Pass':
                    styles[pass_fail_idx] = 'background-color: #28a745; color: white; font-weight: bold'
                elif row['Pass/Fail'] == 'Fail':
                    styles[pass_fail_idx] = 'background-color: #dc3545; color: white; font-weight: bold'
                
                return styles
            
            # Apply styling
            styled_df = df.style.apply(style_pass_fail, axis=1)
            
            # Display styled dataframe
            st.dataframe(
                styled_df,
                use_container_width=True,
                hide_index=True,
                height=200,
                column_config={
                    "Pass/Fail": st.column_config.TextColumn(
                        "Pass/Fail",
                        help="Test result status",
                        width="small"
                    ),
                    "Confidence": st.column_config.TextColumn(
                        "Confidence",
                        help="AI parsing confidence score",
                        width="small"
                    ),
                    "Test Date": st.column_config.TextColumn(
                        "Test Date",
                        width="small"
                    )
                }
            )
            
            st.divider()
            
            # Lot-level approval actions
            col1, col2 = st.columns([1, 1])
            
            with col1:
                if st.button(
                    "✅ APPROVE LOT",
                    key=f"approve_{lot_id}",
                    type="primary",
                    use_container_width=True,
                    help="Approve all test results for this lot"
                ):
                    # Confirmation dialog
                    try:
                        # Check if lot can be approved
                        validation = approval_service.validate_lot_for_approval(db, lot_id)
                        
                        if not validation["can_approve"]:
                            st.error(f"Cannot approve lot: {validation['reason']}")
                            if validation["missing_tests"]:
                                st.write("Missing required tests:")
                                for test in validation["missing_tests"]:
                                    st.write(f"• {test}")
                        else:
                            # Approve all test results
                            approved = approval_service.bulk_approve_results(
                                db, [r.id for r in results], get_current_user()["id"]
                            )
                            
                            # Refresh lot to get updated status
                            db.refresh(lot)
                            
                            st.success(f"✅ Lot {lot.lot_number} approved successfully! Status: {lot.status.value}")
                            st.balloons()
                            
                            # Show debug info
                            with st.expander("Debug Info"):
                                st.write(f"Lot ID: {lot.id}")
                                st.write(f"Lot Status: {lot.status.value}")
                                st.write(f"Generate COA: {lot.generate_coa}")
                                st.write(f"Approved test results: {len(approved)}")
                            
                            st.rerun()
                        
                    except Exception as e:
                        st.error(f"Error approving lot: {str(e)}")
            
            with col2:
                rejection_reason = st.text_input(
                    "Rejection reason",
                    placeholder="Required for rejection",
                    key=f"reason_{lot_id}"
                )
                
                if st.button(
                    "❌ REJECT LOT",
                    key=f"reject_{lot_id}",
                    type="secondary",
                    use_container_width=True,
                    help="Reject all test results for this lot"
                ):
                    if not rejection_reason:
                        st.error("Please provide a rejection reason")
                    else:
                        # Show confirmation dialog
                        @st.dialog(f"Confirm Rejection - Lot {lot.lot_number}")
                        def confirm_rejection():
                            st.warning("⚠️ This will reject ALL test results for this lot!")
                            st.write(f"**Reason:** {rejection_reason}")
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                if st.button("Cancel", use_container_width=True):
                                    st.rerun()
                            with col2:
                                if st.button("Confirm Rejection", type="primary", use_container_width=True):
                                    try:
                                        for result in results:
                                            approval_service.reject_test_result(
                                                db,
                                                result.id,
                                                get_current_user()["id"],
                                                rejection_reason,
                                            )
                                        
                                        st.error(f"❌ Lot {lot.lot_number} rejected")
                                        st.rerun()
                                        
                                    except Exception as e:
                                        st.error(f"Error rejecting lot: {str(e)}")
                        
                        confirm_rejection()
            
            # Add spacing between cards
            st.markdown("<br>", unsafe_allow_html=True)


def show_approval_history(db: Session, approval_service: ApprovalService):
    """Show approval history."""
    st.subheader("Approval History")

    # Date filter
    col1, col2 = st.columns(2)

    with col1:
        start_date = st.date_input("From Date", datetime.now().date().replace(day=1))

    with col2:
        end_date = st.date_input("To Date", datetime.now().date())

    # Get approvals
    # Convert date range to days back
    days_back = (datetime.now().date() - start_date).days + 1
    approvals = approval_service.get_approval_history(db, days_back=days_back)
    
    # Filter by date range
    approvals = [a for a in approvals if a.get('timestamp') and start_date <= a['timestamp'].date() <= end_date]

    if len(approvals) > 0:
        # Convert to dataframe
        history_data = []
        for approval in approvals:
            history_data.append(
                {
                    "Date": approval['timestamp'].strftime("%Y-%m-%d %H:%M"),
                    "Lot": approval.get('lot_number', 'N/A'),
                    "Test": approval.get('test_type', 'N/A'),
                    "Action": (
                        "✅ Approved" if approval['action'] == "approve" else "❌ Rejected"
                    ),
                    "By": approval.get('user', 'Unknown'),
                    "Reason": approval.get('reason', '-') or "-",
                }
            )

        df = pd.DataFrame(history_data)

        # Color code actions
        def color_action(val):
            if "Approved" in val:
                return "color: green"
            else:
                return "color: red"

        styled_df = df.style.applymap(color_action, subset=["Action"])

        st.dataframe(styled_df, use_container_width=True, hide_index=True)

        # Export option
        if st.button("Export History"):
            import io
            buffer = io.BytesIO()
            df.to_excel(buffer, index=False)
            excel_data = buffer.getvalue()
            st.download_button(
                label="Download Excel",
                data=excel_data,
                file_name=f"approval_history_{start_date}_{end_date}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

    else:
        st.info("No approval history found for the selected date range")


def bulk_approval(db: Session, approval_service: ApprovalService):
    """Bulk approval interface with lot-based selection."""
    st.subheader("Bulk Approval")

    st.info("Select multiple lots to approve or reject at once")

    # Get all pending results grouped by lot
    pending_results = (
        db.query(TestResult)
        .filter(
            TestResult.status == TestResultStatus.DRAFT
        )
        .all()
    )

    if not pending_results:
        st.info("No test results pending approval")
        return

    # Group by lot
    lots_data = {}
    for result in pending_results:
        lot_id = result.lot_id
        if lot_id not in lots_data:
            lot = result.lot
            lots_data[lot_id] = {
                "Lot Number": lot.lot_number,
                "Reference": lot.reference_number,
                "Products": ", ".join([lp.product.display_name for lp in lot.lot_products]),
                "Test Count": 0,
                "All Passing": True,
                "lot_obj": lot,
                "results": []
            }
        lots_data[lot_id]["results"].append(result)
        lots_data[lot_id]["Test Count"] += 1
        if not check_test_result_pass(result):
            lots_data[lot_id]["All Passing"] = False

    # Create dataframe for AG-Grid
    df_data = []
    for lot_id, data in lots_data.items():
        df_data.append({
            "lot_id": lot_id,
            "Lot Number": data["Lot Number"],
            "Reference": data["Reference"],
            "Products": data["Products"],
            "Test Count": data["Test Count"],
            "Status": "✓ All Passing" if data["All Passing"] else "✗ Tests Failing"
        })
    
    df = pd.DataFrame(df_data)
    
    # Add Select column for checkbox selection
    df.insert(0, "Select", False)
    
    # Style function for Status column
    def style_status(val):
        if isinstance(val, str):
            if '✓' in val:
                return 'color: #28a745; font-weight: bold'
            elif '✗' in val:
                return 'color: #dc3545; font-weight: bold'
        return ''
    
    # Create editable dataframe with checkbox selection
    edited_df = st.data_editor(
        df,
        use_container_width=True,
        hide_index=True,
        height=300,
        column_config={
            "Select": st.column_config.CheckboxColumn(
                "Select",
                help="Select lots to approve/reject",
                default=False,
                width="small"
            ),
            "lot_id": None,  # Hide lot_id column
            "Status": st.column_config.TextColumn(
                "Status",
                help="✓ All Passing or ✗ Tests Failing",
                width="small"
            ),
            "Lot Number": st.column_config.TextColumn(
                "Lot Number",
                width="medium"
            ),
            "Reference": st.column_config.TextColumn(
                "Reference",
                width="medium"
            ),
            "Products": st.column_config.TextColumn(
                "Products",
                width="large"
            ),
            "Test Count": st.column_config.NumberColumn(
                "Tests",
                help="Number of test results",
                width="small"
            )
        },
        disabled=["Lot Number", "Reference", "Products", "Test Count", "Status"],
        key="bulk_selection"
    )
    
    # Get selected rows
    selected_rows = edited_df[edited_df["Select"]]
    
    if selected_rows is not None and len(selected_rows) > 0:
        st.write(f"**{len(selected_rows)} lots selected**")
        
        # Get all test result IDs for selected lots
        selected_test_ids = []
        for _, row in selected_rows.iterrows():
            lot_id = row['lot_id']
            selected_test_ids.extend([r.id for r in lots_data[lot_id]["results"]])
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button(
                f"✅ Approve {len(selected_rows)} Lots", 
                type="primary", 
                use_container_width=True
            ):
                try:
                    approved = approval_service.bulk_approve_results(
                        db, selected_test_ids, get_current_user()["id"]
                    )
                    st.success(f"✅ Approved {len(selected_rows)} lots ({approved} test results)")
                    st.balloons()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {str(e)}")

        with col2:
            rejection_reason = st.text_input(
                "Rejection reason",
                placeholder="Required for rejection",
                key="bulk_reason"
            )
            
            if st.button(
                f"❌ Reject {len(selected_rows)} Lots", 
                type="secondary",
                use_container_width=True
            ):
                if not rejection_reason:
                    st.error("Rejection reason is required")
                else:
                    try:
                        rejected = 0
                        for test_id in selected_test_ids:
                            approval_service.reject_test_result(
                                db, test_id, get_current_user()["id"], rejection_reason
                            )
                            rejected += 1

                        st.error(f"❌ Rejected {len(selected_rows)} lots ({rejected} test results)")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {str(e)}")

    else:
        st.info("Select lots using the checkboxes to perform bulk actions")
