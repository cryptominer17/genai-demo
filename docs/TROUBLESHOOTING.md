# Troubleshooting Guide

Organized by symptom. Each entry has a diagnosis and concrete fix steps.

---

## Service Won't Start

**Symptom:** `systemctl status streamlit-doc-intelligence` shows `failed` or `activating` indefinitely.

**Diagnosis steps:**
```bash
# Most useful first step — last 50 lines of the journal
journalctl -u streamlit-doc-intelligence -n 50 --no-pager

# Also check the app error log
tail -n 50 /var/log/streamlit/doc-intelligence-error.log
```

**Common causes and fixes:**

1. **Missing .env file**
   ```
   Error: EnvironmentFile=/opt/fi-genai-poc-platform/.env: No such file or directory
   ```
   Fix:
   ```bash
   sudo -u streamlit cp /opt/fi-genai-poc-platform/.env.example /opt/fi-genai-poc-platform/.env
   sudo nano /opt/fi-genai-poc-platform/.env   # fill in real values
   sudo systemctl start streamlit-doc-intelligence
   ```

2. **Port already in use**
   ```
   Error: address already in use (port 8501)
   ```
   Fix:
   ```bash
   sudo lsof -i :8501
   sudo kill <PID>
   sudo systemctl start streamlit-doc-intelligence
   ```

3. **Virtual environment not created**
   ```
   Error: /opt/fi-genai-poc-platform/venv/bin/streamlit: No such file or directory
   ```
   Fix:
   ```bash
   cd /opt/fi-genai-poc-platform
   sudo -u streamlit python3 -m venv venv
   sudo -u streamlit venv/bin/pip install -r shared/requirements.txt
   sudo systemctl start streamlit-doc-intelligence
   ```

4. **Wrong file permissions**
   ```
   Error: Permission denied
   ```
   Fix:
   ```bash
   sudo chown -R streamlit:streamlit /opt/fi-genai-poc-platform
   sudo chown -R streamlit:streamlit /var/log/streamlit
   sudo systemctl start streamlit-doc-intelligence
   ```

5. **Python import error (missing dependency)**
   Check the error log for `ModuleNotFoundError`, then:
   ```bash
   sudo -u streamlit /opt/fi-genai-poc-platform/venv/bin/pip install -r \
       /opt/fi-genai-poc-platform/shared/requirements.txt
   sudo systemctl restart streamlit-doc-intelligence
   ```

---

## 502 Bad Gateway from Nginx

**Symptom:** Browser shows `502 Bad Gateway` when hitting `/Document_AI`, `/Text_to_SQL`, or `/BI_Dashboard`.

**Diagnosis steps:**
```bash
# 1. Is the relevant Streamlit service actually running?
systemctl is-active streamlit-doc-intelligence   # for /Document_AI

# 2. Can nginx reach the port directly?
curl -v http://localhost:8501

# 3. Check nginx error log
tail -n 30 /var/log/nginx/fi-genai-poc-error.log

# 4. Validate nginx config
sudo nginx -t
```

**Common causes and fixes:**

1. **Streamlit service not running** — fix the service first (see above), then nginx will recover automatically.

2. **Nginx config syntax error**
   ```bash
   sudo nginx -t
   # Fix the reported line, then:
   sudo systemctl reload nginx
   ```

3. **Upstream port mismatch** — verify the port in `nginx.conf` upstream blocks matches the `--server.port` in the service file.

4. **Service just started, not ready yet** — Streamlit takes 5–15 seconds to initialize. Wait and refresh.

---

## Authentication Loop / Can't Log In

**Symptom:** Login form submits but immediately redirects back to the login page, or shows "incorrect username or password" for credentials you know are correct.

**Diagnosis steps:**
```bash
tail -n 30 /var/log/streamlit/doc-intelligence-error.log | grep -i auth
```

**Common causes and fixes:**

1. **Cookie key mismatch** — `COOKIE_KEY` in `.env` was changed after users logged in, invalidating existing cookies.
   Fix: Clear browser cookies for the site and log in again.

2. **Password hash version mismatch** — if `streamlit-authenticator` was upgraded between versions, the bcrypt hash format may differ.
   Fix: Regenerate the password hash using the current library version:
   ```python
   import streamlit_authenticator as stauth
   hashed = stauth.Hasher(['your_password']).generate()
   print(hashed)
   ```
   Update the config/users file with the new hash.

3. **Session state collision** — multiple browser tabs can sometimes corrupt session state.
   Fix: Open a fresh incognito window and try again.

4. **Clock skew** — JWT tokens are time-sensitive. If the droplet clock is wrong:
   ```bash
   sudo timedatectl set-ntp true
   timedatectl status
   ```

---

## LLM Calls Failing

**Symptom:** App loads, authentication works, but any AI feature returns an error or blank response.

**Diagnosis steps:**
```bash
# Check error log for API errors
grep -i "anthropic\|api\|rate.limit\|401\|403\|500" \
    /var/log/streamlit/doc-intelligence-error.log | tail -20
```

**Common causes and fixes:**

1. **ANTHROPIC_API_KEY missing or wrong in .env**
   ```bash
   grep ANTHROPIC_API_KEY /opt/fi-genai-poc-platform/.env
   ```
   Test the key directly:
   ```bash
   curl https://api.anthropic.com/v1/messages \
     -H "x-api-key: $ANTHROPIC_API_KEY" \
     -H "anthropic-version: 2023-06-01" \
     -H "content-type: application/json" \
     -d '{"model":"claude-haiku-20240307","max_tokens":10,"messages":[{"role":"user","content":"hi"}]}'
   # Should return a JSON response, not {"error": ...}
   ```
   Fix: Update `.env`, then restart services:
   ```bash
   sudo systemctl restart streamlit-doc-intelligence streamlit-data-qa streamlit-report-generator
   ```

