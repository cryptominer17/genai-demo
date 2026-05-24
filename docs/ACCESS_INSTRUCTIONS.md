# Access Instructions — FI GenAI PoC Platform

Single reference document for accessing the deployed platform.
Replace `<DROPLET_IP>` throughout with the actual Digital Ocean droplet IP.

---

## App URLs

| App | URL | Direct Port | Description |
|-----|-----|-------------|-------------|
| Document Intelligence | http://\<DROPLET_IP\>/Document_AI | 8501 | AI-powered document analysis via Claude |
| Data Q&A | http://\<DROPLET_IP\>/Text_to_SQL | 8502 | Natural language queries over datasets |
| Report Generator | http://\<DROPLET_IP\>/BI_Dashboard | 8503 | AI-generated business intelligence reports |
| Health Check | http://\<DROPLET_IP\>/health | 80 | Service health endpoint — returns `OK` |
| Root (auto-redirect) | http://\<DROPLET_IP\>/ | 80 | Redirects to `/Document_AI/` |

---

## Login Credentials

All three apps share the same credentials, set during initial deployment in `/opt/fi-genai-poc-platform/.env`.

| Field | Value |
|-------|-------|
| Username | Value of `STREAMLIT_USERNAME` in `.env` |
| Password | Value of `STREAMLIT_PASSWORD` in `.env` |

If you don't know the current credentials:
```bash
ssh streamlit@<DROPLET_IP>
grep -E 'STREAMLIT_USERNAME|STREAMLIT_PASSWORD' /opt/fi-genai-poc-platform/.env
```

To change the password:
```bash
nano /opt/fi-genai-poc-platform/.env
# Update STREAMLIT_PASSWORD
sudo systemctl restart streamlit-doc-intelligence streamlit-data-qa streamlit-report-generator
```

---

## SSH Access

```bash
ssh streamlit@<DROPLET_IP>
```

The `streamlit` user has sudo access. Use this for all operational tasks.
Do not log in as root for routine operations.

---

## Log Locations

| Log | File Path | View Command |
|-----|-----------|--------------|
| Deployment | /var/log/streamlit/deploy.log | `tail -f /var/log/streamlit/deploy.log` |
| Doc Intelligence (stdout) | /var/log/streamlit/doc-intelligence.log | `tail -f /var/log/streamlit/doc-intelligence.log` |
| Doc Intelligence (stderr) | /var/log/streamlit/doc-intelligence-error.log | `tail -f /var/log/streamlit/doc-intelligence-error.log` |
| Data Q&A (stdout) | /var/log/streamlit/data-qa.log | `tail -f /var/log/streamlit/data-qa.log` |
| Data Q&A (stderr) | /var/log/streamlit/data-qa-error.log | `tail -f /var/log/streamlit/data-qa-error.log` |
| Report Generator (stdout) | /var/log/streamlit/report-generator.log | `tail -f /var/log/streamlit/report-generator.log` |
| Report Generator (stderr) | /var/log/streamlit/report-generator-error.log | `tail -f /var/log/streamlit/report-generator-error.log` |
| Nginx access | /var/log/nginx/fi-genai-poc-access.log | `tail -f /var/log/nginx/fi-genai-poc-access.log` |
| Nginx error | /var/log/nginx/fi-genai-poc-error.log | `tail -f /var/log/nginx/fi-genai-poc-error.log` |

For richer log output with timestamps and service metadata:
```bash
journalctl -u streamlit-doc-intelligence -n 50 --no-pager
journalctl -u streamlit-data-qa -n 50 --no-pager
journalctl -u streamlit-report-generator -n 50 --no-pager
```

---

## Quick Commands

**Check all services at once:**
```bash
bash /opt/fi-genai-poc-platform/deployment/scripts/health_check.sh
```

**Check individual service status:**
```bash
systemctl status streamlit-doc-intelligence
systemctl status streamlit-data-qa
systemctl status streamlit-report-generator
```

**Restart a specific service:**
```bash
sudo systemctl restart streamlit-doc-intelligence
sudo systemctl restart streamlit-data-qa
sudo systemctl restart streamlit-report-generator
```

**Restart all three services:**
```bash
sudo systemctl restart streamlit-doc-intelligence streamlit-data-qa streamlit-report-generator
```

**View recent errors for any service:**
```bash
journalctl -u streamlit-doc-intelligence -n 50 --no-pager
```

**Trigger a manual deployment (pulls latest from GitHub, restarts services):**
```bash
bash /opt/fi-genai-poc-platform/deployment/scripts/deploy.sh
```

**Test nginx config after any changes:**
```bash
sudo nginx -t && sudo systemctl reload nginx
```

---

## GitHub Actions (CI/CD)

Automated deploys are triggered by any push to the `main` branch.

| Resource | URL |
|----------|-----|
| Workflow runs | https://github.com/cryptominer17/genai-demo/actions |
| Repository | https://github.com/cryptominer17/genai-demo |
| Secrets config | https://github.com/cryptominer17/genai-demo/settings/secrets/actions |

**Required GitHub secrets:**

| Secret | Description |
|--------|-------------|
| `DROPLET_IP` | Droplet static IP address |
| `DROPLET_SSH_KEY` | Private SSH key from `/home/streamlit/.ssh/id_ed25519` |
| `DROPLET_USER` | Always `streamlit` |
| `SMTP_PASSWORD` | Gmail App Password for deployment notifications |

---

## Service Architecture Reference

```
Browser → http://<DROPLET_IP>
              │
              ▼
           Nginx :80
              │
     ┌────────┼────────┐
     │        │        │
 /Document_AI /Text_to_SQL /BI_Dashboard
     │        │        │
  :8501     :8502    :8503
     │        │        │
  Doc Intel  Data Q&A  Report Gen
  (systemd)  (systemd) (systemd)
     │        │        │
     └────────┴────────┘
              │
          shared/
     ┌─────┬──────┬──────┐
  config  auth  llm_  utils
              client
              │
          Anthropic API
```

---

## Deployment Notification Emails

Deployment success and failure emails are sent to `shouvik.pradhan@gmail.com`.

- **Subject on success**: Contains "SUCCESS" and "Deployment completed successfully"
- **Subject on failure**: Contains "FAILURE" and "Check GitHub Actions logs"
- **Sender**: The Gmail address set in `SMTP_USERNAME` in `.env`

If emails are not arriving, check:
1. `SMTP_PASSWORD` secret in GitHub Actions is current
2. Gmail App Password has not been revoked
3. `/var/log/streamlit/deploy.log` for SMTP errors
