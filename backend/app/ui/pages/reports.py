"""Reports and analytics page."""

import streamlit as st
from sqlalchemy.orm import Session
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

from app.services.lot_service import LotService
from app.services.product_service import ProductService
from app.services.approval_service import ApprovalService
from app.models import Lot, Product, TestResult, LotStatus, TestResultStatus


def show(db: Session):
    """Display the reports and analytics page."""
    st.title("📈 Reports & Analytics")

    # Initialize services
    lot_service = LotService()
    product_service = ProductService()
    approval_service = ApprovalService()

    # Date range selector
    col1, col2, col3 = st.columns([1, 1, 2])

    with col1:
        start_date = st.date_input(
            "Start Date", value=datetime.now().date() - timedelta(days=30)
        )

    with col2:
        end_date = st.date_input("End Date", value=datetime.now().date())

    with col3:
        report_type = st.selectbox(
            "Report Type",
            options=[
                "Overview Dashboard",
                "Product Analysis",
                "Test Results Analysis",
                "Turnaround Time",
                "User Activity",
            ],
        )

    st.divider()

    # Display selected report
    if report_type == "Overview Dashboard":
        overview_dashboard(db, start_date, end_date)
    elif report_type == "Product Analysis":
        product_analysis(db, start_date, end_date)
    elif report_type == "Test Results Analysis":
        test_results_analysis(db, start_date, end_date)
    elif report_type == "Turnaround Time":
        turnaround_time_report(db, start_date, end_date)
    elif report_type == "User Activity":
        user_activity_report(db, approval_service, start_date, end_date)


