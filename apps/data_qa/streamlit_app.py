"""
Data Q&A — Streamlit app (port 8502, route /Text_to_SQL)

Allows authenticated users to ask natural-language questions about CSV
datasets. Claude generates pandas code, the app executes it safely, and
results are displayed as a table with an optional auto-generated chart.
A secondary tab provides a multi-turn conversational interface.
"""

import sys
import os

# Ensure the repo root (two levels up) is on the Python path so that
# `from shared.xxx import yyy` works regardless of launch directory.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import textwrap
import traceback

import pandas as pd
import plotly.express as px
import streamlit as st

from shared.auth import setup_authenticator, require_login, require_permission
from shared.llm_client import llm
from shared.utils import load_csv, get_logger
from shared import user_db

# ---------------------------------------------------------------------------
# Page configuration — must be the first Streamlit call
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Data Q&A",
    page_icon="📊",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------
logger = get_logger("data_qa")

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
authenticator = setup_authenticator()
name, username = require_login(authenticator, app_name="data_qa")
require_permission("data_qa")

# ---------------------------------------------------------------------------
# Header row
# ---------------------------------------------------------------------------
header_left, header_right = st.columns([8, 2])
with header_left:
    st.title("📊 Data Q&A")
    st.markdown(
        "Ask plain-English questions about your datasets — Claude translates them to pandas and runs them instantly."
    )
with header_right:
    st.write("")
    authenticator.logout("Logout", location="main")

st.divider()

# ---------------------------------------------------------------------------
# Dataset registry — maps display name → (filename, description, examples)
# ---------------------------------------------------------------------------
DATASETS = {
    "Sales Transactions": {
        "filename": "sales_transactions_2023_2024.csv",
        "description": (
            "Transactional sales data covering Jan 2023 – Dec 2024. "
            "Contains columns for date, region, product, quantity, unit price, and revenue."
        ),
        "examples": [
            "What were total sales by region in Q4 2023?",
            "Which product had the highest revenue last year?",
            "Show me month-over-month revenue growth for 2024.",
        ],
    },
    "Product Inventory": {
        "filename": "product_inventory_realtime.csv",
        "description": (
            "Current inventory snapshot with product ID, category, stock levels, "
            "reorder threshold, unit cost, and warehouse location."
        ),
        "examples": [
            "Which products are below their reorder threshold?",
            "What is the total inventory value by category?",
            "Show the top 10 most valuable items in stock.",
        ],
    },
    "Customer Demographics": {
        "filename": "customer_demographics.csv",
        "description": (
            "Customer master data including company name, industry, tier, "
            "annual revenue, employee count, and health score."
        ),
        "examples": [
            "How many customers are in each industry segment?",
            "What is the average deal size by customer tier?",
            "List the top 5 customers by annual revenue.",
        ],
    },
    "RD Wholesaler Activity": {
        "filename": "rd_wholesaler_activity.csv",
        "description": (
            "Relationship Director (RD) activity log covering Jan 2025–May 2026. "
            "Tracks wholesaler touchpoints with RIA firms across regions, including "
            "activity type, outcome, AUM discussed, and products pitched."
        ),
        "examples": [
            "Which RD had the most 'Closed/Won' outcomes in Q1 2026?",
            "Show total AUM discussed by region and activity type.",
            "Which RIA firms have been contacted most frequently in 2026 YTD?",
            "What is the conversion rate (Closed/Won) by RD?",
            "List all activities where AUM discussed exceeded $200M.",
        ],
    },
    "RIA Distribution Metrics": {
        "filename": "ria_distribution_metrics.csv",
        "description": (
            "Snapshot of RIA firm distribution metrics as of May 2026. Covers 25 "
            "RIA relationships including AUM, net flows, product mix, engagement "
            "scores, and platform capture rates."
        ),
        "examples": [
            "Which RIA firms are classified as At-Risk with negative net flows YTD?",
            "What is the average platform capture percentage by RD owner?",
            "Show AUM on platform by region sorted descending.",
            "Which Platinum-tier firms have an engagement score below 7?",
            "Compare net flows QTD vs YTD for all Growth-status firms.",
        ],
    },
}

# ---------------------------------------------------------------------------
# Sidebar: dataset selector + options
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Data Q&A")
    st.markdown(
        "Select a dataset and ask a question in plain English. "
        "Claude generates and runs the corresponding pandas query."
    )
    st.caption(f"Logged in as: {username} ({st.session_state.get('role', '')})")
    st.divider()

    # Dataset selector
    st.subheader("Dataset")
    selected_dataset = st.selectbox(
        "Choose dataset",
        list(DATASETS.keys()),
        label_visibility="collapsed",
    )
    dataset_meta = DATASETS[selected_dataset]
    st.caption(dataset_meta["description"])

    st.divider()

    # Show schema toggle
    show_schema = st.checkbox("Show dataset schema", value=False)

