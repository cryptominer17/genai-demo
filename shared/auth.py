"""
auth.py — Streamlit authentication helpers for the PoC Platform.

Session-state-based login gate backed by the SQLite user database.

Usage:
    from shared.auth import setup_authenticator, require_login, require_permission

    authenticator = setup_authenticator()
    name, username = require_login(authenticator, app_name="data_qa")
    authenticator.logout("Logout", location="sidebar")
"""

import streamlit as st
import bcrypt

from shared import user_db


class SimpleAuthenticator:
    """
    Lightweight authenticator backed by the SQLite user database.
    Provides login/logout/permission-check via Streamlit session state.
    """

    def login(self, username: str, password: str) -> bool:
        """
        Verify credentials against user_db and populate session state.

        Sets session keys: authenticated, username, name, role,
        and must_change_password (when applicable).
        Returns True on success, False on failure.
        """
        user = user_db.get_user_by_username(username.strip().lower())
        if not user or not user["is_active"]:
            st.session_state["authenticated"] = False
            return False

        try:
            password_ok = bcrypt.checkpw(password.encode(), user["password_hash"].encode())
        except Exception:
            password_ok = False

        if password_ok:
            st.session_state["authenticated"] = True
            st.session_state["username"] = user["username"]
            st.session_state["name"] = user["username"]
            st.session_state["role"] = user["role"]
            # Flag so require_login() can intercept before the app renders.
            if user.get("must_change_password"):
                st.session_state["must_change_password"] = True
            else:
                st.session_state.pop("must_change_password", None)
            return True

        st.session_state["authenticated"] = False
        return False

    def logout(self, button_name: str = "Logout", location: str = "main", key: str = "logout_btn"):
        """
        Render a logout button. Clears all auth session state on click
        and calls st.rerun().
        """
        _key = key or f"logout_{location}"

        if location == "sidebar":
            clicked = st.sidebar.button(button_name, key=_key, type="secondary")
        else:
            clicked = st.button(button_name, key=_key, type="secondary")

        if clicked:
            for k in ["authenticated", "username", "name", "role", "must_change_password"]:
                if k in st.session_state:
                    del st.session_state[k]
            st.rerun()

    def has_permission(self, app_name: str) -> bool:
        """Return True if the current user's role (and any override) allows access."""
        role = st.session_state.get("role")
        username = st.session_state.get("username")
        if not role:
            return False
        return user_db.check_app_permission(role, app_name, username=username)


def setup_authenticator() -> SimpleAuthenticator:
    """Create and return a SimpleAuthenticator instance."""
    return SimpleAuthenticator()


def _show_force_change_password_form() -> None:
    """
    Render a forced password-change form and halt via st.stop().

    Called from require_login() whenever ``must_change_password`` is set in
    the session.  The user cannot reach any app page until they set a new
    password, at which point the flag is cleared and the page reruns.
    """
    username = st.session_state.get("username", "")

    col1, form_col, col2 = st.columns([1, 2, 1])
    with form_col:
        st.warning(
            "You must set a new password before accessing the platform.",
            icon="🔒",
        )
        st.subheader("Set your password")
        with st.form("force_pw_change_form"):
            new_pw = st.text_input("New Password", type="password")
            confirm_pw = st.text_input("Confirm New Password", type="password")
            submitted = st.form_submit_button("Set Password", use_container_width=True)

        if submitted:
            errors = []
            if len(new_pw) < 8:
                errors.append("Password must be at least 8 characters.")
            if new_pw != confirm_pw:
                errors.append("Passwords do not match.")

            if errors:
                for e in errors:
                    st.error(e)
            else:
                user_db.update_password(username, new_pw)
                user_db.set_must_change_password(username, False)
                st.session_state.pop("must_change_password", None)
                st.success("Password updated. Loading the platform…")
                st.rerun()

    st.stop()


def require_login(
    authenticator: SimpleAuthenticator,
    app_name: str = None,
) -> tuple[str, str]:
    """
    Enforce authentication. Shows a branded login form and halts via st.stop()
    if the user is not logged in.

    If the authenticated user has ``must_change_password`` set, a forced
    password-change form is shown instead of the requested app.

    Parameters
    ----------
    authenticator : SimpleAuthenticator
    app_name      : str, optional
        When provided, verifies the authenticated user's role has access.

    Returns
    -------
    tuple[str, str]
        (display_name, username)
    """
    for key, default in [
        ("authenticated", False),
        ("username", None),
        ("name", None),
        ("role", None),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default

    if st.session_state["authenticated"]:
        # Gate: force the user to set a new password before any app renders.
        if st.session_state.get("must_change_password"):
            _show_force_change_password_form()  # never returns; calls st.stop()

        if app_name:
            require_permission(app_name)
        return st.session_state["name"], st.session_state["username"]

    # --- Branded login page ---
    st.markdown(
        """
        <style>
        [data-testid="stAppViewContainer"] { background: #f0f2f6; }
        .login-container {
            background: #ffffff;
            border-radius: 10px;
            border: 1px solid #dde2ea;
            box-shadow: 0 4px 24px rgba(0,0,0,0.10);
            overflow: hidden;
            margin-top: 1rem;
        }
        .fi-header {
            background: #0A3D6B;
            padding: 1.5rem 2rem;
        }
        .fi-header h1 {
            color: #ffffff;
            margin: 0;
            font-size: 1.35rem;
            letter-spacing: 0.01em;
        }
        .fi-header p {
            color: #8ab4c7;
            margin: 0.3rem 0 0;
            font-size: 0.85rem;
        }
        .fi-footer {
            text-align: center;
            color: #9aa3af;
            font-size: 0.75rem;
            padding: 0.75rem 0 0.25rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    col1, form_col, col2 = st.columns([1, 2, 1])
    with form_col:
        st.markdown(
            """
            <div class="login-container">
              <div class="fi-header">
                <h1>🏦 Fidelity Institutional GenAI Platform</h1>
                <p>Secure access — enter your credentials</p>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.container():
            with st.form("fi_login_form"):
                username_input = st.text_input("Username")
                password_input = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Sign In", use_container_width=True)

            if submitted:
                if authenticator.login(username_input, password_input):
                    user_db.record_login(st.session_state["username"])
                    st.rerun()
                else:
                    st.error("Invalid credentials.")

        st.markdown(
            '<p class="fi-footer">© 2026 Fidelity Institutional | AI Platform Demo</p>',
            unsafe_allow_html=True,
        )

    st.stop()


def require_permission(app_name: str) -> None:
    """
    Halt with an access-denied message if the current user lacks permission
    for *app_name*. Checks user-level overrides before the role matrix.
    """
    role = st.session_state.get("role")
    username = st.session_state.get("username")
    if role and user_db.check_app_permission(role, app_name, username=username):
        return
    st.error("You don't have access to this application. Contact your administrator.")
    st.stop()
