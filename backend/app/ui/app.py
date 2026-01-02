"""Main Streamlit application for COA Management System."""

import streamlit as st
from pathlib import Path
import sys

# Add src to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from app.config import settings
from app.utils.logger import logger
from app.database import SessionLocal
from app.ui.pages import (
    dashboard,
    products,
    samples,
    pdf_processing,
    review_queue,
    approvals,
    coa_generation,
    reports,
)
from app.ui.components.auth import check_authentication, login_page
from app.ui.components.sidebar import render_sidebar


def init_session_state():
    """Initialize session state variables."""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "user" not in st.session_state:
        st.session_state.user = None
    if "db_session" not in st.session_state:
        st.session_state.db_session = SessionLocal()


def main():
    """Main application entry point."""
    st.set_page_config(
        page_title="COA Management System",
        page_icon="🧪",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Initialize session state
    init_session_state()

    # Check authentication
    if not check_authentication():
        login_page()
        return

    # Render sidebar and get selected page
    selected_page = render_sidebar()

    # Route to appropriate page
    page_routes = {
        "Dashboard": dashboard.show,
        "Product Management": products.show,
        "Sample Management": samples.show,
        "PDF Processing": pdf_processing.show,
        "Manual Review Queue": review_queue.show,
        "Approval Dashboard": approvals.show,
        "COA Generation": coa_generation.show,
        "Reports & Analytics": reports.show,
    }

    # Display selected page
    if selected_page in page_routes:
        try:
            page_routes[selected_page](st.session_state.db_session)
        except Exception as e:
            logger.error(f"Error displaying page {selected_page}: {e}")
            st.error(f"An error occurred: {str(e)}")
    else:
        st.error(f"Page not found: {selected_page}")


if __name__ == "__main__":
    logger.info("Starting COA Management System")
    main()