# ---------------------------------------------------------------------------
# Load selected dataset (cached)
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def get_dataframe(filename: str) -> pd.DataFrame:
    """Load and cache a CSV dataset by filename."""
    return load_csv(filename)


try:
    df = get_dataframe(dataset_meta["filename"])
except FileNotFoundError:
    st.error(
        f"Dataset file `{dataset_meta['filename']}` not found in shared/mock_data/datasets/. "
        "Please check the file exists."
    )
    st.stop()

# Show schema if requested
if show_schema:
    with st.sidebar:
        st.subheader("Schema")
        schema_df = pd.DataFrame(
            {"Column": df.columns, "Type": [str(t) for t in df.dtypes]}
        ).reset_index(drop=True)
        st.dataframe(schema_df, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------
if "query_history" not in st.session_state:
    st.session_state.query_history = []  # list of {question, code, result_df, error}
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []  # list of {role, content}
if "last_query_key" not in st.session_state:
    st.session_state.last_query_key = None
if "last_code" not in st.session_state:
    st.session_state.last_code = None
if "last_result" not in st.session_state:
    st.session_state.last_result = None

# ---------------------------------------------------------------------------
# Helper: build schema string for LLM prompt
# ---------------------------------------------------------------------------
def build_schema_string(dataframe: pd.DataFrame) -> str:
    """Return a readable schema string including column names and types."""
    lines = [f"Table name: df  (rows: {len(dataframe):,})"]
    lines.append("Columns:")
    for col, dtype in dataframe.dtypes.items():
        sample = dataframe[col].dropna().head(3).tolist()
        lines.append(f"  - {col} ({dtype}) — sample: {sample}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helper: safely execute generated pandas code
# ---------------------------------------------------------------------------
def execute_pandas_code(code: str, dataframe: pd.DataFrame):
    """
    Execute LLM-generated pandas code in a restricted namespace.

    The code must assign its final result to a variable called `result`.
    Returns (result, error_string). Either result or error_string will be None.
    """
    # Strip markdown fences if the LLM wrapped the code
    cleaned = code.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        cleaned = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    namespace = {"df": dataframe, "pd": pd}
    try:
        exec(cleaned, namespace)  # noqa: S102
    except Exception:  # noqa: BLE001
        return None, traceback.format_exc()

    # Accept `result` variable or the last assignment
    if "result" in namespace:
        return namespace["result"], None

    # Try to infer result from local namespace (last DataFrame-like value)
    for var_name in reversed(list(namespace.keys())):
        if var_name in ("df", "pd", "__builtins__"):
            continue
        val = namespace[var_name]
        if isinstance(val, (pd.DataFrame, pd.Series)):
            return val, None
        if isinstance(val, (int, float, str, list)):
            return val, None

    return None, "Code ran but no `result` variable was found. Assign your answer to `result`."


# ---------------------------------------------------------------------------
# Main tabs: Query Mode | Chat with Data
# ---------------------------------------------------------------------------
tab_query, tab_chat = st.tabs(["Generate & Run Query", "Chat with Data"])

# ===========================================================================
# Tab 1 — Generate & Run Query
# ===========================================================================
with tab_query:
    st.subheader(f"Ask a question about: {selected_dataset}")

    # Example queries
    with st.expander("Example questions", expanded=False):
        for ex in dataset_meta["examples"]:
            st.markdown(f"- {ex}")

    # Question input
    question = st.text_input(
        "Your question",
        placeholder="e.g. What are the top 5 products by total revenue?",
        key="query_input",
    )

    run_button = st.button(
        "Generate pandas & Run",
        type="primary",
        disabled=not question.strip(),
    )

    if run_button and question.strip():
        query_key = f"{selected_dataset}::{question.strip()}"

        if st.session_state.last_query_key == query_key:
            st.info("Showing cached result. Change the question to re-run.")
        else:
            logger.info("Data query | dataset=%s | question=%s", selected_dataset, question.strip())

            schema_str = build_schema_string(df)
            prompt = textwrap.dedent(f"""
                Given this table schema:
                {schema_str}

                Generate a pandas DataFrame query (not SQL, use pandas syntax) to answer:
                {question.strip()}

                Return only the pandas code, no explanation. Assign the final result to a variable called `result`.
                The DataFrame is already loaded as `df`. Do not re-read any files.
            """).strip()

            with st.spinner("Claude is generating the query…"):
                generated_code, tokens = llm.query_with_usage(
                    prompt=prompt,
                    system_message=(
                        "You are a pandas expert. Generate concise, correct pandas code. "
                        "Always assign the final answer to a variable named `result`. "
                        "Use only standard pandas operations."
                    ),
                    max_tokens=1000,
                )
                if tokens > 0:
                    user_db.record_usage(username, "data_qa", tokens)

            result_value, exec_error = execute_pandas_code(generated_code, df)

            st.session_state.last_query_key = query_key
            st.session_state.last_code = generated_code
            st.session_state.last_result = result_value
            st.session_state.last_exec_error = exec_error

            # Append to history
            st.session_state.query_history.append({
                "question": question.strip(),
                "code": generated_code,
                "result": result_value,
                "error": exec_error,
            })

    # Display results
    if st.session_state.last_code:
        st.markdown("---")
        col_code, col_result = st.columns([1, 1])

        with col_code:
            st.markdown("**Generated pandas code**")
            st.code(st.session_state.last_code, language="python")

        with col_result:
            exec_error = getattr(st.session_state, "last_exec_error", None)
            if exec_error:
                st.error("Execution failed. You can retry with a different question.")
                with st.expander("Error details"):
                    st.code(exec_error)
            else:
                result_value = st.session_state.last_result
                if result_value is None:
                    st.warning("Query ran but returned no result.")
                elif isinstance(result_value, pd.DataFrame):
                    st.markdown(f"**Results** ({len(result_value):,} rows)")
                    st.dataframe(result_value, use_container_width=True)

                    # Auto-generate bar chart if DataFrame has numeric columns
                    numeric_cols = result_value.select_dtypes(include="number").columns.tolist()
                    cat_cols = result_value.select_dtypes(exclude="number").columns.tolist()
                    if numeric_cols and cat_cols and len(result_value) > 1:
                        st.markdown("**Auto-chart**")
                        try:
                            fig = px.bar(
                                result_value,
                                x=cat_cols[0],
                                y=numeric_cols[0],
                                title=f"{numeric_cols[0]} by {cat_cols[0]}",
                                template="plotly_white",
                            )
                            st.plotly_chart(fig, use_container_width=True)
                        except Exception:  # noqa: BLE001
                            pass  # Chart generation is best-effort

                elif isinstance(result_value, pd.Series):
                    st.markdown("**Results**")
                    st.dataframe(result_value.to_frame(), use_container_width=True)
                else:
                    st.markdown("**Result**")
                    st.write(result_value)

    # Query history in expander
    if len(st.session_state.query_history) > 1:
        with st.expander(f"Query history ({len(st.session_state.query_history)} queries)"):
            for i, entry in enumerate(reversed(st.session_state.query_history[:-1]), 1):
                st.markdown(f"**Q{i}:** {entry['question']}")
                st.code(entry["code"], language="python")
                if entry["error"]:
                    st.error(entry["error"][:200])
                st.markdown("---")

# ===========================================================================
# Tab 2 — Chat with Data (multi-turn conversational Q&A)
# ===========================================================================
with tab_chat:
    st.subheader(f"Conversational Q&A: {selected_dataset}")
    st.caption(
        "Ask follow-up questions. Context accumulates in this session so you can "
        "say things like 'now filter that to Q4 only' or 'show me the same for product X'."
    )

    # Display existing chat messages
    for msg in st.session_state.chat_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input
    chat_input = st.chat_input("Ask anything about the data…")

    if chat_input:
        logger.info("Chat query | dataset=%s | message=%s", selected_dataset, chat_input)

        # Add user message to history and render immediately
        st.session_state.chat_messages.append({"role": "user", "content": chat_input})
        with st.chat_message("user"):
            st.markdown(chat_input)

        # Build context for LLM: schema + conversation so far
        schema_str = build_schema_string(df)

        # Summarise the conversation history for the prompt
        history_text = "\n".join(
            f"{m['role'].capitalize()}: {m['content']}"
            for m in st.session_state.chat_messages[:-1]  # exclude the just-added message
        )

        chat_prompt = textwrap.dedent(f"""
            You are a data analyst. The user is asking questions about a dataset.

            Dataset schema:
            {schema_str}

            Conversation so far:
            {history_text}

            Latest question: {chat_input}

            Answer the question concisely. If you generate pandas code, wrap it in ```python fences.
            Use available context to understand references like 'that', 'those', 'same filter', etc.
        """).strip()

        with st.chat_message("assistant"):
            with st.spinner("Thinking…"):
                try:
                    response, tokens = llm.query_with_usage(
                        prompt=chat_prompt,
                        system_message=(
                            "You are an expert data analyst. Answer clearly and concisely. "
                            "Include pandas code examples when helpful."
                        ),
                        max_tokens=1500,
                    )
                    if tokens > 0:
                        user_db.record_usage(username, "data_qa", tokens)
                    st.markdown(response)
                    st.session_state.chat_messages.append(
                        {"role": "assistant", "content": response}
                    )
                except Exception as exc:  # noqa: BLE001
                    error_msg = f"Error: {exc}"
                    st.error(error_msg)
                    st.session_state.chat_messages.append(
                        {"role": "assistant", "content": error_msg}
                    )

    # Clear chat button
    if st.session_state.chat_messages:
        if st.button("Clear conversation", key="clear_chat"):
            st.session_state.chat_messages = []
            st.rerun()
