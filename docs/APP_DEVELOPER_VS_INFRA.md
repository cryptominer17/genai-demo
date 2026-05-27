# App Developer vs Infrastructure Team — Responsibility Matrix

## Overview

App developers own the use-case logic, prompts, and all app-specific code under
`apps/<your_app>/`. The infrastructure team owns the runtime: the Digital Ocean
droplet, Nginx reverse proxy configuration (`deployment/nginx.conf`), systemd
service files (`deployment/systemd/`), the CI/CD pipeline
(`.github/workflows/deploy.yml`), and all environment variable management on the
server. This split ensures developers can build and iterate on new PoC apps
independently — without needing SSH access to the droplet or knowledge of the
server stack — while the infra team maintains platform stability across the four
live apps.

---

## Quick Reference Table

| Area | App Developer | Infrastructure Team |
|------|--------------|---------------------|
| App code (`apps/<your_app>/`) | ✅ Owns | reads for deploy |
| `shared/` (auth, llm_client, utils, config) | Read-only | ✅ Owns + reviews changes |
| `shared/requirements.txt` | Add packages + notify | ✅ Deploys + approves |
| `shared/mock_data/` | Add files (naming conventions) | Read-only |
| `deployment/` (nginx, systemd, scripts) | 🚫 Do not touch | ✅ Owns |
| `.github/workflows/deploy.yml` | 🚫 Do not touch | ✅ Owns |
| Port assignment | Suggest, infra assigns | ✅ Assigns final port |
| `.env` file on server | Provide key names (not values) | ✅ Adds values |
| Systemd service file | 🚫 Do not create | ✅ Creates from template |
| Nginx location block | 🚫 Do not edit | ✅ Adds for each app |
| SSL/TLS | 🚫 Not applicable | ✅ Configures when added |
| App-level `README.md` | ✅ Owns | — |
| LLM prompts and system prompts | ✅ Owns | — |
| Session state and UI layout | ✅ Owns | — |
| Local testing before deploy | ✅ Required | — |

---

## App Developer Responsibilities

### What you own

As an app developer your scope is everything inside `apps/<your_app>/`. The platform
is structured so you never need to touch the server directly.

- **`apps/<your_app>/streamlit_app.py`** — the entire Streamlit application: page
  config, sidebar controls, main content area, session state, LLM interaction, and
  result display. Start from `apps/template_app/streamlit_app.py` and follow the
  `# DEVELOPER:` annotations to adapt it.
- **`apps/<your_app>/components/`** — optional directory for local helper modules
  (e.g., chart builders, data formatters). Anything that is specific to your app
  and not shared across other apps belongs here, not in `shared/`.
- **`apps/<your_app>/data/`** — small static data files used only by your app.
  For datasets that multiple apps share, use `shared/mock_data/` instead (see
  naming conventions below).
- **`apps/<your_app>/tests/`** — unit and smoke tests. At minimum, keep
  `tests/test_app.py` with the `test_shared_imports()` smoke test from the
  template. Run with `pytest apps/<your_app>/tests/` before requesting deployment.
- **`shared/mock_data/`** — you may add files here for your app's use. Follow the
  naming convention: `lowercase_with_underscores.csv`, `.json`, or `.txt`. Place
  CSVs/JSONs under `shared/mock_data/datasets/` or `shared/mock_data/bi_data/`
  as appropriate; document-style text files under `shared/mock_data/documents/`.
  Update the relevant `README.md` in that subdirectory so infra can see what data
  is present.
- **`shared/requirements.txt`** — if your app needs a Python package not already
  listed, add it here with a pinned version (e.g. `openpyxl==3.1.2`). Then:
  1. Test locally: `pip install -r shared/requirements.txt`
  2. List the addition explicitly in your deployment request issue so infra can
     review it before the next server deploy.
- **Authentication** — call `setup_authenticator()` and `require_login()` exactly
  as shown in `apps/template_app/streamlit_app.py`. If your app requires
  role-based access control, call `require_permission("your_app_key")` after
  `require_login()`. Do not modify `shared/auth.py` directly — see the Shared Code
  Policy below.
