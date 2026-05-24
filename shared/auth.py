"""
auth.py — Streamlit authentication helpers for the PoC Platform.

Wraps streamlit-authenticator to provide a consistent login gate across
all apps in this deployment. Credentials are sourced from Config so no
secrets are hard-coded here.

Usage:
    from shared.auth import setup_authenticator, require_login

    authenticator = setup_authenticator()
    name, username = require_login(authenticator)
    st.write(f"Welcome, {name}!")
"""

import streamlit as st
import streamlit_authenticator as stauth

from shared.config import Config


def get_auth_config() -> dict:
    """
    Build the credentials dictionary expected by streamlit-authenticator.

    Hashes the plain-text password from Config using stauth.Hasher so the
    raw password is never held in memory longer than necessary.

    Returns:
        A dict in the format::

            {
                "usernames": {
                    "<username>": {
                        "name": "<username>",
                        "password": "<bcrypt-hash>",
                        "email": ""
                    }
                }
            }
    """
    username = Config.STREAMLIT_USERNAME
    password = Config.STREAMLIT_PASSWORD

    hashed_password = stauth.Hasher([password]).generate()[0]

    credentials = {
        "usernames": {
            username: {
                "name": username,
                "password": hashed_password,
                "email": "",
            }
        }
    }
    return credentials


def setup_authenticator() -> stauth.Authenticate:
    """
    Create and return a configured streamlit-authenticator instance.

    The cookie name and signing key are fixed for this deployment.
    Cookie expiry is set to 7 days so users stay logged in across
    browser restarts within a week.

    Returns:
        A ready-to-use `stauth.Authenticate` object.
    """
    credentials = get_auth_config()
    authenticator = stauth.Authenticate(
        credentials=credentials,
        cookie_name="fi_poc_cookie",
        key="fi_poc_key",
        cookie_expiry_days=7,
    )
    return authenticator


def require_login(authenticator: stauth.Authenticate) -> tuple[str, str]:
    """
    Render the login form and enforce authentication.

    Halts execution (via `st.stop()`) if the user is not logged in,
    so any code after this call only runs for authenticated users.

    Args:
        authenticator: The authenticator returned by `setup_authenticator()`.

    Returns:
        A tuple of (display_name, username) for the authenticated user.
    """
    name, auth_status, username = authenticator.login(location="main")

    if auth_status is False:
        st.error("Username/password is incorrect")
        st.stop()

    if auth_status is None:
        st.warning("Please enter your credentials")
        st.stop()

    # auth_status is True — user is authenticated
    return name, username
