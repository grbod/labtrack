"""Authentication components for Streamlit app."""

import streamlit as st
from sqlalchemy.orm import Session
import hashlib

from src.services.user_service import UserService
from src.models.enums import UserRole


def check_authentication() -> bool:
    """Check if user is authenticated."""
    # Streamlit's session_state persists across reruns/refreshes
    return st.session_state.get("authenticated", False)


def login_page():
    """Display login page."""
    st.title("🧪 COA Management System")
    st.subheader("Please log in to continue")

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        with st.form("login_form"):
            username = st.text_input("Username", key="login_username")
            password = st.text_input("Password", type="password", key="login_password")
            submit = st.form_submit_button(
                "Login", type="primary", use_container_width=True
            )

            if submit:
                if authenticate_user(username, password):
                    st.success("Login successful!")
                    st.rerun()
                else:
                    st.error("Invalid username or password")

        # Add demo credentials info
        with st.expander("Demo Credentials"):
            st.write("**Admin:** admin / admin123")
            st.write("**QC Manager:** qc_manager / qc123")
            st.write("**Lab Tech:** lab_tech / lab123")
            st.write("**Read Only:** viewer / view123")


def authenticate_user(username: str, password: str) -> bool:
    """Authenticate user credentials."""
    if not username or not password:
        return False

    # Use real authentication with UserService
    from src.database import get_db
    
    db = next(get_db())
    try:
        user_service = UserService()
        user = user_service.authenticate(db, username, password)
        
        if user:
            # This will persist across page refreshes
            st.session_state.authenticated = True
            st.session_state.user = {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
            }
            return True
    finally:
        db.close()

    return False


def logout():
    """Log out the current user."""
    # Clear authentication from session state
    for key in ["authenticated", "user"]:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()


def require_role(allowed_roles: list[UserRole]):
    """Decorator to require specific user roles for a function."""

    def decorator(func):
        def wrapper(*args, **kwargs):
            if not check_authentication():
                st.error("Please log in to access this page")
                return

            user_role = st.session_state.user.get("role")
            if user_role not in allowed_roles:
                st.error("You don't have permission to access this page")
                return

            return func(*args, **kwargs)

        return wrapper

    return decorator


def get_current_user():
    """Get the current logged-in user."""
    return st.session_state.get("user", None)