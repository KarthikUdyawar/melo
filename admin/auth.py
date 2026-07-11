"""Session-based password authentication for the Streamlit admin dashboard."""

# admin/auth.py
import os

import streamlit as st


def is_authenticated() -> bool:
    """Return True if the current session is authenticated."""
    return bool(st.session_state.get("authenticated", False))


def login_page() -> None:
    """Render the password login form and update session state on submit."""
    st.title("🔐 Melo Admin")
    st.caption("Enter your admin password to continue.")

    password = st.text_input("Password", type="password", key="login_input")

    if st.button("Login", use_container_width=True):
        expected = os.environ.get("ADMIN_PASSWORD")
        if expected and password == expected:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")
