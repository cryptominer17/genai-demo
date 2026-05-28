"""
Data Extraction & Enrichment — Streamlit app (port 8506, route /Template_1/)
Parse contracts, extract key terms, obligations, and risk flags from unstructured documents.
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
    page_title="Data Extraction & Enrichment",
    page_icon="🔍",
    layout="wide",
)

logger = get_logger("Template_1")

authenticator = setup_authenticator()
name, username = require_login(authenticator, app_name="Template_1")

# Header
header_left, header_right = st.columns([8, 2])
with header_left:
    st.title("🔍 Data Extraction & Enrichment")
    st.markdown("**Unstructured to Structured Intelligence**")
with header_right:
    st.write("")
    authenticator.logout("Logout", location="main")

st.divider()

st.markdown(
    """
    Parse contracts, extract key terms, obligations, and risk flags.
    Analyze call transcripts or regulatory filings.
    You own the use-case logic, prompts, and all app-specific code.
    """
)

st.divider()

# ──────────────────────────────────────────────────────────────────────────────
# TODO: Add your use-case logic, prompts, and app-specific code here
# ──────────────────────────────────────────────────────────────────────────────

# Session state
if "extraction_result" not in st.session_state:
    st.session_state["extraction_result"] = None

# Sidebar
with st.sidebar:
    st.header("Controls")
    st.caption(f"Logged in as: {username} ({st.session_state.get('role', '')})")
    st.divider()

    # TODO: replace with your use-case controls (file uploader, dropdowns, etc.)
    user_input = st.text_area(
        "Paste document text",
        placeholder="Paste contract, transcript, or filing text here…",
        height=200,
    )
    run_button = st.button("Extract", type="primary", use_container_width=True)

# Main
if run_button and user_input.strip():
    logger.info("User triggered extraction | user=%s", username)

    # TODO: replace with your system prompt and extraction logic
    system_prompt = (
        "You are a document analysis assistant. "
        "Extract key terms, obligations, and risk flags from the provided text. "
        "Return the results in a clear, structured format."
    )

    with st.spinner("Extracting…"):
        try:
            response, tokens = llm.query_with_usage(
                prompt=user_input.strip(),
                system_message=system_prompt,
                max_tokens=2000,
            )
            st.session_state["extraction_result"] = response
            user_db.record_usage(username, "Template_1", tokens)
        except Exception as exc:
            st.error(f"Error: {exc}")

if st.session_state["extraction_result"]:
    st.markdown("### Extraction Result")
    st.markdown(st.session_state["extraction_result"])
    # TODO: add structured output (tables, download buttons, charts) here
else:
    st.info("Paste document text in the sidebar and click **Extract** to begin.")
