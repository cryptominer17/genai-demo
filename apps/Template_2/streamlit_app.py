"""
Content Generation — Streamlit app (port 8507, route /Template_2/)
Turn structured data into personalized, variant outputs.
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import streamlit as st

from shared.auth import setup_authenticator, require_login
from shared.llm_client import llm
from shared.utils import get_logger
from shared import user_db

st.set_page_config(
    page_title="Content Generation",
    page_icon="✍️",
    layout="wide",
)

logger = get_logger("Template_2")

authenticator = setup_authenticator()
name, username = require_login(authenticator, app_name="Template_2")

# Header
header_left, header_right = st.columns([8, 2])
with header_left:
    st.title("✍️ Content Generation")
    st.markdown("**Turn Structured Data into Personalized, Variant Outputs**")
with header_right:
    st.write("")
    authenticator.logout("Logout", location="main")

st.divider()

st.markdown(
    """
    Generate personalized, variant content from structured data inputs.
    You own the use-case logic, prompts, and all app-specific code.
    """
)

st.divider()

# ──────────────────────────────────────────────────────────────────────────────
# TODO: Add your use-case logic, prompts, and app-specific code here
# ──────────────────────────────────────────────────────────────────────────────

# Session state
if "generation_result" not in st.session_state:
    st.session_state["generation_result"] = None

# Sidebar
with st.sidebar:
    st.header("Controls")
    st.caption(f"Logged in as: {username} ({st.session_state.get('role', '')})")
    st.divider()

    # TODO: replace with your use-case controls (structured data inputs, tone selectors, etc.)
    user_input = st.text_area(
        "Paste structured data",
        placeholder="Paste JSON, CSV row, or key-value pairs here…",
        height=200,
    )
    run_button = st.button("Generate", type="primary", use_container_width=True)

# Main
if run_button and user_input.strip():
    logger.info("User triggered generation | user=%s", username)

    # TODO: replace with your system prompt and generation logic
    system_prompt = (
        "You are a content generation assistant. "
        "Given structured data input, produce personalized, variant content. "
        "Return clear, well-formatted output tailored to the provided data."
    )

    with st.spinner("Generating…"):
        try:
            response, tokens = llm.query_with_usage(
                prompt=user_input.strip(),
                system_message=system_prompt,
                max_tokens=2000,
            )
            st.session_state["generation_result"] = response
            user_db.record_usage(username, "Template_2", tokens)
        except Exception as exc:
            st.error(f"Error: {exc}")

if st.session_state["generation_result"]:
    st.markdown("### Generated Output")
    st.markdown(st.session_state["generation_result"])
    # TODO: add structured output (download buttons, variant comparison, etc.) here
else:
    st.info("Paste structured data in the sidebar and click **Generate** to begin.")
