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

## Custom Data Upload

You can upload your own CSV or JSON file and have Claude analyze it instead of the built-in datasets.

### How to use

1. In the sidebar, find the **Upload custom data (optional)** section below the report type selector.
2. Click **Browse files** and select a `.csv` or `.json` file (maximum 5 MB).
3. After a successful upload, a preview is shown in the sidebar (first 10 rows for CSV; first 5 keys for JSON).
4. **Custom Uploaded Data** appears as a new option in the **Report type** dropdown — select it.
5. Choose your audience and depth, then click **Generate Report**.

### What happens after upload

- **CSV**: The file is parsed into a DataFrame. Row count is displayed in a success message. The first 10 rows are previewed in the sidebar and the full dataset is visible in the **Data** tab.
- **JSON**: The file is parsed as a JSON object or array. Key/item count is shown in a success message. The first 5 keys are previewed in the sidebar and the full document is visible in the **Data** tab.
- The LLM uses a business intelligence system prompt instructing it to identify the top 3-5 business insights from your data, tailored to the selected audience and depth.

### Clearing the upload

Click the **Clear uploaded data** button (visible in the sidebar whenever a file has been loaded). This removes the data from the session and hides the **Custom Uploaded Data** option from the dropdown.

### Session-scoped only

Uploaded data is held in Streamlit session state and is **never written to disk**. It is automatically discarded when the browser tab is closed or the session expires.
