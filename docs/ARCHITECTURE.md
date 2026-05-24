# System Architecture

Technical design document for the FI GenAI PoC Platform.

---

## Overview

The platform is a single-droplet deployment of three Streamlit applications, each demonstrating a distinct enterprise AI use case for the Fidelity Institutional AI Platform. It is intentionally simple — a PoC, not a production system — but is structured to mirror real-world patterns (reverse proxy, service management, shared auth) so it can be reasoned about and extended.

**Technology choices:**
- **Streamlit** — rapid Python UI for ML/AI demos; requires no frontend engineering
- **Nginx** — battle-tested reverse proxy; handles WebSocket upgrade, path routing, and SSL termination
- **systemd** — native Ubuntu service management; auto-restart on crash, logging to files and journal
- **Anthropic Claude** — LLM backend via API; no model hosting overhead
- **Digital Ocean** — simple droplet provisioning; straightforward networking

---

## Component Diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│  GitHub Repository (cryptominer17/genai-demo)                            │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │  apps/                    shared/              deployment/         │  │
│  │  ├─ document_intelligence ├─ auth.py           ├─ nginx.conf       │  │
│  │  ├─ data_qa               ├─ llm_client.py     ├─ systemd/*.service│  │
│  │  └─ report_generator      ├─ utils.py          └─ scripts/         │  │
│  │                           └─ requirements.txt                      │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                │                                                         │
│  .github/workflows/deploy.yml  (GitHub Actions CI/CD)                   │
└────────────────┼─────────────────────────────────────────────────────────┘
                 │  git pull + systemctl restart (SSH)
                 ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  Digital Ocean Droplet — Ubuntu 22.04 LTS — Virginia (NYC3)             │
│                                                                          │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  UFW Firewall: ports 22 (SSH), 80 (HTTP) open                     │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  Nginx :80                                                        │  │
│  │  ├─ /Document_AI/  ─── proxy_pass ──► localhost:8501             │  │
│  │  ├─ /Text_to_SQL/  ─── proxy_pass ──► localhost:8502             │  │
│  │  ├─ /BI_Dashboard/ ─── proxy_pass ──► localhost:8503             │  │
│  │  └─ /health        ─── return 200 "OK"                           │  │
│  │     (WebSocket upgrade headers on all proxy locations)            │  │
│  └────────────────────────┬──────────────────────────────────────────┘  │
│                            │  HTTP + WebSocket (localhost only)          │
│  ┌─────────────────────────▼──────────────────────────────────────────┐  │
│  │  systemd services (user: streamlit)                               │  │
│  │                                                                   │  │
│  │  streamlit-doc-intelligence.service  → port 8501                 │  │
│  │  streamlit-data-qa.service           → port 8502                 │  │
│  │  streamlit-report-generator.service  → port 8503                 │  │
│  │                                                                   │  │
│  │  All read: /opt/fi-genai-poc-platform/.env                       │  │
│  │  All log to: /var/log/streamlit/                                  │  │
│  └─────────────────────────┬──────────────────────────────────────────┘  │
│                             │  HTTPS API (outbound)                      │
└─────────────────────────────┼────────────────────────────────────────────┘
                              ▼
                    ┌──────────────────────┐
                    │  Anthropic API       │
                    │  api.anthropic.com   │
                    │  (Claude models)     │
                    └──────────────────────┘
```

---

## Request Flow

End-to-end path for a user submitting a document question in the Document Intelligence app:

1. **Browser** sends `GET http://<DROPLET_IP>/Document_AI/` (HTTP, port 80)
2. **Nginx** receives the request, matches the `/Document_AI/` location block
3. Nginx **upgrades the connection to WebSocket** (Streamlit requirement) and proxies to `localhost:8501`
4. **Streamlit** (port 8501) serves the app UI
5. User uploads a document and submits a question — Streamlit handles this via WebSocket messages
6. The app calls **`shared/auth.py`** to verify the user's session cookie
7. If authenticated, the app calls **`shared/llm_client.py`** with the document content and question as context
8. `llm_client.py` sends an HTTPS request to **`api.anthropic.com/v1/messages`** with the `ANTHROPIC_API_KEY` from `.env`
9. Anthropic API returns a JSON response with the Claude completion
10. Streamlit renders the response and pushes it to the browser via WebSocket

---

## Authentication Flow

The platform uses `streamlit-authenticator` (based on PyJWT + bcrypt):

1. User visits any app route → Streamlit checks for a valid session cookie
2. No valid cookie → login form is rendered
3. User submits username + password
4. `shared/auth.py` calls `streamlit-authenticator` which bcrypt-verifies the password against the stored hash
5. On success: a signed JWT cookie is set in the browser (`COOKIE_KEY` from `.env` is the signing secret)
6. Subsequent requests: the cookie is verified on each page load (no server-side session storage)
7. Cookie expiry is configurable in the auth config (default: 30 days)

**Key config values in `.env`:**
- `COOKIE_KEY` — JWT signing secret (keep secret, rotation invalidates all sessions)
- User credentials are stored in the app config (hashed passwords, never plaintext)

---

## Data Flow

```
User Input (browser)
    │
    ▼
Streamlit session_state   ← holds conversation history, uploaded file bytes
    │
    ▼
shared/utils.py           ← document parsing, data formatting, mock data loading
    │
    ▼
shared/llm_client.py      ← builds the messages[] array for the Anthropic API
    │                        includes: system prompt, document context, user question
    ▼
Anthropic API             ← Claude processes and returns completion
    │
    ▼
Streamlit session_state   ← stores response, updates chat history
    │
    ▼
Browser (rendered UI)
```

Mock datasets (for Data Q&A) are loaded from static CSV/JSON files at app startup — no live database connection is required for the PoC. This is intentional: the goal is to demonstrate the Text-to-SQL pattern without requiring Snowflake connectivity.

---

## CI/CD Pipeline

```
Developer pushes to main branch
    │
    ▼
GitHub Actions: .github/workflows/deploy.yml triggers
    │
    ├─ (optional) Run tests / linting
    │
    ▼
SSH into droplet as streamlit user
    │
    ├─ cd /opt/fi-genai-poc-platform
    ├─ git pull origin main
    ├─ venv/bin/pip install -r shared/requirements.txt  (picks up new deps)
    │
    ▼
Restart systemd services
    ├─ systemctl restart streamlit-doc-intelligence
    ├─ systemctl restart streamlit-data-qa
    └─ systemctl restart streamlit-report-generator
    │
    ▼
Run health check
    └─ bash deployment/scripts/health_check.sh
    │
    ▼
Send email notification (Gmail SMTP)
    ├─ SUCCESS: "Deployment complete — all 3 services healthy"
    └─ FAILURE: "Deployment health check failed — see logs"
```

**Deployment log:** `/var/log/streamlit/deploy.log` (written by `deploy.sh`)

---

## Security Considerations

- **Secrets never in Git** — `.env` is gitignored, lives on the droplet only. GitHub Secrets are used for CI/CD credentials.
- **Non-root service user** — all Streamlit apps run as the `streamlit` user, not root. Limits blast radius of a compromised app.
- **UFW firewall** — only ports 22 (SSH) and 80 (HTTP) are open. Ports 8501–8503 are bound to `localhost` only (not exposed externally).
- **bcrypt password hashing** — user passwords are stored as bcrypt hashes; plaintext passwords never persist.
- **ANTHROPIC_API_KEY scope** — API key should be scoped to minimum required permissions in the Anthropic console.
- **No HTTPS (PoC limitation)** — for a production deployment, add a Let's Encrypt TLS certificate via Certbot and redirect HTTP to HTTPS. The nginx config is structured to make this a straightforward addition.
- **Input validation** — file uploads are constrained by `client_max_body_size 50M` in nginx. App-level validation should also be implemented.

---

## Scaling Considerations

The single-droplet architecture is appropriate for a PoC with limited concurrent users. Paths to scale:

| Approach | When to use | What changes |
|----------|-------------|--------------|
| Larger droplet | More memory/CPU needed, same architecture | Resize droplet in Digital Ocean console |
| Streamlit Cloud | Managed hosting, no ops overhead | Move apps to share.streamlit.io or Streamlit in Snowflake |
| Multiple droplets + load balancer | High availability, more concurrent users | Add DO Load Balancer, replicate droplets, shared session storage (Redis) |
| Containerize with Docker | Consistent environments, easier scaling | Wrap each app in a Dockerfile, orchestrate with Docker Compose or Kubernetes |
| Snowflake Native App | For Fidelity's Snowflake environment | Repackage as Snowflake Native App with Streamlit in Snowflake |

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `streamlit` | Web app framework |
| `anthropic` | Anthropic API client (Claude) |
| `streamlit-authenticator` | Login/session management |
| `pandas` | Data manipulation for mock datasets |
| `PyJWT` | JWT token handling (used by authenticator) |
| `bcrypt` | Password hashing |
| `python-dotenv` | Load `.env` into environment variables |
| `boto3` *(optional)* | AWS S3 for document storage if needed |

System dependencies (managed by `setup_droplet.sh`):
- `nginx` — reverse proxy
- `python3.10+` — runtime
- `python3-venv` — virtual environment
- `git` — source control
- `ufw` — firewall
