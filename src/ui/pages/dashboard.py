"""Dashboard page for COA Management System."""

import streamlit as st
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import pandas as pd
import plotly.express as px

from src.services.lot_service import LotService
from src.services.sample_service import SampleService
from src.services.approval_service import ApprovalService
from src.models.enums import LotStatus, TestResultStatus


def show(db: Session):
    """Display the dashboard page."""
    st.title("📊 Dashboard")
    st.write(
        f"Welcome to the COA Management System - {datetime.now().strftime('%B %d, %Y')}"
    )

    # Initialize services
    lot_service = LotService()
    sample_service = SampleService()
    approval_service = ApprovalService()

    # Key Metrics Row
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        from src.models import Lot
        total_lots = db.query(Lot).count()
        pending_lots = (
            db.query(Lot).filter_by(status=LotStatus.PENDING).count()
        )
        st.metric(
            "Total Lots",
            total_lots,
            f"{pending_lots} pending",
            help="Total number of lots in the system",
        )

    with col2:
        pending_approvals = len(approval_service.get_pending_approvals(db))
        # Get today's approvals from history
        today_history = approval_service.get_approval_history(db, days_back=1)
        approved_today = len([h for h in today_history if h.get('action') == 'approved' and 
                            h.get('created_at', '').startswith(datetime.now().strftime('%Y-%m-%d'))])
        st.metric(
            "Pending Approvals",
            pending_approvals,
            f"{approved_today} approved today",
            help="Test results awaiting approval",
        )

    with col3:
        # Get pending test results instead of samples
        pending_results = sample_service.get_pending_results(db)
        total_samples = len(pending_results)
        
        # Get today's test results
        from src.models import TestResult
        today_start = datetime.combine(datetime.now().date(), datetime.min.time())
        today_end = datetime.combine(datetime.now().date(), datetime.max.time())
        completed_today = db.query(TestResult).filter(
            TestResult.created_at >= today_start,
            TestResult.created_at <= today_end,
            TestResult.status == TestResultStatus.APPROVED
        ).count()
        
        st.metric(
            "Active Test Results",
            total_samples,
            f"{completed_today} completed today",
            help="Test results being processed",
        )

    with col4:
        # Mock COA generation stats
        coas_this_month = 42  # TODO: Implement COA history service
        coas_last_month = 38
        delta = coas_this_month - coas_last_month
        st.metric(
            "COAs This Month",
            coas_this_month,
            f"{delta:+d} vs last month",
            help="COAs generated this month",
        )

    st.divider()

    # Two column layout for charts and activity
    chart_col, activity_col = st.columns([2, 1])

    with chart_col:
        st.subheader("📈 Test Results by Status")

        # Get test result statistics
        from src.models import TestResult
        status_counts = {
            "Draft": db.query(TestResult)
            .filter_by(status=TestResultStatus.DRAFT)
            .count(),
            "Reviewed": db.query(TestResult)
            .filter_by(status=TestResultStatus.REVIEWED)
            .count(),
            "Approved": db.query(TestResult)
            .filter_by(status=TestResultStatus.APPROVED)
            .count(),
        }

        if any(status_counts.values()):
            df = pd.DataFrame(list(status_counts.items()), columns=["Status", "Count"])

            fig = px.pie(
                df,
                values="Count",
                names="Status",
                color_discrete_map={
                    "Draft": "#FF6B6B",
                    "Reviewed": "#4ECDC4",
                    "Approved": "#45B7D1",
                },
            )
            fig.update_traces(textposition="inside", textinfo="percent+label")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No test results to display yet")

        # Lot Status Overview
        st.subheader("📦 Lot Status Overview")

        from src.models import Lot
        lot_status_counts = {
            "Pending": db.query(Lot)
            .filter_by(status=LotStatus.PENDING)
            .count(),
            "Tested": db.query(Lot)
            .filter_by(status=LotStatus.TESTED)
            .count(),
            "Approved": db.query(Lot)
            .filter_by(status=LotStatus.APPROVED)
            .count(),
            "Released": db.query(Lot)
            .filter_by(status=LotStatus.RELEASED)
            .count(),
        }

        if any(lot_status_counts.values()):
            df_lots = pd.DataFrame(
                list(lot_status_counts.items()), columns=["Status", "Count"]
            )

            fig_lots = px.bar(
                df_lots,
                x="Status",
                y="Count",
                color="Status",
                color_discrete_map={
                    "Pending": "#FF6B6B",
                    "Tested": "#FFE66D",
                    "Approved": "#4ECDC4",
                    "Released": "#45B7D1",
                },
            )
            st.plotly_chart(fig_lots, use_container_width=True)
        else:
            st.info("No lots to display yet")

    with activity_col:
        st.subheader("🔔 Recent Activity")

        # Get recent approvals
        recent_approvals = approval_service.get_recent_approvals(limit=5)

        if recent_approvals:
            for approval in recent_approvals:
                with st.container():
                    if approval.action == "approve":
                        st.success(
                            f"✅ {approval.approved_by} approved test results for Lot {approval.test_result.lot.lot_number}"
                        )
                    else:
                        st.error(
                            f"❌ {approval.approved_by} rejected test results for Lot {approval.test_result.lot.lot_number}"
                        )
                    st.caption(f"{approval.created_at.strftime('%Y-%m-%d %H:%M')}")
        else:
            st.info("No recent activity")

        st.divider()

        st.subheader("⏰ Expiring Soon")

        # Get lots expiring in next 30 days
        expiring_lots = lot_service.get_expiring_lots(db, days_ahead=30)

        if expiring_lots:
            for lot in expiring_lots[:5]:
                days_until = (lot.exp_date - datetime.now().date()).days
                with st.container():
                    st.warning(f"📅 Lot {lot.lot_number} expires in {days_until} days")
                    st.caption(f"Exp: {lot.exp_date.strftime('%Y-%m-%d')}")
        else:
            st.info("No lots expiring soon")

    # Quick Actions
    st.divider()
    st.subheader("⚡ Quick Actions")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if st.button("➕ Create Sample", use_container_width=True):
            st.switch_page("pages/samples.py")

    with col2:
        if st.button("📄 Upload PDF", use_container_width=True):
            st.switch_page("pages/pdf_processing.py")

    with col3:
        if st.button("✅ Review Approvals", use_container_width=True):
            st.switch_page("pages/approvals.py")

    with col4:
        if st.button("🏭 Generate COA", use_container_width=True):
            st.switch_page("pages/coa_generation.py")
