# FAQ — FI GenAI PoC Platform

Organized by category. Jump to the section relevant to your question.

---

## Setup and Prerequisites

**Q: Do I need a paid Anthropic API key?**

Yes. The free tier does not exist in the traditional sense — Anthropic requires a paid account with credits loaded. For demo usage (occasional document analysis and report generation), $5–$20/month in credits is typically sufficient. Costs depend on token volume; Claude Haiku is significantly cheaper than Claude Sonnet or Opus if you want to minimize cost while preserving demo value.

**Q: Can I use a different cloud provider instead of Digital Ocean?**

Yes, with modifications. The platform requires an Ubuntu 22.04 server with a public IP, a user account (named `streamlit` in the default config), and sudo access to install nginx and systemd services. AWS EC2 (t3.small), GCP Compute Engine (e2-small), or Azure VM equivalents all work. You would need to adjust the bootstrap script if the base image differs from Ubuntu 22.04 LTS. Digital Ocean is recommended for this PoC because the setup script is written for it and the $12/mo cost is straightforward.

**Q: What if I don't have a Gmail account for notifications?**

The SMTP configuration supports any provider that uses STARTTLS on port 587. Common alternatives:
- Outlook/Hotmail: `smtp.office365.com`, port `587`
- Yahoo Mail: `smtp.mail.yahoo.com`, port `587`
- Custom SMTP relay: update SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD in `.env`

If you don't need email notifications at all, the platform will still function — notification failures are non-fatal to the deployment pipeline.

**Q: Can I change the app ports from 8501/8502/8503?**

Yes, but you must update three places consistently:
1. Each systemd service file (`deployment/systemd/*.service`) — the `--server.port` argument
2. The nginx upstream definitions in `deployment/nginx.conf`
3. Any health check scripts that reference specific ports

Changing ports after initial deployment requires reloading systemd and nginx configs on the droplet.

---

## Authentication

**Q: How do I change the login password after deployment?**

SSH to the droplet and edit the `.env` file:
```bash
ssh streamlit@<DROPLET_IP>
nano /opt/fi-genai-poc-platform/.env
# Change the STREAMLIT_PASSWORD value
# Save and exit
sudo systemctl restart streamlit-doc-intelligence streamlit-data-qa streamlit-report-generator
```
The new password takes effect immediately after the restart.

**Q: Can I add multiple users?**

The current implementation uses a single username/password pair from environment variables. It does not support multiple user accounts natively. Options to expand:
- Store credentials in a YAML or JSON file and update `shared/auth.py` to load from it
- Integrate `streamlit-authenticator` library's multi-user YAML config
- Replace with OAuth/SSO (see "Known Limitations" in `DEPLOYMENT_SUMMARY.md`)

For the PoC demo, single-user auth is sufficient for stakeholder demos.

**Q: What happens if I forget the password?**

The password is stored in plain text in `/opt/fi-genai-poc-platform/.env` on the droplet. SSH to the droplet and read the file:
```bash
ssh streamlit@<DROPLET_IP>
grep STREAMLIT_PASSWORD /opt/fi-genai-poc-platform/.env
```
If you cannot SSH, see Scenario 4 in `docs/ROLLBACK_GUIDE.md` for full recovery steps.

**Q: How long do login sessions last?**

Session duration is controlled by Streamlit's built-in session state, which persists for the lifetime of the browser session. Closing the browser tab effectively ends the session. There is no configurable session timeout in the current implementation — users remain logged in until they click Logout or close their browser.

---

## Apps and Usage

**Q: The LLM response is slow — is that normal?**

Yes, for the first request after app startup. Subsequent requests to Claude are typically faster. Response time depends on:
- Claude model tier selected (Haiku ~2–5 sec, Sonnet ~5–15 sec)
- Prompt and document length
- Anthropic API load

If responses consistently time out (no response after 60+ seconds), check `journalctl -u streamlit-doc-intelligence -n 30` for API error messages and verify ANTHROPIC_API_KEY is set correctly.

**Q: Can I replace the mock data with real data?**

Yes. The mock data lives in `shared/mock_data/`. Replace or augment the files in:
- `shared/mock_data/documents/` — for Document Intelligence (plain text files)
- `shared/mock_data/datasets/` — for Data Q&A (CSV files)
- `shared/mock_data/bi_data/` — for Report Generator (CSV/JSON metrics files)

For a production upgrade, the longer-term path is connecting to Snowflake Cortex or a real database. The `shared/` layer is designed to abstract data access, making this substitution tractable.

**Q: The charts aren't showing — what's wrong?**

