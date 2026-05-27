# Mock Datasets — Data Dictionary

This directory contains three CSV files used as shared mock data across the PoC Platform Streamlit applications. All data is synthetic and generated for demonstration purposes only.

---

## 1. sales_transactions_2023_2024.csv

**Purpose:** Transaction-level sales data spanning Q1 2023 through Q1 2024. Used for revenue analysis, sales rep performance dashboards, product mix reporting, and Text-to-SQL demos.

**Row count:** 520 rows

### Schema

| Column | Type | Description |
|---|---|---|
| transaction_id | string | Unique transaction identifier (TXN001–TXN520) |
| date | date (YYYY-MM-DD) | Transaction date |
| product_id | string | Product SKU identifier (SKU-1001 to SKU-1005) |
| product_name | string | Human-readable product name |
| quantity | integer | Units sold (1–10 for licenses/modules; 2–20 for services) |
| unit_price | integer | Per-unit list price in USD |
| total_amount | integer | Computed as quantity × unit_price |
| customer_id | string | Customer identifier (CUST-101 to CUST-115) |
| customer_name | string | Customer company name |
| industry | string | Customer industry vertical |
| region | string | US sales region (Northeast, West, Southeast, Midwest, Southwest) |
| sales_rep | string | Assigned sales representative name |
| payment_method | string | ACH (50%), CC (30%), Wire (20%) |
| status | string | Completed (85%), Pending (10%), Cancelled (5%) |
| fiscal_quarter | string | Fiscal quarter label (e.g., Q2 2023) |

### Products Reference

| product_id | product_name | unit_price |
|---|---|---|
| SKU-1001 | Cloud License Annual | $2,000 |
| SKU-1002 | Support Package Premium | $1,500 |
| SKU-1003 | Data Analytics Module | $5,000 |
| SKU-1004 | Implementation Services | $500 |
| SKU-1005 | Training Enablement | $800 |

### Example Natural Language Queries

1. "What was the total revenue by product in Q3 2023?"
2. "Which sales rep had the highest total sales in 2023?"
3. "Show me the monthly revenue trend from January 2023 to March 2024."
4. "How many transactions were Cancelled vs Completed by region?"
5. "What is the average deal size for Data Analytics Module by industry?"

---

## 2. product_inventory_realtime.csv

**Purpose:** Current inventory snapshot as of 2024-03-20. Covers the 5 core products plus 20 sub-products and bundles. Used for inventory management dashboards, reorder alerts, and margin analysis.

**Row count:** 25 rows

### Schema

| Column | Type | Description |
|---|---|---|
| product_id | string | Internal product record ID (PRD-001 to PRD-025) |
| product_name | string | Full product name |
| sku | string | Sales SKU code |
| category | string | Top-level category (Software, Services, Bundle) |
| subcategory | string | Product subcategory |
| quantity_on_hand | integer | Current stock count |
| reorder_point | integer | Threshold below which reorder is triggered |
| unit_cost | integer | Cost of goods sold per unit (USD) |
| list_price | integer | Published sale price per unit (USD) |
| margin_pct | float | Gross margin percentage ((price - cost) / price × 100) |
| warehouse_location | string | Primary storage location (WH-Dallas, WH-Chicago, WH-SFO, WH-NYC) |
| last_updated | datetime (YYYY-MM-DD HH:MM:SS) | Timestamp of last inventory update |
| status | string | Active or Reorder Required |

### Reorder Required Items (4 items)

- PRD-009: Support Package Basic — qty 18, reorder point 25
- PRD-011: Data Analytics Module - Pro — qty 9, reorder point 15
- PRD-022: Custom Reporting Module — qty 13, reorder point 15
- PRD-024: Dedicated Account Manager — qty 8, reorder point 10

### Example Natural Language Queries

1. "Which products are currently below their reorder point?"
2. "What is the average gross margin by product category?"
3. "Show all products stored at WH-Dallas with quantity on hand above 50."
4. "What is the total inventory value (quantity × unit_cost) by warehouse location?"
5. "Which bundles have the highest list price and what is their current stock?"

---

## 3. customer_demographics.csv

