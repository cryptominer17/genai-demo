# FI GenAI PoC Platform

A multi-app Streamlit platform demonstrating Generative AI capabilities for the Fidelity Institutional AI Platform team. Three purpose-built PoC apps are deployed behind a single Nginx reverse proxy on a Digital Ocean droplet.

---

## Project Overview

This repository packages three Streamlit proof-of-concept applications that showcase enterprise AI use cases relevant to Fidelity Institutional:

| App | Route | Port | Purpose |
|-----|-------|------|---------|
| Document Intelligence | `/Document_AI` | 8501 | Upload and interrogate financial documents using Claude |
| Data Q&A (Text-to-SQL) | `/Text_to_SQL` | 8502 | Natural-language queries against structured mock data |
| Report Generator | `/BI_Dashboard` | 8503 | AI-assisted narrative generation from BI metrics |

All apps share a common authentication layer, LLM client, and utility library under `shared/`.

---

## Architecture

```
                        ┌─────────────────────────────────────────┐
  Browser               │  Digital Ocean Droplet (Ubuntu 22.04)   │
    │                   │                                         │
    │  HTTP :80         │  ┌─────────────────────────────────┐   │
    ├──────────────────►│  │  Nginx (reverse proxy)          │   │
    │  /Document_AI     │  │  ├─ /Document_AI  → :8501       │   │
    │  /Text_to_SQL     │  │  ├─ /Text_to_SQL  → :8502       │   │
    │  /BI_Dashboard    │  │  └─ /BI_Dashboard → :8503       │   │
    │                   │  └────────────┬────────────────────┘   │
    │                   │               │  (WebSocket + HTTP)     │
    │                   │  ┌────────────▼────────────────────┐   │
    │                   │  │  Streamlit Apps (systemd)       │   │
    │                   │  │  ├─ doc-intelligence  :8501     │   │
    │                   │  │  ├─ data-qa           :8502     │   │
    │                   │  │  └─ report-generator  :8503     │   │
    │                   │  └────────────┬────────────────────┘   │
    │                   └───────────────┼─────────────────────────┘
    │                                   │  HTTPS API calls
    │                                   ▼
    │                         ┌──────────────────┐
    │                         │  Anthropic API   │
    │                         │  (Claude models) │
    │                         └──────────────────┘
    │
    └── Auth: streamlit-authenticator (bcrypt, session cookies)
```

---

## Apps

**Document Intelligence** (`/Document_AI`)
Upload PDF or text documents and ask natural-language questions. Uses Claude to extract, summarize, and reason over document content. Demonstrates retrieval-augmented generation patterns for financial document workflows.

**Data Q&A — Text-to-SQL** (`/Text_to_SQL`)
Ask plain-English questions about structured mock datasets. Claude generates SQL, executes it against an in-memory database, and returns results with explanations. Demonstrates Snowflake Cortex-style Text-to-SQL patterns.

**Report Generator** (`/BI_Dashboard`)
Input key metrics and Claude drafts executive-ready narrative summaries and commentary. Demonstrates AI-assisted report generation for BI/analytics workflows.

---

## Quick Start (Local)

1. **Clone the repository**
   ```bash
   git clone https://github.com/cryptominer17/genai-demo.git
   cd genai-demo
   ```

2. **Create and activate a virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate   # Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r shared/requirements.txt
   ```

4. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env and add your ANTHROPIC_API_KEY and other values
   ```

5. **Run an app**
   ```bash
   streamlit run apps/document_intelligence/streamlit_app.py --server.port 8501
   # Open http://localhost:8501
   ```

For running all three apps simultaneously, see [docs/LOCAL_SETUP.md](docs/LOCAL_SETUP.md).

---

## Production Deployment

Full step-by-step deployment guide (fresh droplet): [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)

---

## GitHub Secrets

Required secrets for the CI/CD pipeline: [docs/GITHUB_SECRETS_SETUP.md](docs/GITHUB_SECRETS_SETUP.md)

---

## Admin Panel & User Management

### Default Credentials

| Field    | Value                    |
|----------|--------------------------|
| Username | `admin`                  |
| Password | `Admin@123`              |
| Role     | `admin`                  |

> **Change this password immediately in any production or shared deployment.**

### Accessing the Admin Panel

Navigate to the `/Admin` route on your deployment (e.g. `http://<host>/Admin`).  
Only users with the `admin` role can reach this panel; all other roles receive an access-denied page.

### Role Permissions

| App                    | admin | analyst | viewer |
|------------------------|:-----:|:-------:|:------:|
| document_intelligence  | ✓     | —       | ✓      |
| data_qa                | ✓     | ✓       | —      |
| report_generator       | ✓     | ✓       | —      |
| admin                  | ✓     | —       | —      |

### Fresh-Install Setup

Run the setup script once after cloning to initialise the SQLite database and create the default admin:

```bash
# From the project root
python scripts/setup_admin.py
```

To create a custom first admin instead of the default:

```bash
python scripts/setup_admin.py --username alice --email alice@example.com --password MyPass@1
```

The script prints a user table and the full access matrix on exit.

### Adding the Admin App to systemd

A service file is included at `deployment/systemd/streamlit-admin.service` (port 8504, base path `/Admin`).

```bash
sudo cp deployment/systemd/streamlit-admin.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now streamlit-admin
sudo systemctl status streamlit-admin
```

Then add the proxy rule to `deployment/nginx.conf` (already present) and reload Nginx:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

---

## Troubleshooting

Common issues and fixes: [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)

---

## Project Structure

```
genai-demo/
├── apps/
│   ├── document_intelligence/
│   │   └── streamlit_app.py
│   ├── data_qa/
│   │   └── streamlit_app.py
│   └── report_generator/
│       └── streamlit_app.py
├── shared/
│   ├── auth.py
│   ├── llm_client.py
│   ├── utils.py
│   └── requirements.txt
├── deployment/
│   ├── nginx.conf
│   ├── systemd/
│   │   ├── streamlit-doc-intelligence.service
│   │   ├── streamlit-data-qa.service
│   │   └── streamlit-report-generator.service
│   └── scripts/
│       ├── health_check.sh
│       └── verify_droplet.sh
├── docs/
│   ├── DEPLOYMENT.md
│   ├── ARCHITECTURE.md
│   ├── LOCAL_SETUP.md
│   ├── TROUBLESHOOTING.md
│   ├── LOGS_AND_MONITORING.md
│   └── GITHUB_SECRETS_SETUP.md
├── .env.example
├── .github/
│   └── workflows/
│       └── deploy.yml
└── README.md
```

---

## Adding a New App

See [docs/APP_DEVELOPER_VS_INFRA.md](docs/APP_DEVELOPER_VS_INFRA.md) for the
full responsibility matrix and handoff checklist.

Use `apps/template_app/` as the starting point for any new Streamlit app.

