"""
Document Intelligence — Streamlit app (port 8501, route /Document_AI)

Allows authenticated users to select or upload a document and run one of
four AI-powered analysis modes against it via the shared LLM client.
"""

import sys
import os

# Ensure the repo root (two levels up) is on the Python path so that
# `from shared.xxx import yyy` works regardless of launch directory.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import io
import streamlit as st

from shared.auth import setup_authenticator, require_login
from shared.llm_client import llm
from shared.utils import list_documents, load_document, get_logger

# ---------------------------------------------------------------------------
# Page configuration — must be the first Streamlit call
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Document Intelligence",
    page_icon="📄",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------
logger = get_logger("document_intelligence")

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
authenticator = setup_authenticator()
name, username = require_login(authenticator)

# ---------------------------------------------------------------------------
# Header row: title + logout button
# ---------------------------------------------------------------------------
header_left, header_right = st.columns([8, 2])
with header_left:
    st.title("📄 Document Intelligence")
    st.markdown(
        "Upload or select a document, choose an analysis type, and let Claude extract insights."
    )
with header_right:
    st.write("")  # vertical spacing
    authenticator.logout("Logout", location="main")

st.divider()

# ---------------------------------------------------------------------------
# System prompts keyed by analysis type
# ---------------------------------------------------------------------------
SYSTEM_PROMPTS = {
    "Summary": (
        "You are a document analyst. Provide a concise executive summary in 3-5 bullet points."
    ),
    "Key Information Extraction": (
        "Extract all key information: dates, amounts, parties, obligations, deadlines. "
        "Format as a structured list."
    ),
    "Q&A": (
        "Answer questions about the document accurately. Quote relevant sections."
    ),
    "Risk Flags": (
        "Identify potential risks, obligations, unusual clauses, or red flags. "
        "Flag each with severity (High/Medium/Low)."
    ),
}

# ---------------------------------------------------------------------------
# Sidebar: document selection & analysis options
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Document Intelligence")
    st.markdown(
        "AI-powered analysis of contracts, policies, financial documents, and more. "
        "Powered by Claude claude-3-haiku-20240307."
    )
    st.divider()

    # --- Document source ---
    st.subheader("1. Choose a document")
    doc_source = st.radio(
        "Source",
        ["Select from library", "Upload your own"],
        label_visibility="collapsed",
    )

    document_text: str = ""
    selected_doc_name: str = ""

    if doc_source == "Select from library":
        available_docs = list_documents()
        if not available_docs:
            st.warning("No documents found in shared/mock_data/documents/")
        else:
            selected_doc_name = st.selectbox(
                "Select a document",
                available_docs,
                label_visibility="collapsed",
            )
            if selected_doc_name:
                try:
                    document_text = load_document(selected_doc_name)
                except FileNotFoundError as exc:
                    st.error(str(exc))

    else:  # Upload your own
        uploaded_file = st.file_uploader(
            "Upload a document",
            type=["txt", "pdf"],
            label_visibility="collapsed",
        )
        if uploaded_file is not None:
            selected_doc_name = uploaded_file.name
            if uploaded_file.type == "application/pdf":
                try:
                    import PyPDF2  # noqa: PLC0415

                    reader = PyPDF2.PdfReader(io.BytesIO(uploaded_file.read()))
                    document_text = "\n".join(
                        page.extract_text() or "" for page in reader.pages
                    )
                except Exception as exc:
                    st.error(f"Could not read PDF: {exc}")
            else:
                document_text = uploaded_file.read().decode("utf-8", errors="replace")

    st.divider()

    # --- Analysis type ---
    st.subheader("2. Analysis type")
    analysis_type = st.radio(
        "Analysis type",
        list(SYSTEM_PROMPTS.keys()),
        label_visibility="collapsed",
    )

# ---------------------------------------------------------------------------
# Session-state initialisation
# ---------------------------------------------------------------------------
if "last_analysis_key" not in st.session_state:
    st.session_state.last_analysis_key = None
if "last_analysis_result" not in st.session_state:
    st.session_state.last_analysis_result = None
if "last_qa_answer" not in st.session_state:
    st.session_state.last_qa_answer = None

# ---------------------------------------------------------------------------
# Main content area
# ---------------------------------------------------------------------------
if not document_text:
    st.info("Select or upload a document in the sidebar to get started.")
    st.stop()

col_doc, col_analysis = st.columns([4, 6])

# ---- Left column: document preview ----------------------------------------
with col_doc:
    st.subheader(f"Document preview: {selected_doc_name}")
    preview_text = document_text if len(document_text) <= 5000 else document_text[:5000] + "\n\n[...truncated for preview — full text sent to analysis...]"
    st.text_area(
        label="Document content",
        value=preview_text,
        height=520,
        disabled=True,
        label_visibility="collapsed",
    )
    st.caption(f"Characters: {len(document_text):,}")

# ---- Right column: analysis -----------------------------------------------
with col_analysis:
    st.subheader(f"Analysis: {analysis_type}")

    if analysis_type == "Q&A":
        # ---- Q&A mode: question input + ask button -------------------------
        question = st.text_input(
            "Ask a question about the document",
            placeholder="e.g. What are the payment terms?",
        )
        ask_button = st.button("Ask", type="primary", disabled=not question.strip())

        if ask_button and question.strip():
            # Build a unique cache key so we don't re-run unchanged queries
            qa_key = f"qa::{selected_doc_name}::{question.strip()}"
            if st.session_state.last_analysis_key != qa_key:
                logger.info(
                    "Q&A query | doc=%s | question=%s", selected_doc_name, question.strip()
                )
                with st.spinner("Claude is reading the document…"):
                    try:
                        answer = llm.query_with_context(
                            prompt=question.strip(),
                            context=document_text,
                            system_message=SYSTEM_PROMPTS["Q&A"],
                            max_tokens=2000,
                        )
                        st.session_state.last_analysis_key = qa_key
                        st.session_state.last_qa_answer = answer
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"Error calling LLM: {exc}")

        if st.session_state.last_qa_answer and st.session_state.last_analysis_key and \
                st.session_state.last_analysis_key.startswith(f"qa::{selected_doc_name}::"):
            st.markdown("**Answer:**")
            st.markdown(st.session_state.last_qa_answer)

    else:
        # ---- Summary / Extraction / Risk Flags mode ------------------------
        analysis_key = f"{analysis_type}::{selected_doc_name}"
        analyze_button = st.button("Analyze Document", type="primary")

        if analyze_button:
            if st.session_state.last_analysis_key != analysis_key:
                logger.info(
                    "Analysis run | doc=%s | type=%s", selected_doc_name, analysis_type
                )
                with st.spinner(f"Running {analysis_type}…"):
                    try:
                        result = llm.query_with_context(
                            prompt=f"Please perform the following analysis on the document: {analysis_type}",
                            context=document_text,
                            system_message=SYSTEM_PROMPTS[analysis_type],
                            max_tokens=2000,
                        )
                        st.session_state.last_analysis_key = analysis_key
                        st.session_state.last_analysis_result = result
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"Error calling LLM: {exc}")
            else:
                st.info("Using cached result. Change document or analysis type to re-run.")

        # Display cached result if it matches current selection
        if (
            st.session_state.last_analysis_result
            and st.session_state.last_analysis_key == analysis_key
        ):
            st.markdown(st.session_state.last_analysis_result)
        elif not analyze_button:
            st.info(f"Click **Analyze Document** to run {analysis_type}.")
