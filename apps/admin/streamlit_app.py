"""
Admin Console — Streamlit app for user management and RBAC.

Only users with the 'admin' role can access this page.
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import re
from datetime import date, timedelta

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
# Non-admin apps that can have per-user overrides
USER_APPS = ["document_intelligence", "data_qa", "report_generator"]

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab_users, tab_add, tab_perms, tab_reset, tab_usage = st.tabs(
    ["👥 Users", "🔑 Add User", "🔒 App Permissions", "🔄 Reset Password", "📊 Usage"]
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
        display_cols = [
            "username", "email", "role", "is_active",
            "must_change_password", "created_at", "last_login",
        ]
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
        if user.get("must_change_password"):
            expander_label += " ⚠️ must change password"

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

            # ---------------------------------------------------------------
            # App Access Overrides — per-user permissions that override role
            # ---------------------------------------------------------------
            st.divider()
            st.markdown("**App Access Overrides** — override role-based permissions for this user")

            overrides = user_db.get_user_overrides(uname)
            override_map = {o["app_name"]: bool(o["can_access"]) for o in overrides}

            ov_cols = st.columns(len(USER_APPS))
            for i, app_n in enumerate(USER_APPS):
                # Pre-fill: use existing override value; fall back to role permission.
                if app_n in override_map:
                    default_val = override_map[app_n]
                else:
                    default_val = user_db.check_app_permission(user["role"], app_n)

                ov_cols[i].checkbox(
                    app_n.replace("_", " ").title(),
                    value=default_val,
                    key=f"override_{uname}_{app_n}",
                    help=(
                        "Override active" if app_n in override_map
                        else "Using role default — save to set an explicit override"
                    ),
                )

            save_ov_col, info_col = st.columns([1, 3])
            if save_ov_col.button("Save Overrides", key=f"save_overrides_{uname}"):
                for app_n in USER_APPS:
                    can = bool(st.session_state.get(f"override_{uname}_{app_n}", False))
                    user_db.set_user_override(uname, app_n, can, granted_by=username)
                st.success(f"Access overrides saved for '{uname}'.")
                st.rerun()

            if overrides:
                override_desc = ", ".join(
                    f"{o['app_name']} ({'✓' if o['can_access'] else '✗'})"
                    for o in overrides
                )
                info_col.caption(f"Active overrides: {override_desc}")
            else:
                info_col.caption("No overrides set — all permissions come from role.")

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
                    f"**Role:** {created['role']}  \n\n"
                    f"The user will be prompted to set a new password on first login."
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
        force_change = st.checkbox(
            "Require user to change password on next login",
            value=True,
        )
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
            user_db.set_must_change_password(target, force_change)
            st.success(
                f"Password for '{target}' has been reset successfully."
                + (" User will be prompted to change it on next login." if force_change else "")
            )

# ===========================================================================
# TAB 5 — Usage
# ===========================================================================

with tab_usage:
    st.subheader("Platform Usage")

    # Date-range filter
    today = date.today()
    date_range = st.date_input(
        "Date range",
        value=(today - timedelta(days=30), today),
        key="usage_date_range",
    )

    # Unpack the range — the widget can return a partial tuple while the user
    # is still clicking, so handle 0, 1, or 2 elements defensively.
    date_from = date_to = None
    if isinstance(date_range, (list, tuple)):
        if len(date_range) >= 1 and date_range[0]:
            date_from = date_range[0].isoformat()
        if len(date_range) >= 2 and date_range[1]:
            date_to = date_range[1].isoformat()
    elif date_range:
        date_from = date_range.isoformat()

    summary = user_db.get_usage_summary(date_from=date_from, date_to=date_to)

    if not summary:
        st.info("No usage data recorded yet for this date range.")
    else:
        summary_df = pd.DataFrame(summary)

        # Summary table
        st.markdown("#### Requests & Tokens by User and App")
        st.dataframe(summary_df, use_container_width=True, hide_index=True)

        st.markdown("---")

        # Bar chart: total tokens by user
        st.markdown("#### Total Tokens by User")
        user_tokens = (
            summary_df.groupby("username")["total_tokens"]
            .sum()
            .reset_index()
            .set_index("username")
        )
        st.bar_chart(user_tokens["total_tokens"])

        # Quick headline metrics
        st.markdown("---")
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Total Requests", int(summary_df["total_requests"].sum()))
        col_m2.metric("Total Tokens", f"{int(summary_df['total_tokens'].sum()):,}")
        col_m3.metric("Active Users", summary_df["username"].nunique())