- **LLM interaction** — all system prompts, user prompts, `max_tokens` budgets,
  and response parsing logic live in your `streamlit_app.py`. Use
  `llm.query_with_usage(prompt, system_message, max_tokens)` from
  `shared/llm_client.py`. The `ANTHROPIC_API_KEY` is injected at runtime by the
  infra team via the server `.env` file; it is never committed to Git.
- **Session state** — define your `st.session_state` keys in the initialization
  block near the top of `streamlit_app.py` so they are always present on every
  rerun. Keys introduced anywhere else can cause `KeyError` on the first run.
- **UI layout and sidebar controls** — `st.set_page_config()` must be the first
  Streamlit call. Use the two-column header pattern from the template for
  consistency across the platform.
- **Error handling** — catch exceptions from `llm.query_with_usage()` and surface
  them with `st.error()`. Do not let unhandled exceptions crash the app in
  production; the service will restart via `Restart=always` in systemd, but the
  user loses their session.
- **`apps/<your_app>/README.md`** — must be complete before you open a deploy
  request. Use `apps/template_app/README.md` as the template. All sections
  (Local Run, What to Customize, Dependencies, Deployment checklist) must be
  filled in.
- **Local smoke test** — run the app locally with
  `streamlit run apps/<your_app>/streamlit_app.py --server.port <PORT>` and
  confirm login, at least one LLM call, and logout work before requesting deploy.

### What you do NOT touch

These files and directories are managed exclusively by the infra team. Changes to
them — even well-intentioned ones — can take down all four live apps simultaneously.

- **`deployment/`** — contains `nginx.conf`, all systemd service files
  (`deployment/systemd/`), `deployment/scripts/deploy.sh`,
  `deployment/scripts/health_check.sh`, and
  `deployment/scripts/setup_droplet.sh`. The Nginx configuration handles
  WebSocket proxying, which is required for Streamlit's real-time UI updates.
  An incorrect `location` block silently breaks the app UI.
- **`.github/workflows/deploy.yml`** — the CI/CD pipeline. It SSHs into the
  droplet, runs `deployment/scripts/deploy.sh`, waits 20 seconds, and then runs
  `health_check.sh`. Changes here require infra review because a misconfigured
  pipeline can skip health checks and leave broken services running.
- **`shared/auth.py`** — the authentication layer used by every app. A bug here
  locks all users out of the entire platform simultaneously. Use the exported
  functions; do not import internal helpers.
- **`shared/llm_client.py`** — the Anthropic API wrapper. Changes to the model
  name, API version, or retry logic affect every app's LLM calls.
- **`shared/config.py`** — centralized environment variable loading. The
  `.env` file path is resolved relative to the repo root; changing this breaks
  all apps on the server.
- **Server OS, firewall (UFW), or network configuration** — only ports 22, 80,
  and 443 are open inbound. These settings are managed via
  `deployment/sysctl/99-fi-genai.conf` and UFW rules set during droplet
  provisioning.
- **The `.env` file on the server** — located at
  `/opt/fi-genai-poc-platform/.env` on the droplet. You never get shell access;
  the infra team adds values there. You provide key names via a secure channel
  (see Environment Variable Ownership below).

### How to request a new app be hosted

1. Complete the Handoff Checklist (see below) inside your `apps/<name>/README.md`.
2. Open a GitHub issue titled **"Deploy request: `<AppName>`"** and paste the
   completed checklist into the issue body.
3. The infra team assigns a port (next available: **8505** for the first new app)
   and responds with confirmation in the issue.
4. Developer merges the app code to `main`; the CI/CD pipeline (`.github/workflows/deploy.yml`)
   deploys the app code to `/opt/fi-genai-poc-platform/` on the droplet.
5. The infra team creates the systemd service file (modeled on
   `deployment/systemd/streamlit-admin.service`), enables it, adds a new
   `location /Your_Route` block to `deployment/nginx.conf`, and reloads Nginx
   with `sudo nginx -t && sudo systemctl reload nginx`.
6. The infra team confirms the app is reachable at `http://<host>/Your_Route` and
   closes the issue.

---

## Infrastructure Team Responsibilities

### What you own

