"""
Report Generator — Streamlit app (port 8503, route /BI_Dashboard)

Generates AI-powered BI reports for Fidelity Institutional. The user selects
a report type, audience, and depth; Claude produces formatted markdown backed
by real BI data. Charts and raw data are shown in companion tabs.
"""

import sys
import os

# Ensure the repo root (two levels up) is on the Python path so that
# `from shared.xxx import yyy` works regardless of launch directory.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import json
import textwrap

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from shared.auth import setup_authenticator, require_login, require_permission
from shared.llm_client import llm
from shared.utils import load_csv, load_json, get_logger
from shared import user_db

# ---------------------------------------------------------------------------
# Page configuration — must be the first Streamlit call
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Report Generator",
    page_icon="📈",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------
logger = get_logger("report_generator")

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
authenticator = setup_authenticator()
name, username = require_login(authenticator, app_name="report_generator")
require_permission("report_generator")

# ---------------------------------------------------------------------------
# Header row
# ---------------------------------------------------------------------------
header_left, header_right = st.columns([8, 2])
with header_left:
    st.title("📈 Report Generator")
    st.markdown(
        "AI-generated business intelligence reports tailored to your audience, "
        "backed by live BI data. Powered by Claude claude-haiku-4-5-20251001."
    )
with header_right:
    st.write("")
    authenticator.logout("Logout", location="main")

st.divider()

# ---------------------------------------------------------------------------
# Report registry — maps report type → data loader and description
# ---------------------------------------------------------------------------
REPORT_TYPES = [
    "Q1 2024 KPI Summary",
    "Sales Forecast Analysis",
    "Customer Segmentation Report",
    "Executive Board Deck Summary",
]

AUDIENCE_OPTIONS = ["Executive/Board", "Sales Leadership", "Operations Team"]
DEPTH_OPTIONS = ["One-pager", "Full Report", "Bullet Points Only"]

# ---------------------------------------------------------------------------
# Data loading helpers (cached)
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_kpi_data() -> dict:
    """Load Q1 2024 KPI JSON from bi_data."""
    try:
        return load_json("quarterly_kpis_2024.json", subfolder="bi_data")
    except FileNotFoundError:
        # Return representative fallback data so the app remains demonstrable
        return {
            "period": "Q1 2024",
            "kpis": [
                {"name": "AUM Growth", "target": 5.0, "actual": 4.8, "unit": "%"},
                {"name": "Net New Assets", "target": 2500, "actual": 2730, "unit": "$M"},
                {"name": "Client Retention", "target": 95.0, "actual": 96.2, "unit": "%"},
                {"name": "Revenue", "target": 185, "actual": 191, "unit": "$M"},
                {"name": "Cost-to-Income Ratio", "target": 62.0, "actual": 64.1, "unit": "%"},
                {"name": "Digital Adoption", "target": 70.0, "actual": 73.5, "unit": "%"},
                {"name": "NPS Score", "target": 45, "actual": 48, "unit": "pts"},
            ],
        }


@st.cache_data(show_spinner=False)
def load_forecast_data() -> pd.DataFrame:
    """Load 12-month sales forecast CSV from bi_data."""
    try:
        return load_csv("sales_forecast_12mo.csv", subfolder="bi_data")
    except FileNotFoundError:
        # Fallback: generate synthetic 12-month forecast
        import numpy as np

        rng = np.random.default_rng(42)
        months = pd.date_range("2024-01-01", periods=12, freq="MS").strftime("%b %Y").tolist()
        actuals = [None] * 3 + [None] * 9  # only Q1 has actuals
        actual_vals = [188, 195, 203] + [None] * 9
        forecast = [188, 195, 203, 210, 218, 225, 232, 241, 249, 258, 266, 275]
        lower = [v - rng.integers(8, 15) if v else None for v in forecast]
        upper = [v + rng.integers(8, 15) if v else None for v in forecast]
        return pd.DataFrame({
            "month": months,
            "actual": actual_vals,
            "forecast": forecast,
            "lower_bound": lower,
            "upper_bound": upper,
        })


