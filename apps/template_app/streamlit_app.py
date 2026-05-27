"""
<App Name> — Streamlit app (port <PORT>, route /<ROUTE>)  # DEVELOPER: update docstring
<Brief one-line description of what this app does>
"""

import sys
import os

# Ensure the repo root (two levels up) is on the Python path so that
# `from shared.xxx import yyy` works regardless of launch directory.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import streamlit as st

from shared.auth import setup_authenticator, require_login  # DEVELOPER: add require_permission if your app needs role-based access
from shared.llm_client import llm
from shared.utils import get_logger

# ---------------------------------------------------------------------------
# Page configuration — must be the first Streamlit call
# DEVELOPER: set your page title, icon, and layout
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="My App",        # DEVELOPER: rename to your app name
    page_icon="🤖",              # DEVELOPER: pick an emoji or path to .ico
    layout="wide",
)

# ---------------------------------------------------------------------------
# Logger
# DEVELOPER: rename the string to match your app directory name
# ---------------------------------------------------------------------------
logger = get_logger("template_app")

# ---------------------------------------------------------------------------
# Authentication — do not modify this block
# ---------------------------------------------------------------------------
authenticator = setup_authenticator()
name, username = require_login(authenticator, app_name="template_app")  # DEVELOPER: update app_name
# DEVELOPER: uncomment the line below and pass your app's permission key
# require_permission("my_app_key")

# ---------------------------------------------------------------------------
# Header row — standard layout for all platform apps
# DEVELOPER: update the title emoji and text; subtitle describes your use case
# ---------------------------------------------------------------------------
header_left, header_right = st.columns([8, 2])
with header_left:
    st.title("🤖 My App")
    st.markdown("Brief description of what this app does. Powered by Claude.")
with header_right:
    st.write("")
    authenticator.logout("Logout", location="main")

st.divider()

# ---------------------------------------------------------------------------
# Session state initialisation
# DEVELOPER: define your session state keys here; add as many as needed
# ---------------------------------------------------------------------------
if "my_result" not in st.session_state:
    st.session_state["my_result"] = None
# DEVELOPER: add more keys below:
# if "my_other_key" not in st.session_state:
#     st.session_state["my_other_key"] = []

# ---------------------------------------------------------------------------
# Sidebar controls
# DEVELOPER: add your controls here (dropdowns, sliders, file uploaders, etc.)
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Controls")
    st.caption(f"Logged in as: {username} ({st.session_state.get('role', '')})")
    st.divider()

    # DEVELOPER: replace this example with your actual controls
    user_input = st.text_area(
        "Enter your input",
        placeholder="Type something here…",
        height=120,
    )
    run_button = st.button("Run", type="primary", use_container_width=True)

# ---------------------------------------------------------------------------
# Main content area
# DEVELOPER: replace this with your use-case logic
# ---------------------------------------------------------------------------
if run_button and user_input.strip():
    logger.info("User triggered run | user=%s", username)

    # DEVELOPER: build your system prompt and user prompt here
    system_prompt = "You are a helpful assistant."
    user_prompt = user_input.strip()

    with st.spinner("Thinking…"):
        try:
            response, tokens = llm.query_with_usage(
                prompt=user_prompt,
                system_message=system_prompt,
                max_tokens=1500,  # DEVELOPER: adjust as needed
            )
            st.session_state["my_result"] = response
            # DEVELOPER: record token usage if you have user_db imported
            # user_db.record_usage(username, "my_app_key", tokens)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Error: {exc}")

# Display result
if st.session_state["my_result"]:
    st.markdown("### Result")
    st.markdown(st.session_state["my_result"])
    # DEVELOPER: add download buttons, charts, or other output components here
else:
    st.info("Configure your inputs in the sidebar and click **Run** to begin.")