The infra team owns the server, the deployment pipeline, and the runtime
configuration that makes all apps accessible.

- **Digital Ocean droplet** — Ubuntu 22.04 LTS, OS security patches, kernel
  tuning via `deployment/sysctl/99-fi-genai.conf` (TCP tuning, file descriptor
  limits for Streamlit WebSockets).
- **UFW firewall** — inbound rules: port 22 (SSH), 80 (HTTP), 443 (HTTPS when
  added). All other inbound ports are blocked; Streamlit apps bind on
  `localhost` only and are never directly exposed.
- **Nginx reverse proxy** — `deployment/nginx.conf`. Each Streamlit app requires
  two `location` blocks: a redirect from the bare path (e.g. `/Document_AI`) and
  a proxied block for the trailing-slash form (`/Document_AI/`). The proxied
  block must include `Upgrade` and `Connection` headers for WebSocket support, and
  `proxy_read_timeout 86400` to keep long-running LLM calls alive. The current
  upstream blocks are `doc_intelligence` (:8501), `data_qa` (:8502),
  `report_generator` (:8503), and `admin` (:8504).
- **Systemd service files** — created from the pattern in
  `deployment/systemd/streamlit-admin.service`. Each service runs as the
  `streamlit` user with `WorkingDirectory=/opt/fi-genai-poc-platform`, loads
  the `.env` via `EnvironmentFile=`, sets `PYTHONPATH=/opt/fi-genai-poc-platform`,
  and logs to `/var/log/streamlit/<appname>.log` and
  `/var/log/streamlit/<appname>-error.log`. `Restart=always` with `RestartSec=10`
  ensures automatic recovery.
- **CI/CD pipeline** — `.github/workflows/deploy.yml`. Triggered on push to
  `main`. Uses the `DROPLET_SSH_KEY`, `DROPLET_IP`, and `DROPLET_USER` GitHub
  secrets to SSH into the droplet and run `deployment/scripts/deploy.sh`, then
  validates all apps with `deployment/scripts/health_check.sh`. Also sends email
  notifications on success/failure via `deployment/email/notify.py` using the
  `SMTP_PASSWORD` secret.
- **Port allocation** — the current registry is 8501–8504 (see Port Registry
  below). Infra assigns the next available port when responding to a deploy
  request issue. Ports must be unique across all services including the Admin
  REST API (currently on 8505).
- **`.env` file on server** — `/opt/fi-genai-poc-platform/.env`. Contains
  `ANTHROPIC_API_KEY` and all other secrets. Infra adds values; developers
  provide key names via Slack DM or 1Password share, never via Git.
- **Log directory** — `/var/log/streamlit/` is created during droplet
  provisioning (`deployment/scripts/setup_droplet.sh`) and is writable by the
  `streamlit` service user. Log rotation is configured via logrotate.
- **Deployment execution** — a push to `main` triggers `deploy.yml`
  automatically. Infra monitors the Actions run and can roll back by reverting
  the merge commit and pushing to `main` again.
- **Health checks** — `deployment/scripts/health_check.sh` verifies all
  systemd services are active, all app ports respond with 2xx/3xx, Nginx config
  is valid, recent error logs are clean, and disk usage is below 85%.

### What infra does NOT own

- App logic, LLM prompts, or UI decisions — if an app crashes because of a bad
  prompt or unhandled exception in `streamlit_app.py`, that is the developer's
  responsibility to fix.
- Data file content or schema — infra deploys whatever is committed to
  `shared/mock_data/`. If a CSV has the wrong columns, that is a developer issue.
- Whether an app "works" functionally — infra ensures the process is running on
  the correct port and Nginx is routing to it correctly. Feature correctness and
  LLM output quality are the developer's responsibility.

---

## Handoff Checklist

What the developer must provide before infra can deploy. Copy this into your
deploy request GitHub issue and check each item:

- [ ] App directory: `apps/<name>/` with `streamlit_app.py` present and
      syntactically valid (run `python -m py_compile apps/<name>/streamlit_app.py`)
- [ ] Desired route: e.g. `/My_New_App` (must be URL-safe, no spaces; must
      match the `--server.baseUrlPath` argument that infra will add to the
      systemd service)