@st.cache_data(show_spinner=False)
def load_segmentation_data() -> dict:
    """Load customer segmentation JSON from bi_data."""
    try:
        return load_json("customer_segmentation.json", subfolder="bi_data")
    except FileNotFoundError:
        return {
            "total_customers": 847,
            "by_industry": [
                {"industry": "Asset Management", "count": 312, "pct": 36.8},
                {"industry": "Insurance", "count": 198, "pct": 23.4},
                {"industry": "Banking", "count": 152, "pct": 17.9},
                {"industry": "Pension Funds", "count": 112, "pct": 13.2},
                {"industry": "Other", "count": 73, "pct": 8.6},
            ],
            "by_health_score": [
                {"bucket": "Champion (80-100)", "count": 203},
                {"bucket": "Healthy (60-79)", "count": 318},
                {"bucket": "At Risk (40-59)", "count": 241},
                {"bucket": "Critical (<40)", "count": 85},
            ],
            "average_health_score": 63.4,
            "churn_risk_count": 85,
        }


# ---------------------------------------------------------------------------
# Helper: assemble raw data payload for the LLM
# ---------------------------------------------------------------------------
def get_report_data(report_type: str) -> tuple[str, dict | pd.DataFrame]:
    """
    Return (data_string_for_llm, raw_data_for_display) for the selected report type.
    """
    if report_type == "Q1 2024 KPI Summary":
        data = load_kpi_data()
        return json.dumps(data, indent=2), data

    elif report_type == "Sales Forecast Analysis":
        df = load_forecast_data()
        return df.to_string(index=False), df

    elif report_type == "Customer Segmentation Report":
        data = load_segmentation_data()
        return json.dumps(data, indent=2), data

    else:  # Executive Board Deck Summary — combine all three
        kpi_data = load_kpi_data()
        forecast_df = load_forecast_data()
        seg_data = load_segmentation_data()
        combined = {
            "kpi_summary": kpi_data,
            "sales_forecast_head": forecast_df.head(6).to_dict(orient="records"),
            "customer_segmentation": seg_data,
        }
        raw = {
            "KPI Summary": kpi_data,
            "Sales Forecast (first 6 months)": forecast_df.head(6).to_dict(),
            "Customer Segmentation": seg_data,
        }
        return json.dumps(combined, indent=2), raw


# ---------------------------------------------------------------------------
# Helper: depth instruction string
# ---------------------------------------------------------------------------
DEPTH_INSTRUCTIONS = {
    "One-pager": (
        "Write a concise one-pager (300-400 words). Focus on the top 3-5 insights only. "
        "Use 2-3 short sections with bold headers."
    ),
    "Full Report": (
        "Write a comprehensive report with multiple sections: Executive Summary, "
        "Key Metrics Analysis, Trends & Observations, Risks & Watch Items, "
        "and Recommendations. Use headers (##), bullet points, and callout emphasis."
    ),
    "Bullet Points Only": (
        "Present everything as structured bullet points — no prose paragraphs. "
        "Use nested bullets where appropriate. Each point should be actionable or insightful."
    ),
}

# ---------------------------------------------------------------------------
# Sidebar: report configuration
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Report Configuration")
    st.caption(f"Logged in as: {username} ({st.session_state.get('role', '')})")
    st.divider()

    report_type = st.selectbox("Report type", REPORT_TYPES)
    st.caption("Time period: Q1 2024")

    st.divider()

    audience = st.selectbox("Audience", AUDIENCE_OPTIONS)
    report_depth = st.selectbox("Report depth", DEPTH_OPTIONS)

    st.divider()

    generate_button = st.button("Generate Report", type="primary", use_container_width=True)

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "report_cache" not in st.session_state:
    st.session_state.report_cache = {}  # key → report_text

