"""
Admin Console — Streamlit app for user management and RBAC.

Only users with the 'admin' role can access this page.
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import re

import pandas as pd
import streamlit as st

from shared.auth import setup_authenticator, require_login, require_permission
from shared import user_db

# ---------------------------------------------------------------------------
# Page configuration — must be the first Streamlit call
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="FI GenAI Admin",
    page_icon="🔐",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Auth gate
# ---------------------------------------------------------------------------

authenticator = setup_authenticator()
name, username = require_login(authenticator, app_name="admin")
require_permission("admin")

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

header_col, logout_col = st.columns([6, 1])
with header_col:
    st.title("🔐 FI GenAI Platform — Admin Console")
    role = st.session_state.get("role", "")
    st.caption(f"Signed in as **{name}** · role: `{role}`")
with logout_col:
    st.write("")
    authenticator.logout("Logout", location="main", key="admin_logout_top")

st.divider()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ROLES = ["admin", "analyst", "viewer"]
APPS = ["document_intelligence", "data_qa", "report_generator", "admin"]

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab_users, tab_add, tab_perms, tab_reset = st.tabs(
    ["👥 Users", "🔑 Add User", "🔒 App Permissions", "🔄 Reset Password"]
)

# ===========================================================================
# TAB 1 — Users
# ===========================================================================

with tab_users:
    users = user_db.list_users()
    total = len(users)
    active_count = sum(1 for u in users if u["is_active"])
    role_count = len({u["role"] for u in users})

    m1, m2, m3 = st.columns(3)
    m1.metric("Total Users", total)
    m2.metric("Active Users", active_count)
    m3.metric("Distinct Roles", role_count)

    st.subheader("User Directory")
    if users:
        df = pd.DataFrame(users)
        display_cols = ["username", "email", "role", "is_active", "created_at", "last_login"]
        st.dataframe(df[display_cols], use_container_width=True)
    else:
        st.info("No users found.")

    st.subheader("Manage Users")
    for user in users:
        uname = user["username"]
        is_self = uname == username
        status_icon = "🟢" if user["is_active"] else "🔴"
        expander_label = f"{status_icon} {uname} ({user['role']})"
        if is_self:
            expander_label += " — you"

        with st.expander(expander_label):
            col_toggle, col_role, col_delete = st.columns([2, 3, 2])

            with col_toggle:
                toggle_label = "Deactivate" if user["is_active"] else "Activate"
                if st.button(toggle_label, key=f"toggle_{uname}"):
                    user_db.toggle_user_active(uname)
                    action = "deactivated" if user["is_active"] else "activated"
                    st.success(f"User '{uname}' {action}.")
                    st.rerun()

            with col_role:
                current_idx = ROLES.index(user["role"]) if user["role"] in ROLES else 0
                new_role = st.selectbox(
                    "Role",
                    ROLES,
                    index=current_idx,
                    key=f"role_sel_{uname}",
                )
                if st.button("Save Role", key=f"save_role_{uname}"):
                    user_db.update_user_role(uname, new_role)
                    st.success(f"Role for '{uname}' updated to '{new_role}'.")
                    st.rerun()

            with col_delete:
                if is_self:
                    st.warning("Cannot delete your own account.")
                else:
                    confirm = st.checkbox(
                        "Confirm delete", key=f"confirm_del_{uname}"
                    )
                    if st.button(
                        "Delete User",
                        key=f"delete_{uname}",
                        disabled=not confirm,
                    ):
                        user_db.delete_user(uname)
                        st.success(f"User '{uname}' deleted.")
                        st.rerun()

# ===========================================================================
# TAB 2 — Add User
# ===========================================================================

with tab_add:
    st.subheader("Create New User")

    with st.form("add_user_form", clear_on_submit=True):
        new_uname = st.text_input("Username")
        new_email = st.text_input("Email")
        new_role = st.selectbox("Role", ROLES, index=2)
        new_pw = st.text_input("Password", type="password")
        new_pw_confirm = st.text_input("Confirm Password", type="password")
        add_submitted = st.form_submit_button("Create User", use_container_width=True)

    if add_submitted:
        errors = []
        if not new_uname.strip():
            errors.append("Username is required.")
        if not re.match(r"^[^@]+@[^@]+\.[^@]+$", new_email.strip()):
            errors.append("Invalid email address.")
        if new_pw != new_pw_confirm:
            errors.append("Passwords do not match.")
        if len(new_pw) < 8:
            errors.append("Password must be at least 8 characters.")

        if errors:
            for e in errors:
                st.error(e)
        else:
            try:
                created = user_db.create_user(
                    new_uname.strip().lower(),
                    new_email.strip().lower(),
                    new_pw,
                    new_role,
                )
                st.success(
                    f"User created successfully!\n\n"
                    f"**Username:** {created['username']}  \n"
                    f"**Email:** {created['email']}  \n"
                    f"**Role:** {created['role']}"
                )
            except ValueError as exc:
                st.error(str(exc))

# ===========================================================================
# TAB 3 — App Permissions
# ===========================================================================

with tab_perms:
    st.subheader("App Permission Matrix")
    st.info(
        "admin role always retains admin panel access (cannot be revoked).",
        icon="ℹ️",
    )

    if st.button("🔄 Refresh Matrix"):
        for r in ROLES:
            for a in APPS:
                key = f"perm_{r}_{a}"
                if key in st.session_state:
                    del st.session_state[key]
        st.rerun()

    matrix = user_db.get_permissions_matrix()

    # Pre-initialise checkbox state from DB only on first render
    for r in ROLES:
        for a in APPS:
            key = f"perm_{r}_{a}"
            if key not in st.session_state:
                st.session_state[key] = matrix.get(r, {}).get(a, False)

    # Header row
    header_cols = st.columns([2] + [2] * len(APPS))
    header_cols[0].markdown("**Role**")
    for i, app in enumerate(APPS):
        header_cols[i + 1].markdown(f"**{app.replace('_', ' ').title()}**")

    # Data rows — one st.columns() per role
    for r in ROLES:
        row_cols = st.columns([2] + [2] * len(APPS))
        row_cols[0].markdown(f"`{r}`")
        for i, a in enumerate(APPS):
            key = f"perm_{r}_{a}"
            locked = r == "admin" and a == "admin"
            row_cols[i + 1].checkbox(
                label=a,
                key=key,
                disabled=locked,
                label_visibility="collapsed",
            )

    st.write("")
    if st.button("💾 Save Permissions", type="primary"):
        for r in ROLES:
            for a in APPS:
                if r == "admin" and a == "admin":
                    user_db.set_app_permission(r, a, True)
                else:
                    user_db.set_app_permission(r, a, bool(st.session_state.get(f"perm_{r}_{a}", False)))
        st.success("Permissions saved.")

# ===========================================================================
# TAB 4 — Reset Password
# ===========================================================================

with tab_reset:
    st.subheader("Reset User Password")
    all_unames = [u["username"] for u in user_db.list_users()]

    with st.form("reset_pw_form", clear_on_submit=True):
        target = st.selectbox("Select User", all_unames)
        reset_pw = st.text_input("New Password", type="password")
        reset_pw_confirm = st.text_input("Confirm New Password", type="password")
        reset_submitted = st.form_submit_button("Reset Password", use_container_width=True)

    if reset_submitted:
        errors = []
        if reset_pw != reset_pw_confirm:
            errors.append("Passwords do not match.")
        if len(reset_pw) < 8:
            errors.append("Password must be at least 8 characters.")

        if errors:
            for e in errors:
                st.error(e)
        else:
            user_db.update_password(target, reset_pw)
            st.success(f"Password for '{target}' has been reset successfully.")