- [ ] Port requested: suggest the next available from the Port Registry (infra
      confirms the final assignment)
- [ ] New environment variables: list key names only — e.g. `MY_API_KEY` — values
      delivered via secure channel (Slack DM, 1Password share), never in Git
- [ ] New pip packages: added to `shared/requirements.txt` with pinned versions
      and listed explicitly in this issue
- [ ] Local test confirmation: "Ran locally on port `<PORT>` with no errors on
      `<YYYY-MM-DD>`"
- [ ] `apps/<name>/README.md` completed (all sections filled in, no placeholder
      text remaining)
- [ ] Role permissions: which roles should access this app —
      `admin` / `analyst` / `viewer` (used to configure the permission matrix in
      `shared/user_db.py`)

---

## Port Registry

| Port | Route | App | Status |
|------|-------|-----|--------|
| 8501 | /Document_AI | Document Intelligence | Live |
| 8502 | /Text_to_SQL | Data Q&A | Live |
| 8503 | /BI_Dashboard | Report Generator | Live |
| 8504 | /Admin | Admin Panel | Live |
| 8505 | TBD | Next app | Available |

Note: Port 8504 is assigned to the Admin Panel
(`deployment/systemd/streamlit-admin.service`). Port 8505 is currently used by
the Admin REST API (`fi-genai-api.service`) in the Nginx upstream config, but
is available for reassignment if that service is moved. Confirm the current
state with the infra team when requesting a port assignment.

---

## Environment Variable Ownership

| Variable | Purpose | Provided by | Set on server by |
|----------|---------|-------------|-----------------|
| `ANTHROPIC_API_KEY` | Claude API authentication | Platform owner | Infra team |
| `SECRET_KEY` | Streamlit authenticator cookie secret | Infra team generates | Infra team |
| `COOKIE_EXPIRY_DAYS` | Auth session length | Infra team | Infra team |
| `ADMIN_PASSWORD_HASH` | Default admin password hash | Developer (via `scripts/setup_admin.py`) | Infra team |
| `LOG_LEVEL` | Application log verbosity | Infra team | Infra team |
| `ENVIRONMENT` | Runtime environment flag (`dev`/`prod`) | Infra team | Infra team |
| `SMTP_PASSWORD` | Gmail App Password for deploy notifications | Infra team | Infra team |

Developers needing new environment variables for their app must:

1. Add the key name (not value) to `.env.example` with a descriptive comment, e.g.:
   ```
   MY_EXTERNAL_API_KEY=        # API key for the XYZ data service (developer to supply)
   ```
2. List the key name in the deploy request issue.
3. Deliver the actual value to infra via a secure channel — Slack DM to the infra
   lead or a 1Password share — never commit credential values to Git.

---

## Shared Code Policy

The files `shared/auth.py`, `shared/llm_client.py`, `shared/utils.py`,
`shared/config.py`, and `shared/requirements.txt` are loaded by all four live apps
simultaneously. A bug introduced here — a bad import, a changed function signature,
or an incompatible package version — takes down every app at the next service
restart or deploy.

To propose a change to `shared/`:

1. Open a GitHub issue tagged `shared-code-change` describing the proposed change,
   which app needs it, and why it cannot live in `apps/<your_app>/` instead.
2. The infra team reviews the change for security implications and cross-app
   compatibility (e.g., a new `shared/utils.py` function must not conflict with
   names used in existing apps).
3. If approved, the developer opens a pull request; the infra team is a required
   reviewer and must approve before merge.
4. Changes to `shared/auth.py` or `shared/llm_client.py` require manually testing
   all three live apps (Document Intelligence at `/Document_AI`, Data Q&A at
   `/Text_to_SQL`, Report Generator at `/BI_Dashboard`) before the PR is merged.
5. The infra team coordinates the deployment window — typically off-hours — to
   minimize disruption, and monitors the `health_check.sh` output after the
   deploy.

Do not add app-specific logic to `shared/` files. If you need a utility function
that only your app uses, put it in `apps/<your_app>/` as a local module (e.g.,
`apps/<your_app>/components/formatters.py`) and import it with a relative import
or by adding the app directory to `sys.path`.
