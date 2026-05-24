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