2. **Rate limit hit** — look for `429` in error logs. Reduce request frequency or upgrade your Anthropic plan.

3. **Network egress blocked** — verify the droplet can reach the Anthropic API:
   ```bash
   curl -I https://api.anthropic.com
   # Should return HTTP/2 200 or 405, not a timeout
   ```

---

## GitHub Actions Deployment Failing

**Symptom:** GitHub Actions workflow fails on the SSH step or deploy step.

**Diagnosis:** Check the Actions log at `https://github.com/cryptominer17/genai-demo/actions` for the specific error line.

**Common causes and fixes:**

1. **SSH key not in authorized_keys on the droplet**
   ```bash
   # On the droplet, as root:
   cat /home/streamlit/.ssh/authorized_keys
   # If missing the deploy key, add it:
   echo "ssh-ed25519 AAAA... your-deploy-key" >> /home/streamlit/.ssh/authorized_keys
   chmod 600 /home/streamlit/.ssh/authorized_keys
   chmod 700 /home/streamlit/.ssh
   chown -R streamlit:streamlit /home/streamlit/.ssh
   ```

2. **Wrong DROPLET_USER secret** — the GitHub Secret `DROPLET_USER` must be `streamlit` (not `root`).
   Fix in: `Settings → Secrets → DROPLET_USER → Update`

3. **Permission denied on /opt/fi-genai-poc-platform**
   ```bash
   sudo chown -R streamlit:streamlit /opt/fi-genai-poc-platform
   sudo chmod -R u+rwX /opt/fi-genai-poc-platform
   ```

4. **Wrong DROPLET_IP** — verify the secret matches `curl -s ifconfig.me` on the droplet.

5. **Host key verification failed** — the first SSH connection requires accepting the host key. Add this to your workflow or pre-accept:
   ```bash
   # On your local machine:
   ssh-keyscan <DROPLET_IP> >> ~/.ssh/known_hosts
   ```
   Or in the workflow, ensure `StrictHostKeyChecking=no` is set (acceptable for PoC).

---

## Apps Accessible on Port but Not via /path

**Symptom:** `curl http://localhost:8501` works on the droplet, but `http://<IP>/Document_AI/` returns 404 or a blank Streamlit page with no content.

**Diagnosis:**
```bash
# Check nginx is routing correctly
curl -v http://localhost/Document_AI/
# Look at: X-Forwarded headers, response body

# Check the service baseUrlPath matches the nginx location
grep baseUrlPath /etc/systemd/system/streamlit-doc-intelligence.service
# Should show: --server.baseUrlPath /Document_AI
```

**Common causes and fixes:**

1. **baseUrlPath mismatch** — the `--server.baseUrlPath` in the service file must exactly match the nginx `location` block path.
   - Service: `--server.baseUrlPath /Document_AI`
   - Nginx location: `/Document_AI/`
   If they differ, fix the service file and restart:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl restart streamlit-doc-intelligence
   ```

2. **Missing WebSocket upgrade headers in nginx** — Streamlit uses WebSockets for all real-time updates. Without `Upgrade` and `Connection` headers, the app will load but appear blank or frozen.
   Verify your `nginx.conf` location blocks include:
   ```nginx
   proxy_set_header Upgrade $http_upgrade;
   proxy_set_header Connection "upgrade";
   proxy_http_version 1.1;
   ```
   After editing: `sudo nginx -t && sudo systemctl reload nginx`

3. **Trailing slash redirect not configured** — navigating to `/Document_AI` (no trailing slash) must redirect to `/Document_AI/`. The `nginx.conf` includes a `rewrite` rule for this — verify it's present.

---

## Email Notifications Not Sending

**Symptom:** Deployment succeeds but no notification email arrives. GitHub Actions log shows email step failed or completed without sending.

**Common causes and fixes:**

1. **Gmail App Password not configured**
   - Regular Gmail password will not work if 2FA is enabled.
   - Generate an App Password: Google Account → Security → 2-Step Verification → App passwords
   - Add to GitHub Secrets as `GMAIL_APP_PASSWORD`

2. **2FA not enabled on the Gmail account**
   - App Passwords require 2FA to be active on the account.
   - Enable at: myaccount.google.com/security

3. **Wrong Gmail address in secrets** — verify `GMAIL_FROM` and `GMAIL_TO` are set correctly in GitHub Secrets.

4. **Gmail SMTP blocked by Droplet firewall** — verify outbound port 587 is allowed:
   ```bash
   nc -zv smtp.gmail.com 587
   # Should show: Connection to smtp.gmail.com 587 port [tcp/*] succeeded
   ```

---

## General Debug Checklist

When something is broken and you're not sure where to start:

```bash
# 1. Check all three services
systemctl status streamlit-doc-intelligence streamlit-data-qa streamlit-report-generator

# 2. Run the health check
bash /opt/fi-genai-poc-platform/deployment/scripts/health_check.sh

# 3. Check nginx
sudo nginx -t
systemctl status nginx

# 4. Check for Python errors in logs
grep -i "error\|traceback\|exception" /var/log/streamlit/*-error.log | tail -30

# 5. Check disk space (full disk causes silent failures)
df -h /opt

# 6. Check .env is readable by streamlit user
sudo -u streamlit cat /opt/fi-genai-poc-platform/.env | grep -v "KEY\|SECRET\|PASS"
```