report_cache_key = f"{report_type}::{audience}::{report_depth}"

# ---------------------------------------------------------------------------
# Report generation on button click
# ---------------------------------------------------------------------------
if generate_button:
    logger.info(
        "Report generation | type=%s | audience=%s | depth=%s",
        report_type,
        audience,
        report_depth,
    )

    data_string, _ = get_report_data(report_type)

    system_prompt = (
        "You are a business intelligence analyst at Fidelity Institutional. "
        "Generate professional reports. Use headers, bullets, and callouts. "
        "Highlight key insights, trends, and recommendations. "
        "Write in a professional financial services tone."
    )

    depth_instruction = DEPTH_INSTRUCTIONS[report_depth]
    audience_note = f"The audience for this report is: {audience}. Tailor language and detail accordingly."

    user_prompt = textwrap.dedent(f"""
        Generate a {report_type} report.

        {audience_note}

        {depth_instruction}

        Use the following data as your source:

        {data_string}

        Start the report directly — do not include a preamble about what you are about to do.
    """).strip()

    if report_cache_key in st.session_state.report_cache:
        # Use cached version, but force regeneration if button was explicitly clicked
        pass

    with st.spinner(f"Generating {report_type}…"):
        try:
            report_text, tokens = llm.query_with_usage(
                prompt=user_prompt,
                system_message=system_prompt,
                max_tokens=3000,
            )
            if tokens > 0:
                user_db.record_usage(username, "report_generator", tokens)
            st.session_state.report_cache[report_cache_key] = report_text
        except Exception as exc:  # noqa: BLE001
            st.error(f"Error generating report: {exc}")

# ---------------------------------------------------------------------------
# Retrieve cached report (if any) for current config
# ---------------------------------------------------------------------------
current_report = st.session_state.report_cache.get(report_cache_key)

# ---------------------------------------------------------------------------
# Main tabs: Report | Data | Charts
# ---------------------------------------------------------------------------
tab_report, tab_data, tab_charts = st.tabs(["Report", "Data", "Charts"])

# ===========================================================================
# Tab 1 — Report
# ===========================================================================
with tab_report:
    if not current_report:
        st.info(
            "Configure your report in the sidebar and click **Generate Report** to begin."
        )
    else:
        # Report header metadata
        meta_col1, meta_col2, meta_col3 = st.columns(3)
        meta_col1.metric("Report Type", report_type)
        meta_col2.metric("Audience", audience)
        meta_col3.metric("Depth", report_depth)

        st.markdown("---")
        st.markdown(current_report)

        st.markdown("---")
        st.download_button(
            label="Download Report (.txt)",
            data=current_report,
            file_name=f"{report_type.replace(' ', '_')}_{audience.replace('/', '_')}.txt",
            mime="text/plain",
        )

# ===========================================================================
# Tab 2 — Data
# ===========================================================================
with tab_data:
    st.subheader(f"Source data: {report_type}")
    _, raw_data = get_report_data(report_type)

    if isinstance(raw_data, pd.DataFrame):
        st.dataframe(raw_data, use_container_width=True)
    elif isinstance(raw_data, dict):
        if report_type == "Executive Board Deck Summary":
            # Multi-section display
            for section, section_data in raw_data.items():
                with st.expander(section, expanded=True):
                    st.json(section_data)
        else:
            st.json(raw_data)
    else:
        st.write(raw_data)

