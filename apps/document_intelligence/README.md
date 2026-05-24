# Document Intelligence

AI-powered document analysis using Claude claude-3-5-sonnet-20241022. Upload or select from mock documents and run four analysis modes: Summary, Key Information Extraction, Q&A, and Risk Flag detection.

## Local run

```bash
cd apps/document_intelligence
python -m streamlit run streamlit_app.py --server.port 8501
```

## Available mock documents

The following sample documents are pre-loaded from `shared/mock_data/documents/`:

- `contract_sample_nda.txt` — Non-disclosure agreement sample
- `policy_document_it_security.txt` — IT security policy
- `financial_report_q1.txt` — Q1 financial report excerpt
- `vendor_agreement_saas.txt` — SaaS vendor agreement

You can also upload your own `.txt` or `.pdf` file via the sidebar.

## Analysis modes

| Mode | What it does |
|---|---|
| Summary | 3-5 bullet executive summary |
| Key Information Extraction | Dates, amounts, parties, obligations |
| Q&A | Ask any question; Claude quotes relevant sections |
| Risk Flags | Severity-tagged risks, obligations, and unusual clauses |
