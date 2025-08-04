"""Sidebar navigation component."""

import streamlit as st
from src.models.enums import UserRole
from src.ui.components.auth import logout, get_current_user


def render_sidebar() -> str:
    """Render the sidebar navigation and return selected page."""
    with st.sidebar:
        st.title("🧪 COA Management")

        # User info
        user = get_current_user()
        if user:
            st.write(f"👤 {user['username']}")
            st.write(f"📧 {user['email']}")
            st.write(f"🔐 Role: {user['role'].value}")
            st.divider()

        # Navigation menu
        st.subheader("Navigation")

        # Define pages with role restrictions
        pages = {
            "Dashboard": {
                "icon": "📊",
                "roles": [
                    UserRole.ADMIN,
                    UserRole.QC_MANAGER,
                    UserRole.LAB_TECH,
                    UserRole.READ_ONLY,
                ],
            },
            "Product Management": {
                "icon": "📦",
                "roles": [UserRole.ADMIN, UserRole.QC_MANAGER],
            },
            "Sample Submission": {
                "icon": "🧫",
                "roles": [UserRole.ADMIN, UserRole.QC_MANAGER, UserRole.LAB_TECH],
            },
            "PDF Processing": {
                "icon": "📄",
                "roles": [UserRole.ADMIN, UserRole.QC_MANAGER, UserRole.LAB_TECH],
            },
            "Manual Review Queue": {
                "icon": "👁️",
                "roles": [UserRole.ADMIN, UserRole.QC_MANAGER, UserRole.LAB_TECH],
            },
            "Approval Dashboard": {
                "icon": "✅",
                "roles": [UserRole.ADMIN, UserRole.QC_MANAGER],
            },
            "COA Generation": {
                "icon": "🏭",
                "roles": [UserRole.ADMIN, UserRole.QC_MANAGER],
            },
            "Reports & Analytics": {
                "icon": "📈",
                "roles": [UserRole.ADMIN, UserRole.QC_MANAGER, UserRole.READ_ONLY],
            },
        }

        # Filter pages based on user role
        user_role = user["role"] if user else UserRole.READ_ONLY
        available_pages = {
            name: info for name, info in pages.items() if user_role in info["roles"]
        }

        # Create radio buttons for navigation
        selected_page = st.radio(
            "Select Page",
            options=list(available_pages.keys()),
            format_func=lambda x: f"{available_pages[x]['icon']} {x}",
            label_visibility="collapsed",
        )

        # PDF Watcher Status (for authorized users)
        if user_role in [UserRole.ADMIN, UserRole.QC_MANAGER]:
            st.divider()
            st.subheader("PDF Watcher")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("▶️ Start", use_container_width=True):
                    st.success("Watcher started")
            with col2:
                if st.button("⏸️ Stop", use_container_width=True):
                    st.info("Watcher stopped")

            # Show status
            st.metric("Status", "🟢 Running", "5 PDFs processed")

        # Logout button
        st.divider()
        if st.button("🚪 Logout", use_container_width=True):
            logout()

    return selected_page
