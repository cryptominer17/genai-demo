"""
auth.py — Streamlit authentication helpers for the PoC Platform.

Simple session-state-based login gate. No external cookie libraries —
avoids compatibility issues between streamlit-authenticator, extra-
streamlit-components, and Streamlit 1.31.x.

Usage:
    from shared.auth import setup_authenticator, require_login

    authenticator = setup_authenticator()
    name, username = require_login(authenticator)
    st.write(f"Welcome, {name}!")
"""

import streamlit as st

from shared.config import Config


class SimpleAuthenticator:
    """
    Lightweight authenticator that uses Streamlit session state.
    Provides the same login/logout API as streamlit-authenticator
    so app code does not need to change.
    """

    def logout(self, button_name: str, location: str = "main", key: str = None):
        """
        Renders a logout button. Clears session state when clicked.

        Parameters
        ----------
        button_name: str
            Label shown on the button.
        location: str
            "main" or "sidebar".
        key: str
            Optional Streamlit widget key.
        """
        if location == "sidebar":
            clicked = st.sidebar.button(button_name, key=key)
        else:
            clicked = st.button(button_name, key=key)

        if clicked:
            st.session_state["authenticated"] = False
            st.session_state["username"] = None
            st.session_state["name"] = None
            st.rerun()


def setup_authenticator() -> SimpleAuthenticator:
    """
    Create and return a SimpleAuthenticator instance.

    Returns
    -------
    SimpleAuthenticator
    """
    return SimpleAuthenticator()


def require_login(authenticator: SimpleAuthenticator) -> tuple[str, str]:
    """
    Render the login form and enforce authentication.

    Halts execution (via st.stop()) if the user is not logged in,
    so any code after this call only runs for authenticated users.

    Parameters
    ----------
    authenticator: SimpleAuthenticator
        The authenticator returned by setup_authenticator().

    Returns
    -------
    tuple[str, str]
        (display_name, username) for the authenticated user.
    """
    # Initialise session state keys on first run
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
    if "username" not in st.session_state:
        st.session_state["username"] = None
    if "name" not in st.session_state:
        st.session_state["name"] = None

    # Already logged in — return immediately
    if st.session_state["authenticated"]:
        return st.session_state["name"], st.session_state["username"]

    # Show login form
    st.title("Login")
    with st.form("login_form"):
        username_input = st.text_input("Username")
        password_input = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")

    if submitted:
        username_input = username_input.strip().lower()
        correct_username = Config.STREAMLIT_USERNAME.strip().lower()
        correct_password = Config.STREAMLIT_PASSWORD.strip()

        if username_input == correct_username and password_input == correct_password:
            st.session_state["authenticated"] = True
            st.session_state["username"] = username_input
            st.session_state["name"] = username_input
            st.rerun()
        else:
            st.error("Username or password is incorrect. Please try again.")

    st.stop()