**Purpose:** Master customer reference table for the 15 active accounts (CUST-101 to CUST-115). Includes firmographic, contract, and health data. Used for customer success dashboards, renewal forecasting, and segmentation analysis.

**Row count:** 15 rows

### Schema

| Column | Type | Description |
|---|---|---|
| customer_id | string | Unique customer identifier (CUST-101 to CUST-115) |
| customer_name | string | Company name |
| industry | string | Industry vertical (Technology, Financial Services, Healthcare, Consulting, SaaS) |
| company_size | string | Enterprise, Mid-Market, or SMB |
| hq_state | string | US state of headquarters (2-letter code) |
| annual_revenue_usd | integer | Customer's reported annual revenue in USD |
| region | string | Assigned sales region |
| account_manager | string | Fidelity account manager name |
| contract_start_date | date (YYYY-MM-DD) | Current contract start date |
| contract_end_date | date (YYYY-MM-DD) | Current contract end / renewal date |
| arr_value | integer | Annual Recurring Revenue from this account (USD) |
| health_score | integer | Customer health score 0–100 (composite of usage, support tickets, NPS) |
| renewal_probability | float | Predicted renewal probability (0.0–1.0) |
| segment | string | Account segment: Strategic, Enterprise, Growth, SMB |
| support_tier | string | Support tier: Platinum, Gold, Silver, Standard |

### Segment Definitions

| Segment | Criteria |
|---|---|
| Strategic | Enterprise accounts with ARR > $400K or health score > 92 |
| Enterprise | Mid-market or large accounts with ARR $150K–$400K |
| Growth | SMB accounts showing expansion signals; ARR $50K–$150K |
| SMB | Small accounts with ARR < $100K |

### Example Natural Language Queries

1. "Which customers have a renewal date within the next 6 months and a health score below 85?"
2. "What is the total ARR by industry segment?"
3. "List all Strategic-tier customers and their account managers."
4. "Which region has the highest average health score?"
5. "Show customers with renewal probability below 0.85 sorted by ARR descending."

---

## 4. rd_wholesaler_activity.csv

**Purpose:** Relationship Director (RD) activity log covering January 2025 through May 2026. Tracks 120 wholesaler touchpoints with RIA firms across six US regions, capturing activity type, outcome, AUM discussed, and products pitched. Used for RD performance analysis, pipeline management, and sales conversion reporting.

**Row count:** 120 rows

### Schema

| Column | Type | Description |
|---|---|---|
| activity_id | string | Unique activity identifier (ACT-0001 to ACT-0120) |
| rd_name | string | Relationship Director name (6 RDs: Michael Tanaka, Priya Nambiar, Dana Whitfield, James Odem, Carlos Rivera, Lisa Huang) |
| region | string | RD's primary coverage region (Southwest, Northeast, West, Southeast, Northwest, Midwest) |
| activity_date | date (YYYY-MM-DD) | Date the activity occurred (Jan 2025–May 2026) |
| activity_type | string | Type of activity: Phone Call, In-Person Visit, Email Campaign, Webinar, Conference |
| ria_firm_contacted | string | Name of the RIA firm contacted (18 distinct firms) |
| ria_tier | string | RIA firm tier: Platinum (>$400M AUM on platform), Gold ($100M–$400M), Silver ($25M–$100M), Bronze (<$25M) |
| outcome | string | Activity outcome: Meeting Scheduled, Follow-Up Required, Proposal Sent, Closed/Won, No Action |
| aum_discussed_m | float | AUM discussed in millions USD (0.0 for No Action / Email Campaign with no follow-up) |
| products_pitched | string | Pipe-delimited list of products discussed: ETF, Mutual Fund, Model Portfolio, SMAs |
| follow_up_date | date (YYYY-MM-DD) | Scheduled follow-up date (~60% of rows populated; blank for ~40%) |
| notes | string | Synthetic one-sentence summary of the activity |

### Key Statistics

| Metric | Value |
|---|---|
| Total activities | 120 |
| Date range | 2025-01-08 to 2026-05-21 |
| Rows per RD | 20 each (6 RDs) |
| Closed/Won outcomes | 18 (15% conversion rate) |
| Distinct RIA firms | 18 |