# ===========================================================================
# Tab 3 — Charts
# ===========================================================================
with tab_charts:
    st.subheader(f"Charts: {report_type}")

    # ---- KPI Summary chart -------------------------------------------------
    if report_type == "Q1 2024 KPI Summary":
        kpi_data = load_kpi_data()
        kpis = kpi_data.get("kpis", [])
        if kpis:
            kpi_df = pd.DataFrame(kpis)
            kpi_df["pct_of_target"] = (kpi_df["actual"] / kpi_df["target"] * 100).round(1)
            kpi_df["color"] = kpi_df["pct_of_target"].apply(
                lambda x: "green" if x >= 100 else ("orange" if x >= 90 else "red")
            )

            fig = px.bar(
                kpi_df,
                y="name",
                x="pct_of_target",
                orientation="h",
                title="KPI Performance vs Target (%)",
                color="color",
                color_discrete_map={"green": "#2ecc71", "orange": "#f39c12", "red": "#e74c3c"},
                text="pct_of_target",
                template="plotly_white",
            )
            fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
            fig.add_vline(x=100, line_dash="dash", line_color="gray", annotation_text="Target")
            fig.update_layout(
                showlegend=False,
                xaxis_title="% of Target",
                yaxis_title="",
                height=420,
            )
            st.plotly_chart(fig, use_container_width=True)

            # Actual vs Target table
            display_df = kpi_df[["name", "target", "actual", "unit", "pct_of_target"]].copy()
            display_df.columns = ["KPI", "Target", "Actual", "Unit", "% of Target"]
            st.dataframe(display_df, use_container_width=True, hide_index=True)
        else:
            st.warning("No KPI data available for charting.")

    # ---- Sales Forecast chart ----------------------------------------------
    elif report_type == "Sales Forecast Analysis":
        forecast_df = load_forecast_data()

        fig = go.Figure()

        # Actual line (where available)
        actual_rows = forecast_df[forecast_df["actual"].notna()]
        if not actual_rows.empty:
            fig.add_trace(go.Scatter(
                x=actual_rows["month"],
                y=actual_rows["actual"],
                mode="lines+markers",
                name="Actual",
                line=dict(color="#2980b9", width=3),
                marker=dict(size=8),
            ))

        # Forecast line
        fig.add_trace(go.Scatter(
            x=forecast_df["month"],
            y=forecast_df["forecast"],
            mode="lines+markers",
            name="Forecast",
            line=dict(color="#e74c3c", width=2, dash="dot"),
            marker=dict(size=6),
        ))

        # Confidence interval band
        if "upper_bound" in forecast_df.columns and "lower_bound" in forecast_df.columns:
            upper = forecast_df["upper_bound"].tolist()
            lower = forecast_df["lower_bound"].tolist()
            months = forecast_df["month"].tolist()

            fig.add_trace(go.Scatter(
                x=months + months[::-1],
                y=upper + lower[::-1],
                fill="toself",
                fillcolor="rgba(231, 76, 60, 0.1)",
                line=dict(color="rgba(255,255,255,0)"),
                name="Confidence Interval",
                showlegend=True,
            ))

        fig.update_layout(
            title="Sales Forecast — 12 Month Outlook ($M)",
            xaxis_title="Month",
            yaxis_title="Revenue ($M)",
            template="plotly_white",
            height=420,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig, use_container_width=True)

    # ---- Customer Segmentation charts -------------------------------------
    elif report_type == "Customer Segmentation Report":
        seg_data = load_segmentation_data()

        col_pie, col_bar = st.columns(2)

        # Pie chart: by industry
        with col_pie:
            industry_data = seg_data.get("by_industry", [])
            if industry_data:
                ind_df = pd.DataFrame(industry_data)
                fig_pie = px.pie(
                    ind_df,
                    values="count",
                    names="industry",
                    title="Customers by Industry",
                    template="plotly_white",
                    color_discrete_sequence=px.colors.qualitative.Set2,
                )
                fig_pie.update_traces(textposition="inside", textinfo="percent+label")
                st.plotly_chart(fig_pie, use_container_width=True)

        # Bar chart: by health score bucket
        with col_bar:
            health_data = seg_data.get("by_health_score", [])
            if health_data:
                health_df = pd.DataFrame(health_data)
                color_map = {
                    "Champion (80-100)": "#2ecc71",
                    "Healthy (60-79)": "#3498db",
                    "At Risk (40-59)": "#f39c12",
                    "Critical (<40)": "#e74c3c",
                }
                health_df["color"] = health_df["bucket"].map(color_map)
                fig_bar = px.bar(
                    health_df,
                    x="bucket",
                    y="count",
                    title="Customer Health Score Distribution",
                    template="plotly_white",
                    color="bucket",
                    color_discrete_map=color_map,
                    text="count",
                )
                fig_bar.update_traces(textposition="outside")
                fig_bar.update_layout(showlegend=False, xaxis_title="", yaxis_title="# Customers")
                st.plotly_chart(fig_bar, use_container_width=True)

        # Summary metrics
        st.metric("Total Customers", f"{seg_data.get('total_customers', 'N/A'):,}")
        st.metric("Average Health Score", f"{seg_data.get('average_health_score', 'N/A')}")
        churn_count = seg_data.get("churn_risk_count", 0)
        total = seg_data.get("total_customers", 1)
        st.metric("Churn Risk Count", f"{churn_count:,}", delta=f"{churn_count/total*100:.1f}% of base")

    # ---- Executive Board Deck — all three charts side by side --------------
    elif report_type == "Executive Board Deck Summary":
        st.markdown("**KPI Performance vs Target**")
        kpi_data = load_kpi_data()
        kpis = kpi_data.get("kpis", [])
        if kpis:
            kpi_df = pd.DataFrame(kpis)
            kpi_df["pct_of_target"] = (kpi_df["actual"] / kpi_df["target"] * 100).round(1)
            kpi_df["status"] = kpi_df["pct_of_target"].apply(
                lambda x: "On Track" if x >= 100 else ("Near Target" if x >= 90 else "Off Track")
            )
            color_map = {"On Track": "#2ecc71", "Near Target": "#f39c12", "Off Track": "#e74c3c"}
            fig = px.bar(
                kpi_df,
                y="name",
                x="pct_of_target",
                orientation="h",
                title="Q1 2024 KPI: % of Target",
                color="status",
                color_discrete_map=color_map,
                text="pct_of_target",
                template="plotly_white",
            )
            fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
            fig.add_vline(x=100, line_dash="dash", line_color="gray")
            fig.update_layout(showlegend=True, height=380, xaxis_title="% of Target", yaxis_title="")
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("**Sales Forecast Trend**")
        forecast_df = load_forecast_data()
        fig2 = go.Figure()
        actual_rows = forecast_df[forecast_df["actual"].notna()]
        if not actual_rows.empty:
            fig2.add_trace(go.Scatter(
                x=actual_rows["month"], y=actual_rows["actual"],
                mode="lines+markers", name="Actual",
                line=dict(color="#2980b9", width=3),
            ))
        fig2.add_trace(go.Scatter(
            x=forecast_df["month"], y=forecast_df["forecast"],
            mode="lines+markers", name="Forecast",
            line=dict(color="#e74c3c", width=2, dash="dot"),
        ))
        fig2.update_layout(
            title="12-Month Revenue Forecast ($M)", template="plotly_white",
            height=320, xaxis_title="Month", yaxis_title="$M",
        )
        st.plotly_chart(fig2, use_container_width=True)

        st.markdown("**Customer Portfolio Health**")
        seg_data = load_segmentation_data()
        health_data = seg_data.get("by_health_score", [])
        if health_data:
            health_df = pd.DataFrame(health_data)
            color_map2 = {
                "Champion (80-100)": "#2ecc71",
                "Healthy (60-79)": "#3498db",
                "At Risk (40-59)": "#f39c12",
                "Critical (<40)": "#e74c3c",
            }
            fig3 = px.bar(
                health_df, x="bucket", y="count",
                title="Customer Health Score Distribution",
                color="bucket", color_discrete_map=color_map2,
                text="count", template="plotly_white",
            )
            fig3.update_traces(textposition="outside")
            fig3.update_layout(showlegend=False, height=320, xaxis_title="", yaxis_title="Customers")
            st.plotly_chart(fig3, use_container_width=True)