Common causes:
1. **Browser issue**: Hard refresh (`Ctrl+Shift+R`) — Streamlit sometimes caches stale JS
2. **Missing dependency**: Verify `plotly` and `altair` are installed in the venv:
   ```bash
   /opt/fi-genai-poc-platform/venv/bin/pip show plotly
   ```
3. **Data shape mismatch**: The chart function may be receiving unexpected column names. Check `journalctl -u streamlit-data-qa -n 20` for Python errors.
4. **WebSocket blocked**: If behind a corporate proxy or VPN, WebSocket connections (required by Streamlit) may be blocked. Try a direct network connection.

**Q: Can I add my own documents to Document Intelligence?**

Yes. Add `.txt` or `.pdf` files to `shared/mock_data/documents/` on the droplet:
```bash
scp my-document.txt streamlit@<DROPLET_IP>:/opt/fi-genai-poc-platform/shared/mock_data/documents/
```
The app's document list is populated dynamically from that directory, so the new file will appear on next page refresh without a service restart.

---

## Deployment and Infrastructure

**Q: How do I update the app after making code changes?**

Push to the `main` branch on GitHub. The CI/CD pipeline handles the rest automatically (git pull, venv update, service restart, health check, email notification). You do not need to SSH to the droplet for routine code updates.

For urgent fixes that can't wait for CI/CD, SSH and run the deploy script directly:
```bash
ssh streamlit@<DROPLET_IP>
bash /opt/fi-genai-poc-platform/deployment/scripts/deploy.sh
```

**Q: What if my droplet runs out of memory?**

The 2 GB RAM droplet runs three Streamlit processes plus nginx. Under normal demo load this is sufficient, but if memory is exhausted:
1. Check current usage: `free -h`
2. Check per-process usage: `ps aux --sort=-%mem | head -10`
3. Short-term fix: restart the heaviest service, or reboot the droplet (`sudo reboot`)
4. Long-term fix: upgrade to the 4 GB RAM droplet ($24/mo) in Digital Ocean → Resize

**Q: How do I check if all three apps are running?**

One command:
```bash
bash /opt/fi-genai-poc-platform/deployment/scripts/health_check.sh
```

Or individually:
```bash
systemctl is-active streamlit-doc-intelligence streamlit-data-qa streamlit-report-generator
```

**Q: Can I run this on a $6/month droplet?**

The $6/mo droplet has 1 GB RAM. Running three Streamlit processes simultaneously on 1 GB is tight but possible if usage is light (one user at a time, no concurrent requests). For a reliable demo you may encounter OOM kills on the smaller droplet. The $12/mo 2 GB droplet is the minimum recommended spec.

**Q: How do I add HTTPS/SSL?**

Use Let's Encrypt with Certbot:
```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d <YOUR_DOMAIN>
```
This requires a domain name pointed at your droplet's IP. Certbot will auto-update the nginx config to redirect HTTP to HTTPS and handle certificate renewal. Without a domain, you can use a self-signed certificate, though browsers will show a security warning.

**Q: My GitHub Actions workflow is failing — where do I look?**

1. Go to https://github.com/cryptominer17/genai-demo/actions
2. Click the failed workflow run
3. Click the failed step to expand its log
4. Common failure points:
   - "Permission denied (publickey)": `DROPLET_SSH_KEY` secret is wrong or expired
   - "Connection refused": `DROPLET_IP` secret is stale or droplet is down
   - "deploy.sh: No such file": repo wasn't cloned on droplet — run initial setup again
   - "health_check.sh exited with status 1": an app failed to start — check service logs on droplet

See `docs/ROLLBACK_GUIDE.md` Scenario 5 for the full resolution flow.

---

## Costs

**Q: What is the approximate monthly cost to run this platform?**

| Component | Cost |
|-----------|------|
| Digital Ocean Droplet (2 GB RAM) | $12.00/mo |
| Anthropic API (demo usage, occasional calls) | $5–20/mo |
| GitHub (Actions minutes, public repo) | $0 |
| Domain name (optional, for HTTPS) | ~$1–2/mo |
| **Total** | **~$17–34/mo** |

API costs are usage-dependent. A stakeholder demo with 20–30 LLM calls/day using Claude Haiku would be well under $5/month. Claude Sonnet at the same volume would be $10–15/month. Costs rise significantly if you add continuous document processing or high-volume queries.

**Q: Are there any one-time costs?**

The only one-time cost is your time to set up the infrastructure. All software used (Ubuntu, Python, Streamlit, Nginx, systemd) is open source and free. Anthropic requires an initial credit purchase (minimum typically $5).