### Example Natural Language Queries

1. "Which RD had the most 'Closed/Won' outcomes in Q1 2026?"
2. "Show total AUM discussed by region and activity type."
3. "Which RIA firms have been contacted most frequently in 2026 YTD?"
4. "What is the conversion rate (Closed/Won) by RD?"
5. "List all activities where AUM discussed exceeded $200M."

---

## 5. ria_distribution_metrics.csv

**Purpose:** Point-in-time snapshot of RIA firm distribution metrics as of May 2026. Covers 25 RIA relationships (13 from the core BI dashboard plus 12 newer relationships), including platform AUM, net flows, product mix, engagement scores, and platform capture rates. Used for relationship health monitoring, territory planning, and distribution performance reporting.

**Row count:** 25 rows

### Schema

| Column | Type | Description |
|---|---|---|
| ria_firm_id | string | Unique RIA firm identifier (RIA-001 to RIA-025) |
| ria_firm_name | string | Full RIA firm name |
| region | string | Geographic region (Southwest, Northeast, West, Southeast, Northwest, Midwest) |
| rd_owner | string | Assigned Relationship Director name |
| ria_tier | string | Tier based on AUM on platform: Platinum (>$400M), Gold ($100M–$400M), Silver ($25M–$100M), Bronze (<$25M) |
| aum_on_platform_m | float | AUM currently on the platform in millions USD |
| total_aum_m | float | Firm's total AUM under management in millions USD |
| platform_capture_pct | float | Platform AUM as a percentage of total AUM (aum_on_platform_m / total_aum_m × 100, rounded to 1 decimal) |
| net_flows_qtd_m | float | Net flows into platform (current quarter to date) in millions USD |
| net_flows_ytd_m | float | Net flows into platform (year to date 2026) in millions USD |
| product_mix_pct_etf | integer | Percentage of platform AUM in ETFs (all product mix columns sum to 100) |
| product_mix_pct_mutual_fund | integer | Percentage of platform AUM in Mutual Funds |
| product_mix_pct_model_portfolio | integer | Percentage of platform AUM in Model Portfolios |
| product_mix_pct_sma | integer | Percentage of platform AUM in SMAs |
| engagement_score | integer | Engagement score 1–10 (At-Risk: 1–5, Active: 5–8, Growth: 8–10, New: 4–7) |
| last_rd_touchpoint | date (YYYY-MM-DD) | Date of most recent RD activity with this firm (2026-01-15 to 2026-05-20) |
| touchpoint_count_ytd | integer | Number of RD touchpoints in 2026 YTD (range 1–15) |
| status | string | Relationship status: Active, Growth, At-Risk, New |
| primary_product_interest | string | Primary product area of interest: ETF, Mutual Fund, Model Portfolio, SMAs |
| onboarding_date | date (YYYY-MM-DD) | Date the firm was onboarded to the platform (2020-01-01 to 2025-12-31) |

### Data Quality Notes

- Product mix columns (`product_mix_pct_etf`, `product_mix_pct_mutual_fund`, `product_mix_pct_model_portfolio`, `product_mix_pct_sma`) sum to exactly 100 for every row.
- `platform_capture_pct` is computed as `round(aum_on_platform_m / total_aum_m * 100, 1)` and falls between 35% and 51% across all firms.
- `net_flows_ytd_m` is negative or near zero for all At-Risk firms and positive for all Growth firms.
- Rows RIA-001 through RIA-013 correspond to the 13 core firms in `demo_bi_dashboard_data.json`; AUM, flows, engagement scores, product mix, and status values match the JSON exactly.
- Rows RIA-014 through RIA-025 are additional firms introduced in this dataset.

### Example Natural Language Queries

1. "Which RIA firms are classified as At-Risk with negative net flows YTD?"
2. "What is the average platform capture percentage by RD owner?"
3. "Show AUM on platform by region sorted descending."
4. "Which Platinum-tier firms have an engagement score below 7?"
5. "Compare net flows QTD vs YTD for all Growth-status firms."
