"""Approval dashboard for test results."""

import streamlit as st
from sqlalchemy.orm import Session
import pandas as pd
from datetime import datetime

from src.services.approval_service import ApprovalService
from src.services.sample_service import SampleService
from src.models import TestResult, TestResultStatus, Lot
from src.ui.components.auth import get_current_user, require_role
from src.models.enums import UserRole


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
    """Show test results pending approval."""
    st.subheader("Test Results Pending Approval")

    # Get pending test results grouped by lot
    pending_results = (
        db.query(TestResult)
        .filter(
            TestResult.status.in_([TestResultStatus.DRAFT, TestResultStatus.REVIEWED])
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

    # Display each lot
    for lot_id, lot_data in lots_with_pending.items():
        lot = lot_data["lot"]
        results = lot_data["results"]

        with st.expander(
            f"Lot: {lot.lot_number} (Ref: {lot.reference_number})", expanded=True
        ):
            # Lot info
            col1, col2, col3 = st.columns(3)

            with col1:
                st.write(f"**Type:** {lot.lot_type.value}")
                products = ", ".join(
                    [lp.product.display_name for lp in lot.lot_products]
                )
                st.write(f"**Product(s):** {products}")

            with col2:
                st.write(
                    f"**Mfg Date:** {lot.mfg_date.strftime('%Y-%m-%d') if lot.mfg_date else 'N/A'}"
                )
                st.write(
                    f"**Exp Date:** {lot.exp_date.strftime('%Y-%m-%d') if lot.exp_date else 'N/A'}"
                )

            with col3:
                draft_count = len(
                    [r for r in results if r.status == TestResultStatus.DRAFT]
                )
                reviewed_count = len(
                    [r for r in results if r.status == TestResultStatus.REVIEWED]
                )
                st.write(f"**Draft:** {draft_count}")
                st.write(f"**Reviewed:** {reviewed_count}")

            st.divider()

            # Test results table
            results_data = []
            for result in results:
                results_data.append(
                    {
                        "ID": result.id,
                        "Test": result.test_type,
                        "Value": f"{result.result_value} {result.unit}".strip(),
                        "Status": result.status.value,
                        "Confidence": (
                            f"{result.confidence_score:.1%}"
                            if result.confidence_score
                            else "-"
                        ),
                        "Test Date": (
                            result.test_date.strftime("%Y-%m-%d")
                            if result.test_date
                            else "-"
                        ),
                        "Source": result.pdf_source or "-",
                    }
                )

            df = pd.DataFrame(results_data)

            # Show editable table
            edited_df = st.data_editor(
                df,
                use_container_width=True,
                hide_index=True,
                disabled=["ID", "Test", "Confidence", "Test Date", "Source"],
                column_config={
                    "Status": st.column_config.SelectboxColumn(
                        "Status",
                        options=[s.value for s in TestResultStatus],
                        width="small",
                    )
                },
            )

            # Approval actions
            col1, col2, col3 = st.columns([2, 2, 1])

            with col1:
                if st.button(
                    f"✅ Approve All - Lot {lot.lot_number}", key=f"approve_{lot_id}"
                ):
                    try:
                        # Update any edited values
                        for idx, row in edited_df.iterrows():
                            result = next(r for r in results if r.id == row["ID"])
                            if (
                                row["Value"]
                                != f"{result.result_value} {result.unit}".strip()
                            ):
                                # Parse value and unit
                                parts = row["Value"].rsplit(" ", 1)
                                if len(parts) == 2:
                                    result.result_value = parts[0]
                                    result.unit = parts[1]
                                else:
                                    result.result_value = row["Value"]
                                    result.unit = ""

                        db.commit()

                        # Approve all
                        approved = approval_service.bulk_approve_results(
                            db, [r.id for r in results], get_current_user()["id"]
                        )

                        st.success(
                            f"✅ Approved {approved} test results for Lot {lot.lot_number}"
                        )
                        st.balloons()
                        st.rerun()

                    except Exception as e:
                        st.error(f"Error approving results: {str(e)}")

            with col2:
                rejection_reason = st.text_input(
                    "Rejection reason",
                    key=f"reason_{lot_id}",
                    placeholder="Required for rejection",
                )

            with col3:
                if st.button(f"❌ Reject All", key=f"reject_{lot_id}"):
                    if not rejection_reason:
                        st.error("Please provide a rejection reason")
                    else:
                        try:
                            for result in results:
                                approval_service.reject_test_result(
                                    db,
                                    result.id,
                                    get_current_user()["id"],
                                    rejection_reason,
                                )

                            st.error(
                                f"❌ Rejected all test results for Lot {lot.lot_number}"
                            )
                            st.rerun()

                        except Exception as e:
                            st.error(f"Error rejecting results: {str(e)}")


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
    """Bulk approval interface."""
    st.subheader("Bulk Approval")

    st.info("Select multiple test results to approve or reject at once")

    # Get all pending results
    pending_results = (
        db.query(TestResult)
        .filter(
            TestResult.status.in_([TestResultStatus.DRAFT, TestResultStatus.REVIEWED])
        )
        .all()
    )

    if not pending_results:
        st.info("No test results pending approval")
        return

    # Create selectable dataframe
    data = []
    for result in pending_results:
        data.append(
            {
                "Select": False,
                "ID": result.id,
                "Lot": result.lot.lot_number,
                "Reference": result.lot.reference_number,
                "Test": result.test_type,
                "Value": f"{result.result_value} {result.unit}".strip(),
                "Status": result.status.value,
                "Test Date": (
                    result.test_date.strftime("%Y-%m-%d") if result.test_date else "-"
                ),
            }
        )

    df = pd.DataFrame(data)

    # Editable dataframe with checkboxes
    edited_df = st.data_editor(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Select": st.column_config.CheckboxColumn(
                "Select", help="Select results to approve/reject", default=False
            )
        },
        disabled=["ID", "Lot", "Reference", "Test", "Value", "Status", "Test Date"],
    )

    # Get selected IDs
    selected_ids = edited_df[edited_df["Select"]]["ID"].tolist()

    if selected_ids:
        st.write(f"**{len(selected_ids)} test results selected**")

        col1, col2 = st.columns(2)

        with col1:
            if st.button(
                "✅ Approve Selected", type="primary", use_container_width=True
            ):
                try:
                    approved = approval_service.bulk_approve_results(
                        db, selected_ids, get_current_user()["id"]
                    )
                    st.success(f"✅ Approved {approved} test results")
                    st.balloons()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {str(e)}")

        with col2:
            with st.form("bulk_reject_form"):
                reason = st.text_input("Rejection reason (required)")

                if st.form_submit_button(
                    "❌ Reject Selected", use_container_width=True
                ):
                    if not reason:
                        st.error("Rejection reason is required")
                    else:
                        try:
                            rejected = 0
                            for result_id in selected_ids:
                                approval_service.reject_test_result(
                                    db, result_id, get_current_user()["id"], reason
                                )
                                rejected += 1

                            st.error(f"❌ Rejected {rejected} test results")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {str(e)}")

    else:
        st.info("Select test results using the checkboxes to perform bulk actions")
