# Report Generator

AI-generated business intelligence reports for Fidelity Institutional. Select a report type, audience, and depth; Claude produces formatted markdown analysis backed by real BI data. Charts and raw data are available in companion tabs.

## Local run

```bash
cd apps/report_generator
python -m streamlit run streamlit_app.py --server.port 8503
```

## Report types

| Report | Data source |
|---|---|
| Q1 2024 KPI Summary | `quarterly_kpis_2024.json` |
| Sales Forecast Analysis | `sales_forecast_12mo.csv` |
| Customer Segmentation Report | `customer_segmentation.json` |
| Executive Board Deck Summary | All three sources combined |

## Audience options

- Executive/Board — high-level narrative, strategic framing
- Sales Leadership — pipeline and quota focus
- Operations Team — process and efficiency detail

## Report depth

- One-pager — 300-400 words, top-line insights only
- Full Report — structured sections with analysis and recommendations
- Bullet Points Only — scannable, decision-ready format
