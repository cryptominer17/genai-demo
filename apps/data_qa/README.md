# Data Q&A

Natural-language querying over structured CSV datasets. Translates plain-English questions into pandas code, executes it, and renders results as a table and optional chart.

## Local run

```bash
cd apps/data_qa
python -m streamlit run streamlit_app.py --server.port 8502
```

## Available datasets

Loaded from `shared/mock_data/datasets/`:

| Dataset | File |
|---|---|
| Sales Transactions | `sales_transactions_2023_2024.csv` |
| Product Inventory | `product_inventory.csv` |
| Customer Demographics | `customer_demographics.csv` |

## Example queries

**Sales Transactions**
- "What were total sales by region last quarter?"
- "Which product had the highest revenue in Q4 2023?"
- "Show me month-over-month revenue growth"

**Product Inventory**
- "Which products are below reorder threshold?"
- "What is the total inventory value by category?"

**Customer Demographics**
- "How many customers are in each industry segment?"
- "What is the average deal size by customer tier?"