def overview_dashboard(db: Session, start_date, end_date):
    """Display overview dashboard."""
    st.subheader("Overview Dashboard")

    # Key metrics
    col1, col2, col3, col4 = st.columns(4)

    # Get data for date range
    lots_in_range = (
        db.query(Lot)
        .filter(
            Lot.created_at >= start_date,
            Lot.created_at <= datetime.combine(end_date, datetime.max.time()),
        )
        .all()
    )

    tests_in_range = (
        db.query(TestResult)
        .filter(
            TestResult.created_at >= start_date,
            TestResult.created_at <= datetime.combine(end_date, datetime.max.time()),
        )
        .all()
    )

    with col1:
        st.metric("Total Lots Created", len(lots_in_range))

    with col2:
        released = len([l for l in lots_in_range if l.status == LotStatus.RELEASED])
        st.metric("COAs Generated", released)

    with col3:
        st.metric("Test Results", len(tests_in_range))

    with col4:
        approved = len(
            [t for t in tests_in_range if t.status == TestResultStatus.APPROVED]
        )
        approval_rate = approved / max(1, len(tests_in_range))
        st.metric("Approval Rate", f"{approval_rate:.1%}")

    # Charts
    col1, col2 = st.columns(2)

    with col1:
        st.write("**Lots by Status**")

        status_counts = {}
        for status in LotStatus:
            count = len([l for l in lots_in_range if l.status == status])
            if count > 0:
                status_counts[status.value] = count

        if status_counts:
            fig = px.pie(
                values=list(status_counts.values()),
                names=list(status_counts.keys()),
                color_discrete_map={
                    "pending": "#FF6B6B",
                    "tested": "#FFE66D",
                    "approved": "#4ECDC4",
                    "released": "#45B7D1",
                },
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data for selected period")

    with col2:
        st.write("**Daily Lot Creation**")

        # Group by date
        daily_counts = {}
        for lot in lots_in_range:
            date_key = lot.created_at.date()
            daily_counts[date_key] = daily_counts.get(date_key, 0) + 1

        if daily_counts:
            df = pd.DataFrame(
                list(daily_counts.items()), columns=["Date", "Count"]
            ).sort_values("Date")

            fig = px.line(df, x="Date", y="Count", markers=True, line_shape="spline")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data for selected period")


def product_analysis(db: Session, start_date, end_date):
    """Display product analysis."""
    st.subheader("Product Analysis")

    # Get lots with products in date range
    lots = (
        db.query(Lot)
        .filter(
            Lot.created_at >= start_date,
            Lot.created_at <= datetime.combine(end_date, datetime.max.time()),
        )
        .all()
    )

    # Count by product
    product_counts = {}
    brand_counts = {}

    for lot in lots:
        for lp in lot.lot_products:
            product_key = lp.product.display_name
            brand_key = lp.product.brand

            product_counts[product_key] = product_counts.get(product_key, 0) + 1
            brand_counts[brand_key] = brand_counts.get(brand_key, 0) + 1

    col1, col2 = st.columns(2)

    with col1:
        st.write("**Top Products**")

        if product_counts:
            # Sort and get top 10
            top_products = sorted(
                product_counts.items(), key=lambda x: x[1], reverse=True
            )[:10]

            df = pd.DataFrame(top_products, columns=["Product", "Count"])

            fig = px.bar(
                df,
                x="Count",
                y="Product",
                orientation="h",
                color="Count",
                color_continuous_scale="Blues",
            )
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No product data for selected period")

    with col2:
        st.write("**Brand Distribution**")

        if brand_counts:
            fig = px.pie(
                values=list(brand_counts.values()),
                names=list(brand_counts.keys()),
                hole=0.4,
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No brand data for selected period")

    # Product table
    st.write("**Product Details**")

    if product_counts:
        product_data = []

        for product_name, count in product_counts.items():
            # Get product info
            product = db.query(Product).filter_by(display_name=product_name).first()
            if product:
                product_data.append(
                    {
                        "Product": product_name,
                        "Brand": product.brand,
                        "Samples": count,
                        "Percentage": f"{count / len(lots) * 100:.1f}%",
                    }
                )

        df = pd.DataFrame(product_data)
        st.dataframe(
            df.sort_values("Samples", ascending=False),
            use_container_width=True,
            hide_index=True,
        )

        # Export button
        if st.button("Export Product Report"):
            excel_data = df.to_excel(index=False)
            st.download_button(
                label="Download Excel",
                data=excel_data,
                file_name=f"product_report_{start_date}_{end_date}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )


def test_results_analysis(db: Session, start_date, end_date):
    """Display test results analysis."""
    st.subheader("Test Results Analysis")

    # Get test results in date range
    test_results = (
        db.query(TestResult)
        .filter(
            TestResult.created_at >= start_date,
            TestResult.created_at <= datetime.combine(end_date, datetime.max.time()),
        )
        .all()
    )

    if not test_results:
        st.info("No test results found for selected period")
        return

    # Test type distribution
    test_type_counts = {}
    for result in test_results:
        test_type_counts[result.test_type] = (
            test_type_counts.get(result.test_type, 0) + 1
        )

    col1, col2 = st.columns(2)

    with col1:
        st.write("**Test Type Distribution**")

        df = pd.DataFrame(
            list(test_type_counts.items()), columns=["Test Type", "Count"]
        ).sort_values("Count", ascending=False)

        fig = px.bar(
            df,
            x="Test Type",
            y="Count",
            color="Count",
            color_continuous_scale="Viridis",
        )
        fig.update_xaxis(tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.write("**Confidence Score Distribution**")

        confidence_scores = [
            r.confidence_score for r in test_results if r.confidence_score
        ]

        if confidence_scores:
            fig = px.histogram(
                confidence_scores,
                nbins=20,
                labels={"value": "Confidence Score", "count": "Count"},
                color_discrete_sequence=["#45B7D1"],
            )
            fig.update_xaxis(tickformat=".0%")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No confidence scores available")

    # Test results summary
    st.write("**Test Results Summary**")

    # Group by test type and calculate statistics
    test_summary = []

    for test_type, count in test_type_counts.items():
        type_results = [r for r in test_results if r.test_type == test_type]
        approved = len(
            [r for r in type_results if r.status == TestResultStatus.APPROVED]
        )
        avg_confidence = sum(r.confidence_score or 0 for r in type_results) / max(
            1, len([r for r in type_results if r.confidence_score])
        )

        test_summary.append(
            {
                "Test Type": test_type,
                "Total Tests": count,
                "Approved": approved,
                "Approval Rate": f"{approved/count:.1%}",
                "Avg Confidence": (
                    f"{avg_confidence:.1%}" if avg_confidence > 0 else "N/A"
                ),
            }
        )

    summary_df = pd.DataFrame(test_summary)
    st.dataframe(
        summary_df.sort_values("Total Tests", ascending=False),
        use_container_width=True,
        hide_index=True,
    )


def turnaround_time_report(db: Session, start_date, end_date):
    """Display turnaround time analysis."""
    st.subheader("Turnaround Time Analysis")

    # Get lots with complete lifecycle
    completed_lots = (
        db.query(Lot)
        .filter(
            Lot.created_at >= start_date,
            Lot.created_at <= datetime.combine(end_date, datetime.max.time()),
            Lot.status == LotStatus.RELEASED,
        )
        .all()
    )

    if not completed_lots:
        st.info("No completed lots found for selected period")
        return

    # Calculate turnaround times
    turnaround_data = []

    for lot in completed_lots:
        # Get first test result date
        first_test = (
            min(lot.test_results, key=lambda x: x.created_at)
            if lot.test_results
            else None
        )

        if first_test:
            # Time from sample creation to first test
            time_to_test = (
                first_test.created_at - lot.created_at
            ).total_seconds() / 86400  # Days

            # Time from first test to approval (if approved)
            approved_tests = [
                t for t in lot.test_results if t.status == TestResultStatus.APPROVED
            ]
            if approved_tests:
                last_approval = max(approved_tests, key=lambda x: x.updated_at)
                time_to_approval = (
                    last_approval.updated_at - first_test.created_at
                ).total_seconds() / 86400
                total_time = (
                    last_approval.updated_at - lot.created_at
                ).total_seconds() / 86400

                turnaround_data.append(
                    {
                        "Lot": lot.lot_number,
                        "Time to Test (days)": round(time_to_test, 1),
                        "Time to Approval (days)": round(time_to_approval, 1),
                        "Total Time (days)": round(total_time, 1),
                    }
                )

    if turnaround_data:
        df = pd.DataFrame(turnaround_data)

        # Summary statistics
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                "Avg Time to Test", f"{df['Time to Test (days)'].mean():.1f} days"
            )

        with col2:
            st.metric(
                "Avg Time to Approval",
                f"{df['Time to Approval (days)'].mean():.1f} days",
            )

        with col3:
            st.metric("Avg Total Time", f"{df['Total Time (days)'].mean():.1f} days")

        # Distribution chart
        st.write("**Turnaround Time Distribution**")

        fig = go.Figure()

        fig.add_trace(
            go.Box(
                y=df["Time to Test (days)"],
                name="Time to Test",
                boxpoints="all",
                jitter=0.3,
                pointpos=-1.8,
            )
        )

        fig.add_trace(
            go.Box(
                y=df["Time to Approval (days)"],
                name="Time to Approval",
                boxpoints="all",
                jitter=0.3,
                pointpos=-1.8,
            )
        )

        fig.add_trace(
            go.Box(
                y=df["Total Time (days)"],
                name="Total Time",
                boxpoints="all",
                jitter=0.3,
                pointpos=-1.8,
            )
        )

        fig.update_layout(yaxis_title="Days", showlegend=True)

        st.plotly_chart(fig, use_container_width=True)

        # Detailed table
        st.write("**Detailed Turnaround Times**")
        st.dataframe(
            df.sort_values("Total Time (days)", ascending=False),
            use_container_width=True,
            hide_index=True,
        )


def user_activity_report(db: Session, approval_service: ApprovalService, start_date, end_date):
    """Display user activity report."""
    st.subheader("User Activity Report")

    # Get approval activities
    days_back = (datetime.now().date() - start_date).days + 1
    all_approvals = approval_service.get_approval_history(db, days_back=days_back)
    
    # Filter by date range
    approvals = [a for a in all_approvals if start_date <= datetime.fromisoformat(a.get('created_at', '')).date() <= end_date]

    if len(approvals) == 0:
        st.info("No user activity found for selected period")
        return

    # Group by user
    user_stats = {}

    for approval in approvals:
        user = approval.approved_by
        if user not in user_stats:
            user_stats[user] = {"approvals": 0, "rejections": 0, "total": 0}

        user_stats[user]["total"] += 1
        if approval.action == "approve":
            user_stats[user]["approvals"] += 1
        else:
            user_stats[user]["rejections"] += 1

    # Create user activity table
    user_data = []
    for user, stats in user_stats.items():
        user_data.append(
            {
                "User": user,
                "Total Actions": stats["total"],
                "Approvals": stats["approvals"],
                "Rejections": stats["rejections"],
                "Approval Rate": f"{stats['approvals']/stats['total']:.1%}",
            }
        )

    df = pd.DataFrame(user_data).sort_values("Total Actions", ascending=False)

    # Display metrics
    col1, col2 = st.columns(2)

    with col1:
        st.write("**User Activity Summary**")
        st.dataframe(df, use_container_width=True, hide_index=True)

    with col2:
        st.write("**Activity Distribution**")

        fig = px.bar(
            df,
            x="User",
            y=["Approvals", "Rejections"],
            color_discrete_map={"Approvals": "#45B7D1", "Rejections": "#FF6B6B"},
        )
        st.plotly_chart(fig, use_container_width=True)

    # Daily activity
    st.write("**Daily Activity Trend**")

    daily_activity = {}
    for approval in approvals:
        date_key = approval.created_at.date()
        if date_key not in daily_activity:
            daily_activity[date_key] = 0
        daily_activity[date_key] += 1

    if daily_activity:
        activity_df = pd.DataFrame(
            list(daily_activity.items()), columns=["Date", "Actions"]
        ).sort_values("Date")

        fig = px.line(
            activity_df, x="Date", y="Actions", markers=True, line_shape="spline"
        )
        st.plotly_chart(fig, use_container_width=True)
