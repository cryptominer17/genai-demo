# BI Data Files — Data Dictionary

This directory contains structured BI/analytics data used by the PoC Platform Streamlit applications for dashboards, forecasting, and LLM-powered insight generation. All data is synthetic.

---

## 1. quarterly_kpis_2024.json

**Purpose:** Executive KPI summary for Q1 2024. Serves as the primary data source for the BI Dashboard app's executive summary panel and LLM narrative generation.

### Top-Level Structure

| Field | Type | Description |
|---|---|---|
| report_period | string | Quarter label (e.g., "Q1 2024") |
| report_date | string | As-of date for the report (YYYY-MM-DD) |
| company | string | Company name |
| kpis | object | Nested KPI objects (see below) |
| highlights | array | 3 bulleted positive performance highlights |
| risks | array | 3 bulleted risk / concern items |
| prior_quarter_comparison | object | QoQ delta for key metrics |

### KPI Objects

| KPI Key | Key Metrics | Notes |
|---|---|---|
| revenue | total, ytd, target, variance, variance_pct, yoy_growth, trend | In USD |
| new_customers | count, arr_value, target, variance, avg_deal_size, trend | — |
| customer_retention | rate, target, churn_customers, churn_arr, nrr, trend | NRR = Net Revenue Retention |
| arr | total, new, expansion, churn, net_new_arr, net_arr_growth_rate, trend | Annual Recurring Revenue |
| gross_margin | rate, target, variance, cogs, gross_profit, trend | Rate = 0.0–1.0 |
| sales_efficiency | ratio, target, cac, ltv, ltv_cac_ratio, payback_months, trend | Magic Number / efficiency ratio |
| product_adoption | dau, mau, dau_mau_ratio, feature_adoption_rate, trend | DAU/MAU measures stickiness |

### Key Metric Definitions

- **ARR (Annual Recurring Revenue):** Total annualized subscription/contract revenue under management.
- **NRR (Net Revenue Retention):** (Beginning ARR + Expansion - Churn) / Beginning ARR × 100. Values >100% indicate net growth from existing base.
- **CAC (Customer Acquisition Cost):** Total sales & marketing spend divided by new customers acquired.
- **LTV (Lifetime Value):** Average ARR × average contract length × gross margin.
- **Magic Number / Sales Efficiency Ratio:** Net new ARR / prior quarter S&M spend. Values >1.0 indicate efficient growth.

### Example LLM Prompts

1. "Summarize Q1 2024 performance in 3 bullet points for a C-suite audience."
2. "What are the top 2 risks based on the KPI data and what should the team prioritize?"
3. "How does Q1 2024 ARR compare to Q4 2023 and what is driving the change?"
4. "Write a 2-paragraph board narrative covering revenue, retention, and sales efficiency."

---

## 2. sales_forecast_12mo.csv

**Purpose:** Monthly revenue forecast for full-year 2024 (January–December). Jan–Mar are actuals; Apr–Dec are model forecasts. Used for trend line charts and variance analysis.

**Row count:** 12 rows

### Schema

| Column | Type | Description |
|---|---|---|
| month | string (YYYY-MM) | Month identifier |
| forecast_revenue | integer | Forecasted (or actual) revenue for the month in USD |
| confidence_interval_low | integer | Lower bound of 90% confidence interval (±7% of forecast) |
| confidence_interval_high | integer | Upper bound of 90% confidence interval (±7% of forecast) |
| historical_actual | integer | Actual revenue if month is a historical period; blank for forecast months |
| forecast_type | string | "Actual" (Jan–Mar 2024) or "Forecast" (Apr–Dec 2024) |
| growth_rate_mom | float | Month-over-month growth rate as decimal (0.0 for actuals) |
| cumulative_forecast | integer | Running cumulative total of forecast_revenue from Jan to that month |

### Notes

- Confidence intervals are only meaningful for Forecast months; Actual months show the same value in all three revenue columns.
- The model shows acceleration from Q2 onward (~3% MoM) reflecting seasonality and pipeline growth.
- Full-year 2024 cumulative forecast at December: $73,325,000.

### Example LLM Prompts

1. "What is the expected full-year 2024 revenue based on the forecast?"
2. "At what month does the business cross $50M in cumulative revenue for 2024?"
3. "What is the average monthly growth rate for the forecast period (April–December)?"
4. "If actual April revenue comes in at $5.4M instead of the forecast $5.68M, what is the variance and revised full-year outlook?"

---

## 3. customer_segmentation.json

**Purpose:** Aggregated customer segmentation data as of 2024-03-31. Covers 100 total customers across five segmentation dimensions. Used for customer success dashboards, CS team prioritization, and strategic planning.

### Top-Level Structure

| Field | Type | Description |
|---|---|---|
| report_date | string | As-of date (YYYY-MM-DD) |
| total_customers | integer | Total active customer count |
| total_arr | integer | Total ARR across all customers in USD |
| segmentation | object | Four segmentation views (see below) |
| top_10_customers | array | Ranked list of top 10 customers by ARR |

### Segmentation Dimensions

**by_industry** — 5 verticals: Technology, Financial Services, Healthcare, Consulting, SaaS
- Fields per segment: customer_count, arr_value, avg_contract_value, health_score_avg, churn_rate, growth_rate

**by_company_size** — 3 tiers: Enterprise, Mid-Market, SMB
- Fields: customer_count, arr_value, health_score_avg, expansion_potential, upsell_opportunities

**by_region** — 5 regions: Northeast, West, Southeast, Midwest, Southwest
- Fields: customer_count, arr_value, top_products (list)

**by_health_score** — 4 bands: 95+ (Champion), 85–94 (Healthy), 70–84 (Needs Attention), <70 (At Risk)
- Fields: count, arr_value, recommended_action

### top_10_customers Fields

| Field | Description |
|---|---|
| rank | ARR rank (1 = largest) |
| name | Customer name |
| industry | Industry vertical |
| arr | ARR value in USD |
| health_score | Current health score (0–100) |
| renewal_date | Next contract renewal date (YYYY-MM-DD) |

### Example LLM Prompts

1. "Which industry has the highest churn risk and what is the recommended action for at-risk customers?"
2. "What percentage of total ARR is concentrated in the top 10 customers?"
3. "Summarize the upsell opportunity by company size tier."
4. "Which region has the highest ARR per customer and which products are driving it?"
