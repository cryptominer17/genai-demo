# Production Deployment Guide

Step-by-step instructions for deploying the FI GenAI PoC Platform to a fresh Digital Ocean Ubuntu 22.04 droplet. Assumes `setup_droplet.sh` has already been run (system packages installed, `streamlit` user created, directories created).

---

## Prerequisites

- Droplet provisioned (Ubuntu 22.04 LTS, Digital Ocean Virginia region)
- You can SSH in as root or a sudo user
- `setup_droplet.sh` has been run (or equivalent manual setup)
- You have your `ANTHROPIC_API_KEY` and any other `.env` values ready
- SSH key for `streamlit` user added (see [GITHUB_SECRETS_SETUP.md](GITHUB_SECRETS_SETUP.md))

Run the pre-flight check first:
```bash
bash /opt/fi-genai-poc-platform/deployment/scripts/verify_droplet.sh
```

---

## Step 1 — Clone the Repository

```bash
sudo -u streamlit git clone https://github.com/cryptominer17/genai-demo.git /opt/fi-genai-poc-platform
```

If the directory already exists (re-deploy):
```bash
cd /opt/fi-genai-poc-platform
sudo -u streamlit git pull origin main
```

Verify ownership:
```bash
ls -la /opt/ | grep fi-genai
# Should show: streamlit streamlit ... fi-genai-poc-platform
```

---

## Step 2 — Create Virtual Environment and Install Dependencies

```bash
cd /opt/fi-genai-poc-platform

# Create venv as the streamlit user
sudo -u streamlit python3 -m venv venv

# Install dependencies
sudo -u streamlit venv/bin/pip install --upgrade pip
sudo -u streamlit venv/bin/pip install -r shared/requirements.txt
```

Verify installation:
```bash
sudo -u streamlit venv/bin/pip list | grep streamlit
# Should show streamlit and its version
```

---

## Step 3 — Create the .env File

```bash
sudo -u streamlit cp /opt/fi-genai-poc-platform/.env.example /opt/fi-genai-poc-platform/.env
sudo nano /opt/fi-genai-poc-platform/.env
```

Minimum required values (see `.env.example` for the full list):

```env
ANTHROPIC_API_KEY=sk-ant-...
APP_SECRET_KEY=<random 32+ char string>
COOKIE_KEY=<random 32+ char string>
# Add any other app-specific keys from .env.example
```

Lock down permissions:
```bash
sudo chmod 600 /opt/fi-genai-poc-platform/.env
sudo chown streamlit:streamlit /opt/fi-genai-poc-platform/.env
```

**Important:** The `.env` file never goes into Git. It lives on the droplet only.

---

## Step 4 — Install systemd Services

```bash
# Copy service files
sudo cp /opt/fi-genai-poc-platform/deployment/systemd/*.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable all three services (auto-start on reboot)
sudo systemctl enable streamlit-doc-intelligence
sudo systemctl enable streamlit-data-qa
sudo systemctl enable streamlit-report-generator

# Start all three services
sudo systemctl start streamlit-doc-intelligence
sudo systemctl start streamlit-data-qa
sudo systemctl start streamlit-report-generator
```

Check status:
```bash
sudo systemctl status streamlit-doc-intelligence
sudo systemctl status streamlit-data-qa
sudo systemctl status streamlit-report-generator
```

All three should show `active (running)`. If any show `failed`, check logs:
```bash
journalctl -u streamlit-doc-intelligence -n 50 --no-pager
```

---

## Step 5 — Install Nginx Config

```bash
# Copy config to sites-available
sudo cp /opt/fi-genai-poc-platform/deployment/nginx.conf \
    /etc/nginx/sites-available/fi-genai-poc

# Create symlink in sites-enabled
sudo ln -sf /etc/nginx/sites-available/fi-genai-poc \
    /etc/nginx/sites-enabled/fi-genai-poc

# Remove default nginx site if present (avoids port 80 conflicts)
sudo rm -f /etc/nginx/sites-enabled/default

# Test config
sudo nginx -t
# Expected: nginx: configuration file /etc/nginx/nginx.conf test is successful

# Reload nginx
sudo systemctl restart nginx
```

---

## Step 6 — Run Verification Script

```bash
bash /opt/fi-genai-poc-platform/deployment/scripts/verify_droplet.sh
```

All items should show `[PASS]`. Fix any `[FAIL]` items before proceeding.

---

## Step 7 — Run Health Check

```bash
bash /opt/fi-genai-poc-platform/deployment/scripts/health_check.sh
```

Expected output: all green `[OK]` for services, ports, nginx, and logs.

If any port shows `[FAIL]`, wait 10–15 seconds (Streamlit takes a moment to initialize) and re-run.

---

## Step 8 — Access the Apps

Once all checks pass, the apps are available at:

| App | URL |
|-----|-----|
| Document Intelligence | `http://<DROPLET_IP>/Document_AI/` |
| Data Q&A (Text-to-SQL) | `http://<DROPLET_IP>/Text_to_SQL/` |
| Report Generator | `http://<DROPLET_IP>/BI_Dashboard/` |
| Health endpoint | `http://<DROPLET_IP>/health` |

Get your droplet IP:
```bash
curl -s ifconfig.me
```

---

## Step 9 — Set Up GitHub Secrets for CI/CD

See [GITHUB_SECRETS_SETUP.md](GITHUB_SECRETS_SETUP.md) for the complete list of secrets to add to your GitHub repository (`Settings → Secrets and variables → Actions`).

---

## Step 10 — Trigger First CI/CD Run

Once secrets are configured, trigger the pipeline:

```bash
# On your local machine
git checkout main
# Make a minor change (e.g., update a comment)
echo "# deployment test" >> README.md
git add README.md
git commit -m "chore: trigger initial CI/CD deployment"
git push origin main
```

Watch the run at: `https://github.com/cryptominer17/genai-demo/actions`

The workflow will:
1. SSH into the droplet
2. Pull latest code
3. Install any new dependencies
4. Restart systemd services
5. Run the health check
6. Send an email notification with the result

---

## Useful Management Commands

```bash
# Restart a single app
sudo systemctl restart streamlit-doc-intelligence

# Restart all three at once
sudo systemctl restart streamlit-doc-intelligence streamlit-data-qa streamlit-report-generator

# View live logs
tail -f /var/log/streamlit/doc-intelligence.log

# View systemd journal
journalctl -u streamlit-data-qa -f

# Reload nginx after config change
sudo nginx -t && sudo systemctl reload nginx
```

For log management see [LOGS_AND_MONITORING.md](LOGS_AND_MONITORING.md).
